"""Confere, em modo de leitura, um EPUB e sua edição em Markdown."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


LINK = re.compile(
    r'(?P<imagem>!)?\[(?:\\.|[^\]\n])*\]\(\s*'
    r'(?:<(?P<entre_angulos>[^>\n]+)>|(?P<simples>(?:\\.|\([^()\n]*\)|[^()\n])+?))'
    r'(?:\s+"[^"\n]*")?\s*\)'
)
BLOCO = re.compile(r'\S.*?(?=\n[ \t]*\n|\Z)', re.S)
PALAVRA = re.compile(r"[^\W\d_]+", re.UNICODE)
CARACTERE_SUSPEITO = re.compile(r'[\ufffd⁇]|\b(?:inserir tradução|trecho pendente)\b', re.I)
ESTADOS_IMAGEM = {'sem_texto', 'traduzido', 'parcial', 'ilegivel', 'pendente'}
EPUB_TYPE = '{http://www.idpf.org/2007/ops}type'
XLINK_HREF = '{http://www.w3.org/1999/xlink}href'


@dataclass
class Achado:
    nivel: str
    local: str
    mensagem: str


def resolver_epub(pagina, referencia):
    caminho = unquote(urlsplit(referencia).path)
    return posixpath.normpath(posixpath.join(posixpath.dirname(pagina), caminho)) if caminho else pagina


def ler_epub(epub):
    container = ET.fromstring(epub.read('META-INF/container.xml'))
    pacote = container.find('.//{*}rootfile').attrib['full-path']
    opf = ET.fromstring(epub.read(pacote))
    manifesto = {
        item.attrib['id']: resolver_epub(pacote, item.attrib['href'])
        for item in opf.findall('./{*}manifest/{*}item')
    }
    spine = opf.find('./{*}spine')
    paginas = [manifesto[item.attrib['idref']] for item in spine.findall('./{*}itemref')]
    item_nav = next(
        (item for item in opf.findall('./{*}manifest/{*}item')
         if 'nav' in item.get('properties', '').split()),
        None,
    )
    if item_nav is not None:
        nav = manifesto[item_nav.attrib['id']]
        arvore = ET.fromstring(epub.read(nav))
        toc = next((elemento for elemento in arvore.findall('.//{*}nav')
                    if 'toc' in elemento.get(EPUB_TYPE, '').split()), None)
        if toc is not None:
            destinos = [resolver_epub(nav, link.attrib['href']) for link in toc.findall('.//{*}a[@href]')]
            return paginas, destinos
    if spine.get('toc'):
        nav = manifesto[spine.attrib['toc']]
        toc = ET.fromstring(epub.read(nav))
        destinos = [resolver_epub(nav, item.attrib['src']) for item in toc.findall('.//{*}navPoint/{*}content')]
        return paginas, destinos
    return paginas, []


def extrair_pagina(epub, pagina):
    raiz = ET.fromstring(epub.read(pagina))
    corpo = raiz.find('.//{*}body')
    if corpo is None:
        raise ValueError(f'Página XHTML sem corpo: {pagina}')
    elementos = []
    for no in corpo.iter():
        tag = no.tag.rsplit('}', 1)[-1]
        if tag == 'p':
            texto = ' '.join(''.join(no.itertext()).split())
            if texto:
                elementos.append(('texto', texto))
        elif tag in {'img', 'image'}:
            referencia = no.get('src') or no.get('href') or no.get(XLINK_HREF)
            if referencia and not urlsplit(referencia).scheme and not referencia.startswith('//'):
                elementos.append(('imagem', resolver_epub(pagina, referencia)))
    return elementos


def caminho_local(volume, pasta, destino):
    url = urlsplit(destino)
    if url.scheme or url.netloc or not url.path:
        return None
    caminho = (pasta / unquote(url.path)).resolve()
    if not caminho.is_relative_to(volume):
        raise ValueError(f'O destino sai da pasta do volume: {destino}')
    return caminho


def links(texto):
    for link in LINK.finditer(texto):
        destino = link['entre_angulos'] or link['simples']
        yield link, re.sub(r'\\([()\\])', r'\1', destino)


def contar_palavras(texto):
    sem_links = LINK.sub('', texto)
    return len(PALAVRA.findall(sem_links or texto))


def blocos_markdown(texto):
    return [(texto.count('\n', 0, bloco.start()) + 1, bloco[0]) for bloco in BLOCO.finditer(texto)]


def verificar(epub, inventario, volume):
    achados = []
    volume = volume.resolve()

    def achado(nivel, local, mensagem):
        achados.append(Achado(nivel, local, mensagem))

    def arquivo(nome):
        caminho = caminho_local(volume, volume, nome)
        if caminho is None or not caminho.is_file():
            achado('ERRO', nome, 'Arquivo ausente.')
            return None
        return caminho

    def ler_markdown(caminho):
        local = caminho.relative_to(volume).as_posix()
        texto = caminho.read_text(encoding='utf-8-sig')
        for n, linha in enumerate(texto.splitlines(), 1):
            if CARACTERE_SUSPEITO.search(linha):
                achado('AVISO', f'{local}:{n}', 'Possível caractere corrompido ou trecho pendente.')
        destinos = []
        for link, destino in links(texto):
            linha = texto.count('\n', 0, link.start()) + 1
            try:
                alvo = caminho_local(volume, caminho.parent, destino)
            except ValueError as erro:
                achado('ERRO', f'{local}:{linha}', str(erro))
                continue
            if alvo is not None:
                if not alvo.exists() or (link['imagem'] and not alvo.is_file()):
                    achado('ERRO', f'{local}:{linha}', f'Destino ausente: {destino}')
                destinos.append((bool(link['imagem']), alvo))
        return texto, destinos

    if inventario.get('schema') != 1 or not inventario['unidades']:
        raise ValueError('Informe schema 1 e ao menos uma unidade.')
    unidades = inventario['unidades']
    nomes = [unidade['markdown'] for unidade in unidades]
    if len(nomes) != len(set(nomes)):
        raise ValueError('Há arquivos Markdown repetidos no inventário.')
    nome_sumario = inventario['sumario']
    sumario = arquivo(nome_sumario)
    if sumario:
        _, destinos = ler_markdown(sumario)
        ordem_md = [alvo.relative_to(volume).as_posix() for imagem, alvo in destinos
                    if not imagem and alvo.suffix.lower() == '.md']
        if ordem_md != nomes:
            achado('ERRO', nome_sumario, 'Os links para unidades diferem do inventário em cobertura ou ordem.')

    ordem_epub, toc_epub = ler_epub(epub)
    navegacao = inventario.get('paginas_de_navegacao', [])
    ignoradas = set(navegacao)
    if len(ignoradas) != len(navegacao) or not ignoradas.issubset(ordem_epub):
        achado('ERRO', 'EPUB', 'A lista de páginas de navegação tem duplicatas ou páginas fora do spine.')
    origem_por_pagina = {}
    paginas_inventariadas = []
    for unidade in unidades:
        paginas = unidade['paginas_epub']
        if not paginas:
            raise ValueError(f'Unidade sem páginas EPUB: {unidade["markdown"]}')
        paginas_inventariadas.extend(paginas)
        for pagina in paginas:
            origem_por_pagina[pagina] = unidade['markdown']
    esperado = [pagina for pagina in ordem_epub if pagina not in ignoradas]
    if paginas_inventariadas != esperado:
        ausentes = [pagina for pagina in esperado if pagina not in origem_por_pagina]
        extras = [pagina for pagina in paginas_inventariadas if pagina not in esperado]
        achado('ERRO', 'EPUB', f'As páginas inventariadas diferem do spine em cobertura ou ordem. '
               f'Ausentes: {ausentes or "nenhuma"}. Extras: {extras or "nenhuma"}.')
    toc_unidades = list(dict.fromkeys(origem_por_pagina[pagina] for pagina in toc_epub if pagina in origem_por_pagina))
    unidades_no_toc = set(toc_unidades)
    if toc_unidades != [nome for nome in nomes if nome in unidades_no_toc]:
        achado('ERRO', 'EPUB', 'A ordem das unidades no sumário do EPUB difere da ordem de entrega.')

    imagens_registradas = 0
    arquivos_epub = set(epub.namelist())
    for unidade in unidades:
        nome = unidade['markdown']
        caminho = arquivo(nome)
        if caminho is None:
            continue
        elementos_epub = []
        for pagina in unidade['paginas_epub']:
            if pagina in esperado:
                elementos_epub.extend(extrair_pagina(epub, pagina))
        origem_imagens = [valor for tipo, valor in elementos_epub if tipo == 'imagem']
        registros = unidade.get('imagens', [])
        if origem_imagens != [imagem['epub'] for imagem in registros]:
            achado('ERRO', nome, 'O inventário de imagens difere das referências do EPUB em cobertura ou ordem.')
        for origem in origem_imagens:
            if origem not in arquivos_epub:
                achado('ERRO', nome, f'Imagem referenciada no EPUB está ausente do pacote: {origem}')

        texto, destinos = ler_markdown(caminho)
        md_imagens = [alvo.relative_to(volume).as_posix() for imagem, alvo in destinos if imagem]
        if md_imagens != [imagem['markdown'] for imagem in registros]:
            achado('ERRO', nome, 'As imagens do Markdown diferem do inventário em cobertura ou ordem.')
        imagens_registradas += len(registros)

        cabecalho = unidade.get('blocos_iniciais', 0)
        if not isinstance(cabecalho, int) or cabecalho < 0:
            raise ValueError(f'Número inválido de blocos iniciais em {nome}.')
        blocos = blocos_markdown(texto)
        if cabecalho > len(blocos):
            achado('ERRO', nome, 'O arquivo contém menos blocos do que o cabeçalho cadastrado.')
        corpo = blocos[cabecalho:]
        imagem_por_bloco = [
            i for i, (_, bloco) in enumerate(corpo)
            if any(link['imagem'] for link, _ in links(bloco))
        ]
        indices_imagem = set(imagem_por_bloco)
        if len(imagem_por_bloco) != len(md_imagens):
            achado('ERRO', nome, 'Use um bloco Markdown separado para cada imagem.')
        legendas = set()
        for indice, imagem in zip(imagem_por_bloco, registros):
            estado = imagem['estado']
            blocos_legenda = imagem.get('blocos_traducao', 0)
            local = f'{nome}:{corpo[indice][0]}'
            if estado not in ESTADOS_IMAGEM or not isinstance(blocos_legenda, int) or blocos_legenda < 0:
                raise ValueError(f'Estado ou total de blocos inválido na inspeção de {imagem["markdown"]}.')
            if (blocos_legenda > 0) != (estado in {'traduzido', 'parcial'}):
                achado('ERRO', local, 'O estado da imagem é incompatível com o número de blocos de tradução.')
            indices = range(indice + 1, indice + 1 + blocos_legenda)
            if any(i >= len(corpo) or i in indices_imagem or i in legendas for i in indices):
                achado('ERRO', local, 'A tradução da imagem deve estar em blocos consecutivos logo abaixo dela.')
            else:
                legendas.update(indices)
            if estado in {'parcial', 'ilegivel', 'pendente'}:
                nota = imagem.get('nota', '').strip()
                if estado != 'pendente' and not nota:
                    achado('ERRO', local, 'Descreva o trecho ilegível ou que ficou sem tradução.')
                achado('AVISO', local, f'Inspeção de imagem {estado}: {nota or imagem["markdown"]}')
        corpo_md = [
            (linha, bloco, 'imagem' if i in indices_imagem else 'texto')
            for i, (linha, bloco) in enumerate(corpo) if i not in legendas
        ]
        origem_texto = [texto for tipo, texto in elementos_epub if tipo == 'texto']
        traducao_texto = [(linha, bloco) for linha, bloco, tipo in corpo_md if tipo == 'texto']
        divisoes = unidade.get('divisoes_de_paragrafo', {})
        indices_validos = {str(i) for i in range(1, len(origem_texto) + 1)}
        if divisoes.keys() - indices_validos or any(type(total) is not int or total < 2 for total in divisoes.values()):
            raise ValueError(f'Divisão de parágrafo inválida em {nome}.')
        totais = [divisoes.get(str(i), 1) for i in range(1, len(origem_texto) + 1)]
        esperado_texto = sum(totais)
        if esperado_texto != len(traducao_texto):
            achado('AVISO', nome, f'Total de blocos diferente: EPUB {len(origem_texto)}, '
                   f'Markdown {len(traducao_texto)}, esperado {esperado_texto}. '
                   'Confira divisões, omissões e acréscimos.')
            continue
        ordem = []
        tamanhos = iter(totais)
        for tipo, _ in elementos_epub:
            ordem.extend([tipo] * (next(tamanhos) if tipo == 'texto' else 1))
        if ordem != [tipo for _, _, tipo in corpo_md]:
            achado('AVISO', nome, 'Uma imagem aparece entre blocos diferentes dos indicados pelo EPUB.')
        inicio = 0
        for fonte, total in zip(origem_texto, totais):
            blocos = traducao_texto[inicio:inicio + total]
            inicio += total
            palavras_fonte = contar_palavras(fonte)
            palavras_traducao = sum(contar_palavras(bloco) for _, bloco in blocos)
            if palavras_fonte >= 20 and palavras_traducao < palavras_fonte * 0.6:
                achado('AVISO', f'{nome}:{blocos[0][0]}', 'Bloco muito curto em relação à fonte. Confira possíveis omissões.')

    return achados, len(unidades), imagens_registradas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('epub', type=Path)
    parser.add_argument('inventario', type=Path, help='JSON de inventário na pasta do volume')
    parser.add_argument('--estrito', action='store_true', help='retorna 1 quando houver erros ou avisos')
    args = parser.parse_args(argv)
    try:
        inventario = json.loads(args.inventario.read_text(encoding='utf-8-sig'))
        with ZipFile(args.epub) as epub:
            achados, unidades, imagens = verificar(epub, inventario, args.inventario.parent)
    except (OSError, BadZipFile, ET.ParseError, KeyError, TypeError, ValueError, AttributeError) as erro:
        parser.exit(2, f'ERRO ao ler edição ou inventário: {erro}\n')
    for item in achados:
        print(f'{item.nivel} {item.local} · {item.mensagem}')
    erros = sum(item.nivel == 'ERRO' for item in achados)
    print(f'{unidades} unidades, {imagens} imagens, {erros} erros, {len(achados) - erros} avisos.')
    return int(bool(achados) if args.estrito else erros > 0)


if __name__ == '__main__':
    raise SystemExit(main())
