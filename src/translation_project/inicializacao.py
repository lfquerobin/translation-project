"""Criação local de projetos a partir dos modelos compartilhados."""

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from .arquivos import criar_arquivo, json_texto
from .epub import caminho_registro
from .registro import calcular_status
from .vistas import VISTAS, gerar_vistas


def _modelos():
    modulo = Path(__file__).resolve()
    for local in (modulo.parents[2] / "modelos" / "projeto",
                  modulo.parents[1] / "share" / "translation-project" / "modelos" / "projeto"):
        if local.is_dir():
            return sorted(local.glob("*.md"))
    try:
        pacote = distribution("translation-project")
    except PackageNotFoundError:
        raise ValueError("Modelos indisponíveis. Execute na cópia do repositório ou instale a ferramenta.") from None
    return sorted(pacote.locate_file(item) for item in (pacote.files or ())
                  if item.as_posix().endswith(".md") and "share/translation-project/modelos/projeto/" in item.as_posix())


def iniciar(raiz, *, estruturado=False, aplicar=False):
    raiz = raiz.resolve()
    if raiz.exists() and not raiz.is_dir():
        raise ValueError("A raiz do projeto precisa ser um diretório.")
    modelos = _modelos()
    if not modelos:
        raise ValueError("A instalação não contém os modelos do projeto.")
    arquivos = {arquivo.name: arquivo.read_bytes() for arquivo in modelos
                if not estruturado or arquivo.name not in VISTAS}
    if estruturado and not (raiz / "projeto.json").exists():
        registro = {"schema": 2, "obra": None, "versao": None, "idioma_destino": "pt-BR",
                    "unidades": [], "ocorrencias": [], "volumes": [], "convencoes": {"vistas": True}}
        arquivos.update(gerar_vistas(registro, calcular_status(registro, raiz)))
        arquivos["projeto.json"] = json_texto(registro).encode("utf-8")
    criar, preservar = [], []
    for nome in arquivos:
        caminho = caminho_registro(raiz, nome)
        if caminho.exists() or caminho.is_symlink():
            preservar.append(nome)
        else:
            criar.append(nome)
    if aplicar:
        raiz.mkdir(parents=True, exist_ok=True)
        for nome in criar:
            criar_arquivo(caminho_registro(raiz, nome), arquivos[nome])
    return {"aplicado": aplicar, "novos": criar, "preservados": preservar}
