"""Edições artificiais geradas exclusivamente em diretórios temporários."""

import json
from zipfile import ZIP_DEFLATED, ZipFile


CAPITULO = "Capítulo 01.md"
SUMARIO = "Sumário.md"
PAGINA = "OEBPS/capítulo.xhtml"
TEXTO = "Um exemplo sintético para conferir a estrutura."


def xhtml(corpo):
    return f'<html xmlns="http://www.w3.org/1999/xhtml"><body>{corpo}</body></html>'


def entradas_epub():
    return {
        "META-INF/container.xml": '<container><rootfiles><rootfile full-path="OEBPS/obra.opf"/></rootfiles></container>',
        "OEBPS/obra.opf": (
            '<package><metadata><language>pt</language></metadata><manifest>'
            '<item id="cap" href="cap%C3%ADtulo.xhtml" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="cap"/></spine></package>'
        ),
        PAGINA: xhtml(f"<p>{TEXTO}</p>"),
    }


def inventario():
    return {
        "schema": 1,
        "sumario": SUMARIO,
        "unidades": [{"markdown": CAPITULO, "paginas_epub": [PAGINA]}],
    }


def gravar_epub(caminho, entradas):
    with ZipFile(caminho, "w", compression=ZIP_DEFLATED) as epub:
        for nome, conteudo in entradas.items():
            epub.writestr(nome, conteudo)


def preparar(pasta, *, entradas=None, registro=None, texto=TEXTO, newline="\n"):
    epub = pasta / "Edição sintética.epub"
    volume = pasta / "Volume 01"
    volume.mkdir(exist_ok=True)
    arquivo = volume / "inventário.json"
    gravar_epub(epub, entradas_epub() if entradas is None else entradas)
    dados = inventario() if registro is None else registro
    arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    (volume / SUMARIO).write_text(f"[Capítulo](<{CAPITULO}>)\n", encoding="utf-8", newline=newline)
    (volume / CAPITULO).write_text(texto + "\n", encoding="utf-8", newline=newline)
    return epub, arquivo
