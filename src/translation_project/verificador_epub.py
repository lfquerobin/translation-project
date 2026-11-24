"""Confere, em modo de leitura, um EPUB e sua edição em Markdown."""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
from zipfile import BadZipFile
from zlib import error as ErroCompressao

from .arquivos import ler_json, sha256_arquivo
from .epub import Limites, Pacote, caminho_local, caminho_registro, chave_portavel, eventos_item, ler_edicao
from .markdown import SEPARADOR, analisar_links, ancoras, blocos_markdown


PALAVRA = re.compile(r"[^\W\d_]+", re.UNICODE)
CARACTERE_SUSPEITO = re.compile(r'[\ufffd⁇]|\b(?:inserir tradução|trecho pendente)\b', re.I)
ESTADOS_IMAGEM = {'sem_texto', 'traduzido', 'parcial', 'ilegivel', 'pendente'}
IDIOMAS_COM_ESPACOS = set("pt en es fr it de nl sv no da fi pl cs ro hu tr ru uk el ar he id vi".split())


@dataclass(frozen=True)
class Achado:
    codigo: str
    gravidade: str
    caminho: str
    mensagem: str
    unidade: str | None = None
    localizacao: int | None = None


def contar_palavras(texto):
    return len(PALAVRA.findall(texto))


def palavras_markdown(texto):
    links = analisar_links(texto)
    partes, cursor = [], 0
    for link in links:
        if link.inicio >= cursor:
            partes.append(texto[cursor:link.inicio])
            cursor = link.fim
        else:
            cursor = max(cursor, link.fim)
    partes.append(texto[cursor:])
    return contar_palavras(" ".join(partes).strip() or texto)


def verificar_imagem(epub, registro, destino, hashes, reportar):
    origem = registro["epub"]
    if origem not in epub.entradas or not destino.is_file():
        return
    if origem not in hashes:
        hashes[origem] = sha256(epub.read(origem)).hexdigest()
    hash_origem = hashes[origem]
    hash_destino = sha256_arquivo(destino)
    conversao = registro.get("conversao")
    if conversao is not None:
        if not isinstance(conversao, dict) or any(
            not isinstance(conversao.get(campo), str) or not conversao[campo].strip()
            for campo in ("metodo", "justificativa", "sha256_origem", "sha256_destino")
        ):
            raise ValueError("A conversão de imagem exige método, justificativa e os dois SHA-256.")
        if (hash_origem, hash_destino) != (conversao["sha256_origem"], conversao["sha256_destino"]):
            reportar("IMAGEM_CONVERSAO", "Hashes da conversão diferem do registro.")
    elif hash_origem != hash_destino:
        reportar("IMAGEM_HASH", "Imagem difere do EPUB. Registre a conversão se ela for intencional.")


def conferir_alinhamento(unidade, origem, traducao, reportar, metrica):
    ids_origem = [f"e{i}" for i, (tipo, _) in enumerate(origem, 1) if tipo == "texto"]
    ids_destino = [f"m{i}" for i, (_, _, tipo) in enumerate(traducao, 1) if tipo == "texto"]
    origens, destinos = [], []
    posicao_origem, posicao_destino = {}, {}
    pares = unidade.get("alinhamento")
    if not isinstance(pares, list):
        reportar("ALINHAMENTO_AUSENTE", "Informe o alinhamento explícito dos segmentos.")
        return
    for grupo, par in enumerate(pares, 1):
        e, m = par["origem"], par["destino"]
        if any(not isinstance(itens, list) or not itens or not all(isinstance(i, str) for i in itens)
               for itens in (e, m)):
            raise ValueError("Cada grupo deve indicar segmentos de origem e destino.")
        if (len(e) != 1 or len(m) != 1) and not par.get("justificativa", "").strip():
            reportar("ALINHAMENTO_JUSTIFICATIVA", f"Informe a justificativa do grupo {grupo}.")
        origens.extend(e)
        destinos.extend(m)
        posicao_origem.update((item, grupo) for item in e)
        posicao_destino.update((item, grupo) for item in m)
    if origens != ids_origem or destinos != ids_destino:
        reportar("ALINHAMENTO_COBERTURA", f"Segmentos ausentes, repetidos ou fora de ordem. "
                 f"Origem esperada: {ids_origem}. Destino esperado: {ids_destino}.")
        return

    def marcos(tipos, prefixo, posicoes):
        marcas, grupo = [], None
        for i, tipo in enumerate(tipos, 1):
            if tipo != "texto":
                marcas.append(tipo)
            elif grupo != posicoes[f"{prefixo}{i}"] or not marcas or marcas[-1] != grupo:
                grupo = posicoes[f"{prefixo}{i}"]
                marcas.append(grupo)
        return marcas

    if (marcos([tipo for tipo, _ in origem], "e", posicao_origem)
            != marcos([tipo for _, _, tipo in traducao], "m", posicao_destino)):
        reportar("ALINHAMENTO_POSICAO", "Imagens ou separadores aparecem em posições divergentes.")
    proporcao, minimo, comparar_palavras = metrica
    if comparar_palavras:
        for par in pares:
            palavras_fonte = sum(contar_palavras(origem[int(i[1:]) - 1][1]) for i in par["origem"])
            blocos_md = [traducao[int(i[1:]) - 1] for i in par["destino"]]
            palavras_destino = sum(palavras_markdown(bloco) for _, bloco, _ in blocos_md)
            if palavras_fonte >= minimo and palavras_destino < palavras_fonte * proporcao:
                reportar("PALAVRAS_PROPORCAO", "Grupo muito curto em relação à fonte. Confira possíveis omissões.",
                         "aviso", blocos_md[0][0])


def politica_metrica(inventario, idioma, legado):
    config = inventario.get("metrica_palavras", {})
    idioma = config.get("idioma_fonte", idioma)
    base = idioma.lower().replace("_", "-").split("-")[0] if idioma else ""
    bases_destino = inventario.get("idioma_destino", "pt").lower().split("-")
    habilitada = config.get("habilitada", True)
    proporcao = config.get("proporcao_minima", 0.6)
    minimo = config.get("minimo_fonte", 20)
    if (type(habilitada) is not bool or type(proporcao) not in (int, float)
            or not 0 <= proporcao <= 1 or type(minimo) is not int or minimo < 1):
        raise ValueError("Configuração inválida da métrica de palavras.")
    compativel = bases_destino[0] in IDIOMAS_COM_ESPACOS and (base in IDIOMAS_COM_ESPACOS or (legado and not base))
    return proporcao, minimo, habilitada and compativel


def verificar(epub, inventario, volume):
    achados = []
    volume = volume.resolve()

    def achado(codigo, nivel, local, mensagem, *, unidade=None, linha=None):
        achados.append(Achado(codigo, nivel, local, mensagem, unidade, linha))

    def arquivo(nome, unidade=None):
        caminho = caminho_registro(volume, nome)
        if not caminho.is_file():
            achado("ARQUIVO_AUSENTE", "erro", nome, "Arquivo ausente.", unidade=unidade)
            return None
        return caminho

    permitir_html = inventario.get("permitir_html", False)
    ancoras_por_arquivo = {}

    def ler_markdown(caminho, unidade=None):
        local = caminho.relative_to(volume).as_posix()
        texto = caminho.read_text(encoding='utf-8-sig')

        def localizar(codigo, nivel, linha, mensagem):
            achado(codigo, nivel, local, mensagem, unidade=unidade, linha=linha)

        for n, linha in enumerate(texto.splitlines(), 1):
            if CARACTERE_SUSPEITO.search(linha):
                localizar("TEXTO_SUSPEITO", "aviso", n, "Possível caractere corrompido ou trecho pendente.")
        destinos = []
        for link in analisar_links(texto, html=permitir_html):
            destino = link.destino
            try:
                alvo = caminho_local(volume, caminho.parent, destino)
                url = urlsplit(destino)
            except ValueError as erro:
                localizar("LINK_CAMINHO", "erro", link.linha, str(erro))
                continue
            if alvo is not None:
                if not alvo.exists() or (link.imagem and not alvo.is_file()):
                    localizar("LINK_AUSENTE", "erro", link.linha, f"Destino ausente: {destino}")
                destinos.append((link, alvo))
            elif not url.scheme and not url.netloc:
                alvo = caminho
            elif link.imagem:
                localizar("IMAGEM_MD_EXTERNA", "aviso", link.linha, f"Imagem externa não conferida: {destino}")
            if url.fragment and alvo is not None and alvo.suffix.lower() == ".md" and alvo.is_file():
                if alvo not in ancoras_por_arquivo:
                    conteudo = texto if alvo == caminho else alvo.read_text(encoding="utf-8-sig")
                    ancoras_por_arquivo[alvo] = ancoras(conteudo, html=permitir_html)
                if unquote(url.fragment) not in ancoras_por_arquivo[alvo]:
                    localizar("LINK_FRAGMENTO", "aviso", link.linha, f"Âncora Markdown não reconhecida: {destino}")
        return texto, destinos

    versao = inventario.get("schema")
    legado = versao == 1
    if type(versao) is not int or versao not in (1, 2) or not inventario["unidades"]:
        raise ValueError("Informe schema 1 ou 2 e ao menos uma unidade.")
    unidades = inventario['unidades']
    nomes = [unidade['markdown'] for unidade in unidades]
    nome_sumario = inventario['sumario']
    if len(nomes) + 1 != len({chave_portavel(nome) for nome in [*nomes, nome_sumario]}):
        raise ValueError("Há caminhos Markdown repetidos ou em colisão no inventário.")
    ids = [unidade.get("id", unidade["markdown"]) for unidade in unidades]
    if len(ids) != len(set(ids)):
        raise ValueError("Há IDs de unidades repetidos no inventário.")
    sumario = arquivo(nome_sumario)
    if sumario:
        _, destinos = ler_markdown(sumario)
        ordem_md = [alvo.relative_to(volume).as_posix() for link, alvo in destinos
                    if not link.imagem and alvo.suffix.lower() == '.md']
        if ordem_md != nomes:
            achado("SUMARIO_COBERTURA", "erro", nome_sumario,
                   "Os links para unidades diferem do inventário em cobertura ou ordem.")

    edicao = ler_edicao(epub)
    if "sha256_epub" in inventario and inventario["sha256_epub"] != epub.digest():
        achado("EPUB_EDICAO_DIVERGENTE", "erro", "EPUB", "O hash da edição difere do inventário.")
    ordem_epub = [pagina.item.caminho for pagina in edicao.spine]
    for codigo, mensagem in edicao.avisos:
        achado(codigo, "aviso", "EPUB", mensagem)
    metrica = politica_metrica(inventario, edicao.metadados["idioma"], legado)
    proporcao, minimo, comparar_palavras = metrica
    navegacao = inventario.get('paginas_de_navegacao', [])
    ignoradas = set(navegacao)
    if len(ignoradas) != len(navegacao) or not ignoradas.issubset(ordem_epub):
        achado("SPINE_NAV_INVALIDA", "erro", "EPUB", "A navegação tem duplicatas ou páginas fora do spine.")
    origem_por_pagina = defaultdict(list)
    paginas_inventariadas = []
    for unidade in unidades:
        paginas = unidade['paginas_epub']
        if not paginas:
            raise ValueError(f'Unidade sem páginas EPUB: {unidade["markdown"]}')
        paginas_inventariadas.extend(paginas)
        for pagina in paginas:
            origem_por_pagina[pagina].append(unidade["markdown"])
    esperado = [pagina for pagina in ordem_epub if pagina not in ignoradas]
    if paginas_inventariadas != esperado:
        ausentes = list((Counter(esperado) - Counter(paginas_inventariadas)).elements())
        extras = list((Counter(paginas_inventariadas) - Counter(esperado)).elements())
        achado("SPINE_COBERTURA", "erro", "EPUB", f'As páginas inventariadas diferem do spine em cobertura ou ordem. '
               f'Ausentes: {ausentes or "nenhuma"}. Extras: {extras or "nenhuma"}.')
    toc_unidades = []
    for pagina, _, _ in edicao.toc:
        candidatos = set(origem_por_pagina[pagina])
        if len(candidatos) == 1:
            toc_unidades.append(next(iter(candidatos)))
        elif candidatos:
            achado("NAV_OCORRENCIA_AMBIGUA", "aviso", pagina, "O sumário aponta para página de múltiplas unidades.")
    toc_unidades = list(dict.fromkeys(toc_unidades))
    unidades_no_toc = set(toc_unidades)
    if toc_unidades != [nome for nome in nomes if nome in unidades_no_toc]:
        achado("NAV_ORDEM", "erro", "EPUB", "A ordem das unidades no sumário do EPUB difere da ordem de entrega.")

    imagens_registradas = 0
    paginas_esperadas = set(esperado)
    cache_paginas, hashes = {}, {}
    itens_spine = {pagina.item.caminho: pagina.item for pagina in edicao.spine}
    for unidade, id_unidade in zip(unidades, ids):
        nome = unidade['markdown']

        def reportar(codigo, mensagem, nivel="erro", linha=None, local=nome, id_unidade=id_unidade):
            achado(codigo, nivel, local, mensagem, unidade=id_unidade, linha=linha)

        caminho = arquivo(nome, id_unidade)
        if caminho is None:
            continue
        elementos_epub = []
        for pagina in unidade['paginas_epub']:
            if pagina not in paginas_esperadas:
                continue
            if pagina not in epub.entradas:
                reportar("XHTML_AUSENTE", "Página do spine ausente do pacote.", local=pagina)
                continue
            if pagina not in cache_paginas:
                cache_paginas[pagina] = eventos_item(epub, itens_spine[pagina], legado=legado)
            eventos, avisos = cache_paginas[pagina]
            elementos_epub.extend(eventos)
            for codigo, mensagem in avisos:
                reportar(codigo, mensagem, "aviso", local=pagina)
        origem_imagens = [valor for tipo, valor in elementos_epub if tipo == 'imagem']
        registros = unidade.get('imagens', [])
        if origem_imagens != [imagem['epub'] for imagem in registros]:
            reportar("IMAGEM_EPUB_COBERTURA", "O inventário de imagens difere das referências do EPUB em cobertura ou ordem.")
        for origem in origem_imagens:
            if origem not in epub.entradas:
                reportar("IMAGEM_EPUB_AUSENTE", f"Imagem referenciada no EPUB está ausente do pacote: {origem}")

        texto, destinos = ler_markdown(caminho, id_unidade)
        links_imagens = [(link, alvo) for link, alvo in destinos if link.imagem]
        md_imagens = [alvo.relative_to(volume).as_posix() for _, alvo in links_imagens]
        if md_imagens != [imagem['markdown'] for imagem in registros]:
            reportar("IMAGEM_MD_COBERTURA", "As imagens do Markdown diferem do inventário em cobertura ou ordem.")
        imagens_registradas += len(registros)

        cabecalho = unidade.get('blocos_iniciais', 0)
        if type(cabecalho) is not int or cabecalho < 0:
            raise ValueError(f'Número inválido de blocos iniciais em {nome}.')
        blocos = blocos_markdown(texto, legado=legado)
        if cabecalho > len(blocos):
            reportar("CABECALHO_BLOCOS", "O arquivo contém menos blocos do que o cabeçalho cadastrado.")
        corpo = blocos[cabecalho:]
        linhas_corpo = [linha for linha, _ in corpo]
        imagem_por_bloco = [bisect_right(linhas_corpo, link.linha) - 1 for link, _ in links_imagens]
        indices_imagem = set(imagem_por_bloco) - {-1}
        if len(indices_imagem) != len(md_imagens):
            reportar("IMAGEM_BLOCO", "Use um bloco Markdown separado para cada imagem.")
        legendas = set()
        for n, imagem in enumerate(registros):
            estado = imagem['estado']
            blocos_legenda = imagem.get('blocos_traducao', 0)
            if estado not in ESTADOS_IMAGEM or type(blocos_legenda) is not int or blocos_legenda < 0:
                raise ValueError(f'Estado ou total de blocos inválido na inspeção de {imagem["markdown"]}.')
            destino = caminho_registro(volume, imagem["markdown"])
            verificar_imagem(epub, imagem, destino, hashes, reportar)
            indice = imagem_por_bloco[n] if n < len(imagem_por_bloco) else -1
            linha = corpo[indice][0] if indice >= 0 else None
            if (blocos_legenda > 0) != (estado in {'traduzido', 'parcial'}):
                reportar("IMAGEM_ESTADO", "O estado da imagem é incompatível com o número de blocos de tradução.", linha=linha)
            if indice >= 0:
                indices = range(indice + 1, indice + 1 + blocos_legenda)
                if any(i >= len(corpo) or i in indices_imagem or i in legendas for i in indices):
                    reportar("IMAGEM_LEGENDA", "A tradução da imagem deve estar em blocos consecutivos logo abaixo dela.", linha=linha)
                else:
                    legendas.update(indices)
            if estado in {'parcial', 'ilegivel', 'pendente'}:
                nota = imagem.get('nota', '').strip()
                if estado != 'pendente' and not nota:
                    reportar("IMAGEM_NOTA", "Descreva o trecho ilegível ou que ficou sem tradução.", linha=linha)
                reportar("IMAGEM_INSPECAO", f'Inspeção de imagem {estado}: {nota or imagem["markdown"]}', "pendencia", linha)
        corpo_md = [
            (linha, bloco, 'imagem' if i in indices_imagem
             else 'separador' if not legado and SEPARADOR.fullmatch(bloco.strip()) else 'texto')
            for i, (linha, bloco) in enumerate(corpo) if i not in legendas
        ]
        if not legado:
            conferir_alinhamento(unidade, elementos_epub, corpo_md, reportar, metrica)
            continue
        origem_texto = [texto for tipo, texto in elementos_epub if tipo == 'texto']
        traducao_texto = [(linha, bloco) for linha, bloco, tipo in corpo_md if tipo == 'texto']
        divisoes = unidade.get('divisoes_de_paragrafo', {})
        indices_validos = {str(i) for i in range(1, len(origem_texto) + 1)}
        if divisoes.keys() - indices_validos or any(type(total) is not int or total < 2 for total in divisoes.values()):
            raise ValueError(f'Divisão de parágrafo inválida em {nome}.')
        totais = [divisoes.get(str(i), 1) for i in range(1, len(origem_texto) + 1)]
        esperado_texto = sum(totais)
        if esperado_texto != len(traducao_texto):
            reportar("BLOCOS_TOTAL", f'Total de blocos diferente: EPUB {len(origem_texto)}, '
                   f'Markdown {len(traducao_texto)}, esperado {esperado_texto}. '
                   'Confira divisões, omissões e acréscimos.', "aviso")
            continue
        ordem = []
        tamanhos = iter(totais)
        for tipo, _ in elementos_epub:
            ordem.extend([tipo] * (next(tamanhos) if tipo == 'texto' else 1))
        if ordem != [tipo for _, _, tipo in corpo_md]:
            reportar("IMAGEM_POSICAO", "Uma imagem aparece entre blocos diferentes dos indicados pelo EPUB.", "aviso")
        if not comparar_palavras:
            continue
        inicio = 0
        for fonte, total in zip(origem_texto, totais):
            blocos = traducao_texto[inicio:inicio + total]
            inicio += total
            palavras_fonte = contar_palavras(fonte)
            palavras_traducao = sum(palavras_markdown(bloco) for _, bloco in blocos)
            if palavras_fonte >= minimo and palavras_traducao < palavras_fonte * proporcao:
                reportar("PALAVRAS_PROPORCAO", "Bloco muito curto em relação à fonte. Confira possíveis omissões.",
                         "aviso", blocos[0][0])

    return achados, len(unidades), imagens_registradas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('epub', type=Path)
    parser.add_argument('inventario', type=Path, help='JSON de inventário na pasta do volume')
    parser.add_argument('--estrito', action='store_true', help='retorna 1 quando houver erros, avisos ou pendências')
    parser.add_argument('--json', action='store_true', help='gera diagnósticos em JSON')
    parser.add_argument('--debug', action='store_true', help='exibe rastreamento de falhas de leitura')
    parser.add_argument('--limite-entradas', type=int, default=Limites.entradas)
    parser.add_argument('--limite-bytes-entrada', type=int, default=Limites.bytes_entrada)
    parser.add_argument('--limite-bytes-total', type=int, default=Limites.bytes_total)
    args = parser.parse_args(argv)
    try:
        inventario = ler_json(args.inventario)
        limites = Limites(args.limite_entradas, args.limite_bytes_entrada, args.limite_bytes_total)
        with Pacote.abrir(args.epub, limites) as epub:
            achados, unidades, imagens = verificar(epub, inventario, args.inventario.parent)
    except (OSError, BadZipFile, ET.ParseError, KeyError, TypeError, ValueError, AttributeError,
            RuntimeError, ErroCompressao) as erro:
        if args.debug:
            raise
        mensagem = f"Erro ao ler edição ou inventário: {erro}"
        if args.json:
            print(json.dumps({"schema": 1, "diagnosticos": [asdict(Achado(
                "ENTRADA_INVALIDA", "erro", str(args.inventario), mensagem))]}, ensure_ascii=False))
        else:
            print(mensagem, file=sys.stderr)
        return 2
    contagem = Counter(item.gravidade for item in achados)
    erros, avisos, pendencias = (contagem[nivel] for nivel in ("erro", "aviso", "pendencia"))
    if args.json:
        print(json.dumps({"schema": 1, "unidades": unidades, "imagens": imagens, "erros": erros,
                          "avisos": avisos, "pendencias": pendencias,
                          "diagnosticos": [asdict(item) for item in achados]}, ensure_ascii=False))
    else:
        for item in achados:
            local = f"{item.caminho}:{item.localizacao}" if item.localizacao else item.caminho
            print(f"{item.gravidade.upper()} {item.codigo} {local} · {item.mensagem}")
        print(f"{unidades} unidades, {imagens} imagens, {erros} erros, {avisos} avisos, {pendencias} pendências.")
    return int(bool(achados) if args.estrito else erros > 0)


if __name__ == '__main__':
    raise SystemExit(main())
