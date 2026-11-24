# Traduzir um EPUB para Markdown

Use este fluxo quando a edição de trabalho estiver em EPUB e a entrega for em Markdown. Registre em `AGENTS.md` as convenções que a obra adotar para pastas, nomes de arquivos e imagens.

## Identificar e catalogar a edição

1. Registre em `LINKS.md` a edição original e a edição de trabalho, com idioma, editora, data, ISBN digital quando disponível e créditos. Indique quais trechos de cada fonte estão acessíveis.
2. Antes de traduzir, inventarie o volume. Inclua capa, introdução, capítulos, epílogo, ilustrações, notas, créditos e outros extras que existirem na edição. Identifique cada unidade como narrativa, extra ou material editorial para acompanhar a cobertura de cada tipo.
3. Use o sumário para identificar as unidades e a ordem de leitura do EPUB para localizar as partes de cada unidade. Confira também páginas que aparecem na sequência de leitura sem entrada no sumário.

### Descoberta e importação assistidas

Da raiz das ferramentas, faça primeiro uma leitura da edição:

```sh
python -B -m src.translation_project importar "/caminho/edicao.epub" --projeto "/caminho/obra" --dry-run
```

A proposta JSON inclui SHA-256, metadados, manifesto, spine, navegação, ocorrências de imagens e agrupamentos sugeridos. O spine preserva capas, extras, páginas sem entrada no sumário, itens não lineares e repetições. Revise as sugestões e prepare um arquivo de confirmação no formato abaixo. Os IDs `p0001`, `p0002` e seguintes correspondem a ocorrências do spine, não a nomes de arquivo.

```json
{
  "sha256_epub": "<copie o valor da proposta>",
  "sumario": "000. Sumário.md",
  "navegacao": ["p0001"],
  "unidades": [
    {"id": "V01-C01", "markdown": "001. Capítulo.md", "paginas": ["p0002", "p0003"]}
  ]
}
```

Inclua todas as ocorrências do spine em ordem. A lista `navegacao` pode excluir as páginas nav declaradas no manifesto. A confirmação pertence à edição identificada pelo hash. Use `--anterior` com a proposta ou o inventário anterior para comparar a edição.

```sh
python -B -m src.translation_project inventario gerar "/caminho/edicao.epub" --projeto "/caminho/obra" --confirmacao "/caminho/confirmacao.json" --saida "Volume 01/inventario.json" --dry-run
python -B -m src.translation_project inventario gerar "/caminho/edicao.epub" --projeto "/caminho/obra" --confirmacao "/caminho/confirmacao.json" --saida "Volume 01/inventario.json" --aplicar --extrair-imagens --esqueleto
```

`--extrair-imagens` e `--esqueleto` são opcionais. O esqueleto contém sumário e arquivos vazios de tradução, com indicação de pendência. `--deduplicar` usa o SHA-256 da arte para compartilhar cópias físicas e manter cada ocorrência no inventário. A inspeção começa pendente e o alinhamento v2 precisa ser preenchido. Arquivos existentes idênticos são reaproveitados. Um arquivo divergente bloqueia a gravação, para que a revisão anterior possa ser comparada e preservada.

## Registrar a inspeção de cada imagem

Use o [modelo de inventário em JSON](../modelos/epub/inventario-epub.json) na pasta do volume. Registre cada ocorrência de imagem na unidade em que aparece, na ordem de leitura, com o caminho no EPUB, o caminho na edição em Markdown e o resultado da inspeção. Uma arte repetida em outra passagem ganha outra entrada.

| Estado | Quando usar |
| --- | --- |
| `sem_texto` | A imagem foi inspecionada e não contém texto que peça tradução. Uma marca preservada pode ser anotada nesse estado. |
| `traduzido` | Todo o texto traduzível foi incluído logo abaixo da imagem. |
| `parcial` | Parte do texto foi traduzida. Descreva em `nota` o que ficou pendente. |
| `ilegivel` | O texto não pôde ser lido. Identifique em `nota` a área afetada. |
| `pendente` | A inspeção ainda não foi feita. |

Em `blocos_traducao`, conte os blocos de Markdown separados por linhas em branco que pertencem à tradução da imagem. Preencha esse campo para `traduzido` e `parcial`. Inclua títulos, créditos e legendas quando fizerem parte da tradução. No acompanhamento do volume, aponte para o inventário e dê o total por estado.

## Montar a edição em Markdown

- Reúna num mesmo arquivo todas as partes de um capítulo dividido entre arquivos internos do EPUB. Preserve a ordem das passagens, as quebras de cena, as notas e os destaques pertinentes. Mantenha extras independentes na posição que ocupam no volume.
- Crie um sumário em Markdown com links relativos para a abertura, os capítulos e os extras incluídos. Uma estrutura possível é `Volume 01/000. Sumário.md`, com capítulos na mesma pasta e imagens em `Volume 01/Imagens/`.
- Use links relativos para as imagens. Posicione cada imagem junto à passagem correspondente. Se ela interrompe um capítulo no EPUB, insira-a entre as mesmas passagens no Markdown. Preserve também a posição das imagens de abertura e encerramento.
- Inspecione as imagens em busca de texto. Mantenha a arte e acrescente a tradução legível em Markdown imediatamente abaixo da imagem, incluindo falas, legendas, créditos e trechos de prosa. Preserve nomes e marcas conforme as convenções da obra. Registre no acompanhamento trechos ilegíveis ou que ainda precisem de cotejo.

## Acompanhar e conferir a entrega

- Siga o [fluxo de aprovação por capítulo](../AGENTS.md#traduzir-e-aprovar-por-capítulo) para cada unidade, incluindo extras e textos das imagens. Compare o capítulo completo com a edição de trabalho e faça a releitura em português em outra passada. Registre ambas por unidade antes de considerar o volume revisado.
- Registre a cobertura da tradução separadamente do cotejo com cada fonte e da releitura em português. Identifique a primeira passagem automatizada como versão de trabalho. Se o cotejo for parcial, indique até onde foi feito e o que falta conferir.
- Compare o inventário e a sequência de leitura do EPUB com os arquivos Markdown. Confira começos e fins de capítulos, continuações, separadores, notas e extras. Compare as imagens com as passagens que as antecedem e sucedem para verificar a posição.
- Abra os links do sumário e confira se cada referência de imagem aponta para o arquivo correto. Verifique se a tradução de cada imagem com texto aparece logo abaixo dela. Execute o [verificador de EPUB e Markdown](registro-e-verificador.md#verificador-de-epub-e-markdown) para conferir o inventário, a sequência e os links.
