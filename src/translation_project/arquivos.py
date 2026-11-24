"""Operações portáveis de leitura, hash e criação exclusiva."""

from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile


def sha256_arquivo(caminho):
    digest = sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(64 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _objeto_sem_duplicatas(pares):
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError(f"Chave repetida no JSON: {chave}")
        objeto[chave] = valor
    return objeto


def ler_json(caminho):
    with caminho.open(encoding="utf-8-sig") as arquivo:
        return json.load(arquivo, object_pairs_hook=_objeto_sem_duplicatas)


def json_texto(dados):
    return json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def criar_arquivo(destino, conteudo):
    """Publica bytes completos sem substituir um destino existente."""
    temporario = None
    try:
        with NamedTemporaryFile(dir=destino.parent, delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        if os.name == "nt":
            temporario.rename(destino)
        else:
            os.link(temporario, destino)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def substituir_arquivo(destino, conteudo, anterior):
    """Grava a vista inteira e verifica o conteúdo anterior antes da substituição."""
    temporario = None
    try:
        with NamedTemporaryFile(dir=destino.parent, delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        if destino.is_symlink() or destino.read_bytes() != anterior:
            raise ValueError(f"O arquivo mudou durante a operação: {destino}")
        temporario.replace(destino)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
