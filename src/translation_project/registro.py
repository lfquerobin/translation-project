"""Contrato e status derivados do registro central de uma obra."""

from collections import Counter
from datetime import date
from hashlib import sha256
from pathlib import Path
import re

from .arquivos import json_texto, ler_json, sha256_arquivo
from .epub import caminho_registro, chave_portavel


PAPEIS = ("original", "intermediaria")
ETAPAS = ("fidelidade_original", "fidelidade_intermediaria", "naturalidade", "falantes", "formato")
ESTADOS = {"pendente", "parcial", "concluida", "em_investigacao", "inaplicavel", "historica", "desatualizada"}
TIPOS_UNIDADE = {"narrativa", "extra", "editorial"}
HASH = re.compile(r"[0-9a-f]{64}\Z")


def objeto(valor, campo):
    if not isinstance(valor, dict):
        raise ValueError(f"{campo} precisa ser um objeto.")
    return valor


def lista(valor, campo):
    if not isinstance(valor, list):
        raise ValueError(f"{campo} precisa ser uma lista.")
    return valor


def texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{campo} precisa ser um texto não vazio.")
    return valor


def validar_hash(valor, campo):
    if not isinstance(valor, str) or not HASH.fullmatch(valor):
        raise ValueError(f"{campo} precisa ser SHA-256 hexadecimal minúsculo.")
    return valor


def validar_data(valor, campo):
    if not isinstance(valor, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        raise ValueError(f"{campo} precisa ter formato AAAA-MM-DD.")
    date.fromisoformat(valor)


def indice_unico(registros, campo):
    indice = {}
    for item in lista(registros, campo):
        id_item = texto(objeto(item, campo).get("id"), f"{campo}.id")
        if id_item in indice:
            raise ValueError(f"ID repetido em {campo}: {id_item}")
        indice[id_item] = item
    return indice


def _evidencias(valor, campo):
    if not lista(valor, campo):
        raise ValueError(f"{campo} exige ao menos uma evidência.")
    for valor in valor:
        texto(valor, campo)


def _validar_revisao(evento, unidade):
    etapa, estado = evento.get("etapa"), evento.get("estado")
    campo = f"{unidade}.{evento['id']}"
    if etapa not in ETAPAS or estado not in ESTADOS:
        raise ValueError(f"Etapa ou estado de revisão inválido em {campo}.")
    if evento.get("data") is not None:
        validar_data(evento["data"], f"{campo}.data")
    if estado in {"inaplicavel", "desatualizada"}:
        texto(evento.get("motivo"), f"{campo}.motivo")
    if estado == "inaplicavel" and etapa not in {"falantes", "fidelidade_intermediaria"}:
        raise ValueError(f"Etapa obrigatória marcada inaplicável em {campo}.")
    if estado not in {"concluida", "parcial"}:
        return
    validar_data(evento.get("data"), f"{campo}.data")
    validar_hash(evento.get("hash_texto"), f"{campo}.hash_texto")
    _evidencias(evento.get("evidencias"), f"{campo}.evidencias")
    escopo = evento.get("escopo")
    if estado == "concluida" and escopo != "integral":
        raise ValueError(f"Revisão concluída exige escopo integral em {campo}.")
    if estado == "parcial":
        _evidencias(escopo, f"{campo}.escopo")
    if etapa == "formato":
        texto(evento.get("arquivo_conferido"), f"{campo}.arquivo_conferido")
    papel_esperado = etapa.removeprefix("fidelidade_") if etapa.startswith("fidelidade_") else None
    fonte = evento.get("fonte")
    if papel_esperado or fonte is not None:
        fonte = objeto(fonte, f"{campo}.fonte")
        if fonte.get("papel") not in PAPEIS or (papel_esperado and fonte["papel"] != papel_esperado):
            raise ValueError(f"Papel de fonte incompatível com a etapa em {campo}.")
        texto(fonte.get("referencia"), f"{campo}.fonte.referencia")
        if fonte.get("hash") is not None:
            validar_hash(fonte["hash"], f"{campo}.fonte.hash")


def validar_registro(dados, raiz):
    objeto(dados, "projeto")
    if type(dados.get("schema")) is not int or dados["schema"] != 2:
        raise ValueError("Use o schema central 2. Para o schema central 1, consulte o comando migrar.")
    texto(dados.get("idioma_destino"), "idioma_destino")
    convencoes = objeto(dados.get("convencoes", {}), "convencoes")
    if type(convencoes.get("painel", False)) is not bool:
        raise ValueError("convencoes.painel precisa ser booleano.")
    unidades = indice_unico(dados.get("unidades"), "unidades")
    volumes = indice_unico(dados.get("volumes", []), "volumes")
    ocorrencias = indice_unico(dados.get("ocorrencias", []), "ocorrencias")
    ordens, caminhos = set(), set()
    for id_unidade, unidade in unidades.items():
        nome = texto(unidade.get("arquivo"), f"{id_unidade}.arquivo")
        caminho_registro(raiz, nome)
        chave = chave_portavel(nome)
        ordem = unidade.get("ordem")
        if chave in caminhos or type(ordem) is not int or ordem < 1 or ordem in ordens:
            raise ValueError(f"Caminho ou ordem narrativa inválida ou repetida em {id_unidade}.")
        caminhos.add(chave)
        ordens.add(ordem)
        if unidade.get("tipo") is not None and unidade["tipo"] not in TIPOS_UNIDADE:
            raise ValueError(f"Tipo inválido em {id_unidade}.")
        if unidade.get("volume") is not None and unidade["volume"] not in volumes:
            raise ValueError(f"Volume desconhecido em {id_unidade}: {unidade['volume']}")
        fontes = objeto(unidade.get("fontes"), f"{id_unidade}.fontes")
        for papel in PAPEIS:
            fonte = fontes.get(papel)
            if fonte is not None:
                objeto(fonte, f"{id_unidade}.fontes.{papel}")
                if fonte.get("arquivo") is not None:
                    caminho_registro(raiz, texto(fonte["arquivo"], f"{id_unidade}.fontes.{papel}.arquivo"))
                if fonte.get("referencia") is not None:
                    texto(fonte["referencia"], f"{id_unidade}.fontes.{papel}.referencia")
                if fonte.get("data_publicacao") is not None:
                    validar_data(fonte["data_publicacao"], f"{id_unidade}.fontes.{papel}.data_publicacao")
        trabalho = unidade.get("edicao_trabalho")
        if trabalho is not None and (trabalho not in PAPEIS or fontes.get(trabalho) is None):
            raise ValueError(f"Edição de trabalho sem fonte identificada em {id_unidade}.")
        cobertura = objeto(unidade.get("cobertura"), f"{id_unidade}.cobertura")
        if cobertura.get("estado") not in {"pendente", "parcial", "integral"}:
            raise ValueError(f"Cobertura inválida em {id_unidade}.")
        if cobertura.get("hash_texto") is not None:
            validar_hash(cobertura["hash_texto"], f"{id_unidade}.cobertura.hash_texto")
        for tipo in ("imagens", "notas"):
            inspecao = objeto(unidade.get(tipo, {"estado": "pendente"}), f"{id_unidade}.{tipo}")
            estado = inspecao.get("estado")
            if estado not in {"pendente", "parcial", "concluida", "inaplicavel"}:
                raise ValueError(f"Inspeção inválida em {id_unidade}.{tipo}.")
            if estado == "concluida":
                validar_hash(inspecao.get("hash_texto"), f"{id_unidade}.{tipo}.hash_texto")
                _evidencias(inspecao.get("evidencias"), f"{id_unidade}.{tipo}.evidencias")
            elif estado == "inaplicavel":
                texto(inspecao.get("motivo"), f"{id_unidade}.{tipo}.motivo")
        for evento in indice_unico(unidade.get("historico"), f"{id_unidade}.historico").values():
            _validar_revisao(evento, id_unidade)
    for id_ocorrencia, ocorrencia in ocorrencias.items():
        if ocorrencia.get("unidade") not in unidades:
            raise ValueError(f"Unidade desconhecida na ocorrência {id_ocorrencia}.")
        if type(ocorrencia.get("bloqueante", False)) is not bool:
            raise ValueError(f"bloqueante precisa ser booleano em {id_ocorrencia}.")
        if ocorrencia.get("estado") not in {"aberta", "em_investigacao", "resolvida", "anonimato_intencional"}:
            raise ValueError(f"Estado inválido na ocorrência {id_ocorrencia}.")
    for id_volume, volume in volumes.items():
        nomes_conjunto = lista(volume.get("arquivos_conjunto", []), f"{id_volume}.arquivos_conjunto")
        nomes_conjunto = [texto(nome, f"{id_volume}.arquivos_conjunto") for nome in nomes_conjunto]
        if len({chave_portavel(nome) for nome in nomes_conjunto}) != len(nomes_conjunto):
            raise ValueError(f"Arquivos de conjunto repetidos no volume {id_volume}.")
        for nome in nomes_conjunto:
            caminho_registro(raiz, nome)
        conjunto = objeto(volume.get("conjunto", {"estado": "pendente"}), f"{id_volume}.conjunto")
        if conjunto.get("estado") == "concluida":
            validar_data(conjunto.get("data"), f"{id_volume}.conjunto.data")
            validar_hash(conjunto.get("hash"), f"{id_volume}.conjunto.hash")
            _evidencias(conjunto.get("evidencias"), f"{id_volume}.conjunto.evidencias")
        elif conjunto.get("estado") != "pendente":
            raise ValueError(f"Estado de conjunto inválido em {id_volume}.")
    return unidades, volumes, ocorrencias


def fonte_atual(raiz, papel, fonte):
    if fonte is None:
        return None
    arquivo = caminho_registro(raiz, fonte["arquivo"]) if fonte.get("arquivo") else None
    return {
        "papel": papel,
        "referencia": fonte.get("referencia") or fonte.get("arquivo"),
        "edicao": fonte.get("edicao"),
        "hash": sha256_arquivo(arquivo) if arquivo and arquivo.is_file() else None,
        "local_ausente": bool(arquivo and not arquivo.is_file()),
    }


def estado_revisao(evento, hash_texto, arquivo, fontes, papel_trabalho):
    if evento is None:
        return "pendente", None
    estado = evento["estado"]
    if estado == "inaplicavel" and evento["etapa"] == "fidelidade_intermediaria" and fontes["intermediaria"]:
        return "desatualizada", "Há uma fonte intermediária cadastrada."
    if estado not in {"concluida", "parcial"}:
        return estado, evento.get("motivo")
    if evento["hash_texto"] != hash_texto:
        return "desatualizada", "O arquivo salvo mudou ou está ausente."
    if evento["etapa"] == "formato" and evento["arquivo_conferido"] != arquivo:
        return "desatualizada", "O caminho do arquivo mudou."
    fonte = evento.get("fonte")
    if fonte is not None:
        papel = fonte["papel"]
        atual = fontes.get(papel)
        if (atual is None or atual["local_ausente"]
                or any(fonte.get(campo) != atual[campo] for campo in ("referencia", "edicao", "hash"))
                or (not evento["etapa"].startswith("fidelidade_") and papel != papel_trabalho)):
            return "desatualizada", "A fonte registrada mudou ou está indisponível."
    elif papel_trabalho and evento["etapa"] in {"falantes", "formato", "naturalidade"}:
        return "desatualizada", "A evidência não identifica a edição de trabalho."
    return estado, None


def estado_unidade(raiz, unidade, bloqueios):
    id_unidade, arquivo = unidade["id"], unidade["arquivo"]
    caminho = caminho_registro(raiz, arquivo)
    hash_texto = sha256_arquivo(caminho) if caminho.is_file() else None
    fontes = {papel: fonte_atual(raiz, papel, unidade["fontes"].get(papel)) for papel in PAPEIS}
    trabalho = unidade.get("edicao_trabalho")
    eventos = {evento["etapa"]: evento for evento in unidade["historico"]}
    revisoes = {}
    for etapa in ETAPAS:
        evento = eventos.get(etapa)
        estado, motivo = estado_revisao(evento, hash_texto, arquivo, fontes, trabalho)
        revisoes[etapa] = {"estado": estado, "evento": evento["id"] if evento else None, "motivo": motivo}
    cobertura = unidade["cobertura"]["estado"]
    if cobertura == "integral" and (not hash_texto or unidade["cobertura"].get("hash_texto") != hash_texto):
        cobertura = "desatualizada"
    inspecoes = {}
    for tipo in ("imagens", "notas"):
        inspecao = unidade.get(tipo, {"estado": "pendente"})
        estado = inspecao["estado"]
        if estado == "concluida" and inspecao["hash_texto"] != hash_texto:
            estado = "desatualizada"
        inspecoes[tipo] = estado
    revisada = (
        trabalho is not None and unidade.get("tipo") is not None and cobertura == "integral" and not bloqueios
        and all(revisoes[etapa]["estado"] == "concluida"
                for etapa in (f"fidelidade_{trabalho}", "naturalidade", "formato"))
        and revisoes["falantes"]["estado"] in {"concluida", "inaplicavel"}
        and all(estado in {"concluida", "inaplicavel"} for estado in inspecoes.values())
    )
    return {
        "id": id_unidade, "arquivo": arquivo, "ordem": unidade["ordem"], "volume": unidade.get("volume"),
        "hash_texto": hash_texto, "cobertura": cobertura, "edicao_trabalho": trabalho,
        "revisoes": revisoes, "inspecoes": inspecoes, "bloqueios": bloqueios,
        "estado": "revisada_edicao_trabalho" if revisada else "em_trabalho",
    }


def calcular_status(dados, raiz, unidade=None):
    unidades, volumes, ocorrencias = validar_registro(dados, raiz)
    if unidade is not None and unidade not in unidades:
        raise ValueError(f"Unidade desconhecida: {unidade}")
    bloqueios = {}
    for ocorrencia in ocorrencias.values():
        if ocorrencia.get("bloqueante") and ocorrencia["estado"] in {"aberta", "em_investigacao"}:
            bloqueios.setdefault(ocorrencia["unidade"], []).append(ocorrencia["id"])
    selecionadas = [unidades[unidade]] if unidade else sorted(unidades.values(), key=lambda u: u["ordem"])
    estados = [estado_unidade(raiz, u, bloqueios.get(u["id"], [])) for u in selecionadas]
    estados_volumes = []
    if unidade is None:
        por_volume = {}
        for item in estados:
            por_volume.setdefault(item["volume"], []).append(item)
        for id_volume, volume in volumes.items():
            membros = por_volume.get(id_volume, [])
            conjunto = volume.get("conjunto", {})
            arquivos = {}
            for nome in volume.get("arquivos_conjunto", []):
                caminho = caminho_registro(raiz, nome)
                arquivos[nome] = sha256_arquivo(caminho) if caminho.is_file() else None
            conteudo = {"unidades": membros, "arquivos_conjunto": arquivos}
            hash_conjunto = sha256(json_texto(conteudo).encode("utf-8")).hexdigest()
            estado_conjunto = conjunto.get("estado", "pendente")
            if estado_conjunto == "concluida" and (conjunto["hash"] != hash_conjunto or None in arquivos.values()):
                estado_conjunto = "desatualizada"
            revisadas = sum(item["estado"] == "revisada_edicao_trabalho" for item in membros)
            estados_volumes.append({
                "id": id_volume, "unidades": len(membros), "revisadas": revisadas, "hash_conjunto": hash_conjunto,
                "conjunto": estado_conjunto, "estado": (
                    "em_preparacao" if not membros else "revisado_edicao_trabalho"
                    if revisadas == len(membros) and estado_conjunto == "concluida" else "em_trabalho"
                ),
            })
    return {
        "schema": 1, "estado": "em_preparacao" if not estados else "com_unidades",
        "unidades": estados, "volumes": estados_volumes,
        "totais": {**Counter(item["estado"] for item in estados), "unidades": len(estados)},
    }


def abrir_projeto(raiz):
    raiz = Path(raiz).resolve()
    arquivo = caminho_registro(raiz, "projeto.json")
    return ler_json(arquivo), raiz
