import json
from pathlib import Path
import tempfile
import unittest
import unicodedata

from fixtures import CAPITULO, PAGINA, SUMARIO, TEXTO, entradas_epub, inventario, preparar, xhtml
from test_verificar_epub import executar
from src.translation_project.epub import caminho_registro


OPF = "OEBPS/obra.opf"
IMAGEM = "OEBPS/gravura.png"
REGISTRO_IMAGEM = {"epub": IMAGEM, "markdown": "gravura.png", "estado": "sem_texto"}


class RobustezTest(unittest.TestCase):
    def test_registro_aceita_raiz_e_destino_com_resolucao_equivalente(self):
        auxiliar = self.pasta / "auxiliar"
        auxiliar.mkdir()
        arquivo = self.pasta / "Capítulo.md"
        arquivo.write_text("Trecho sintético.", encoding="utf-8")
        raiz_alternativa = auxiliar / ".."
        self.assertEqual(caminho_registro(raiz_alternativa, arquivo.name).resolve(), arquivo.resolve())

    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)

    def diagnosticos(self, epub, registro, *opcoes, codigo=0):
        retorno = executar(epub, registro, "--json", *opcoes)
        self.assertEqual(retorno.returncode, codigo, retorno.stdout + retorno.stderr)
        return {item["codigo"] for item in json.loads(retorno.stdout)["diagnosticos"]}

    def test_continuacoes_imagem_isolada_repetida_e_arquivo_alterado(self):
        entradas = entradas_epub()
        entradas[OPF] = entradas[OPF].replace(
            "</manifest>", '<item id="arte" href="arte.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="extra" href="extra.xhtml" media-type="application/xhtml+xml"/></manifest>',
        ).replace("</spine>", '<itemref idref="arte" linear="no"/><itemref idref="extra"/></spine>')
        entradas.update({
            "OEBPS/arte.xhtml": xhtml('<img src="gravura.png"/>'),
            "OEBPS/extra.xhtml": xhtml('<p>Continuação.</p><img src="gravura.png"/>'),
            IMAGEM: b"imagem sintetica",
        })
        dados = inventario()
        unidade = dados["unidades"][0]
        unidade["paginas_epub"] += ["OEBPS/arte.xhtml", "OEBPS/extra.xhtml"]
        unidade["imagens"] = [REGISTRO_IMAGEM, REGISTRO_IMAGEM]
        texto = f"{TEXTO}\n\n![Arte](gravura.png)\n\nContinuação.\n\n![Arte][imagem]\n\n[imagem]: gravura.png"
        epub, registro = preparar(self.pasta, entradas=entradas, registro=dados, texto=texto)
        destino = registro.parent / "gravura.png"
        destino.write_bytes(entradas[IMAGEM])
        self.assertEqual(self.diagnosticos(epub, registro, "--estrito"), set())
        destino.write_bytes(b"imagem diferente")
        self.assertIn("IMAGEM_HASH", self.diagnosticos(epub, registro, codigo=1))

    def test_alinhamento_n_m_com_listas_tabelas_e_imagem_em_posicao(self):
        entradas = entradas_epub()
        entradas[PAGINA] = xhtml(
            '<section><h1>Parte</h1><ul><li><p>Um.</p></li><li>Dois.</li></ul>'
            '<img src="gravura.png"/><table><tr><td>A</td><td>B</td></tr></table>'
            '<hr/><aside><p>Nota com <ruby>字<rt>じ</rt></ruby>.</p></aside></section>'
        )
        entradas[IMAGEM] = b"imagem"
        dados = inventario()
        dados["schema"] = 2
        dados["unidades"][0].update(imagens=[REGISTRO_IMAGEM], alinhamento=[
            {"origem": ["e1"], "destino": ["m1"]},
            {"origem": ["e2", "e3"], "destino": ["m2"], "justificativa": "Lista no mesmo bloco."},
            {"origem": ["e5", "e6"], "destino": ["m4"], "justificativa": "Tabela no mesmo bloco."},
            {"origem": ["e8"], "destino": ["m6", "m7"], "justificativa": "Nota em duas partes."},
        ])
        texto = "# Parte\n\n- Um.\n- Dois.\n\n![Arte](gravura.png)\n\n| A | B |\n\n***\n\nNota.\n\nCom palavra."
        epub, registro = preparar(self.pasta, entradas=entradas, registro=dados, texto=texto)
        (registro.parent / "gravura.png").write_bytes(entradas[IMAGEM])
        self.assertEqual(self.diagnosticos(epub, registro, "--estrito"), set())
        dados["unidades"][0]["alinhamento"][1]["origem"].reverse()
        registro.write_text(json.dumps(dados), encoding="utf-8")
        self.assertIn("ALINHAMENTO_COBERTURA", self.diagnosticos(epub, registro, codigo=1))

    def test_divisao_legada_conta_somente_paragrafos_com_texto(self):
        entradas = entradas_epub()
        entradas[PAGINA] = xhtml("<p> </p><p>Primeiro.</p><p>Segundo.</p>")
        dados = inventario()
        dados["unidades"][0]["divisoes_de_paragrafo"] = {"2": 2}
        epub, registro = preparar(self.pasta, entradas=entradas, registro=dados,
                                  texto="Primeiro.\n\nSegundo.\n\nContinuação.")
        self.assertEqual(self.diagnosticos(epub, registro, "--estrito"), set())

    def test_links_referencia_escapes_ancoras_e_codigo(self):
        dados = inventario()
        dados["permitir_html"] = True
        dados["unidades"][0]["blocos_iniciais"] = 4
        texto = ("# Seção\n\n<!-- [Comentário](ausente.md) -->\n\n"
                 "```md\n[Exemplo](ausente.md)\n```\n\n"
                 "`[Exemplo](ausente.md)`\n\n[Seção](#se%C3%A7%C3%A3o) "
                 "[Nota](nota\\(1\\).txt) <a href='#seção'>ver</a>")
        epub, registro = preparar(self.pasta, registro=dados, texto=texto)
        (registro.parent / "nota(1).txt").write_text("nota", encoding="utf-8")
        (registro.parent / SUMARIO).write_text(
            f"[Capítulo][unidade]\n\n[unidade]: <{CAPITULO}#seção>\n", encoding="utf-8",
        )
        self.assertEqual(self.diagnosticos(epub, registro, "--estrito"), set())

    def test_nav_divergente_inclui_capa_e_extra_sem_link(self):
        entradas = entradas_epub()
        entradas[OPF] = entradas[OPF].replace(
            "</manifest>", '<item id="capa" href="capa.xhtml"/><item id="extra" href="extra.xhtml"/>'
            '<item id="nav" href="nav.xhtml" properties="nav"/></manifest>',
        ).replace('<itemref idref="cap"/>', '<itemref idref="capa"/><itemref idref="cap"/><itemref idref="extra"/>')
        entradas.update({"OEBPS/capa.xhtml": xhtml("<p>Capa.</p>"),
                         "OEBPS/extra.xhtml": xhtml("<p>Créditos.</p>"),
                         "OEBPS/nav.xhtml": xhtml(
                             '<nav xmlns:epub="http://www.idpf.org/2007/ops" epub:type="toc">'
                             '<a href="extra.xhtml">Extra</a><a href="cap%C3%ADtulo.xhtml">Capítulo</a></nav>')})
        dados = inventario()
        dados["unidades"].extend([{"markdown": "Extra.md", "paginas_epub": ["OEBPS/extra.xhtml"]}])
        epub, registro = preparar(self.pasta, entradas=entradas, registro=dados)
        (registro.parent / "Extra.md").write_text("Créditos.", encoding="utf-8")
        (registro.parent / SUMARIO).write_text(f"[Capítulo](<{CAPITULO}>)\n[Extra](Extra.md)", encoding="utf-8")
        self.assertEqual(self.diagnosticos(epub, registro, codigo=1), {"NAV_ORDEM", "SPINE_COBERTURA"})

    def test_tamanho_entradas_traversal_e_colisoes(self):
        for nome in ("../absoluto", "OEBPS/OBRA.OPF", unicodedata.normalize("NFD", PAGINA)):
            with self.subTest(nome=nome):
                entradas = entradas_epub()
                entradas[nome] = "extra"
                epub, registro = preparar(self.pasta, entradas=entradas)
                self.assertEqual(self.diagnosticos(epub, registro, codigo=2), {"ENTRADA_INVALIDA"})
        entradas = entradas_epub()
        entradas["grande.txt"] = b"x" * 4096
        epub, registro = preparar(self.pasta, entradas=entradas)
        self.assertEqual(self.diagnosticos(epub, registro, "--limite-bytes-entrada", "1000", codigo=2),
                         {"ENTRADA_INVALIDA"})
        self.assertEqual(self.diagnosticos(epub, registro, "--limite-entradas", "3", codigo=2),
                         {"ENTRADA_INVALIDA"})

    def test_traversal_link_e_dtd(self):
        epub, registro = preparar(self.pasta, texto="[Fora](../fora.md)")
        self.assertEqual(self.diagnosticos(epub, registro, codigo=1), {"LINK_CAMINHO"})
        entradas = entradas_epub()
        entradas[PAGINA] = '<!DOCTYPE html [<!ENTITY marca "texto">]>' + xhtml("<p>&marca;</p>")
        epub, registro = preparar(self.pasta, entradas=entradas)
        self.assertEqual(self.diagnosticos(epub, registro, codigo=2), {"ENTRADA_INVALIDA"})

    def test_metrica_ignora_japones_preserva_legado_e_permite_configurar(self):
        entradas = entradas_epub()
        entradas[PAGINA] = xhtml("<p>" + "言葉 " * 25 + "</p>")
        entradas[OPF] = entradas[OPF].replace(">pt<", ">ja<")
        epub, registro = preparar(self.pasta, entradas=entradas, texto="Curto.")
        self.assertEqual(self.diagnosticos(epub, registro, "--estrito"), set())
        entradas[OPF] = entradas[OPF].replace("<language>ja</language>", "")
        epub, registro = preparar(self.pasta, entradas=entradas, texto="Curto.")
        self.assertEqual(self.diagnosticos(epub, registro, "--estrito", codigo=1), {"PALAVRAS_PROPORCAO"})
        dados = inventario()
        dados["metrica_palavras"] = {"habilitada": False}
        epub, registro = preparar(self.pasta, entradas=entradas, registro=dados, texto="Curto.")
        self.assertEqual(self.diagnosticos(epub, registro, "--estrito"), set())
