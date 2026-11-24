# Registro estruturado e verificador

Use esta estrutura como referência ao automatizar um projeto. O [modelo inicial](../modelos/projeto/) usa Markdown. O [verificador de Re:Zero](https://github.com/lfquerobin/rezero-webnovel/tree/main/tools) é um exemplo que aplica as convenções daquela obra.

## Registro da obra

O esquema abaixo serve como ponto de partida. Re:Zero usa um esquema próprio. Os campos `capitulos` e `ocorrencias_anonimas` correspondem às unidades e às ocorrências de falante da web novel. O campo único `revisoes.fidelidade` registra o cotejo da obra de acordo com seu escopo documentado. Se houver migração, separe os cotejos por fonte somente quando o histórico comprovar o alcance de cada um.

Escolha um esquema e documente a versão. Um `projeto.json` inicial pode ser:

```json
{
  "schema": 1,
  "obra": null,
  "versao": null,
  "idioma_destino": "pt-BR",
  "unidades": [],
  "ocorrencias": [],
  "variantes_terminologicas": []
}
```

Ao cadastrar uma unidade, use um ID que continue valendo se o arquivo for renomeado. Use um caminho relativo à raiz do repositório. Registre original e intermediária em campos próprios, com idioma, referência, data de publicação e crédito quando aplicáveis. Use `null` para o que estiver ausente ou pendente. Atribua datas de revisão somente conforme o trabalho realizado.

```json
{
  "id": "V01-C01",
  "arquivo": "Volume 01/001. Capítulo 1.md",
  "fontes": {
    "original": null,
    "intermediaria": null
  },
  "cobertura": {"estado": "pendente", "escopo": null},
  "revisoes": {
    "fidelidade_original": {"estado": "pendente", "data": null, "escopo": null},
    "fidelidade_intermediaria": {"estado": "pendente", "data": null, "escopo": null},
    "naturalidade": {"estado": "pendente", "data": null, "escopo": null},
    "falantes": {"estado": "pendente", "data": null, "escopo": null},
    "formato": {"estado": "pendente", "data": null, "escopo": null}
  }
}
```

Use `cobertura` para registrar se a unidade tem tradução integral ou parcial e se o texto está em versão de trabalho. Nos campos de revisão, indique o trecho conferido de cada fonte ou por que a etapa continua aberta. Indique que o cotejo com a intermediária é inaplicável quando a tradução partir diretamente do original. Distinga etapas pendentes, concluídas, históricas e com questões em investigação. Uma ocorrência deve ter ID próprio, ID da unidade, trecho exato, tipo, motivo e fonte. Para atribuição pendente, registre também original quando disponível, candidatos, estado e próximo passo. Ao resolver, preserve a conclusão e sua evidência.

## Vistas e migração

1. Migre as unidades já existentes e as dúvidas abertas do Markdown para o registro, preservando caminhos, fontes, datas e decisões.
2. Gere `ACOMPANHAMENTO.md` e `PENDÊNCIAS.md` a partir do registro. Identifique nos dois arquivos a origem dos dados e o comando de geração. Gerar sempre os mesmos arquivos facilita a comparação no Git.
3. Compare as vistas com as informações anteriores antes de adotar a automação como fluxo padrão. Daí em diante, edite o registro quando houver mudanças e regenere as vistas.

## Verificador

Se criar `tools/verificar_projeto.py`, siga as convenções documentadas pela obra. Uma implementação pode verificar:

- Existência dos caminhos, IDs únicos e registros sem arquivos associados. Mantenha os arquivos de texto dentro da pasta da obra.
- Campos do cabeçalho, correspondência entre título e nome de arquivo, fontes cadastradas e datas válidas.
- Separadores, delimitadores de fala, rótulos repetidos e outros problemas objetivos previstos pelo formato. Dê contexto às marcações ambíguas para revisão humana.
- Correspondência entre as ocorrências de falante anônimo e o registro, incluindo repetições idênticas na mesma unidade. A identidade ocultada pela narrativa e a dúvida editorial têm tratamentos distintos.
- Variantes do glossário explicitamente cadastradas como alertas, com indicação de arquivo e trecho. A decisão de substituição depende do contexto.
- Para volumes ilustrados, destinos dos links do sumário e referências a imagens. Quando houver um inventário da edição, compare também a cobertura e a sequência registradas.
- Correspondência entre o registro e as vistas geradas.

Mantenha a conferência comum em modo de leitura. Separe a opção de regenerar vistas e limite as escritas aos arquivos gerados. Documente os comandos e a distinção entre erro, aviso e pendência editorial. Se o projeto não usar determinado cabeçalho, marcador ou separador, adapte a validação à convenção local.

Teste com exemplos artificiais de arquivos válidos, registros incompletos, caminhos divergentes, falas repetidas e vistas desatualizadas. Verifique também que a regeneração preserva os textos e que um registro vazio é tratado como um projeto em preparação. A leitura das fontes e a revisão em português continuam a cargo da revisão editorial.


## Verificador de EPUB e Markdown

Preencha o [inventário do volume](../modelos/epub/inventario-epub.json) ao lado do sumário em Markdown.

- Em `sumario`, informe o caminho do sumário em relação ao inventário. Liste as `unidades` na ordem de leitura, com o caminho de cada `markdown` relativo ao inventário.
- Em `paginas_epub`, liste os caminhos internos completos, incluindo continuações e páginas de imagem. Use a ordem do `spine` do EPUB. Declare em `paginas_de_navegacao` as páginas de índice do `spine` representadas pelo sumário Markdown.
- Em `blocos_iniciais`, informe quantos blocos Markdown separados por linhas em branco precedem o texto traduzido, incluindo o título e o cabeçalho editorial. O padrão é zero. Para as imagens, siga o [registro de inspeção](traduzir-epub.md#registrar-a-inspeção-de-cada-imagem).
- Após conferir o texto de uma divisão legítima, registre-a em `divisoes_de_paragrafo` na unidade. Por exemplo, `{"9": 2}` indica que o nono parágrafo da fonte corresponde a dois blocos em português. A numeração começa em 1, segue todas as continuações na ordem do EPUB e conta apenas os parágrafos com texto. O verificador usa a divisão para conferir a posição das imagens e medir o tamanho conjunto dos blocos.

Execute com Python 3.10 ou mais recente, da raiz do projeto principal.

```sh
python tools/verificar_epub.py "caminho/volume.epub" "caminho/Volume 02/inventario-epub.json"
```

O verificador compara o inventário com o `spine` e os sumários disponíveis, verifica os destinos dos links Markdown locais em linha e compara a ordem das imagens de cada unidade. Para a comparação de texto, conta parágrafos XHTML e blocos Markdown, descontando o cabeçalho e as traduções das imagens registradas. Quando os totais coincidem, compara a posição das imagens entre blocos e sinaliza traduções com menos de 60% do número de palavras de um parágrafo de pelo menos 20 palavras na fonte. Também aponta caracteres suspeitos e inspeções pendentes.

Execute-o em modo de leitura e use a saída para localizar os trechos a cotejar. Uma mudança legítima na divisão de parágrafos pode gerar aviso. A inspeção visual confirma o conteúdo das imagens e a comparação editorial confirma o sentido e a cobertura das passagens. Use `--estrito` na conferência da entrega para retornar 1 também se houver avisos. A saída é 0 quando os critérios do modo escolhido forem atendidos e 2 se o EPUB ou o inventário não puder ser lido.
