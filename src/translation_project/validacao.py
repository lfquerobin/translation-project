"""Verificações objetivas do projeto e da preparação de uma entrega."""

from collections import Counter
import re
from urllib.parse import unquote, urlsplit

from .arquivos import ler_json
from .editorial import abrir_editorial, ocorrencias_glossario, validar_vozes
from .epub import Pacote, caminho_local, caminho_registro
from .markdown import analisar_links, ancoras, visivel
from .registro import calcular_status, lista, objeto, texto, validar_data
from .verificador_epub import Achado, verificar
from .vistas import gerar_vistas, inspecionar_vistas


def _links(raiz, caminho, conteudo, html, reportar):
    cache = {}
    for link in analisar_links(conteudo, html=html):
        try:
            alvo = caminho_local(raiz, caminho.parent, link.destino)
        except ValueError as erro:
            reportar("LINK_CAMINHO", "erro", str(erro), link.linha)
            continue
        url = urlsplit(link.destino)
        if url.scheme or url.netloc:
            continue
        if alvo is not None and (not alvo.exists() or (link.imagem and not alvo.is_file())):
            reportar("LINK_AUSENTE", "erro", f"Destino ausente: {link.destino}", link.linha)
            continue
        alvo = alvo or caminho
        if url.fragment and alvo.is_file() and alvo.suffix.lower() == ".md":
            if alvo not in cache:
                cache[alvo] = ancoras(conteudo if alvo == caminho else alvo.read_text(encoding="utf-8-sig"), html=html)
            if unquote(url.fragment) not in cache[alvo]:
                reportar("LINK_FRAGMENTO", "aviso", f"Âncora Markdown não reconhecida: {link.destino}", link.linha)


def _cabecalhos(conteudo, convencoes, reportar):
    campos = lista(convencoes.get("cabecalhos", []), "convencoes.cabecalhos")
    limite = convencoes.get("linhas_cabecalho", 20)
    if type(limite) is not int or limite < 1:
        raise ValueError("linhas_cabecalho deve ser um inteiro positivo.")
    inicio = visivel(conteudo).splitlines()[:limite]
    for campo in campos:
        nome = texto(campo if isinstance(campo, str) else campo.get("nome"), "cabecalhos.nome")
        tipo = "texto" if isinstance(campo, str) else campo.get("tipo", "texto")
        if tipo not in {"texto", "data", "link"}:
            raise ValueError(f"Tipo inválido para o campo de cabeçalho {nome}.")
        padrao = re.compile(r"^\s*(?:\*\*)?" + re.escape(nome) + r"\s*:\s*(?:\*\*)?(.*?)\s*(?:\*\*)?\s*$")
        encontrados = [(n, m[1]) for n, linha in enumerate(inicio, 1) if (m := padrao.match(linha)) and m[1]]
        if len(encontrados) != 1:
            reportar("CABECALHO_CAMPO", "erro", f"Informe uma ocorrência do campo {nome}.")
            continue
        linha, valor = encontrados[0]
        if tipo == "data" and valor != "não informada":
            try:
                validar_data(valor, nome)
            except ValueError as erro:
                reportar("CABECALHO_DATA", "erro", str(erro), linha)
        if tipo == "link" and not analisar_links(valor) and urlsplit(valor).scheme not in {"http", "https"}:
            reportar("CABECALHO_LINK", "erro", f"Informe um link no campo {nome}.", linha)


def _falas(conteudo, convencoes, ocorrencias, reportar):
    if "falas" not in convencoes:
        return
    regras = objeto(convencoes["falas"], "falas")
    abertura = texto(regras.get("abertura"), "falas.abertura")
    fechamento = texto(regras.get("fechamento"), "falas.fechamento")
    rotulos = set(lista(regras.get("rotulos", []), "falas.rotulos"))
    anonimo = regras.get("rotulo_anonimo")
    rotulos.discard(anonimo)
    encontrados = Counter()
    for n, linha in enumerate(visivel(conteudo).splitlines(), 1):
        rotulo, dois_pontos, corpo = linha.partition(":")
        corpo = corpo.strip()
        rotulo = rotulo.strip()
        if not dois_pontos or (rotulo not in rotulos and rotulo != anonimo and not corpo.startswith(abertura)):
            continue
        if not corpo.startswith(abertura) or not corpo.endswith(fechamento):
            reportar("FALA_DELIMITADOR", "erro", "Fala com delimitadores incompletos.", n)
            continue
        if rotulo == anonimo:
            trecho = corpo[len(abertura):-len(fechamento)]
            encontrados[trecho] += 1
        elif rotulos and rotulo not in rotulos:
            reportar("FALA_ROTULO", "aviso", f"Rótulo fora da lista: {rotulo}", n)
    esperados = Counter(
        texto(item.get("trecho"), f"{item['id']}.trecho") for item in ocorrencias
        if item.get("tipo") == "falante" and item["estado"] != "resolvida"
    )
    if anonimo and encontrados != esperados:
        reportar("FALA_OCORRENCIAS", "erro", "As ocorrências anônimas diferem do registro, incluindo repetições.")


def verificar_projeto(dados, raiz, *, unidade=None, volume=None, conferir_vistas=False):
    status = calcular_status(dados, raiz, unidade)
    achados = []
    convencoes = objeto(dados.get("convencoes", {}), "convencoes")
    if volume is not None and volume not in {v["id"] for v in status["volumes"]}:
        raise ValueError(f"Volume desconhecido: {volume}")
    ocorrencias = {}
    glossario = abrir_editorial(dados, raiz, "glossario")
    vozes = abrir_editorial(dados, raiz, "vozes")
    if vozes is not None:
        validar_vozes(vozes, dados)
    for item in dados.get("ocorrencias", []):
        ocorrencias.setdefault(item["unidade"], []).append(item)
    for item in status["unidades"]:
        if volume is not None and item["volume"] != volume:
            continue
        nome, id_unidade = item["arquivo"], item["id"]

        def reportar(codigo, gravidade, mensagem, linha=None, *, nome=nome, id_unidade=id_unidade):
            achados.append(Achado(codigo, gravidade, nome, mensagem, id_unidade, linha))

        caminho = caminho_registro(raiz, nome)
        if not caminho.is_file():
            reportar("ARQUIVO_AUSENTE", "erro", "Arquivo da unidade ausente.")
            continue
        conteudo = caminho.read_text(encoding="utf-8-sig")
        _links(raiz, caminho, conteudo, convencoes.get("permitir_html", False), reportar)
        _cabecalhos(conteudo, convencoes, reportar)
        _falas(conteudo, convencoes, ocorrencias.get(id_unidade, []), reportar)
        for etapa, revisao in item["revisoes"].items():
            if revisao["estado"] == "desatualizada":
                reportar("REVISAO_DESATUALIZADA", "pendencia", f"{etapa}. {revisao['motivo']}")
        for id_bloqueio in item["bloqueios"]:
            reportar("EDITORIAL_BLOQUEIO", "pendencia", f"Pendência bloqueante: {id_bloqueio}")
    if glossario is not None:
        achados.extend(ocorrencias_glossario(glossario, dados, raiz, unidade_id=unidade, volume=volume))
    if unidade is None and volume is None:
        registrados = {u["arquivo"] for u in dados["unidades"]}
        orfaos = set()
        for nome in lista(convencoes.get("pastas_texto", []), "convencoes.pastas_texto"):
            pasta = caminho_registro(raiz, texto(nome, "convencoes.pastas_texto"))
            if not pasta.is_dir():
                achados.append(Achado("PASTA_TEXTOS_AUSENTE", "aviso", nome, "Pasta de textos não encontrada."))
                continue
            orfaos.update(p.relative_to(raiz).as_posix() for p in pasta.rglob("*")
                          if p.is_file() and not p.is_symlink() and p.suffix.lower() == ".md")
        for nome in sorted(orfaos - registrados):
            achados.append(Achado("ARQUIVO_ORFAO", "aviso", nome, "Texto sem unidade correspondente."))
        if conferir_vistas or convencoes.get("vistas") or convencoes.get("painel"):
            for nome, (_, estado, _) in inspecionar_vistas(raiz, gerar_vistas(dados, status, raiz)).items():
                if estado != "atual":
                    achados.append(Achado("VISTA_DIVERGENTE", "aviso", nome, f"Vista {estado}."))
    return status, achados


def validar_entrega(dados, raiz, volume):
    status, achados = verificar_projeto(dados, raiz, volume=volume)
    item = next(v for v in status["volumes"] if v["id"] == volume)
    if item["estado"] != "revisado_edicao_trabalho":
        achados.append(Achado("VOLUME_PENDENTE", "erro", volume, "A revisão de todas as unidades e do conjunto está pendente."))
    volume_registro = next(v for v in dados["volumes"] if v["id"] == volume)
    if "epub" in volume_registro or "inventario" in volume_registro:
        edicao = caminho_registro(raiz, texto(volume_registro.get("epub"), "volume.epub"))
        inventario = caminho_registro(raiz, texto(volume_registro.get("inventario"), "volume.inventario"))
        with Pacote.abrir(edicao) as pacote:
            achados.extend(verificar(pacote, ler_json(inventario), inventario.parent)[0])
    return item, achados
