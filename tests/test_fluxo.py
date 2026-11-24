"""Exercita ferramentas em conjunto com uma obra efêmera."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from fixtures import PAGINA, entradas_epub, gravar_epub, xhtml
from src.translation_project.arquivos import json_texto, ler_json, sha256_arquivo
from src.translation_project.registro import calcular_status
from test_registro import REPO, projeto_revisado
from test_verificar_epub import executar


class FluxoTest(unittest.TestCase):
    def test_da_edicao_epub_a_memoria_com_evidencias(self):
        with TemporaryDirectory(prefix="fluxo tradução ") as pasta:
            raiz = Path(pasta) / "Obra sintética"

            def gravar(nome, dados):
                caminho = raiz / nome
                caminho.write_text(json_texto(dados), encoding="utf-8")
                return caminho

            def cli(*args):
                retorno = subprocess.run(
                    [sys.executable, "-B", "-X", "utf8", "-m", "src.translation_project",
                     *args, "--projeto", str(raiz)],
                    cwd=REPO, encoding="utf-8", capture_output=True, check=False,
                )
                self.assertEqual(retorno.returncode, 0, retorno.stderr + retorno.stdout)
                return json.loads(retorno.stdout)

            cli("init", "--estruturado", "--aplicar")
            epub = raiz / "Edição.epub"
            entradas = entradas_epub()
            entradas[PAGINA] = xhtml("<p>Exemplo sintético.</p>")
            gravar_epub(epub, entradas)
            descoberta = cli("importar", str(epub), "--dry-run")["proposta"]
            confirmacao = gravar("confirmacao.json", {
                "sha256_epub": descoberta["sha256_epub"], "sumario": "Sumário.md",
                "unidades": [{"id": "C01", "markdown": "Texto.md", "paginas": ["p0001"]}],
            })
            resultado = cli(
                "inventario", "gerar", str(epub), "--confirmacao", str(confirmacao),
                "--saida", "inventario.json", "--esqueleto", "--aplicar",
            )
            inventario = resultado["inventario"]
            inventario["unidades"][0]["alinhamento"] = [{"origem": ["e1"], "destino": ["m1"]}]
            caminho_inventario = gravar("inventario.json", inventario)
            revisado, texto, _ = projeto_revisado(raiz)
            unidade = revisado["unidades"][0]
            unidade["volume"] = "V01"
            revisado["versao"] = "E1"
            revisado["volumes"] = [{"id": "V01", "epub": epub.name, "inventario": caminho_inventario.name,
                                   "arquivos_conjunto": ["Sumário.md", "inventario.json", epub.name]}]
            revisado["convencoes"] = {"painel": True, "memoria": {"segmentos": "segmentos.json"}}
            compatibilidade = executar(epub, caminho_inventario, "--json", "--estrito")
            self.assertEqual(compatibilidade.returncode, 0, compatibilidade.stdout + compatibilidade.stderr)

            unidade_legada = {k: v for k, v in unidade.items() if k != "historico"}
            unidade_legada["revisoes"] = {"fidelidade": {"estado": "concluida"}}
            gravar("projeto.json", dict(revisado, schema=1, unidades=[unidade_legada]))
            cli("migrar", "--aplicar", "--saida", "migrado.json")
            migrado = ler_json(raiz / "migrado.json")
            migrado["unidades"][0]["historico"].extend(unidade["historico"])
            estados = calcular_status(migrado, raiz)
            self.assertEqual(estados["unidades"][0]["revisoes"]["fidelidade_original"]["estado"], "pendente")
            migrado["volumes"][0]["conjunto"] = {
                "estado": "concluida", "data": "2026-11-24", "hash": estados["volumes"][0]["hash_conjunto"],
                "evidencias": ["Conferência da fixture."],
            }
            gravar("projeto.json", migrado)
            cli("sincronizar", "--aplicar")
            self.assertIn("Unidades revisadas pela edição de trabalho: 1/1",
                          (raiz / "PAINEL.md").read_text(encoding="utf-8"))
            self.assertEqual(cli("verificar", "--estrito", "--json")["diagnosticos"], [])
            self.assertEqual(cli("validar-entrega", "--volume", "V01", "--json")["diagnosticos"], [])
            gravar("segmentos.json", {"schema": 1, "segmentos": [{
                "id": "S01", "unidade": "C01", "traducao": texto.read_text(encoding="utf-8"),
                "hash_texto": sha256_arquivo(texto), "referencia": "Parágrafo 1 da fixture.",
            }]})
            cli("memoria", "atualizar", "--aplicar")
            observados = cli("memoria", "buscar", "sintetico", "--obra", revisado["obra"], "--versao", "E1", "--ate", "C01")
            self.assertEqual([item["id"] for item in observados["resultados"]], ["S01"])
