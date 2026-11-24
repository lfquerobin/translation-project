"""Entrada da linha de comando das ferramentas de tradução."""

import argparse
from pathlib import Path
import sys

from .arquivos import json_texto
from .epub import caminho_registro
from .migracao import invalidar, migrar, salvar_copia
from .registro import abrir_projeto, calcular_status


def _projeto(comando):
    comando.add_argument("--projeto", type=Path, required=True, help="raiz da obra")


def _escrita_opcional(comando):
    modo = comando.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true", help="mostra resultados sem gravar (padrão)")
    modo.add_argument("--aplicar", action="store_true", help="grava o registro em uma cópia nova")
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
    args = parser.parse_args(argv)
    try:
        return args.executar(args)
    except (OSError, ValueError, KeyError, TypeError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
