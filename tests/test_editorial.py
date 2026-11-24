from pathlib import Path
import tempfile
import unittest
import unicodedata

from src.translation_project.arquivos import json_texto
from src.translation_project.editorial import ocorrencias_glossario, validar_vozes
from src.translation_project.registro import calcular_status
from src.translation_project.vistas import gerar_vistas
from test_registro import vazio


def termo(**campos):
    return dict({"id": "T1", "original": "語", "idioma": "ja", "traducao": "termo",
                 "estado": "alternativa_contextual", "contexto_busca": ["magia"],
                 "excluir_contexto": ["nome"], "variantes_alerta": [{"forma": "fórmula", "flexoes": ["fórmulas"]}],
                 "referencias": ["Edição sintética, parágrafo 2."],
                 "escopo": {"inicio": 1, "fim": 1}, "edicao": "E1"}, **campos)


class EditorialTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)
        unidades = [
            {"id": f"C{n}", "ordem": n, "arquivo": f"C{n}.md", "fontes": {},
             "historico": [], "cobertura": {"estado": "pendente"}}
            for n in (1, 2)
        ]
        self.dados = dict(vazio(), versao="E1", unidades=unidades, convencoes={
            "glossario": "glossario.json", "vozes": "vozes.json",
        })

    def test_variantes_flexao_unicode_contexto_e_escopo(self):
        arquivo = self.raiz / "C1.md"
        arquivo.write_text("\n".join([
            unicodedata.normalize("NFD", "A magia usa FÓRMULAS."),
            "A magia usa uma megaFórmula.",
            "A fórmula está fora do contexto.",
            'A magia usa o nome fórmula.',
            'A magia cita “fórmula”.',
            'A magia usa `fórmula`.',
        ]), encoding="utf-8")
        (self.raiz / "C2.md").write_text("A magia usa fórmula.", encoding="utf-8")
        registro = {"schema": 1, "termos": [termo()]}
        observados = ocorrencias_glossario(registro, self.dados, self.raiz)
        self.assertEqual([(d.unidade, d.localizacao) for d in observados], [("C1", 1)])
        self.assertIn("FÓRMULAS", observados[0].mensagem)
        self.assertEqual(ocorrencias_glossario({"schema": 1, "termos": [termo(sensivel_caixa=True)]},
                                              self.dados, self.raiz), [])

    def test_termo_alterado_lista_candidatas_sem_editar_texto(self):
        arquivo = self.raiz / "C1.md"
        arquivo.write_text("A magia usa cifra e termo.", encoding="utf-8")
        antes = arquivo.read_bytes()
        registro = {"schema": 1, "termos": [termo(historico=[{"forma_anterior": "cifra", "motivo": "Mudança"}])]}
        observados = ocorrencias_glossario(registro, self.dados, self.raiz, termo_id="T1")
        self.assertEqual(len(observados), 2)
        self.assertTrue(all(d.codigo == "GLOSSARIO_AFETADA" for d in observados))
        self.assertEqual(arquivo.read_bytes(), antes)

    def test_homonimas_e_evidencia_confirmada_com_referencia(self):
        exemplo = {"id": "E1", "estado": "hipotese", "unidade": "C1", "original": "例", "traducao": "Exemplo"}
        vozes = {"schema": 1, "vozes": [
            {"id": "V1", "nome": "Ana", "tipo": "personagem", "exemplos": [exemplo]},
            {"id": "V2", "nome": "Ana", "tipo": "personagem"},
        ]}
        self.assertEqual(list(validar_vozes(vozes, self.dados)), ["V1", "V2"])
        exemplo.update(estado="confirmada", edicao="E1")
        with self.assertRaisesRegex(ValueError, "referencia"):
            validar_vozes(vozes, self.dados)
        exemplo.update(referencia="Fonte sintética, seção 1.")
        self.assertEqual(validar_vozes(vozes, self.dados)["V1"]["exemplos"][0]["estado"], "confirmada")

    def test_vistas_retiveram_historico_e_notas(self):
        dados_glossario = {"schema": 1, "termos": [
            termo(nota="Nota editorial.", historico=[{"forma_anterior": "cifra", "motivo": "Decisão anterior"}]),
        ]}
        dados_vozes = {"schema": 1, "vozes": [
            {"id": "V1", "nome": "Ana", "tipo": "personagem", "nota": "Evolução de tratamento.",
             "exemplos": [{"id": "E1", "estado": "hipotese", "situacao": "Chegada."}]},
        ]}
        (self.raiz / "glossario.json").write_text(json_texto(dados_glossario), encoding="utf-8")
        (self.raiz / "vozes.json").write_text(json_texto(dados_vozes), encoding="utf-8")
        status = calcular_status(self.dados, self.raiz)
        vistas = gerar_vistas(self.dados, status, self.raiz)
        self.assertEqual(vistas, gerar_vistas(self.dados, status, self.raiz))
        glossario = vistas["GLOSSÁRIO.md"].decode()
        vozes = vistas["VOZES.md"].decode()
        self.assertIn("Nota editorial.", glossario)
        self.assertIn("Decisão anterior", glossario)
        self.assertIn("Evolução de tratamento.", vozes)
        self.assertIn("Chegada.", vozes)
