"""Índice SQLite local e descartável de segmentos com procedência editorial."""

from contextlib import closing
from hashlib import sha256
import re
import sqlite3
import unicodedata

from .arquivos import json_texto, ler_json
from .epub import caminho_registro
from .registro import calcular_status, indice_unico, lista, objeto, texto, validar_hash


INDICE = ".traducao/memoria.sqlite3"
VERSAO = 1
PALAVRAS = re.compile(r"[^\W_]+")


def _normalizar(valor):
    return unicodedata.normalize("NFC", valor).casefold()


def _segmentos(dados, raiz):
    config = objeto(dados.get("convencoes", {}).get("memoria"), "convencoes.memoria")
    nome = texto(config.get("segmentos"), "convencoes.memoria.segmentos")
    registro = objeto(ler_json(caminho_registro(raiz, nome)), "segmentos")
    if type(registro.get("schema")) is not int or registro["schema"] != 1:
        raise ValueError("Use o schema 1 no registro de segmentos.")
    obra = texto(dados.get("obra"), "obra")
    excluidas = set(lista(config.get("excluir_unidades", []), "excluir_unidades"))
    estados = {u["id"]: u for u in calcular_status(dados, raiz)["unidades"]}
    unidades = {u["id"]: u for u in dados["unidades"]}
    if excluidas - unidades.keys():
        raise ValueError("A política de exclusão contém unidades desconhecidas.")
    entradas = {}
    textos_salvos = {}
    for item in indice_unico(registro.get("segmentos"), "segmentos").values():
        id_unidade = texto(item.get("unidade"), "segmento.unidade")
        if id_unidade not in unidades:
            raise ValueError(f"Unidade desconhecida no segmento {item['id']}: {id_unidade}")
        if type(item.get("indexar", True)) is not bool:
            raise ValueError(f"indexar precisa ser booleano no segmento {item['id']}.")
        if id_unidade in excluidas or not item.get("indexar", True):
            continue
        unidade = unidades[id_unidade]
        estado = estados[id_unidade]
        versao = texto(unidade.get("edicao") or dados.get("versao"), "versao")
        limite = item.get("visivel_apos", id_unidade)
        if limite not in unidades:
            raise ValueError(f"Limite narrativo desconhecido no segmento {item['id']}.")
        if (unidades[limite].get("edicao") or dados.get("versao")) != versao:
            raise ValueError(f"Limite narrativo de outra edição no segmento {item['id']}.")
        ordem_visivel = max(unidade["ordem"], unidades[limite]["ordem"])
        original = item.get("original")
        intermediaria = item.get("intermediaria")
        if original is not None:
            texto(original, "segmento.original")
        if intermediaria is not None:
            texto(intermediaria, "segmento.intermediaria")
        traducao = texto(item.get("traducao"), "segmento.traducao")
        referencia = texto(item.get("referencia"), "segmento.referencia")
        hash_atestado = item.get("hash_texto")
        if hash_atestado is not None:
            validar_hash(hash_atestado, "segmento.hash_texto")
        campos_contexto = ("contexto", "interlocutor", "cena")
        for campo in campos_contexto:
            if item.get(campo) is not None:
                texto(item[campo], f"segmento.{campo}")
        falante = item.get("falante")
        if falante is not None:
            falante = objeto(falante, "segmento.falante")
            if falante.get("estado") not in {"confirmado", "incerto", "anonimo"}:
                raise ValueError(f"Estado de falante inválido no segmento {item['id']}.")
            if falante["estado"] == "confirmado":
                texto(falante.get("id"), "segmento.falante.id")
        termos = [texto(termo, "segmento.termos") for termo in lista(item.get("termos", []), "segmento.termos")]
        alinhamento = item.get("alinhamento")
        if alinhamento is not None:
            alinhamento = objeto(alinhamento, "segmento.alinhamento")
            for lado in ("origem", "destino"):
                ids = lista(alinhamento.get(lado), f"segmento.alinhamento.{lado}")
                if not ids or any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
                    raise ValueError(f"IDs de alinhamento inválidos no segmento {item['id']}.")
        status = "em_trabalho"
        if hash_atestado and hash_atestado != estado["hash_texto"]:
            status = "desatualizada"
        elif hash_atestado and estado["estado"] == "revisada_edicao_trabalho":
            if id_unidade not in textos_salvos:
                arquivo = caminho_registro(raiz, unidade["arquivo"])
                textos_salvos[id_unidade] = arquivo.read_text(encoding="utf-8-sig")
            if traducao.replace("\r\n", "\n") in textos_salvos[id_unidade]:
                status = "revisada_edicao_trabalho"
        entrada = {
            "id": item["id"], "unidade": id_unidade, "ordem": unidade["ordem"], "ordem_visivel": ordem_visivel,
            "arquivo": unidade["arquivo"], "obra": obra, "versao": versao, "estado": status,
            "fidelidade_original": estado["revisoes"]["fidelidade_original"]["estado"],
            "hash_texto": estado["hash_texto"], "referencia": referencia, "original": original,
            "intermediaria": intermediaria, "traducao": traducao,
            **{campo: item.get(campo) for campo in campos_contexto},
            "falante": falante, "termos": termos, "alinhamento": alinhamento,
        }
        combinado = " ".join(v for v in (original, intermediaria, traducao, *(item.get(c) for c in campos_contexto)) if v)
        # Os itens aprovados são recalculados na busca. Um índice obsoleto nunca atesta aprovação.
        digest = sha256(json_texto(entrada).encode("utf-8")).hexdigest()
        entradas[item["id"]] = (entrada, _normalizar(combinado), digest)
    return entradas, unidades, obra


def _conexao(caminho, *, leitura=False):
    if leitura and not caminho.is_file():
        raise ValueError("O índice local ainda não existe. Execute memoria atualizar --aplicar.")
    if caminho.is_symlink():
        raise ValueError("O índice não pode ser um link simbólico.")
    uri = caminho.as_uri() + ("?mode=ro" if leitura else "?mode=rwc")
    conexao = sqlite3.connect(uri, uri=True)
    conexao.execute("PRAGMA trusted_schema=OFF")
    return closing(conexao)


def _tem_tabela(db, nome):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone() is not None


def _fts_pendente(db):
    return _tem_tabela(db, "estado_fts") and db.execute("SELECT 1 FROM estado_fts").fetchone() is not None


def _executar_fts(db, sql):
    try:
        db.execute(sql)
    except sqlite3.OperationalError as erro:
        if str(erro) != "no such module: fts5":
            raise
        return False
    return True


def _preparar(db):
    versao = db.execute("PRAGMA user_version").fetchone()[0]
    if versao == 0 and not db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
        db.execute("""CREATE TABLE segmentos(
            id TEXT PRIMARY KEY, obra TEXT, versao TEXT, ordem_visivel INTEGER,
            estado TEXT, busca TEXT, digest TEXT
        )""")
        db.execute(f"PRAGMA user_version={VERSAO}")
    elif versao != VERSAO:
        raise ValueError("O arquivo existente não é um índice de memória compatível.")
    db.execute("CREATE TABLE IF NOT EXISTS estado_fts (pendente INTEGER PRIMARY KEY)")


def _preparar_fts(db, habilitado):
    existe = _tem_tabela(db, "busca_fts")
    if not habilitado:
        return False, False
    if not existe:
        criado = _executar_fts(
            db, "CREATE VIRTUAL TABLE busca_fts USING fts5(id UNINDEXED, busca, tokenize='unicode61 remove_diacritics 0')",
        )
        return criado, criado
    if not _executar_fts(db, "SELECT rowid FROM busca_fts LIMIT 0"):
        return False, False
    return True, _fts_pendente(db)


def atualizar(dados, raiz, *, aplicar=False, reconstruir=False, sem_fts=False):
    entradas, _, _ = _segmentos(dados, raiz)
    caminho = caminho_registro(raiz, INDICE)
    if not aplicar:
        return {"aplicado": False, "segmentos_elegiveis": len(entradas), "indice": INDICE}
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with _conexao(caminho) as db, db:
        db.execute("BEGIN IMMEDIATE")
        _preparar(db)
        fts, repovoar = _preparar_fts(db, not sem_fts)
        existentes = dict(db.execute("SELECT id, digest FROM segmentos"))
        remover = set(existentes) - entradas.keys()
        mudar = {id for id, (_, _, digest) in entradas.items() if reconstruir or existentes.get(id) != digest}
        if fts and repovoar:
            db.execute("DELETE FROM busca_fts")
        elif fts:
            for id in sorted(remover | mudar):
                db.execute("DELETE FROM busca_fts WHERE id=?", (id,))
        db.executemany("DELETE FROM segmentos WHERE id=?", [(id,) for id in sorted(remover)])
        for id in sorted(mudar):
            entrada, busca, digest = entradas[id]
            db.execute("INSERT OR REPLACE INTO segmentos VALUES(?, ?, ?, ?, ?, ?, ?)", (
                id, entrada["obra"], entrada["versao"], entrada["ordem_visivel"], entrada["estado"], busca, digest,
            ))
        if fts:
            ids_fts = entradas if repovoar else mudar
            db.executemany("INSERT INTO busca_fts VALUES(?, ?)", [(id, entradas[id][1]) for id in sorted(ids_fts)])
            db.execute("DELETE FROM estado_fts")
        elif (mudar or remover) and _tem_tabela(db, "busca_fts"):
            db.execute("INSERT OR IGNORE INTO estado_fts VALUES(1)")
    return {"aplicado": True, "segmentos_elegiveis": len(entradas), "atualizados": len(mudar),
            "removidos": len(remover), "fts": fts and not sem_fts, "indice": INDICE}


def buscar(dados, raiz, consulta, *, obra, versao, ate, futuro=False, trabalho=False, limite=10, sem_fts=False):
    entradas, unidades, obra_atual = _segmentos(dados, raiz)
    texto(versao, "versao")
    if obra != obra_atual or ate not in unidades:
        raise ValueError("Informe a obra exata e uma unidade cadastrada como limite narrativo.")
    edicao_limite = unidades[ate].get("edicao") or dados.get("versao")
    if edicao_limite != versao:
        raise ValueError("O limite narrativo precisa pertencer à versão consultada.")
    termos = list(dict.fromkeys(PALAVRAS.findall(_normalizar(consulta))))
    if not termos or len(termos) > 20 or not 1 <= limite <= 20:
        raise ValueError("Use entre 1 e 20 termos de busca e limite de 1 a 20 resultados.")
    ordem = max(u["ordem"] for u in unidades.values()) if futuro else unidades[ate]["ordem"]
    filtro = """s.obra=? AND s.versao=? AND s.ordem_visivel<=? AND
                (s.estado='revisada_edicao_trabalho' OR (? AND s.estado='em_trabalho'))"""
    valores = (obra, versao, ordem, trabalho)
    caminho = caminho_registro(raiz, INDICE)
    with _conexao(caminho, leitura=True) as db:
        if db.execute("PRAGMA user_version").fetchone()[0] != VERSAO:
            raise ValueError("O índice tem um formato incompatível.")
        fts = (not sem_fts and _tem_tabela(db, "busca_fts") and not _fts_pendente(db)
               and _executar_fts(db, "SELECT rowid FROM busca_fts LIMIT 0"))
        encontrados = []
        if fts:
            expressao = " AND ".join(f'"{t}"' for t in termos)
            encontrados = db.execute(
                f"""SELECT s.id, s.digest FROM busca_fts JOIN segmentos s ON busca_fts.id=s.id
                    WHERE {filtro} AND busca_fts MATCH ? ORDER BY rank, s.id""", (*valores, expressao),
            ).fetchall()
        if not encontrados:
            trechos = " AND ".join("instr(s.busca, ?) > 0" for _ in termos)
            encontrados = db.execute(
                f"SELECT s.id, s.digest FROM segmentos s WHERE {filtro} AND {trechos} ORDER BY s.id",
                (*valores, *termos),
            ).fetchall()
    resultados = []
    for id, digest in encontrados:
        if id not in entradas or entradas[id][2] != digest:
            continue
        entrada = entradas[id][0]
        estados = {"revisada_edicao_trabalho", "em_trabalho"} if trabalho else {"revisada_edicao_trabalho"}
        if (entrada["estado"] not in estados or entrada["versao"] != versao
                or entrada["obra"] != obra or entrada["ordem_visivel"] > ordem):
            continue
        resumo = dict(entrada)
        for campo in ("original", "intermediaria", "traducao", "contexto", "interlocutor", "cena", "referencia"):
            if resumo[campo] and len(resumo[campo]) > 240:
                resumo[campo] = resumo[campo][:237] + "…"
        resultados.append(resumo)
        if len(resultados) == limite:
            break
    return {"schema": 1, "obra": obra, "versao": versao, "ate": ate, "inclui_futuro": futuro, "resultados": resultados}
