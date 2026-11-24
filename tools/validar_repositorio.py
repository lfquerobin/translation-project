"""Confere os contratos JSON, os links locais e a instalação da CLI."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit, urlunsplit

from jsonschema import Draft202012Validator


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.translation_project.arquivos import ler_json
from src.translation_project.epub import caminho_local
from src.translation_project.markdown import analisar_links, ancoras


def validar_schemas():
    exemplos = {
        "inventario-epub": [
            ler_json(RAIZ / "modelos/epub/inventario-epub.json"),
            {"schema": 2, "sumario": "Índice.md", "unidades": [
                {"markdown": "Capítulo.md", "paginas_epub": ["capitulo.xhtml"],
                 "alinhamento": [{"origem": ["e1"], "destino": ["m1"]}]},
            ]},
        ],
        "projeto-v2": [{"schema": 2, "idioma_destino": "pt-BR", "unidades": [], "convencoes": {"painel": True}}],
        "glossario-v1": [{"schema": 1, "termos": [
            {"id": "T1", "original": "term", "idioma": "en", "traducao": "termo", "estado": "proposto"},
        ]}],
        "vozes-v1": [{"schema": 1, "vozes": [
            {"id": "V1", "nome": "Narradora", "tipo": "narrativa"},
        ]}],
        "segmentos-v1": [{"schema": 1, "segmentos": [
            {"id": "S1", "unidade": "C1", "traducao": "Trecho sintético.", "referencia": "Parágrafo 1."},
        ]}],
    }
    encontrados = set()
    for arquivo in sorted((RAIZ / "schemas").glob("*.schema.json")):
        nome = arquivo.name.removesuffix(".schema.json")
        schema = ler_json(arquivo)
        Draft202012Validator.check_schema(schema)
        validador = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
        if nome not in exemplos:
            raise ValueError(f"Adicione uma instância de exemplo para {nome}.")
        for exemplo in exemplos[nome]:
            validador.validate(exemplo)
        if validador.is_valid({**exemplos[nome][0], "schema": 99}):
            raise ValueError(f"O contrato {nome} aceitou uma versão desconhecida.")
        encontrados.add(nome)
    if encontrados != exemplos.keys():
        raise ValueError(f"Schemas ausentes: {sorted(exemplos.keys() - encontrados)}")
    print(f"{len(encontrados)} schemas e exemplos conferidos.")


def validar_links():
    documentos = [RAIZ / "README.md", RAIZ / "AGENTS.md"]
    for nome in ("docs", "modelos", "projetos"):
        documentos.extend(sorted((RAIZ / nome).rglob("*.md")))
    total = 0
    for arquivo in documentos:
        conteudo = arquivo.read_text(encoding="utf-8")
        for link in analisar_links(conteudo, html=True):
            uri = urlsplit(link.destino)
            if uri.scheme or uri.netloc:
                continue
            caminho = urlunsplit(("", "", uri.path.rstrip("/"), "", ""))
            destino = caminho_local(RAIZ, arquivo.parent, caminho) if caminho else arquivo
            valido = destino.exists()
            if valido and uri.fragment and destino.suffix.lower() == ".md":
                valido = unquote(uri.fragment) in ancoras(destino.read_text(encoding="utf-8"), html=True)
            if not valido:
                raise ValueError(f"{arquivo.relative_to(RAIZ)}:{link.linha}: {link.destino}")
            total += 1
    print(f"{total} links locais conferidos em {len(documentos)} documentos.")


def validar_instalacao():
    comando = shutil.which("traducao")
    if comando is None:
        raise ValueError("Instale o pacote e deixe o executável traducao no PATH.")
    with TemporaryDirectory(prefix="validação instalação ") as pasta:
        obra = Path(pasta) / "Obra sintética"
        retorno = subprocess.run(
            [comando, "init", "--projeto", str(obra), "--estruturado", "--dry-run"],
            cwd=pasta, env={**os.environ, "PYTHONUTF8": "1"},
            capture_output=True, encoding="utf-8", check=True,
        )
        novos = set(json.loads(retorno.stdout)["novos"])
        if not {"GLOSSÁRIO.md", "PENDÊNCIAS.md", "projeto.json"} <= novos or obra.exists():
            raise ValueError("A CLI instalada não localizou os modelos ou gravou no dry-run.")
    print("CLI instalada: modelos disponíveis fora do checkout.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instalacao", action="store_true")
    args = parser.parse_args()
    if args.instalacao:
        validar_instalacao()
    else:
        validar_schemas()
        validar_links()
