"""Registros opcionais de glossário e vozes, com alertas contextuais."""

import re
import unicodedata

from .arquivos import ler_json
from .epub import caminho_registro
from .markdown import visivel
from .registro import indice_unico, lista, objeto, texto
from .verificador_epub import Achado


ESTADOS_TERMO = {"obrigatorio", "preferencia", "alternativa_contextual", "em_investigacao", "proposto", "revogado"}
ATIVOS = {"obrigatorio", "preferencia", "alternativa_contextual"}
CITACAO = re.compile(r'“[^”]*”|«[^»]*»|"[^"]*"')


def _normalizar(valor):
    return unicodedata.normalize("NFC", valor)


def _textos(valor, campo):
    return [texto(item, campo) for item in lista(valor, campo)]


def abrir_editorial(dados, raiz, chave):
    arquivo = dados.get("convencoes", {}).get(chave)
    if arquivo is None:
        return None
    registro = objeto(ler_json(caminho_registro(raiz, texto(arquivo, chave))), chave)
    if type(registro.get("schema")) is not int or registro["schema"] != 1:
        raise ValueError(f"Schema inválido em {chave}. Use schema 1.")
    return registro


def _escopo(item, campo):
    escopo = objeto(item.get("escopo", {}), campo)
    inicio, fim = escopo.get("inicio"), escopo.get("fim")
    if any(v is not None and (type(v) is not int or v < 1) for v in (inicio, fim)):
        raise ValueError(f"Ordem narrativa inválida em {campo}.")
    if inicio is not None and fim is not None and inicio > fim:
        raise ValueError(f"Intervalo invertido em {campo}.")
    return inicio, fim


def _variantes(regra, campo):
    formas = []
    for entrada in lista(regra.get(campo, []), campo):
        if isinstance(entrada, str):
            formas.append(texto(entrada, campo))
        else:
            entrada = objeto(entrada, campo)
            formas.append(texto(entrada.get("forma"), campo))
            formas.extend(_textos(entrada.get("flexoes", []), "flexoes"))
    return formas


def validar_glossario(registro):
    termos = indice_unico(registro.get("termos"), "termos")
    for id_termo, termo in termos.items():
        for chave in ("original", "idioma", "traducao"):
            texto(termo.get(chave), f"{id_termo}.{chave}")
        if termo.get("estado") not in ESTADOS_TERMO:
            raise ValueError(f"Estado inválido em {id_termo}.")
        _escopo(termo, id_termo)
        if (termo["estado"] == "alternativa_contextual" and not
                any(termo.get(chave) for chave in ("contexto_busca", "excluir_contexto", "escopo", "edicao"))):
            raise ValueError(f"Informe o contexto ou escopo da alternativa {id_termo}.")
        for chave in ("sensivel_caixa", "incluir_citacoes"):
            if type(termo.get(chave, False)) is not bool:
                raise ValueError(f"{chave} exige booleano em {id_termo}.")
        for chave in ("referencias", "contexto_busca", "excluir_contexto"):
            _textos(termo.get(chave, []), chave)
        for chave in ("variantes_aceitas", "variantes_alerta"):
            _variantes(termo, chave)
        for evento in lista(termo.get("historico", []), "historico"):
            evento = objeto(evento, "evento do glossário")
            if "forma_anterior" in evento:
                texto(evento["forma_anterior"], "forma_anterior")
    return termos


def validar_vozes(registro, dados):
    vozes = indice_unico(registro.get("vozes"), "vozes")
    unidades = {u["id"]: u for u in dados["unidades"]}
    for id_voz, voz in vozes.items():
        texto(voz.get("nome"), f"{id_voz}.nome")
        if voz.get("tipo") not in {"personagem", "narrativa"}:
            raise ValueError(f"Tipo inválido em {id_voz}.")
        _escopo(voz, id_voz)
        for exemplo in indice_unico(voz.get("exemplos", []), f"{id_voz}.exemplos").values():
            id_unidade = exemplo.get("unidade")
            if id_unidade is not None and id_unidade not in unidades:
                raise ValueError(f"Unidade desconhecida em {id_voz}/{exemplo['id']}.")
            _escopo(exemplo, exemplo["id"])
            if exemplo.get("estado") not in {"confirmada", "hipotese"}:
                raise ValueError(f"Estado de exemplo inválido em {id_voz}/{exemplo['id']}.")
            if exemplo["estado"] == "confirmada":
                for chave in ("referencia", "edicao", "unidade", "original", "traducao"):
                    texto(exemplo.get(chave), f"{id_voz}/{exemplo['id']}.{chave}")
    for item in dados.get("ocorrencias", []):
        id_voz = item.get("voz")
        if id_voz is not None and id_voz not in vozes:
            raise ValueError(f"Voz desconhecida na ocorrência {item['id']}.")
    return vozes


def _padrao(formas, sensivel):
    valores = sorted({_normalizar(v) for v in formas}, key=lambda v: (-len(v), v))
    if not valores:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, valores)) + r")(?!\w)", 0 if sensivel else re.I)


def _aplicavel(termo, unidade, versao):
    inicio, fim = _escopo(termo, termo["id"])
    ordem = unidade["ordem"]
    return (
        (termo.get("edicao") is None or termo["edicao"] == (unidade.get("edicao") or versao))
        and (inicio is None or inicio <= ordem) and (fim is None or ordem <= fim)
    )


def ocorrencias_glossario(registro, dados, raiz, *, termo_id=None, unidade_id=None, volume=None):
    termos = validar_glossario(registro)
    if termo_id is not None and termo_id not in termos:
        raise ValueError(f"Termo desconhecido: {termo_id}")
    selecionados = [termos[termo_id]] if termo_id else [t for t in termos.values() if t["estado"] in ATIVOS]
    buscas = []
    for termo in selecionados:
        sensivel = termo.get("sensivel_caixa", False)
        formas = _variantes(termo, "variantes_alerta")
        aceitas = [termo["traducao"], *_variantes(termo, "variantes_aceitas")]
        def chave(v):
            normalizado = _normalizar(v)
            return normalizado if sensivel else normalizado.casefold()
        if termo_id:
            formas += aceitas + [e["forma_anterior"] for e in termo.get("historico", []) if "forma_anterior" in e]
        else:
            indiferentes = {chave(v) for v in aceitas}
            formas = [v for v in formas if chave(v) not in indiferentes]
        contexto = _padrao(termo.get("contexto_busca", []), sensivel)
        exclusoes = _padrao(termo.get("excluir_contexto", []), sensivel)
        padrao = _padrao(formas, sensivel)
        if padrao:
            buscas.append((termo, padrao, contexto, exclusoes))
    achados = []
    for unidade in sorted(dados["unidades"], key=lambda u: u["ordem"]):
        if (unidade_id and unidade["id"] != unidade_id) or (volume is not None and unidade.get("volume") != volume):
            continue
        aplicaveis = [item for item in buscas if _aplicavel(item[0], unidade, dados.get("versao"))]
        if not aplicaveis:
            continue
        caminho = caminho_registro(raiz, unidade["arquivo"])
        if not caminho.is_file():
            continue
        conteudo = caminho.read_text(encoding="utf-8-sig")
        for n, (original, visivel_linha) in enumerate(zip(conteudo.split("\n"), visivel(conteudo).split("\n")), 1):
            linha = _normalizar(visivel_linha)
            for regra, padrao, contexto, exclusoes in aplicaveis:
                candidata = linha if regra.get("incluir_citacoes") else CITACAO.sub(" ", linha)
                if (contexto and not contexto.search(candidata)) or (exclusoes and exclusoes.search(candidata)):
                    continue
                for resultado in padrao.finditer(candidata):
                    achados.append(Achado(
                        "GLOSSARIO_AFETADA" if termo_id else "GLOSSARIO_VARIANTE", "aviso", unidade["arquivo"],
                        f"{regra['id']} · {resultado[0]} · {original.strip()}",
                        unidade["id"], n,
                    ))
    return achados
