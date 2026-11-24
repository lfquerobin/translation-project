from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.translation_project.arquivos import json_texto, sha256_arquivo
from src.translation_project.migracao import invalidar, migrar
from src.translation_project.registro import calcular_status


REPO = Path(__file__).resolve().parents[1]


def vazio():
    return {"schema": 2, "obra": "Obra sintética", "idioma_destino": "pt-BR", "unidades": []}


def projeto_revisado(pasta):
    arquivo = pasta / "Texto.md"
    arquivo.write_bytes(b"Texto sintetico.")
    intermediaria = pasta / "Edicao.txt"
    intermediaria.write_bytes(b"Colophon and synthetic text.")
    hash_texto = sha256_arquivo(arquivo)
    fonte = {"papel": "intermediaria", "referencia": "Edicao.txt",
             "edicao": "edição sintética", "hash": sha256_arquivo(intermediaria)}
    historico = [
        {"id": etapa, "etapa": etapa, "estado": "concluida", "escopo": "integral",
         "data": "2026-11-24", "hash_texto": hash_texto, "fonte": fonte,
         "evidencias": ["Referência sintética"], "arquivo_conferido": arquivo.name}
        for etapa in ("fidelidade_intermediaria", "naturalidade", "formato")
    ]
    historico.append({"id": "falantes", "etapa": "falantes", "estado": "inaplicavel", "motivo": "Sem falas."})
    unidade = {
        "id": "C01", "arquivo": arquivo.name, "ordem": 1, "tipo": "narrativa",
        "edicao_trabalho": "intermediaria", "fontes": {
            "original": None, "intermediaria": {"arquivo": intermediaria.name, "edicao": fonte["edicao"]},
        },
        "cobertura": {"estado": "integral", "hash_texto": hash_texto},
        "imagens": {"estado": "inaplicavel", "motivo": "Sem imagens."},
        "notas": {"estado": "inaplicavel", "motivo": "Sem notas."},
        "historico": historico,
    }
    return dict(vazio(), unidades=[unidade]), arquivo, intermediaria


class RegistroTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory(prefix="registro sintético ")
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)

    def test_status_vazio_e_volume_sem_unidades(self):
        dados = dict(vazio(), volumes=[{"id": "V01"}])
        status = calcular_status(dados, self.raiz)
        self.assertEqual(status["estado"], "em_preparacao")
        self.assertEqual(status["volumes"][0]["estado"], "em_preparacao")
        self.assertEqual(status["totais"], {"unidades": 0})

    def test_revisao_separada_do_original_e_restauracao(self):
        dados, arquivo, _ = projeto_revisado(self.raiz)
        antes = arquivo.read_bytes()
        status = calcular_status(dados, self.raiz)["unidades"][0]
        self.assertEqual(status["estado"], "revisada_edicao_trabalho")
        self.assertEqual(status["revisoes"]["fidelidade_original"]["estado"], "pendente")
        arquivo.write_bytes(antes + b"\nOutra linha.")
        status = calcular_status(dados, self.raiz)["unidades"][0]
        self.assertEqual(status["cobertura"], "desatualizada")
        self.assertEqual(status["revisoes"]["naturalidade"]["estado"], "desatualizada")
        alterado, relatorio = invalidar(dados, self.raiz)
        self.assertEqual(len(relatorio), 3)
        historico = dados["unidades"][0]["historico"]
        self.assertEqual(alterado["unidades"][0]["historico"][:len(historico)], historico)
        self.assertEqual(invalidar(alterado, self.raiz), (alterado, []))
        arquivo.write_bytes(antes)
        self.assertEqual(calcular_status(dados, self.raiz)["unidades"][0]["estado"], "revisada_edicao_trabalho")
        self.assertEqual(calcular_status(alterado, self.raiz)["unidades"][0]["estado"], "em_trabalho")

    def test_renomeacao_preserva_cotejo_mas_exige_formato(self):
        dados, arquivo, _ = projeto_revisado(self.raiz)
        novo = arquivo.with_name("Renomeado.md")
        arquivo.rename(novo)
        dados["unidades"][0]["arquivo"] = novo.name
        status = calcular_status(dados, self.raiz)["unidades"][0]
        estados = {etapa: revisao["estado"] for etapa, revisao in status["revisoes"].items()}
        self.assertEqual(status["id"], "C01")
        self.assertEqual(estados["fidelidade_intermediaria"], "concluida")
        self.assertEqual(estados["formato"], "desatualizada")

    def test_fonte_trocada_revisao_parcial_e_bloqueio(self):
        dados, _, fonte = projeto_revisado(self.raiz)
        evento = dados["unidades"][0]["historico"][0]
        evento.update(estado="parcial", escopo=["Parágrafos 1–2"])
        status = calcular_status(dados, self.raiz)["unidades"][0]
        self.assertEqual(status["revisoes"]["fidelidade_intermediaria"]["estado"], "parcial")
        self.assertEqual(status["estado"], "em_trabalho")
        fonte.write_bytes(b"Outra edicao.")
        dados["ocorrencias"] = [{"id": "P01", "unidade": "C01", "bloqueante": True, "estado": "aberta"}]
        status = calcular_status(dados, self.raiz)["unidades"][0]
        self.assertEqual(status["revisoes"]["fidelidade_intermediaria"]["estado"], "desatualizada")
        self.assertEqual(status["revisoes"]["naturalidade"]["estado"], "desatualizada")
        self.assertEqual(status["bloqueios"], ["P01"])

    def test_inaplicavel_requer_motivo(self):
        dados, _, _ = projeto_revisado(self.raiz)
        dados["unidades"][0]["historico"][-1].pop("motivo")
        with self.assertRaisesRegex(ValueError, "motivo"):
            calcular_status(dados, self.raiz)

    def test_conjunto_do_volume_depende_do_sumario(self):
        dados, _, _ = projeto_revisado(self.raiz)
        sumario = self.raiz / "Sumário.md"
        sumario.write_bytes(b"# Sumario")
        dados["unidades"][0]["volume"] = "V01"
        volume = {"id": "V01", "arquivos_conjunto": [sumario.name]}
        dados["volumes"] = [volume]
        estado = calcular_status(dados, self.raiz)["volumes"][0]
        self.assertEqual(estado["estado"], "em_trabalho")
        volume["conjunto"] = {"estado": "concluida", "hash": estado["hash_conjunto"],
                              "data": "2026-11-24", "evidencias": ["Sumário sintético conferido."]}
        self.assertEqual(calcular_status(dados, self.raiz)["volumes"][0]["estado"], "revisado_edicao_trabalho")
        sumario.write_bytes(b"# Sumario modificado")
        self.assertEqual(calcular_status(dados, self.raiz)["volumes"][0]["conjunto"], "desatualizada")

    def test_migracao_conserva_campos_e_e_idempotente(self):
        revisoes = {"fidelidade": {"estado": "concluida", "detalhe": "Escopo histórico incerto."},
                    "naturalidade": {"estado": "concluida", "data": "2026-11-22"}}
        dados = dict(vazio(), schema=1, campo_da_obra=True, unidades=[
            {"id": "C01", "arquivo": "Texto.md", "campo_local": "preservar", "revisoes": revisoes},
        ])
        original = deepcopy(dados)
        resultado, mapeamento = migrar(dados, self.raiz)
        self.assertEqual(dados, original)
        self.assertTrue(mapeamento[0]["fidelidade_unica_preservada"])
        self.assertTrue(resultado["campo_da_obra"])
        self.assertEqual(resultado["unidades"][0]["revisoes_legadas"], revisoes)
        status = calcular_status(resultado, self.raiz)["unidades"][0]
        self.assertEqual(status["revisoes"]["naturalidade"]["estado"], "historica")
        self.assertEqual(status["revisoes"]["fidelidade_original"]["estado"], "pendente")
        self.assertEqual(status["revisoes"]["fidelidade_intermediaria"]["estado"], "pendente")
        self.assertEqual(migrar(resultado, self.raiz), (resultado, []))

    def test_cli_migracao_so_grava_copia_explicita(self):
        arquivo = self.raiz / "projeto.json"
        conteudo = json_texto(dict(vazio(), schema=1)).encode("utf-8")
        arquivo.write_bytes(conteudo)
        comando = [sys.executable, "-B", "-X", "utf8", "-m", "src.translation_project",
                   "migrar", "--projeto", str(self.raiz), "--saida", "migrado.json"]
        for extras, retorno in (([], 0), (["--aplicar"], 0), (["--aplicar"], 2)):
            resultado = subprocess.run(comando + extras, cwd=REPO, capture_output=True,
                                       encoding="utf-8", check=False)
            self.assertEqual(resultado.returncode, retorno, resultado.stdout + resultado.stderr)
            self.assertEqual(arquivo.read_bytes(), conteudo)
            if not extras:
                self.assertFalse((self.raiz / "migrado.json").exists())
        self.assertEqual(json.loads((self.raiz / "migrado.json").read_text(encoding="utf-8"))["schema"], 2)
