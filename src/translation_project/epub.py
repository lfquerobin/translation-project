"""Leitura do pacote EPUB e validação de caminhos portáveis."""

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PureWindowsPath
import ntpath
import posixpath
import stat
import unicodedata
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree as ET
from zipfile import ZipFile


EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
RESERVADO = getattr(ntpath, "isreserved", lambda nome: PureWindowsPath(nome).is_reserved())


def chave_portavel(nome):
    return unicodedata.normalize("NFC", nome.casefold())


def partes_portaveis(nome):
    if not nome or nome.startswith("/") or "\\" in nome or ":" in nome:
        raise ValueError(f"Caminho local inválido: {nome!r}")
    partes = nome.split("/")
    for parte in partes:
        if parte in {".", ".."}:
            continue
        if (not parte or parte.endswith((" ", ".")) or RESERVADO(parte)
                or any(ord(c) < 32 or c in '<>"|?*' for c in parte)):
            raise ValueError(f"Componente de caminho inválido: {parte!r}")
    return partes


def resolver_epub(pagina, referencia):
    url = urlsplit(referencia)
    if url.scheme or url.netloc or referencia.startswith("//"):
        raise ValueError(f"Recurso externo no EPUB: {referencia}")
    caminho = unquote(url.path, errors="strict")
    if not caminho:
        return pagina
    partes_portaveis(caminho)
    destino = posixpath.normpath(posixpath.join(posixpath.dirname(pagina), caminho))
    if destino in {".", ".."} or destino.startswith("../"):
        raise ValueError(f"O caminho sai da raiz do EPUB: {referencia}")
    return destino


def caminho_local(volume, pasta, destino):
    url = urlsplit(destino)
    if len(url.scheme) == 1 or url.scheme == "file" or (not url.netloc and destino.startswith(("/", "\\"))):
        raise ValueError(f"Caminho absoluto: {destino}")
    if url.scheme or url.netloc or not url.path:
        return None
    caminho = pasta
    for parte in partes_portaveis(unquote(url.path, errors="strict")):
        if parte == ".":
            continue
        if parte == "..":
            caminho = caminho.parent
        else:
            if caminho.is_dir():
                candidatos = [entrada.name for entrada in caminho.iterdir()
                              if chave_portavel(entrada.name) == chave_portavel(parte)]
                if candidatos and candidatos != [parte]:
                    raise ValueError(f"Caixa ou normalização Unicode ambígua no destino: {destino}")
            caminho = caminho / parte
        if not caminho.resolve().is_relative_to(volume):
            raise ValueError(f"O destino sai da pasta do volume: {destino}")
    return caminho


def caminho_registro(raiz, nome):
    partes = partes_portaveis(nome)
    if any(p in {".", ".."} or p.casefold() == ".git" for p in partes):
        raise ValueError(f"Caminho de registro precisa ser relativo e canônico: {nome}")
    caminho = caminho_local(raiz, raiz, quote(nome))
    if any(p.casefold() == ".git" for p in caminho.resolve().relative_to(raiz).parts):
        raise ValueError(f"Caminho de registro aponta para metadados Git: {nome}")
    return caminho


@dataclass(frozen=True)
class Limites:
    entradas: int = 10_000
    bytes_entrada: int = 32 * 1024**2
    bytes_total: int = 256 * 1024**2

    def __post_init__(self):
        if min(self.entradas, self.bytes_entrada, self.bytes_total) <= 0:
            raise ValueError("Os limites do EPUB precisam ser positivos.")


class SemDTD(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError("Declarações DOCTYPE e entidades XML são proibidas no EPUB.")


class Pacote:
    """Valida o índice do ZIP antes de permitir acesso às entradas."""

    def __init__(self, zip_file, limites):
        self.zip = zip_file
        self.entradas = {}
        infos = zip_file.infolist()
        if len(infos) > limites.entradas or sum(i.file_size for i in infos) > limites.bytes_total:
            raise ValueError("O EPUB ultrapassa o limite de entradas ou de bytes descompactados.")
        caminhos = {}
        explicitos = set()
        for info in infos:
            nome = info.orig_filename.removesuffix("/") if info.is_dir() else info.orig_filename
            partes = partes_portaveis(nome)
            if any(p in {".", ".."} for p in partes) or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Caminho inseguro no ZIP: {nome}")
            if info.file_size > limites.bytes_entrada:
                raise ValueError(f"Entrada acima do limite de bytes descompactados: {nome}")
            if info.flag_bits & 1:
                raise ValueError(f"Entrada criptografada no EPUB: {nome}")
            for i in range(1, len(partes) + 1):
                prefixo = "/".join(partes[:i])
                chave = chave_portavel(prefixo)
                destino = (prefixo, i < len(partes) or info.is_dir())
                if caminhos.setdefault(chave, destino) != destino:
                    raise ValueError(f"Colisão de caminhos no EPUB: {nome}")
            if nome in explicitos:
                raise ValueError(f"Entrada repetida no pacote EPUB: {nome}")
            explicitos.add(nome)
            if not info.is_dir():
                self.entradas[nome] = info

    @classmethod
    @contextmanager
    def abrir(cls, caminho, limites=Limites()):
        if caminho.stat().st_size > limites.bytes_total + 64 * 1024**2:
            raise ValueError("O tamanho do arquivo EPUB ultrapassa o limite de leitura do pacote.")
        with ZipFile(caminho) as zip_file:
            yield cls(zip_file, limites)

    def read(self, nome):
        return self.zip.read(self.entradas[nome])

    def xml(self, nome):
        return ET.fromstring(self.read(nome), parser=ET.XMLParser(target=SemDTD()))

    def digest(self):
        arquivo = self.zip.fp
        posicao = arquivo.tell()
        try:
            arquivo.seek(0)
            digest = sha256()
            for bloco in iter(lambda: arquivo.read(64 * 1024), b""):
                digest.update(bloco)
            return digest.hexdigest()
        finally:
            arquivo.seek(posicao)


@dataclass(frozen=True)
class Item:
    id: str
    caminho: str
    tipo: str
    propriedades: tuple[str, ...]


@dataclass(frozen=True)
class Pagina:
    item: Item
    linear: bool


@dataclass(frozen=True)
class Edicao:
    metadados: dict
    manifesto: dict[str, Item]
    spine: list[Pagina]
    toc: list[tuple[str, str, str]]
    avisos: list[tuple[str, str]]


def ler_edicao(epub):
    container = epub.xml("META-INF/container.xml")
    rootfile = container.find(".//{*}rootfile")
    if rootfile is None:
        raise ValueError("O container não informa o pacote OPF.")
    arquivo_opf = rootfile.attrib["full-path"]
    partes_portaveis(arquivo_opf)
    opf = epub.xml(arquivo_opf)
    manifesto = {}
    for item in opf.findall("./{*}manifest/{*}item"):
        id_item = item.attrib["id"]
        if id_item in manifesto:
            raise ValueError(f"ID repetido no manifesto: {id_item}")
        manifesto[id_item] = Item(
            id_item, resolver_epub(arquivo_opf, item.attrib["href"]),
            item.get("media-type", ""), tuple(item.get("properties", "").split()),
        )
    spine_opf = opf.find("./{*}spine")
    if spine_opf is None:
        raise ValueError("Pacote OPF sem spine.")
    spine = []
    for itemref in spine_opf.findall("./{*}itemref"):
        linear = itemref.get("linear", "yes")
        if linear not in {"yes", "no"}:
            raise ValueError(f"Valor de linear inválido: {linear}")
        spine.append(Pagina(manifesto[itemref.attrib["idref"]], linear == "yes"))
    if not spine:
        raise ValueError("O spine não contém páginas.")

    def metadado(tag):
        return opf.findtext(f"./{{*}}metadata/{{*}}{tag}") or None

    avisos = []
    toc = []
    ancoras = {}

    def link_toc(arquivo, href, titulo):
        url = urlsplit(href)
        if url.scheme or url.netloc:
            avisos.append(("NAV_EXTERNA", f"Referência externa no sumário: {href}"))
            return
        destino = resolver_epub(arquivo, href)
        fragmento = unquote(url.fragment, errors="strict")
        toc.append((destino, fragmento, titulo.strip()))
        if destino not in epub.entradas:
            avisos.append(("NAV_AUSENTE", f"Destino ausente no sumário: {href}"))
        elif destino not in paginas_spine:
            avisos.append(("NAV_FORA_SPINE", f"Destino fora do spine: {href}"))
        elif fragmento:
            if destino not in ancoras:
                ancoras[destino] = {valor for no in epub.xml(destino).iter()
                                    for valor in (no.get("id"), no.get("name"),
                                                  no.get("{http://www.w3.org/XML/1998/namespace}id")) if valor}
            if fragmento not in ancoras[destino]:
                avisos.append(("NAV_FRAGMENTO", f"Fragmento ausente no sumário: {href}"))

    paginas_spine = {pagina.item.caminho for pagina in spine}
    item_nav = next((item for item in manifesto.values() if "nav" in item.propriedades), None)
    if item_nav:
        raiz = epub.xml(item_nav.caminho)
        nav = next((no for no in raiz.findall(".//{*}nav")
                    if "toc" in no.get(EPUB_TYPE, "").split()), None)
        if nav is not None:
            for link in nav.findall(".//{*}a[@href]"):
                link_toc(item_nav.caminho, link.attrib["href"], "".join(link.itertext()))
        else:
            avisos.append(("NAV_SEM_TOC", "O documento nav não contém um sumário epub:type toc."))
    if not toc and spine_opf.get("toc"):
        arquivo = manifesto[spine_opf.attrib["toc"]].caminho
        for ponto in epub.xml(arquivo).findall(".//{*}navPoint"):
            conteudo = ponto.find("./{*}content")
            if conteudo is not None:
                link_toc(arquivo, conteudo.attrib["src"], ponto.findtext("./{*}navLabel/{*}text", ""))
    metadados = {campo: metadado(tag) for campo, tag in (
        ("titulo", "title"), ("idioma", "language"), ("identificador", "identifier"),
        ("autor", "creator"), ("editora", "publisher"), ("data", "date"),
    )}
    return Edicao(metadados, manifesto, spine, toc, avisos)


BLOCOS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "dt", "dd",
          "td", "th", "caption", "blockquote", "pre", "div", "section", "article",
          "aside", "figure", "figcaption", "header", "footer"}
IGNORADOS = {"script", "style", "rt", "rp", "template"}
MIDIA = {"video", "audio", "object", "iframe", "math", "canvas", "input"}


def extrair_pagina(epub, pagina, *, legado=False):
    raiz = epub.xml(pagina)
    tag_raiz = raiz.tag.rsplit("}", 1)[-1]
    corpo = raiz if tag_raiz == "svg" else raiz.find(".//{*}body")
    if corpo is None:
        raise ValueError(f"Página XHTML sem corpo: {pagina}")
    eventos, avisos = [], []

    def imagem(no):
        referencia = no.get("src") or no.get("href") or no.get(XLINK_HREF)
        if referencia and not (urlsplit(referencia).scheme or urlsplit(referencia).netloc):
            eventos.append(("imagem", resolver_epub(pagina, referencia)))
        else:
            avisos.append(("IMAGEM_REFERENCIA", "Imagem sem referência local verificável."))

    def coletar(no, pendente):
        tag = no.tag.rsplit("}", 1)[-1]
        if tag in IGNORADOS:
            return
        if tag in MIDIA:
            descarregar(pendente)
            avisos.append(("XHTML_NAO_SUPORTADO", f"Elemento requer conferência manual: {tag}."))
            return
        if tag == "svg":
            descarregar(pendente)
            if any(n.tag.rsplit("}", 1)[-1] not in {"svg", "image", "title", "desc", "g"}
                   for n in no.iter()):
                avisos.append(("XHTML_NAO_SUPORTADO", "SVG vetorial requer conferência manual."))
            for n in no.iter():
                if n.tag.rsplit("}", 1)[-1] == "image":
                    imagem(n)
            return
        if tag in {"img", "image", "hr"}:
            descarregar(pendente)
            if tag == "hr":
                eventos.append(("separador", ""))
            else:
                imagem(no)
            return
        if tag in BLOCOS:
            descarregar(pendente)
        if no.text:
            pendente.append(no.text)
        if tag == "br":
            pendente.append(" ")
        for filho in no:
            coletar(filho, pendente)
            if filho.tail:
                pendente.append(filho.tail)
        if tag in BLOCOS:
            descarregar(pendente)

    def descarregar(pendente):
        texto = " ".join("".join(pendente).split())
        pendente.clear()
        if texto:
            eventos.append(("texto", texto))

    if not legado:
        pendente = []
        coletar(corpo, pendente)
        descarregar(pendente)
    else:
        for no in corpo.iter():
            tag = no.tag.rsplit("}", 1)[-1]
            if tag == "p":
                descarregar(list(no.itertext()))
            elif tag in {"img", "image"}:
                imagem(no)
        eventos_v1 = eventos[:]
        textos_v1 = sum(tipo == "texto" for tipo, _ in eventos_v1)
        eventos.clear()
        pendente = []
        coletar(corpo, pendente)
        descarregar(pendente)
        if (sum(tipo == "texto" for tipo, _ in eventos) != textos_v1
                or any(tipo == "separador" for tipo, _ in eventos)):
            avisos.append(("XHTML_LEGADO", "Conteúdo fora da contagem v1. Confira pelo inventário v2."))
        eventos = eventos_v1
    return eventos, list(dict.fromkeys(avisos))


def eventos_item(epub, item, *, legado=False):
    if item.tipo in {"", "application/xhtml+xml", "text/html", "image/svg+xml"}:
        return extrair_pagina(epub, item.caminho, legado=legado)
    if item.tipo.startswith("image/"):
        return [("imagem", item.caminho)], []
    return [], [("SPINE_NAO_SUPORTADO", f"Mídia do spine requer conferência manual: {item.tipo}.")]
