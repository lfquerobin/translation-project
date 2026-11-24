"""Entrada da linha de comando das ferramentas de tradução."""

import argparse
from dataclasses import asdict
from pathlib import Path
import sqlite3
import sys
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile
from zlib import error as ErroCompressao

from .arquivos import json_texto, ler_json
from .editorial import abrir_editorial, ocorrencias_glossario, validar_vozes
from .epub import Pacote, caminho_registro
from .importacao import confirmar, conferir_destinos, descobrir, publicar_importacao
from .inicializacao import iniciar
from .memoria import atualizar as atualizar_memoria, buscar as buscar_memoria
from .migracao import invalidar, migrar, salvar_copia
from .registro import abrir_projeto, calcular_status, validar_registro
from .validacao import validar_entrega, verificar_projeto
from .vistas import aplicar_vistas, gerar_vistas, inspecionar_vistas


def _projeto(comando):
    comando.add_argument("--projeto", type=Path, required=True, help="raiz da obra")


def _escrita_opcional(comando, ajuda="grava o registro em uma cópia nova"):
    modo = comando.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true", help="mostra resultados sem gravar (padrão)")
    modo.add_argument("--aplicar", action="store_true", help=ajuda)
    comando.add_argument("--saida", help="caminho relativo para uma cópia no projeto")


def _status(args):
    dados, raiz = abrir_projeto(args.projeto)
    status = calcular_status(dados, raiz, args.unidade)
    if args.json:
        print(json_texto(status), end="")
    else:
        print(f"Projeto · {status['estado']}")
        for unidade in status["unidades"]:
            etapas = ", ".join(f"{etapa}={revisao['estado']}" for etapa, revisao in unidade["revisoes"].items())
            print(f"{unidade['id']} · {unidade['estado']} · {etapas}")
        for volume in status["volumes"]:
            print(f"{volume['id']} · {volume['estado']} · {volume['revisadas']}/{volume['unidades']} revisadas")
    return 0


def _copia(args):
    dados, raiz = abrir_projeto(args.projeto)
    operacao = migrar if args.comando == "migrar" else invalidar
    resultado, relatorio = operacao(dados, raiz)
    if args.aplicar:
        if not args.saida:
            raise ValueError("--aplicar exige --saida com nome de um arquivo novo.")
        saida = caminho_registro(raiz, args.saida)
        salvar_copia(saida, resultado)
    print(json_texto({
        "operacao": args.comando, "aplicado": args.aplicar,
        "saida": args.saida if args.aplicar else None, "mapeamento": relatorio,
    }), end="")
    return 0


def _importar(args):
    if args.aplicar and not args.saida:
        raise ValueError("--aplicar exige --saida.")
    if (args.extrair_imagens or args.esqueleto or args.deduplicar) and not args.confirmacao:
        raise ValueError("Extração, deduplicação e esqueleto exigem --confirmacao.")
    projeto = args.projeto.resolve() if args.projeto else Path.cwd()
    if args.projeto and not projeto.is_dir():
        raise ValueError("A raiz indicada por --projeto precisa existir.")
    saida = None
    if args.saida:
        if args.projeto:
            saida = caminho_registro(projeto, args.saida)
        else:
            pedido = Path(args.saida)
            saida = caminho_registro(pedido.parent.resolve(), pedido.name)
    with Pacote.abrir(args.epub) as epub:
        proposta = descobrir(epub, epub.digest())
        relatorio = {"proposta": proposta, "aplicado": args.aplicar, "novos": []}
        if args.anterior:
            hash_anterior = ler_json(args.anterior).get("sha256_epub")
            relatorio["comparacao_edicao"] = {
                "anterior": hash_anterior, "atual": proposta["sha256_epub"],
                "estado": "desconhecida" if not hash_anterior else
                "igual" if hash_anterior == proposta["sha256_epub"] else "alterada",
            }
        if args.confirmacao:
            registro, imagens = confirmar(epub, proposta, ler_json(args.confirmacao), deduplicar=args.deduplicar)
            relatorio["inventario"] = registro
            relatorio["imagens"] = imagens
            if saida:
                conferir_destinos(saida.parent, saida, registro, imagens)
            if args.aplicar:
                relatorio["novos"] = publicar_importacao(
                    epub, saida.parent, saida, registro, imagens, extrair=args.extrair_imagens,
                    esqueleto=args.esqueleto,
                )
        elif args.aplicar:
            if saida.is_file() and ler_json(saida) == proposta:
                pass
            elif saida.exists() or saida.is_symlink():
                raise ValueError("A proposta de destino já existe e é divergente.")
            else:
                salvar_copia(saida, proposta)
                relatorio["novos"].append(saida.name)
    print(json_texto(relatorio), end="")
    return 0


def _argumentos_importar(comando, *, projeto_obrigatorio):
    comando.add_argument("epub", type=Path, help="edição EPUB")
    comando.add_argument("--projeto", type=Path, required=projeto_obrigatorio, help="raiz da obra")
    _escrita_opcional(comando, "grava a proposta ou o inventário confirmado no destino")
    comando.add_argument("--anterior", type=Path, help="proposta ou inventário anterior para comparar a edição")
    comando.add_argument("--confirmacao", type=Path, help="agrupamento confirmado em JSON")
    comando.add_argument("--extrair-imagens", action="store_true")
    comando.add_argument("--deduplicar", action="store_true")
    comando.add_argument("--esqueleto", action="store_true")
    comando.set_defaults(executar=_importar)


def _iniciar(args):
    relatorio = iniciar(args.projeto, estruturado=args.estruturado, aplicar=args.aplicar)
    print(json_texto(relatorio), end="")
    return 0


def _sincronizar(args):
    dados, raiz = abrir_projeto(args.projeto)
    geradas = gerar_vistas(dados, calcular_status(dados, raiz), raiz)
    plano = inspecionar_vistas(raiz, geradas)
    if args.aplicar:
        aplicar_vistas(geradas, plano)
    estados = {nome: estado for nome, (_, estado, _) in plano.items()}
    print(json_texto({"schema": 1, "aplicado": args.aplicar, "vistas": estados}), end="")
    return int(args.conferir and any(estado != "atual" for estado in estados.values()))


def _validar(args):
    dados, raiz = abrir_projeto(args.projeto)
    entrega = args.comando == "validar-entrega"
    if entrega:
        status, achados = validar_entrega(dados, raiz, args.volume)
    else:
        status, achados = verificar_projeto(dados, raiz, unidade=args.unidade, conferir_vistas=args.conferir_vistas)
    if args.json:
        print(json_texto({"schema": 1, "status": status, "diagnosticos": [asdict(item) for item in achados]}), end="")
    else:
        for item in achados:
            local = f"{item.caminho}:{item.localizacao}" if item.localizacao else item.caminho
            print(f"{item.gravidade.upper()} {item.codigo} {local} · {item.mensagem}")
        print(f"{len(achados)} diagnósticos. Confira as etapas editoriais com o comando status.")
    return int(bool(achados) if entrega or args.estrito else any(item.gravidade == "erro" for item in achados))


def _modo_local(comando):
    modo = comando.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true", help="mostra resultados sem gravar (padrão)")
    modo.add_argument("--aplicar", action="store_true", help="grava os artefatos locais")
    return modo


def _editorial(args):
    dados, raiz = abrir_projeto(args.projeto)
    unidades, _, _ = validar_registro(dados, raiz)
    registro = abrir_editorial(dados, raiz, args.comando)
    if registro is None:
        raise ValueError(f"Configure convencoes.{args.comando} no registro da obra.")
    if args.comando == "vozes":
        itens = validar_vozes(registro, dados)
        print(json_texto({"schema": 1, "vozes": list(itens)}), end="")
        return 0
    if args.unidade and args.unidade not in unidades:
        raise ValueError(f"Unidade desconhecida: {args.unidade}")
    achados = ocorrencias_glossario(registro, dados, raiz, termo_id=getattr(args, "termo", None), unidade_id=args.unidade)
    print(json_texto({"schema": 1, "diagnosticos": [asdict(item) for item in achados]}), end="")
    return int(bool(achados) and getattr(args, "estrito", False))


def _memoria(args):
    dados, raiz = abrir_projeto(args.projeto)
    if args.acao == "atualizar":
        resultado = atualizar_memoria(
            dados, raiz, aplicar=args.aplicar, reconstruir=args.reconstruir, sem_fts=args.sem_fts,
        )
    else:
        resultado = buscar_memoria(
            dados, raiz, args.consulta, obra=args.obra, versao=args.versao, ate=args.ate,
            futuro=args.incluir_futuro, trabalho=args.incluir_trabalho, limite=args.limite, sem_fts=args.sem_fts,
        )
    print(json_texto(resultado), end="")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="traducao", description=__doc__)
    comandos = parser.add_subparsers(dest="comando", required=True)
    status = comandos.add_parser("status", help="calcula o estado editorial registrado")
    _projeto(status)
    status.add_argument("--unidade", help="ID de uma unidade")
    status.add_argument("--json", action="store_true")
    status.set_defaults(executar=_status)
    for nome, ajuda in (("migrar", "prepara migração do registro central v1"),
                        ("invalidar", "prepara eventos para revisões desatualizadas")):
        comando = comandos.add_parser(nome, help=ajuda)
        _projeto(comando)
        _escrita_opcional(comando)
        comando.set_defaults(executar=_copia)
    importar = comandos.add_parser("importar", help="propõe ou prepara uma edição EPUB")
    _argumentos_importar(importar, projeto_obrigatorio=True)
    inventario = comandos.add_parser("inventario", help="trabalha com inventários EPUB")
    acoes = inventario.add_subparsers(dest="acao", required=True)
    gerar = acoes.add_parser("gerar", help="descobre páginas, recursos e agrupamentos")
    _argumentos_importar(gerar, projeto_obrigatorio=False)
    init = comandos.add_parser("init", help="copia modelos para um projeto local")
    _projeto(init)
    _modo_local(init)
    init.add_argument("--estruturado", action="store_true", help="cria um registro central vazio e vistas iniciais")
    init.set_defaults(executar=_iniciar)
    sincronizar = comandos.add_parser("sincronizar", help="compara ou regenera as vistas locais")
    _projeto(sincronizar)
    _modo_local(sincronizar).add_argument("--conferir", action="store_true", help="falha se alguma vista divergir")
    sincronizar.set_defaults(executar=_sincronizar)
    verificar = comandos.add_parser("verificar", help="confere a estrutura do projeto")
    _projeto(verificar)
    verificar.add_argument("--unidade", help="ID da unidade")
    verificar.add_argument("--json", action="store_true")
    verificar.add_argument("--estrito", action="store_true")
    verificar.add_argument("--conferir-vistas", action="store_true")
    verificar.set_defaults(executar=_validar)
    entrega = comandos.add_parser("validar-entrega", help="confere revisão registrada e estrutura do volume")
    _projeto(entrega)
    entrega.add_argument("--volume", required=True, help="ID do volume")
    entrega.add_argument("--json", action="store_true")
    entrega.set_defaults(executar=_validar)
    glossario = comandos.add_parser("glossario", help="confere decisões e lista ocorrências terminológicas")
    acoes_glossario = glossario.add_subparsers(dest="acao", required=True)
    for nome in ("verificar", "afetadas"):
        acao = acoes_glossario.add_parser(nome)
        _projeto(acao)
        acao.add_argument("--unidade")
        acao.set_defaults(executar=_editorial)
        if nome == "afetadas":
            acao.add_argument("--termo", required=True)
        else:
            acao.add_argument("--estrito", action="store_true")
    vozes = comandos.add_parser("vozes", help="confere identidades e referências de voz")
    acao = vozes.add_subparsers(dest="acao", required=True).add_parser("verificar")
    _projeto(acao)
    acao.set_defaults(executar=_editorial)
    memoria = comandos.add_parser("memoria", help="reconstrói ou consulta o índice local opcional")
    acoes_memoria = memoria.add_subparsers(dest="acao", required=True)
    atualizar = acoes_memoria.add_parser("atualizar")
    buscar = acoes_memoria.add_parser("buscar")
    for acao in (atualizar, buscar):
        _projeto(acao)
        acao.add_argument("--sem-fts", action="store_true", help="usa a alternativa de busca simples")
        acao.set_defaults(executar=_memoria)
    _modo_local(atualizar)
    atualizar.add_argument("--reconstruir", action="store_true")
    buscar.add_argument("consulta")
    buscar.add_argument("--obra", required=True)
    buscar.add_argument("--versao", required=True)
    buscar.add_argument("--ate", required=True, help="última unidade que pode ser revelada")
    buscar.add_argument("--incluir-futuro", action="store_true")
    buscar.add_argument("--incluir-trabalho", action="store_true")
    buscar.add_argument("--limite", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        return args.executar(args)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, BadZipFile, ParseError,
            RuntimeError, ErroCompressao, sqlite3.Error) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
