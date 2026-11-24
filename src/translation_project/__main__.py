"""Entrada da linha de comando das ferramentas de tradução."""

import argparse
from pathlib import Path
import sys
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile
from zlib import error as ErroCompressao

from .arquivos import json_texto, ler_json
from .epub import Pacote, caminho_registro
from .importacao import confirmar, conferir_destinos, descobrir, publicar_importacao
from .migracao import invalidar, migrar, salvar_copia
from .registro import abrir_projeto, calcular_status


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
    args = parser.parse_args(argv)
    try:
        return args.executar(args)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, BadZipFile, ParseError,
            RuntimeError, ErroCompressao) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
