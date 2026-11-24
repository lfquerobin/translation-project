"""Vistas determinísticas do registro, protegidas contra substituição editorial."""

from hashlib import sha256
from html import escape
import re
from urllib.parse import quote

from .arquivos import criar_arquivo, substituir_arquivo
from .epub import caminho_registro
from .registro import ETAPAS


AVISO = "<!-- Gerado de projeto.json com traducao sincronizar --aplicar. SHA-256: "
VISTAS = ("ACOMPANHAMENTO.md", "PENDÊNCIAS.md")


def celula(valor):
    texto = " ".join(str(valor if valor is not None else "—").split())
    return escape(texto, quote=False).replace("|", "&#124;")


def linha_tabela(valores):
    return "| " + " | ".join(celula(valor) for valor in valores) + " |"


def vista(linhas):
    corpo = ("\n".join(linhas).rstrip() + "\n").encode("utf-8")
    return (AVISO + sha256(corpo).hexdigest() + " -->\n\n").encode("utf-8") + corpo


def _validar_assinatura(dados):
    marcador, _, corpo = dados.partition(b"\n\n")
    if not marcador.startswith(AVISO.encode("utf-8")) or not marcador.endswith(b" -->"):
        return False
    hash_esperado = marcador[len(AVISO.encode("utf-8")):].removesuffix(b" -->")
    return sha256(corpo).hexdigest().encode("ascii") == hash_esperado


def _normalizar_lf(dados):
    return dados.replace(b"\r\n", b"\n")


def gerar_vistas(dados, status):
    acompanhamento = [
        "# Acompanhamento da tradução", "",
        "Fonte de verdade: `projeto.json`. Regenere com `traducao sincronizar --projeto . --aplicar`.", "",
    ]
    if not status["unidades"]:
        acompanhamento += ["Projeto em preparação.", ""]
    acompanhamento += [
        linha_tabela(["Unidade", "Cobertura", *ETAPAS, "Edição de trabalho"]),
        linha_tabela(["---"] * (len(ETAPAS) + 3)),
    ]
    for unidade in status["unidades"]:
        rotulo = re.sub(r"([\[\]\\])", r"\\\1", unidade["id"])
        link = f"[{rotulo}]({quote(unidade['arquivo'])})" if unidade["hash_texto"] else rotulo
        acompanhamento.append(linha_tabela([
            link, unidade["cobertura"],
            *(unidade["revisoes"][etapa]["estado"] for etapa in ETAPAS), unidade["estado"],
        ]))
    pendencias = [
        "# Pendências editoriais", "",
        "Fonte de verdade: `projeto.json`. Regenere com `traducao sincronizar --projeto . --aplicar`.", "",
    ]
    grupos = {
        "Dúvidas em investigação": {"aberta", "em_investigacao"},
        "Dúvidas resolvidas": {"resolvida"},
        "Anonimato intencional": {"anonimato_intencional"},
    }
    for titulo, estados in grupos.items():
        pendencias += [
            f"## {titulo}", "",
            linha_tabela(["ID", "Unidade", "Trecho", "Estado", "Motivo, fonte e próximo passo"]),
            linha_tabela(["---"] * 5),
        ]
        for item in dados.get("ocorrencias", []):
            if item["estado"] in estados:
                detalhes = [item.get(campo) for campo in ("motivo", "fonte", "proximo_passo", "resolucao", "nota")]
                pendencias.append(linha_tabela([
                    item["id"], item["unidade"], item.get("trecho"), item["estado"],
                    " · ".join(str(v) for v in detalhes if v) or None,
                ]))
        pendencias.append("")
    return dict(zip(VISTAS, (vista(acompanhamento), vista(pendencias))))


def inspecionar_vistas(raiz, geradas):
    resultado = {}
    for nome, conteudo in geradas.items():
        caminho = caminho_registro(raiz, nome)
        if caminho.is_symlink() or (caminho.exists() and not caminho.is_file()):
            raise ValueError(f"Destino de vista inválido: {nome}")
        anterior = caminho.read_bytes() if caminho.is_file() else None
        estado = "ausente" if anterior is None else (
            "atual" if _normalizar_lf(anterior) == conteudo else
            "desatualizada" if _validar_assinatura(_normalizar_lf(anterior)) else "manual"
        )
        resultado[nome] = (caminho, estado, anterior)
    return resultado


def aplicar_vistas(geradas, plano):
    manuais = [nome for nome, (_, estado, _) in plano.items() if estado == "manual"]
    if manuais:
        raise ValueError("Migre e arquive as anotações antes de gerar vistas: " + ", ".join(manuais))
    for nome, (caminho, estado, anterior) in plano.items():
        if estado == "ausente":
            criar_arquivo(caminho, geradas[nome])
        elif estado == "desatualizada":
            substituir_arquivo(caminho, geradas[nome], anterior)
