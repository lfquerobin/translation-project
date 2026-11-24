import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fixtures import PAGINA, entradas_epub, gravar_epub, xhtml
from test_verificar_epub import executar


REPO = Path(__file__).resolve().parents[1]


class ImportacaoTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory(prefix="importação ")
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)
        self.epub = self.raiz / "Edição.epub"
        self.entradas = entradas_epub()
        opf = "OEBPS/obra.opf"
        self.entradas[opf] = self.entradas[opf].replace(
            "</manifest>", '<item id="capa" href="capa.png" media-type="image/png"/>'
            '<item id="extra" href="extra.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/></manifest>',
        ).replace('<itemref idref="cap"/>', '<itemref idref="capa"/><itemref idref="nav"/>'
                  '<itemref idref="cap"/><itemref idref="extra" linear="no"/><itemref idref="cap"/>')
        self.entradas[PAGINA] = xhtml('<p>Demonstração editorial.</p><img src="gravura.png"/>')
        self.entradas.update({
            "OEBPS/capa.png": b"arte sintetica", "OEBPS/gravura.png": b"arte sintetica",
            "OEBPS/extra.xhtml": xhtml("<p>Extra.</p>"),
            "OEBPS/nav.xhtml": xhtml('<nav xmlns:epub="http://www.idpf.org/2007/ops" epub:type="toc">'
                                    '<a href="cap%C3%ADtulo.xhtml">Capítulo</a></nav>'),
        })
        gravar_epub(self.epub, self.entradas)

    def importar(self, *opcoes, codigo=0):
        resultado = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", "-m", "src.translation_project",
             "importar", str(self.epub), "--projeto", str(self.raiz), *opcoes],
            cwd=REPO, capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(resultado.returncode, codigo, resultado.stdout + resultado.stderr)
        return json.loads(resultado.stdout) if codigo == 0 else resultado.stderr

    def confirmacao(self):
        proposta = self.importar("--dry-run")["proposta"]
        self.confirmado = self.raiz / "confirmação.json"
        self.dados = {"sha256_epub": proposta["sha256_epub"], "sumario": "Sumário.md",
                      "navegacao": ["p0002"], "unidades": [
                          {"id": "CAPA", "markdown": "Capa.md", "paginas": ["p0001"]},
                          {"id": "A", "markdown": "Parte A.md", "paginas": ["p0003"]},
                          {"id": "EXTRA", "markdown": "Extra.md", "paginas": ["p0004"]},
                          {"id": "B", "markdown": "Parte B.md", "paginas": ["p0005"]},
                      ]}
        self.confirmado.write_text(json.dumps(self.dados), encoding="utf-8")
        return ["--confirmacao", str(self.confirmado), "--saida", "Volume 01/inventário.json"]

    def test_dry_run_deterministico_inclui_todas_ocorrencias(self):
        antes = self.epub.read_bytes()
        a, b = self.importar("--dry-run"), self.importar()
        self.assertEqual(a, b)
        self.assertEqual([p["id"] for p in a["proposta"]["spine"]], [f"p{i:04}" for i in range(1, 6)])
        self.assertFalse(a["proposta"]["spine"][3]["linear"])
        self.assertEqual(list(self.raiz.iterdir()), [self.epub])
        self.assertEqual(self.epub.read_bytes(), antes)

    def test_importacao_repetida_preserva_revisoes_e_nao_sobrescreve(self):
        argumentos = self.confirmacao() + ["--extrair-imagens", "--deduplicar", "--esqueleto"]
        self.assertFalse(self.importar(*argumentos)["aplicado"])
        self.assertFalse((self.raiz / "Volume 01").exists())
        primeiro = self.importar(*argumentos, "--aplicar")
        self.assertEqual(len(primeiro["imagens"]), 1)
        self.assertEqual(len(primeiro["novos"]), 7)
        inventario = primeiro["inventario"]
        ocorrencias = [i for unidade in inventario["unidades"] for i in unidade["imagens"]]
        self.assertEqual(len({oc["id"] for oc in ocorrencias}), 3)
        self.assertTrue(all(oc["estado"] == "pendente" for oc in ocorrencias))
        self.assertEqual(self.importar(*argumentos, "--aplicar")["novos"], [])
        pasta = self.raiz / "Volume 01"
        registro = pasta / "inventário.json"
        resultado = executar(self.epub, registro, "--json")
        self.assertEqual(resultado.returncode, 1, resultado.stdout + resultado.stderr)
        capa = pasta / "Capa.md"
        capa.write_text("Alteração editorial.", encoding="utf-8")
        self.assertIn("Destino divergente", self.importar(*argumentos, "--aplicar", codigo=2))
        self.assertEqual(capa.read_text(encoding="utf-8"), "Alteração editorial.")
        inventario["unidades"][0]["imagens"][0]["estado"] = "sem_texto"
        registro.write_text(json.dumps(inventario), encoding="utf-8")
        self.assertIn("Destino divergente", self.importar(*self.confirmacao(), "--aplicar", codigo=2))

    def test_confirmacao_exige_ordem_cobertura_e_mesma_edicao(self):
        argumentos = self.confirmacao()
        self.dados["unidades"].pop()
        self.confirmado.write_text(json.dumps(self.dados), encoding="utf-8")
        self.assertIn("cada ocorrência", self.importar(*argumentos, codigo=2))
        argumentos = self.confirmacao()
        anterior = self.raiz / "proposta.json"
        self.importar("--saida", anterior.name, "--aplicar")
        self.entradas[PAGINA] = xhtml("<p>Outra edição.</p>")
        gravar_epub(self.epub, self.entradas)
        self.assertEqual(self.importar("--anterior", str(anterior))["comparacao_edicao"]["estado"], "alterada")
        self.assertIn("outra edição", self.importar(*argumentos, "--aplicar", codigo=2))
        self.assertFalse((self.raiz / "Volume 01").exists())
