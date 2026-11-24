"""Descoberta da edição e geração de inventários explicitamente confirmados."""

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import PurePosixPath
from posixpath import relpath
from urllib.parse import quote

from .arquivos import criar_arquivo, json_texto, sha256_arquivo
from .epub import caminho_registro, chave_portavel, eventos_item, ler_edicao
from .registro import indice_unico, lista, texto


def descobrir(epub, hash_epub):
    edicao = ler_edicao(epub)
    avisos = [{"codigo": cod, "mensagem": msg} for cod, msg in edicao.avisos]
    paginas, cache = [], {}
    toc = defaultdict(list)
    for caminho, fragmento, titulo in edicao.toc:
        toc[caminho].append({"fragmento": fragmento or None, "titulo": titulo or None})
    repeticoes = Counter(pagina.item.caminho for pagina in edicao.spine)
    grupos = []
    for ordem, pagina in enumerate(edicao.spine, 1):
        item = pagina.item
        id_pagina = f"p{ordem:04}"
        existe = item.caminho in epub.entradas
        if not existe:
            avisos.append({"codigo": "IMPORTACAO_PAGINA_AUSENTE", "caminho": item.caminho,
                           "mensagem": "Página do spine ausente do EPUB."})
        if item.id not in cache:
            cache[item.id] = eventos_item(epub, item) if existe else ([], [])
        eventos, diagnosticos = cache[item.id]
        for codigo, mensagem in diagnosticos:
            avisos.append({"codigo": codigo, "caminho": item.caminho, "mensagem": mensagem})
        navegacao = "nav" in item.propriedades
        imagens = [{"id": f"{id_pagina}-i{n}", "epub": valor, "estado": "pendente",
                    "disponivel": valor in epub.entradas}
                   for n, (tipo, valor) in enumerate(eventos, 1) if tipo == "imagem"]
        paginas.append({
            "id": id_pagina, "caminho": item.caminho, "midia": item.tipo, "linear": pagina.linear,
            "navegacao": navegacao, "existe": existe, "toc": toc[item.caminho], "imagens": imagens,
            "eventos": [{"id": f"{id_pagina}-e{n}", "tipo": tipo}
                        for n, (tipo, _) in enumerate(eventos, 1)],
        })
        if navegacao:
            continue
        entradas_toc = toc[item.caminho]
        ancora = len(entradas_toc) == 1 and repeticoes[item.caminho] == 1
        if not entradas_toc and grupos and grupos[-1]["inicio_no_toc"] and pagina.linear:
            grupo = grupos[-1]
            grupo["paginas"].append(id_pagina)
            grupo["motivos"].append(f"{id_pagina} fora do sumário pode ser continuação ou unidade independente.")
        else:
            motivos = []
            if not ancora:
                motivos.append("Sem correspondência inequívoca entre o sumário e a ocorrência no spine.")
            if not pagina.linear:
                motivos.append("Item não linear. Confirme a posição editorial.")
            if any(entrada["fragmento"] for entrada in entradas_toc):
                motivos.append("O sumário aponta para um trecho da página.")
            grupos.append({"paginas": [id_pagina], "titulo": entradas_toc[0]["titulo"] if ancora else None,
                           "inicio_no_toc": ancora, "motivos": motivos})
    return {
        "schema": 1, "sha256_epub": hash_epub, "metadados": edicao.metadados,
        "manifesto": [{"id": item.id, "caminho": item.caminho, "midia": item.tipo,
                      "propriedades": list(item.propriedades), "existe": item.caminho in epub.entradas}
                     for item in edicao.manifesto.values()],
        "spine": paginas, "sumario_epub": [{"caminho": c, "fragmento": f or None, "titulo": t or None}
                                         for c, f, t in edicao.toc],
        "agrupamentos_sugeridos": grupos, "diagnosticos": avisos,
    }


def confirmar(epub, proposta, confirmacao, *, deduplicar=False):
    if confirmacao.get("sha256_epub") != proposta["sha256_epub"]:
        raise ValueError("A confirmação é de outra edição. Gere uma proposta para o EPUB atual.")
    paginas = {pagina["id"]: pagina for pagina in proposta["spine"]}
    navegacao = lista(confirmacao.get("navegacao", []), "navegacao")
    id_nav = set(navegacao)
    if len(id_nav) != len(navegacao) or any(id not in paginas or not paginas[id]["navegacao"] for id in id_nav):
        raise ValueError("Somente ocorrências nav do spine podem ser excluídas como navegação.")
    # O inventário usa nomes de página para a exclusão. Todos os usos de uma mesma página devem concordar.
    nomes_nav = list(dict.fromkeys(p["caminho"] for id, p in paginas.items() if id in id_nav))
    if any(id not in id_nav and p["caminho"] in nomes_nav for id, p in paginas.items()):
        raise ValueError("Uma página repetida deve ter a mesma política de navegação em todas as ocorrências.")
    grupos = indice_unico(confirmacao.get("unidades"), "unidades confirmadas")
    ordem_registrada = [id for unidade in grupos.values() for id in lista(unidade.get("paginas"), "paginas")]
    if not grupos or ordem_registrada != [id for id in paginas if id not in id_nav]:
        raise ValueError("A confirmação precisa cobrir cada ocorrência do spine em ordem, uma vez.")
    ativos = {}
    por_origem, por_hash = {}, {}
    nomes = [texto(confirmacao.get("sumario"), "sumario")]
    unidades = []
    for id_unidade, grupo in grupos.items():
        nome = texto(grupo.get("markdown"), f"{id_unidade}.markdown")
        nomes.append(nome)
        if not grupo["paginas"]:
            raise ValueError(f"Unidade sem páginas: {id_unidade}")
        imagens = []
        caminhos = []
        for id_pagina in grupo["paginas"]:
            pagina = paginas[id_pagina]
            if not pagina["existe"]:
                raise ValueError(f"Página ausente na edição: {pagina['caminho']}")
            caminhos.append(pagina["caminho"])
            for imagem in pagina["imagens"]:
                origem = imagem["epub"]
                if not imagem["disponivel"]:
                    raise ValueError(f"Imagem ausente na edição: {origem}")
                if origem not in por_origem:
                    digest = sha256(epub.read(origem)).hexdigest() if deduplicar else sha256(origem.encode()).hexdigest()
                    base = PurePosixPath(origem).name
                    destino = f"Imagens/{digest[:16]}-{base}"
                    if deduplicar:
                        destino = por_hash.setdefault(digest, destino)
                    por_origem[origem] = destino
                    if destino in ativos and not deduplicar:
                        raise ValueError(f"Colisão de nomes de imagem: {destino}")
                    ativos.setdefault(destino, origem)
                imagens.append({"id": imagem["id"], "epub": origem, "markdown": por_origem[origem],
                                "estado": "pendente", "blocos_traducao": 0})
        unidades.append({"id": id_unidade, "markdown": nome, "paginas_epub": caminhos,
                         "blocos_iniciais": 0, "imagens": imagens, "alinhamento": []})
    registro = {
        "schema": 2, "sha256_epub": proposta["sha256_epub"], "metadados": proposta["metadados"],
        "sumario": nomes[0], "paginas_de_navegacao": nomes_nav, "unidades": unidades,
    }
    if len(nomes) != len({chave_portavel(nome) for nome in nomes}):
        raise ValueError("Caminhos de unidade ou sumário em colisão.")
    if any(PurePosixPath(nome).suffix.lower() != ".md" for nome in nomes):
        raise ValueError("O sumário e as unidades confirmadas precisam de caminhos Markdown.")
    return registro, ativos


def gerar_esqueleto(registro):
    pasta_sumario = PurePosixPath(registro["sumario"]).parent.as_posix()
    sumario = ["# Sumário", "", "<!-- Estrutura inicial. Confirme títulos e ordem na edição de trabalho. -->", ""]
    textos = {}
    for unidade in registro["unidades"]:
        nome = unidade["markdown"]
        destino = quote(relpath(nome, pasta_sumario))
        id_link = " ".join(unidade["id"].split()).replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
        sumario.append(f"- [{id_link}]({destino})")
        textos[nome] = "<!-- Tradução pendente. Preencha conforme as convenções do projeto. -->\n".encode("utf-8")
    textos[registro["sumario"]] = ("\n".join(sumario) + "\n").encode("utf-8")
    return textos


def conferir_destinos(raiz, saida, registro, imagens):
    destinos = {chave_portavel(saida.name): saida.name}
    for nome in [registro["sumario"], *(u["markdown"] for u in registro["unidades"]), *imagens]:
        chave = chave_portavel(nome)
        if chave in destinos:
            raise ValueError(f"O destino {nome} conflita com outro arquivo da importação.")
        destinos[chave] = nome
        caminho_registro(raiz, nome)
    diretorios = {}
    for nome in destinos.values():
        partes = nome.split("/")
        for i in range(1, len(partes)):
            diretorio = "/".join(partes[:i])
            chave = chave_portavel(diretorio)
            if chave in destinos or diretorios.setdefault(chave, diretorio) != diretorio:
                raise ValueError(f"O destino {nome} conflita com um diretório da importação.")


def publicar_importacao(epub, raiz, saida, registro, imagens, *, extrair=False, esqueleto=False):
    conferir_destinos(raiz, saida, registro, imagens)
    conteudos = gerar_esqueleto(registro) if esqueleto else {}
    arquivos = [(caminho_registro(raiz, nome), conteudo, None) for nome, conteudo in conteudos.items()]
    if extrair:
        arquivos.extend((caminho_registro(raiz, nome), None, origem) for nome, origem in imagens.items())
    arquivos.append((saida, json_texto(registro).encode("utf-8"), None))
    novos = []
    for caminho, conteudo, origem in arquivos:
        if caminho.exists() or caminho.is_symlink():
            dados = conteudo if origem is None else epub.read(origem)
            if not caminho.is_file() or sha256_arquivo(caminho) != sha256(dados).hexdigest():
                raise ValueError(f"Destino divergente. Preserve o arquivo e escolha outro caminho: {caminho}")
        else:
            for pasta in caminho.parents:
                if pasta.exists() and not pasta.is_dir():
                    raise ValueError(f"Um componente do destino não é diretório: {pasta}")
                if pasta == raiz:
                    break
            novos.append((caminho, conteudo, origem))
    for caminho, conteudo, origem in novos:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        criar_arquivo(caminho, conteudo if origem is None else epub.read(origem))
    return [caminho.relative_to(raiz).as_posix() for caminho, _, _ in novos]
