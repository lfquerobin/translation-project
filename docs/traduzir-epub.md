# Traduzir um EPUB para Markdown

Use este fluxo quando a edição de trabalho estiver em EPUB e a entrega for em Markdown. Registre em `AGENTS.md` as convenções que a obra adotar para pastas, nomes de arquivos e imagens.

## Identificar e catalogar a edição

1. Registre em `LINKS.md` a edição original e a edição de trabalho, com idioma, editora, data, ISBN digital quando disponível e créditos. Indique quais trechos de cada fonte estão acessíveis.
2. Antes de traduzir, inventarie o volume. Inclua capa, introdução, capítulos, epílogo, ilustrações, notas, créditos e outros extras que existirem na edição. Identifique cada unidade como narrativa, extra ou material editorial para acompanhar a cobertura de cada tipo.
3. Use o sumário para identificar as unidades e a ordem de leitura do EPUB para localizar as partes de cada unidade. Confira também páginas que aparecem na sequência de leitura sem entrada no sumário.

## Montar a edição em Markdown

- Reúna num mesmo arquivo todas as partes de um capítulo dividido entre arquivos internos do EPUB. Preserve a ordem das passagens, as quebras de cena, as notas e os destaques pertinentes. Mantenha extras independentes na posição que ocupam no volume.
- Crie um sumário em Markdown com links relativos para a abertura, os capítulos e os extras incluídos. Uma estrutura possível é `Volume 01/000. Sumário.md`, com capítulos na mesma pasta e imagens em `Volume 01/Imagens/`.
- Use links relativos para as imagens. Posicione cada imagem junto à passagem correspondente. Se ela interrompe um capítulo no EPUB, insira-a entre as mesmas passagens no Markdown. Preserve também a posição das imagens de abertura e encerramento.
- Inspecione as imagens em busca de texto. Mantenha a arte e acrescente a tradução legível em Markdown imediatamente abaixo da imagem, incluindo falas, legendas, créditos e trechos de prosa. Preserve nomes e marcas conforme as convenções da obra. Registre no acompanhamento trechos ilegíveis ou que ainda precisem de cotejo.

## Acompanhar e conferir a entrega

- Registre a cobertura da tradução separadamente do cotejo com cada fonte e da releitura em português. Identifique a primeira passagem automatizada como versão de trabalho. Se o cotejo for parcial, indique até onde foi feito e o que falta conferir.
- Compare o inventário e a sequência de leitura do EPUB com os arquivos Markdown. Confira começos e fins de capítulos, continuações, separadores, notas e extras. Compare as imagens com as passagens que as antecedem e sucedem para verificar a posição.
- Abra os links do sumário e confira se cada referência de imagem aponta para o arquivo correto. Verifique se a tradução de cada imagem com texto aparece logo abaixo dela. Use o [guia de registro e verificador](registro-e-verificador.md) para automatizar as verificações de estrutura que se repetirem.
