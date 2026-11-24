"""Leitura do subconjunto editorial de Markdown, sem renderização de HTML."""

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re
import string


ESCAPE = re.compile(r"\\([" + re.escape(string.punctuation) + "])")
CODIGO = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)", re.S)
COMENTARIO = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
CERCA = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)")
ROTULO = r"(?:\\.|[^\[\]\\\n])*"
REFERENCIA = re.compile(r"^ {0,3}\[(" + ROTULO + r")\]:[ \t]*(.+)$")
TITULO = r"""(?:\s+(?:"[^"]*"|'[^']*'|\([^()]*\)))?\s*"""
FIM_INLINE = re.compile(TITULO + r"\)")
ROTULO_REF = re.compile(r"\[(" + ROTULO + r")\]")
SEPARADOR = re.compile(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})")
BLOCO = re.compile(r"\S.*?(?=\n[ \t]*\n|\Z)", re.S)


def limpar_destino(destino):
    return unescape(ESCAPE.sub(r"\1", destino))


def _mascara(trecho):
    return "".join("\n" if c == "\n" else " " for c in trecho)


def _codigo_blocos(texto):
    cerca = ""
    for linha in texto.splitlines(keepends=True):
        inicio = CERCA.match(linha)
        if cerca:
            if inicio and inicio[1][0] == cerca[0] and len(inicio[1]) >= len(cerca) and not inicio[2].strip():
                cerca = ""
            yield _mascara(linha)
        elif inicio:
            cerca = inicio[1]
            yield _mascara(linha)
        elif linha.startswith(("    ", "\t")):
            yield _mascara(linha)
        else:
            yield linha


def visivel(texto):
    sem_cercas = "".join(_codigo_blocos(texto))
    return re.sub(f"{COMENTARIO.pattern}|{CODIGO.pattern}", lambda m: _mascara(m[0]), sem_cercas, flags=re.S)


def _destino(texto, inicio):
    while inicio < len(texto) and texto[inicio] in " \t":
        inicio += 1
    if texto[inicio:inicio + 1] == "<":
        fim = texto.find(">", inicio + 1)
        if fim > inicio and "\n" not in texto[inicio:fim]:
            return limpar_destino(texto[inicio + 1:fim]), fim + 1
        return None
    i = inicio
    profundidade = 0
    while i < len(texto):
        char = texto[i]
        if char == "\\" and i + 1 < len(texto):
            i += 2
            continue
        if char.isspace() or (char == ")" and profundidade == 0):
            break
        profundidade += (char == "(") - (char == ")")
        i += 1
    if profundidade == 0:
        return limpar_destino(texto[inicio:i]), i
    return None


def _rotulo(texto):
    return " ".join(limpar_destino(texto).split()).casefold()


def _escapado(texto, i):
    inicio = i
    while i and texto[i - 1] == "\\":
        i -= 1
    return (inicio - i) % 2


@dataclass(frozen=True)
class Link:
    destino: str
    imagem: bool
    inicio: int
    fim: int
    linha: int


class HTML(HTMLParser):
    def __init__(self, texto):
        super().__init__()
        self.links = []
        self.ids = set()
        self.linhas = [0, *(m.end() for m in re.finditer("\n", texto))]
        self.feed(texto)
        self.close()

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        ancora = atributos.get("id") or (atributos.get("name") if tag == "a" else None)
        if ancora:
            self.ids.add(ancora)
        if tag in {"a", "img"}:
            destino = atributos.get("src" if tag == "img" else "href")
            if destino:
                linha, coluna = self.getpos()
                inicio = self.linhas[linha - 1] + coluna
                self.links.append(Link(destino, tag == "img", inicio, inicio + len(self.get_starttag_text()), linha))


def analisar_links(texto, *, html=False):
    seguro = visivel(texto)
    rotulos = {}
    linhas = seguro.splitlines(keepends=True)
    for i, linha in enumerate(linhas):
        referencia = REFERENCIA.match(linha)
        if referencia:
            candidato = _destino(referencia[2], 0)
            if candidato and candidato[0] and re.fullmatch(TITULO, referencia[2][candidato[1]:]):
                rotulos.setdefault(_rotulo(referencia[1]), candidato[0])
                linhas[i] = _mascara(linha)
    seguro = "".join(linhas)
    encontrados = []
    pilha = []
    i = 0
    linha = 1
    while i < len(seguro):
        char = seguro[i]
        if char == "\\" and i + 1 < len(seguro) and seguro[i + 1] in string.punctuation:
            i += 2
            continue
        if char == "[":
            imagem = i > 0 and seguro[i - 1] == "!" and not _escapado(seguro, i - 1)
            pilha.append((i, linha, imagem))
        elif char == "]" and pilha:
            inicio, linha_link, imagem = pilha.pop()
            fim = i + 1
            destino = None
            if seguro[fim:fim + 1] == "(":
                candidato = _destino(seguro, fim + 1)
                if candidato:
                    fechamento = FIM_INLINE.match(seguro, candidato[1])
                    if fechamento:
                        destino, fim = candidato[0], fechamento.end()
            if destino is None:
                rotulo = seguro[inicio + 1:i]
                ref = ROTULO_REF.match(seguro, fim)
                if ref:
                    rotulo = ref[1] or rotulo
                if _rotulo(rotulo) in rotulos:
                    destino = rotulos[_rotulo(rotulo)]
                    if ref:
                        fim = ref.end()
            if destino is not None:
                encontrados.append(Link(destino, imagem, inicio - imagem, fim, linha_link))
                linha += seguro.count("\n", i, fim)
                i = fim
                continue
        linha += char == "\n"
        i += 1
    if html:
        encontrados.extend(HTML(seguro).links)
    return sorted(encontrados, key=lambda link: (link.inicio, link.fim))


def ancoras(texto, *, html=False):
    seguro = visivel(texto)
    encontrados = HTML(seguro).ids if html else set()
    contagens = {}
    for titulo in re.finditer(r"^ {0,3}#{1,6}[ \t]+(.+)$|^([^\n]+)\n {0,3}(?:=+|-+)[ \t]*$", seguro, re.M):
        nome = limpar_destino((titulo[1] or titulo[2]).strip().rstrip("#").strip()).lower()
        slug = "".join(c for c in nome if c.isalnum() or c in " -_").replace(" ", "-")
        numero = contagens.get(slug, 0)
        ancora = f"{slug}-{numero}" if numero else slug
        while ancora in encontrados:
            numero += 1
            ancora = f"{slug}-{numero}"
        contagens[slug] = numero + 1
        encontrados.add(ancora)
    return encontrados


def blocos_markdown(texto, *, legado):
    limpo = visivel(texto)
    linhas = (texto if legado else limpo).splitlines(keepends=True)
    # Definições de referência são metadados, mesmo quando o documento usa v1.
    texto = "".join(_mascara(original) if REFERENCIA.match(segura) else original
                    for original, segura in zip(linhas, limpo.splitlines(keepends=True)))
    anterior, linha = 0, 1
    resultado = []
    for bloco in BLOCO.finditer(texto):
        linha += texto.count("\n", anterior, bloco.start())
        anterior = bloco.start()
        resultado.append((linha, bloco[0]))
    return resultado
