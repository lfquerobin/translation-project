from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from src.translation_project.arquivos import json_texto
from src.translation_project.registro import calcular_status
from src.translation_project.vistas import gerar_vistas
from test_registro import projeto_revisado, vazio


class PainelTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)

    def vistas(self, dados):
        return gerar_vistas(dados, calcular_status(dados, self.raiz), self.raiz)

    def test_optativo_e_projeto_vazio(self):
        dados = vazio()
        self.assertNotIn("PAINEL.md", self.vistas(dados))
        dados["convencoes"] = {"painel": True}
        painel = self.vistas(dados)["PAINEL.md"].decode()
        self.assertIn("Projeto em preparação.", painel)
        self.assertIn("Unidades revisadas pela edição de trabalho: 0/0", painel)

    def test_painel_reflete_etapas_pendencias_e_ocorrencias_por_volume(self):
        dados, arquivo, _ = projeto_revisado(self.raiz)
        dados["convencoes"] = {"painel": True}
        dados["volumes"] = [{"id": "V1", "inventario": "inventario.json"}, {"id": "V2"}]
        dados["unidades"][0]["volume"] = "V1"
        parcial = deepcopy(dados["unidades"][0])
        parcial.update(id="C2", ordem=2, volume="V2", arquivo="Parcial.md",
                       cobertura={"estado": "parcial"}, historico=[])
        dados["unidades"].append(parcial)
        dados["ocorrencias"] = [{"id": "P1", "unidade": "C2", "bloqueante": True, "estado": "aberta"}]
        imagem = {"epub": "figura.png", "markdown": "figura.png", "estado": "pendente"}
        inventario = {"schema": 1, "unidades": [{"imagens": [imagem, imagem]}]}
        (self.raiz / "inventario.json").write_text(json_texto(inventario), encoding="utf-8")
        painel = self.vistas(dados)["PAINEL.md"].decode()
        self.assertEqual(painel, self.vistas(dados)["PAINEL.md"].decode())
        self.assertIn("Unidades com tradução integral: 1/2", painel)
        self.assertIn("Unidades com tradução parcial: 1/2", painel)
        self.assertIn("Unidades revisadas pela edição de trabalho: 1/2", painel)
        self.assertIn("Pendências bloqueantes: 1 em 1/2 unidades", painel)
        self.assertIn("| Cotejo com a intermediária | 1/2 | 0 | 0 |", painel)
        self.assertIn("| Falantes | 0/1 | 1 | 0 |", painel)
        self.assertIn("pendente: 2/2", painel)
        self.assertIn("Inventário de imagens indisponível.", painel)
        arquivo.write_text("Texto alterado.", encoding="utf-8")
        alterado = self.vistas(dados)["PAINEL.md"].decode()
        self.assertIn("| Naturalidade | 0/2 | 0 | 1 |", alterado)
        self.assertIn("Unidades revisadas pela edição de trabalho: 0/2", alterado)
