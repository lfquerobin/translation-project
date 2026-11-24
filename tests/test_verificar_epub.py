import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import unicodedata

from fixtures import CAPITULO, PAGINA, entradas_epub, inventario, preparar


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "verificar_epub.py"


def executar(epub, inventario, *opcoes):
    return subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(SCRIPT), str(epub), str(inventario), *opcoes],
        cwd=epub.parent, capture_output=True, encoding="utf-8", check=False,
    )


class VerificadorLegadoTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory(prefix="tradução ")
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)

    def test_edicao_valida_lf_e_crlf_sem_escritas(self):
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=newline):
                epub, registro = preparar(self.pasta, newline=newline)
                antes = {p: p.read_bytes() for p in self.pasta.rglob("*") if p.is_file()}
                resultado = executar(epub, registro, "--estrito")
                self.assertEqual(resultado.returncode, 0, resultado.stderr + resultado.stdout)
                self.assertIn("1 unidades", resultado.stdout)
                self.assertEqual(antes, {p: p.read_bytes() for p in self.pasta.rglob("*") if p.is_file()})

    def test_aviso_so_falha_em_modo_estrito(self):
        epub, registro = preparar(self.pasta, texto="Um bloco.\n\nOutro.")
        self.assertEqual(executar(epub, registro).returncode, 0)
        self.assertEqual(executar(epub, registro, "--estrito").returncode, 1)

    def test_arquivo_ausente_falha_nos_dois_modos(self):
        epub, registro = preparar(self.pasta)
        (registro.parent / CAPITULO).unlink()
        for modo in ((), ("--estrito",)):
            resultado = executar(epub, registro, *modo)
            self.assertEqual(resultado.returncode, 1, resultado.stderr)
            self.assertIn("ausente", resultado.stdout)

    def test_json_invalido_e_inventario_vazio(self):
        epub, registro = preparar(self.pasta)
        for dados in ("{", json.dumps(dict(inventario(), unidades=[]))):
            with self.subTest(dados=dados):
                registro.write_text(dados, encoding="utf-8")
                resultado = executar(epub, registro)
                self.assertEqual(resultado.returncode, 2, resultado.stdout)
                self.assertNotIn("Traceback", resultado.stderr)

    def test_epub_ilegivel(self):
        epub, registro = preparar(self.pasta)
        epub.write_bytes(b"sem zip")
        resultado = executar(epub, registro)
        self.assertEqual(resultado.returncode, 2)
        self.assertNotIn("Traceback", resultado.stderr)

    def test_nome_interno_nfd_preservado(self):
        pagina = unicodedata.normalize("NFD", PAGINA)
        entradas = entradas_epub()
        entradas[pagina] = entradas.pop(PAGINA)
        opf = "OEBPS/obra.opf"
        entradas[opf] = entradas[opf].replace("cap%C3%ADtulo", "capi%CC%81tulo")
        dados = inventario()
        dados["unidades"][0]["paginas_epub"] = [pagina]
        epub, registro = preparar(self.pasta, entradas=entradas, registro=dados)
        resultado = executar(epub, registro, "--estrito")
        self.assertEqual(resultado.returncode, 0, resultado.stderr + resultado.stdout)
