import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.translation_project.arquivos import json_texto
from src.translation_project.registro import calcular_status
from test_registro import projeto_revisado, vazio


REPO = Path(__file__).resolve().parents[1]


class CliTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory(prefix="cli tradução ")
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name) / "Obra"

    def comando(self, nome, *opcoes, codigo=0):
        retorno = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", "-m", "src.translation_project",
             nome, "--projeto", str(self.raiz), *opcoes],
            cwd=REPO, capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(retorno.returncode, codigo, retorno.stdout + retorno.stderr)
        return retorno

    def salvar_registro(self, registro):
        (self.raiz / "projeto.json").write_text(json_texto(registro), encoding="utf-8")

    def test_init_dry_run_reutiliza_sem_substituir_modelos(self):
        self.comando("init", "--dry-run")
        self.assertFalse(self.raiz.exists())
        self.comando("init", "--aplicar", "--estruturado")
        leia_me = self.raiz / "README.md"
        leia_me.write_text("Decisões da obra.", encoding="utf-8")
        resultado = json.loads(self.comando("init", "--aplicar", "--estruturado").stdout)
        self.assertEqual(resultado["novos"], [])
        self.assertIn("README.md", resultado["preservados"])
        self.assertEqual(leia_me.read_text(encoding="utf-8"), "Decisões da obra.")
        self.assertEqual(json.loads(self.comando("status", "--json").stdout)["estado"], "em_preparacao")
        self.comando("sincronizar", "--conferir")

    def test_sincronizar_deterministico_e_preserva_anotacoes_manuais(self):
        self.comando("init", "--aplicar", "--estruturado")
        acompanhamento = self.raiz / "ACOMPANHAMENTO.md"
        pendencias = self.raiz / "PENDÊNCIAS.md"
        antigo = acompanhamento.read_bytes()
        dados, _, _ = projeto_revisado(self.raiz)
        self.salvar_registro(dados)
        self.comando("sincronizar", "--conferir", codigo=1)
        self.assertEqual(acompanhamento.read_bytes(), antigo)
        self.comando("sincronizar", "--aplicar")
        atual = acompanhamento.read_bytes()
        self.assertNotEqual(atual, antigo)
        self.comando("sincronizar", "--aplicar")
        self.assertEqual(acompanhamento.read_bytes(), atual)
        original = pendencias.read_bytes()
        pendencias.write_bytes(original + b"\n<!-- Anotacao manual -->\n")
        self.comando("sincronizar", "--aplicar", codigo=2)
        self.assertIn(b"Anotacao manual", pendencias.read_bytes())

    def test_verificar_convencoes_e_falas_repetidas_sem_escritas(self):
        self.raiz.mkdir()
        pasta = self.raiz / "Capítulos"
        pasta.mkdir()
        arquivo = pasta / "Texto.md"
        arquivo.write_text(
            "**Título: Capítulo**\n**Publicação: 2026-02-30**\n\n"
            "???: [Olá.]\n???: [Olá.]\n\n[Erro](ausente.md)",
            encoding="utf-8",
        )
        (pasta / "Órfão.md").write_text("Ausente do registro.", encoding="utf-8")
        registro = dict(vazio(), unidades=[{
            "id": "C1", "arquivo": "Capítulos/Texto.md", "ordem": 1, "fontes": {},
            "cobertura": {"estado": "pendente"}, "historico": [],
        }], ocorrencias=[{
            "id": "P1", "unidade": "C1", "estado": "anonimato_intencional", "tipo": "falante", "trecho": "Olá.",
        }], convencoes={
            "pastas_texto": ["Capítulos"],
            "cabecalhos": ["Título", {"nome": "Publicação", "tipo": "data"}],
            "falas": {"abertura": "[", "fechamento": "]", "rotulo_anonimo": "???"},
        })
        self.salvar_registro(registro)
        antes = {p: p.read_bytes() for p in self.raiz.rglob("*") if p.is_file()}
        diagnosticos = json.loads(self.comando("verificar", "--json", codigo=1).stdout)["diagnosticos"]
        self.assertEqual({d["codigo"] for d in diagnosticos},
                         {"CABECALHO_DATA", "LINK_AUSENTE", "FALA_OCORRENCIAS", "ARQUIVO_ORFAO"})
        self.assertEqual(antes, {p: p.read_bytes() for p in self.raiz.rglob("*") if p.is_file()})
        registro["ocorrencias"].append(dict(registro["ocorrencias"][0], id="P2"))
        self.salvar_registro(registro)
        diagnosticos = json.loads(self.comando("verificar", "--unidade", "C1", "--json", codigo=1).stdout)["diagnosticos"]
        self.assertEqual({d["codigo"] for d in diagnosticos}, {"CABECALHO_DATA", "LINK_AUSENTE"})

    def test_validar_entrega_exige_conjunto_com_evidencia(self):
        self.raiz.mkdir()
        dados, _, _ = projeto_revisado(self.raiz)
        volume = {"id": "V01"}
        dados["volumes"] = [volume]
        dados["unidades"][0]["volume"] = "V01"
        self.salvar_registro(dados)
        self.assertIn("VOLUME_PENDENTE", self.comando("validar-entrega", "--volume", "V01", codigo=1).stdout)
        estado = calcular_status(dados, self.raiz)["volumes"][0]
        volume["conjunto"] = {"estado": "concluida", "hash": estado["hash_conjunto"],
                              "data": "2026-11-24", "evidencias": ["Conferência sintética."]}
        self.salvar_registro(dados)
        self.comando("validar-entrega", "--volume", "V01")
