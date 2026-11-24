from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.translation_project.arquivos import json_texto, sha256_arquivo
from src.translation_project.memoria import INDICE, _executar_fts, atualizar, buscar
from test_registro import REPO, projeto_revisado


class MemoriaTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory(prefix="memória ")
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)
        self.dados, self.arquivo, _ = projeto_revisado(self.raiz)
        self.dados.update(versao="E1", convencoes={"memoria": {"segmentos": "segmentos.json"}})
        self.segmentos = []
        for n in range(1, 5):
            id_unidade = f"C0{n}"
            arquivo = self.arquivo
            if n > 1:
                unidade = deepcopy(self.dados["unidades"][0])
                arquivo = self.raiz / f"{id_unidade}.md"
                arquivo.write_bytes(self.arquivo.read_bytes())
                unidade.update(id=id_unidade, ordem=n, arquivo=arquivo.name, edicao="E2" if n == 4 else "E1")
                for evento in unidade["historico"]:
                    if evento["etapa"] == "formato":
                        evento["arquivo_conferido"] = arquivo.name
                self.dados["unidades"].append(unidade)
            self.segmentos.append({
                "id": f"S{n}", "unidade": id_unidade, "traducao": "Texto sintetico.",
                "referencia": f"Parte {n}, edição sintética.", "hash_texto": sha256_arquivo(arquivo),
            })
        self.segmentos.append(dict(self.segmentos[0], id="revelacao", visivel_apos="C03"))
        self.segmentos.append(dict(self.segmentos[0], id="trabalho", hash_texto=None))
        self.salvar()

    def salvar(self):
        (self.raiz / "segmentos.json").write_text(
            json_texto({"schema": 1, "segmentos": self.segmentos}), encoding="utf-8",
        )

    def busca(self, **opcoes):
        parametros = {"obra": self.dados["obra"], "versao": "E1", "ate": "C01", **opcoes}
        return buscar(self.dados, self.raiz, "sintetico", **parametros)["resultados"]

    def test_recuperacao_respeita_limite_edicao_e_trabalho(self):
        self.assertEqual(atualizar(self.dados, self.raiz)["segmentos_elegiveis"], 6)
        self.assertFalse((self.raiz / INDICE).exists())
        atualizar(self.dados, self.raiz, aplicar=True)
        self.assertEqual({s["id"] for s in self.busca()}, {"S1"})
        self.assertEqual({s["id"] for s in self.busca(trabalho=True)}, {"S1", "trabalho"})
        self.assertEqual({s["id"] for s in self.busca(futuro=True)}, {"S1", "S2", "S3", "revelacao"})
        with self.assertRaisesRegex(ValueError, "versão"):
            self.busca(ate="C04")
        self.assertTrue(self.busca()[0]["referencia"])

    def test_indice_antigo_nunca_aprova_versao_modificada(self):
        atualizar(self.dados, self.raiz, aplicar=True)
        self.arquivo.write_bytes(b"Texto modificado.")
        self.assertEqual(self.busca(), [])
        resumo = atualizar(self.dados, self.raiz, aplicar=True)
        self.assertGreater(resumo["atualizados"], 0)
        self.assertEqual(self.busca(), [])

    def test_hash_atual_sem_trecho_salvo_nao_e_aprovado(self):
        self.segmentos[0]["traducao"] = "Trecho sintetico que não consta na unidade."
        self.salvar()
        atualizar(self.dados, self.raiz, aplicar=True)
        self.assertEqual(self.busca(), [])
        self.assertEqual({s["id"] for s in self.busca(trabalho=True)}, {"S1", "trabalho"})

    def test_reconstruir_sem_fts_excluir_e_nao_escrever_na_busca(self):
        resumo = atualizar(self.dados, self.raiz, aplicar=True, sem_fts=True)
        self.assertFalse(resumo["fts"])
        indice = self.raiz / INDICE
        anteriores = {p: p.read_bytes() for p in self.raiz.rglob("*") if p.is_file()}
        self.assertEqual({s["id"] for s in self.busca(sem_fts=True)}, {"S1"})
        self.assertEqual(anteriores, {p: p.read_bytes() for p in self.raiz.rglob("*") if p.is_file()})
        self.dados["convencoes"]["memoria"]["excluir_unidades"] = ["C01"]
        self.segmentos.pop(1)
        self.salvar()
        resumo = atualizar(self.dados, self.raiz, aplicar=True, reconstruir=True)
        self.assertEqual(resumo["removidos"], 4)
        self.assertTrue(indice.exists())
        self.assertEqual({s["id"] for s in self.busca(futuro=True)}, {"S3"})

    def test_indice_fts_portavel_e_reconstruido_ao_reabrir_com_suporte(self):
        if not atualizar(self.dados, self.raiz, aplicar=True)["fts"]:
            self.skipTest("É necessário FTS5 para criar o índice de origem.")
        db = Mock()
        db.execute.side_effect = sqlite3.OperationalError("no such module: fts5")
        self.assertFalse(_executar_fts(db, "SELECT rowid FROM busca_fts LIMIT 0"))
        self.segmentos[0]["contexto"] = "Uma palavra inédita."
        self.salvar()
        with patch("src.translation_project.memoria._executar_fts", return_value=False):
            self.assertFalse(atualizar(self.dados, self.raiz, aplicar=True)["fts"])
            self.assertEqual({s["id"] for s in self.busca()}, {"S1"})
        self.assertEqual({s["id"] for s in self.busca()}, {"S1"})
        relatorio = atualizar(self.dados, self.raiz, aplicar=True)
        self.assertTrue(relatorio["fts"])
        self.assertEqual(relatorio["atualizados"], 0)
        encontrados = buscar(self.dados, self.raiz, "inédita", obra=self.dados["obra"], versao="E1", ate="C01")
        self.assertEqual([s["id"] for s in encontrados["resultados"]], ["S1"])

    def test_cli_dry_run_atualizacao_e_busca(self):
        (self.raiz / "projeto.json").write_text(json_texto(self.dados), encoding="utf-8")

        def cli(acao, *args):
            resultado = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", "-m", "src.translation_project",
                 "memoria", acao, "--projeto", str(self.raiz), *args],
                cwd=REPO, capture_output=True, encoding="utf-8", check=False,
            )
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            return json.loads(resultado.stdout)

        self.assertEqual(cli("atualizar")["segmentos_elegiveis"], 6)
        self.assertFalse((self.raiz / INDICE).exists())
        self.assertEqual(cli("atualizar", "--aplicar")["atualizados"], 6)
        retorno = cli("buscar", "sintetico", "--obra", self.dados["obra"], "--versao", "E1", "--ate", "C01")
        self.assertEqual([item["id"] for item in retorno["resultados"]], ["S1"])
