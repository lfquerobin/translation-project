# Registro estruturado e verificador

Use esta estrutura como referência ao automatizar um projeto. O [modelo inicial](../modelos/projeto/) usa Markdown. O [verificador de Re:Zero](https://github.com/lfquerobin/rezero-webnovel/tree/main/tools) é um exemplo que aplica as convenções daquela obra.

## Registro da obra

O exemplo histórico abaixo usa o schema central v1. Novos projetos que adotarem automação podem usar o [schema central v2](../schemas/projeto-v2.schema.json). Re:Zero usa um esquema próprio e pode manter seu verificador durante a adoção gradual. Seus campos `capitulos`, `ocorrencias_anonimas` e `revisoes.fidelidade` precisam de um mapeamento próprio com revisão do alcance de cada evidência.

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

### Revisões e vigência no schema central v2

- A unidade mantém um ID ao ser renomeada. Registre `ordem`, `tipo`, `fontes`, `edicao_trabalho` como o papel `original` ou `intermediaria`, e o histórico em ordem de inclusão. Campos desconhecidos permanecem `null` ou ausentes. Use a referência da edição de trabalho também nas evidências de naturalidade, falantes e formato para detectar mudanças nessa edição.
- Um evento de revisão tem `id`, `etapa` e `estado`. Revisões concluídas exigem `data`, `escopo: "integral"`, `hash_texto` e `evidencias`. Revisões parciais usam uma lista de intervalos em `escopo`. Registre o responsável quando conhecido. A revisão de formato usa `arquivo_conferido`. Use `motivo` ao registrar uma etapa inaplicável.
- O objeto `fonte` da revisão informa `papel`, `referencia`, `edicao` e o SHA-256 dos bytes da fonte local ou captura, quando existente. Sem captura, o estado deriva do registro editorial e da referência declarada. Uma URL não comprova a permanência do conteúdo remoto. A ferramenta nunca consulta a rede.
- `cobertura` integral e inspeções `imagens` ou `notas` concluídas usam `hash_texto`. Confirme a inaplicabilidade de cada inspeção com um motivo. Uma unidade revisada exige cotejo integral com a edição de trabalho, releitura, formato, falantes quando aplicável e ausência de dúvida bloqueante. O cotejo original continua visível mesmo quando a edição de trabalho é outra.
- Se a obra usar volumes, registre cada ID em `volumes` e associe as unidades. Liste os arquivos de conjunto, como sumário e inventário, em `arquivos_conjunto`. Após conferir o conjunto, registre a data, as evidências e o `hash_conjunto` exibido pelo status no objeto `conjunto`, sob a chave `hash`.

O SHA-256 é calculado sobre os bytes completos da versão salva, incluindo finais de linha e formatação. Mudanças de texto invalidam conservadoramente as revisões associadas. Renomear preserva os hashes de texto e exige reconferir o formato. O estado deriva da evidência mais recente de cada etapa. A restauração dos mesmos bytes pode restabelecer a vigência enquanto não houver uma invalidação explícita registrada.

```sh
python -B -m src.translation_project status --projeto "/caminho/obra" --json
python -B -m src.translation_project invalidar --projeto "/caminho/obra" --dry-run
python -B -m src.translation_project invalidar --projeto "/caminho/obra" --aplicar --saida projeto-reavaliado.json
```

A cópia produzida por `invalidar` acrescenta eventos de invalidação e mantém as evidências anteriores. A obra decide quando adotar a cópia como registro. A saída exige um nome novo dentro do projeto. A mesma regra vale para `migrar`.

## Vistas e migração

1. Migre as unidades já existentes e as dúvidas abertas do Markdown para o registro, preservando caminhos, fontes, datas e decisões.
2. Gere `ACOMPANHAMENTO.md` e `PENDÊNCIAS.md` a partir do registro. Identifique nos dois arquivos a origem dos dados e o comando de geração. Gerar sempre os mesmos arquivos facilita a comparação no Git.
3. Compare as vistas com as informações anteriores antes de adotar a automação como fluxo padrão. Daí em diante, edite o registro quando houver mudanças e regenere as vistas.

Para migrar o registro central v1, examine o mapeamento em modo de leitura. A opção explícita `--aplicar` grava uma cópia nova. A migração preserva campos locais e o objeto anterior em `revisoes_legadas`. Ela conserva o cotejo de escopo único sem atribuí-lo ao original ou à intermediária. Revise os tipos, as edições e as evidências antes de adotar a cópia.

```sh
python -B -m src.translation_project migrar --projeto "/caminho/obra" --dry-run
python -B -m src.translation_project migrar --projeto "/caminho/obra" --aplicar --saida projeto-v2.json
```

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

Preencha o [inventário do volume](../modelos/epub/inventario-epub.json) ao lado do sumário em Markdown. Consulte o [schema dos inventários](../schemas/inventario-epub.schema.json).

- Em `sumario`, informe o caminho do sumário em relação ao inventário. Liste as `unidades` na ordem de leitura, com o caminho de cada `markdown` relativo ao inventário.
- Em `paginas_epub`, liste os caminhos internos completos, incluindo continuações e páginas de imagem. Use a ordem do `spine` do EPUB. Declare em `paginas_de_navegacao` as páginas de índice do `spine` representadas pelo sumário Markdown.
- Em `blocos_iniciais`, informe quantos blocos Markdown separados por linhas em branco precedem o texto traduzido, incluindo o título e o cabeçalho editorial. O padrão é zero. Para as imagens, siga o [registro de inspeção](traduzir-epub.md#registrar-a-inspeção-de-cada-imagem).
- Após conferir o texto de uma divisão legítima, registre-a em `divisoes_de_paragrafo` na unidade. Por exemplo, `{"9": 2}` indica que o nono parágrafo da fonte corresponde a dois blocos em português. A numeração começa em 1, segue todas as continuações na ordem do EPUB e conta apenas os parágrafos com texto. O verificador usa a divisão para conferir a posição das imagens e medir o tamanho conjunto dos blocos.

Execute com Python 3.10 ou mais recente, da raiz do projeto principal.

```sh
python tools/verificar_epub.py "caminho/volume.epub" "caminho/Volume 02/inventario-epub.json"
```

O verificador compara a sequência de todas as ocorrências do `spine`, inclusive itens não lineares, com o inventário. Exclui apenas as páginas explicitamente cadastradas como navegação. Consulta o sumário nav ou NCX quando disponível. Um destino pode aparecer várias vezes, e o verificador sinaliza quando uma página do sumário corresponde a mais de uma unidade.

O parser aceita links em linha e por referência, imagens, escapes e destinos percent-encoded. A conferência ignora links em cercas de código, código inline e comentários. Valida âncoras de títulos Markdown por slug e IDs HTML quando `permitir_html` estiver habilitado. O parser cobre o subconjunto editorial documentado e não promete compatibilidade com todas as extensões ou construções multilinha do CommonMark. Recursos externos nunca são buscados.

No inventário v1, a numeração permanece restrita aos parágrafos XHTML com texto. O verificador desconta os blocos de cabeçalho e os de tradução de imagem e avisa quando há conteúdo que requer a contagem ampliada. A comparação de palavras usa 20 palavras como mínimo de origem e 60% como limiar padrão. No v1, um idioma ausente preserva a heurística anterior. Informe `metrica_palavras.idioma_fonte` para substituir o idioma do OPF, ou `metrica_palavras.habilitada: false` para desativar. Ajuste `minimo_fonte` e `proporcao_minima` no mesmo objeto. A métrica é desativada para idiomas sem contagem comparável, como o japonês.

### Alinhamento explícito no inventário v2

Use `schema: 2` e informe `alinhamento` em cada unidade. O extrator mantém eventos de texto, imagem e separador na ordem de ocorrência. Títulos, células, itens de lista e notas contam como blocos de origem. Em contêineres aninhados, o texto já atribuído a um bloco não é repetido. A leitura principal de ruby conta o texto base. A inspeção de arte SVG vetorial, mídia e texto alternativo continua editorial.

Os IDs posicionais da edição são `e1`, `e2`, … na origem e `m1`, `m2`, … no Markdown. Eles permanecem iguais em reexecuções com a mesma estrutura. Imagens e separadores ocupam posição na sequência, mas só os IDs de texto entram nos grupos. Revise o mapa quando inserir ou remover um evento. No Markdown, cada bloco é delimitado por linha em branco, e traduções de imagem seguem o campo `blocos_traducao`. A métrica do v2 é calculada por grupo quando os idiomas forem compatíveis. Sem idioma de origem declarado, ela fica desativada. Registre grupos consecutivos e justifique divisões e uniões:

```json
[
  {"origem": ["e1", "e2"], "destino": ["m1"], "justificativa": "O par de frases forma um bloco contínuo."},
  {"origem": ["e4"], "destino": ["m3", "m4"], "justificativa": "A fala e a ação ficam em blocos separados."}
]
```

Nesse exemplo, `e3` e `m2` são ocorrências da mesma imagem. O verificador compara arquivos de imagem por SHA-256. Uma conversão exige o objeto `conversao` com `metodo`, `justificativa`, `sha256_origem` e `sha256_destino`. A equivalência visual e o estado de inspeção exigem revisão editorial.

### Diagnósticos e limites

Use `--json` para receber códigos estáveis, gravidade, unidade, caminho e linha quando disponível. A execução retorna 0 se os critérios técnicos do modo escolhido forem atendidos, 1 para divergências e 2 para entrada inválida ou ilegível. Em `--estrito`, avisos e pendências também retornam 1. Use `--debug` para ver rastreamento de falhas de leitura.

O verificador limita o ZIP a 10.000 entradas, 32 MiB por entrada e 256 MiB descompactados. Ajuste com `--limite-entradas`, `--limite-bytes-entrada` e `--limite-bytes-total`. A leitura rejeita escapes da raiz, colisões portáveis, links simbólicos no ZIP e declarações XML DOCTYPE. Nenhum arquivo é extraído durante a conferência.
