"""Migração conservadora do registro central v1 e registro de invalidações."""

from copy import deepcopy

from .arquivos import criar_arquivo, json_texto
from .registro import ETAPAS, calcular_status, objeto, validar_registro


def migrar(dados, raiz):
    objeto(dados, "projeto")
    if type(dados.get("schema")) is not int:
        raise ValueError("O registro precisa informar a versão do schema.")
    if dados["schema"] == 2:
        validar_registro(dados, raiz)
        return deepcopy(dados), []
    if dados["schema"] != 1 or not isinstance(dados.get("unidades"), list):
        raise ValueError("Migração limitada ao esquema central v1 com unidades. Confira o contrato da obra.")
    resultado = deepcopy(dados)
    resultado["schema"] = 2
    relatorio = []
    for ordem, unidade in enumerate(resultado["unidades"], 1):
        objeto(unidade, "unidade")
        id_unidade = unidade["id"]
        if "historico" in unidade or "revisoes_legadas" in unidade:
            raise ValueError(f"Campos reservados para migração já existem em {id_unidade}.")
        unidade.setdefault("ordem", ordem)
        unidade.setdefault("tipo", None)
        unidade.setdefault("edicao_trabalho", None)
        unidade.setdefault("fontes", {})
        unidade.setdefault("cobertura", {"estado": "pendente", "escopo": None})
        unidade["historico"] = []
        if "revisoes" in unidade:
            revisoes = objeto(unidade.pop("revisoes"), f"{id_unidade}.revisoes")
            unidade["revisoes_legadas"] = revisoes
            for etapa in ETAPAS:
                revisao = revisoes.get(etapa)
                if revisao and objeto(revisao, etapa).get("estado") != "pendente":
                    unidade["historico"].append({
                        "id": f"legado-{etapa}", "etapa": etapa, "estado": "historica",
                        "motivo": "Registro migrado sem comprovação de vigência por hash.",
                    })
        relatorio.append({
            "unidade": id_unidade, "ordem": unidade["ordem"],
            "historico": [evento["etapa"] for evento in unidade["historico"]],
            "fidelidade_unica_preservada": "fidelidade" in unidade.get("revisoes_legadas", {}),
            "campos_a_confirmar": [campo for campo in ("tipo", "edicao_trabalho") if unidade[campo] is None],
        })
    validar_registro(resultado, raiz)
    return resultado, relatorio


def invalidar(dados, raiz):
    status = calcular_status(dados, raiz)
    resultado = deepcopy(dados)
    revisoes = {u["id"]: u["revisoes"] for u in status["unidades"]}
    relatorio = []
    for unidade in resultado["unidades"]:
        historico = unidade["historico"]
        eventos = {evento["id"]: evento for evento in historico}
        for etapa, revisao in revisoes[unidade["id"]].items():
            evento = eventos.get(revisao["evento"], {})
            if revisao["estado"] != "desatualizada" or evento.get("estado") == "desatualizada":
                continue
            id_evento = f"invalidacao-{evento['id']}-{len(historico) + 1}"
            while id_evento in eventos:
                id_evento += "-nova"
            historico.append({
                "id": id_evento, "etapa": etapa, "estado": "desatualizada",
                "evento_anterior": evento["id"], "motivo": revisao["motivo"],
            })
            relatorio.append({"unidade": unidade["id"], "etapa": etapa, "evento": id_evento})
    return resultado, relatorio


def salvar_copia(saida, dados):
    criar_arquivo(saida, json_texto(dados).encode("utf-8"))
