# Projeto de Tradução

Guia para criar e manter projetos de tradução literária para o português brasileiro. Cada obra ou versão em trabalho tem seu próprio repositório, com os textos, as fontes, o glossário e o registro das revisões.

- [Guia editorial](AGENTS.md)
- [Como criar um projeto e preencher os arquivos](docs/criar-projeto.md)
- [Como traduzir um EPUB para Markdown](docs/traduzir-epub.md)
- [Inventário e verificação de EPUB](docs/registro-e-verificador.md#verificador-de-epub-e-markdown)
- [Modelos iniciais copiáveis](modelos/projeto/)
- [Registro estruturado e verificador](docs/registro-e-verificador.md)
- [Índice de projetos](projetos/README.md)
- [Progresso da implementação](docs/implementacao.md)

O guia reúne práticas adotadas no trabalho com *Re:Zero*. As convenções de uma obra ficam no seu próprio repositório e podem variar conforme a edição, os idiomas e a forma de publicação.

## Testes locais

Com Python 3.10 ou mais recente, execute na raiz do guia:

```sh
python -B -m unittest discover -s tests -v
```

Os testes usam EPUBs sintéticos gerados em pastas temporárias.
