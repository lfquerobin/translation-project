# Guia para projetos de tradução literária

O objetivo é produzir traduções naturais em português brasileiro, preservando o sentido, a voz, o ritmo, a intensidade e as ambiguidades da obra. Use este guia ao criar um projeto e consulte, em cada trabalho, as instruções e referências específicas do seu repositório.

## Criar um projeto

1. Use um repositório próprio para cada obra ou versão. Siga o [passo a passo de criação](docs/criar-projeto.md) e copie os [modelos de arquivos](modelos/projeto/) para a raiz do repositório da obra.
2. Prepare `README.md` e `AGENTS.md` para definir escopo e convenções, `LINKS.md` para as fontes, `GLOSSÁRIO.md` e `VOZES.md` para as decisões editoriais e `ACOMPANHAMENTO.md` e `PENDÊNCIAS.md` para registrar o trabalho. Preencha os dados verificáveis e mantenha em aberto o que ainda depende da edição ou da fonte.
3. Antes de salvar a primeira unidade, confirme a edição, as fontes e as convenções de arquivo, cabeçalho, diálogo, notas, estado e revisão. Registre as escolhas no repositório da obra. Se já houver registros estruturados, use a fonte de verdade definida pela obra.
4. Adicione o link, a versão e a situação do repositório no [índice de projetos](projetos/README.md).

Use `Referências/` conforme houver material auxiliar local. Para automatizar o acompanhamento, consulte o [guia de registro e verificador](docs/registro-e-verificador.md).

Para obras em EPUB com entrega em Markdown, siga o [guia de preparação do volume e preservação das ilustrações](docs/traduzir-epub.md).

## Preparar a tradução

- Confira se o original e qualquer fonte intermediária correspondem à mesma versão e unidade da obra. Compare títulos, numeração, edição e começo e fim quando houver dúvida. Trate índices de erros e guias de outras versões como referências para investigar passagens.
- Leia as fontes inteiras antes de traduzir. Consulte o capítulo anterior quando houver retomada, além do glossário, das referências de voz e das dúvidas já registradas. Selecione o contexto pertinente à cena, ao interlocutor e ao que as personagens e o leitor sabem naquele ponto.
- Use o original para conferir sentido, sujeitos, ações, referentes, negações, quantificadores, grau de certeza, causalidade e ordem temporal. Confira a fonte intermediária quando for utilizada. Se uma fonte necessária estiver inacessível, registre o que ficou sem cotejo e mantenha a etapa correspondente em aberto.
- Quando o projeto acompanhar um manual ou uma fonte online, compare o texto da obra e as notas. Desconsidere alterações apenas de navegação, estilos, scripts, espaços ou elementos automáticos. Quando houver mudança de conteúdo relevante, preserve uma captura datada ou outro registro verificável e identifique as passagens afetadas.

## Traduzir prosa e diálogos

- Reformule a sintaxe quando o português pedir, conferindo novamente o sentido. Preserve repetições intencionais, pausas, hesitações, interrupções, intensidade e grau de formalidade. Use as referências de voz como exemplos de contexto. Evite acrescentar gíria, regionalismo, palavrão ou solenidade sem apoio na fonte.
- Preserve o ponto de vista da cena. Explicite um referente apenas quando houver evidência e a explicitação mantiver as possibilidades que a obra deixa em aberto. Preserve motivos, identidades e revelações para o momento em que aparecem no texto.
- Confira quem fala pela narração, pelas ações, pelos referentes e pelo diálogo completo. Alternância, pronomes e cacoetes são pistas auxiliares. Diferencie fala pronunciada, pensamento, citação e narração. Ao rotular falas, conserve as citações internas e respeite as falas incorporadas à narração.
- No registro da obra, diferencie o anonimato intencional de uma atribuição ainda incerta. Para uma dúvida editorial, anote o trecho exato, o original quando disponível, os candidatos, o motivo, a fonte e o que falta confirmar. Use no texto a marcação definida pela obra e mantenha as hipóteses no registro.
- Preserve e traduza as notas da fonte. Registre observações novas fora da narrativa, nos arquivos editoriais do projeto, salvo instrução do usuário.

## Instruções e retomada

Leia o guia central e o `AGENTS.md` da obra. Use as convenções locais para edição, fontes, formato e registros, preservando as exigências de fidelidade, clareza de evidência e aprovação deste guia.

| Tarefa | Leitura antes de começar |
| --- | --- |
| Criar obra ou mudar convenções | [Criação de projeto](docs/criar-projeto.md) e modelos aplicáveis. |
| Traduzir ou revisar | Unidade e fontes integrais, `LINKS.md`, glossário, vozes, pendências e contexto anterior relevante. |
| Preparar volume EPUB | [Guia de EPUB](docs/traduzir-epub.md), inventário e convenções de imagens. |
| Migrar, validar, gerar vistas ou buscar memória | [Guia de registro e verificador](docs/registro-e-verificador.md) e registros canônicos da obra. |

Ao retomar, identifique a unidade e a edição, compare o hash salvo com o registrado quando houver e confira a fonte e o estado de cada etapa. Use apenas o contexto disponível no ponto narrativo. Só reutilize uma revisão anterior quando a evidência indicar o escopo e sua vigência. Antes de editar uma passagem em revisão, localize a evidência e, depois da edição, confira a passagem integral. Siga as passadas abaixo e registre data, escopo e, quando o formato comportar, hash das etapas efetivamente realizadas.

## Traduzir e aprovar por capítulo

Trate cada capítulo como uma unidade de tradução e aprovação. Prólogos, epílogos e extras passam pelo mesmo fluxo, conforme o conteúdo e a fonte de cada um. Se um capítulo estiver dividido entre arquivos do EPUB, reúna todas as partes antes do cotejo. Uma primeira passagem automatizada em lote pode servir de rascunho. Retome cada capítulo individualmente para traduzir ou revisar e registre o resultado por unidade.

Desde a primeira redação editorial, trabalhe cada unidade para entrega em versão final, com atenção à precisão do sentido, à voz, ao ritmo e à naturalidade. Reserve a indicação de versão final para a unidade que concluiu todas as etapas pela edição de trabalho. Registre separadamente o alcance do cotejo com o original.

1. **Preparação e tradução.** Localize o capítulo inteiro na edição de trabalho, incluindo as continuações, notas, imagens e separadores. Leia a fonte e produza uma versão em português que cubra toda a unidade.
2. **Fidelidade e cobertura.** Faça uma passada separada pela fonte, do início ao fim do capítulo, comparando parágrafos, falas, notas e quebras de cena. Procure saltos de parágrafo, frases cortadas, duplicações e alterações de sentido. Confira nomes, tratamentos, negações, números, agentes e ordem dos acontecimentos. Se uma passagem foi dividida ou reunida no português, confira todas as frases correspondentes. Registre separadamente o alcance do cotejo com cada fonte.
3. **Naturalidade.** Leia o português continuamente, com a fonte fechada, verificando ritmo, transições, clareza, registro e voz. Depois, coteje as passagens reformuladas para confirmar o sentido. Dê atenção a falas curtas, gritos, interrupções e mudanças de falante.
4. **Conferência da versão salva.** Revise cabeçalho, formatação, nomes, diálogos, notas e posição das imagens. Execute o verificador, quando houver, e investigue cada aviso da unidade. Registre a evidência de diferenças legítimas, como dividir a fala e a narração em parágrafos separados.

Antes de corrigir uma passagem, confira a redação vigente e localize a evidência na fonte ou na cena. Diferencie um problema demonstrável de uma alternativa plausível. Edite apenas o necessário e confira a passagem inteira após o ajuste. Em revisão em lote, confirme que o texto ainda é o mesmo que foi analisado antes de aplicar a correção.

## Registrar e entregar

- Marque uma unidade como revisada pela edição de trabalho depois de conferir sua cobertura integral, concluir o cotejo com essa edição, reler o português e registrar a conferência da versão salva. Indique separadamente o que foi cotejado com o original e o que segue pendente. Quando uma dúvida puder alterar o sentido ou a cobertura, mantenha a etapa correspondente aberta.
- Entregue um volume como revisado somente depois de conferir no acompanhamento todas as unidades do volume e verificar o conjunto salvo, incluindo sumário, imagens e extras. Se houver unidades em versão de trabalho, identifique o volume e essas unidades como versão de trabalho.
- Registre decisões reutilizáveis com o termo no original, a forma adotada, o contexto, a versão, a unidade da obra e uma referência verificável. Distinga erro da fonte intermediária confirmado pelo original, adaptação deliberada e interpretação incerta. Ao mudar uma decisão do glossário, localize as passagens afetadas e confira o impacto no contexto.
- Registre a cobertura da tradução, o cotejo com o original, o cotejo com a intermediária quando houver e a releitura em português como etapas distintas. Identifique a primeira passagem automatizada como versão de trabalho. Informe o trecho conferido quando o cotejo for parcial.
- Registre somente revisões realizadas, com data e escopo. Preserve o histórico ao registrar trabalho anterior. Coteje os trechos alterados após mudanças de conteúdo; alterações extensas pedem nova revisão integral. Após mudar a apresentação, verifique se a releitura contínua da versão final ainda está pendente.
- Salve o texto integral no formato da obra. Confira no cabeçalho o título, o link, a data de publicação e o crédito da fonte usada. Indique dados ausentes com precisão e preserve as marcações pertinentes no texto e no nome do arquivo.
- Execute o verificador da obra, quando houver, e confira os arquivos gerados. Use alertas automáticos para localizar problemas objetivos. A confirmação de sentido, voz, cobertura e falantes exige leitura. Na entrega, indique o arquivo salvo, as correções relevantes e as dúvidas ou limitações que permanecerem.
- Ao concluir uma alteração, faça um commit das mudanças no repositório do projeto correspondente. Se o trabalho afetar mais de um projeto, faça commits separados em cada repositório. Siga o fluxo autorizado de sincronização e confira o resultado do envio antes de declará-lo concluído.

## Referência de aplicação

O projeto de Re:Zero mostra como aplicar essas práticas com uma web novel em japonês, uma fonte intermediária em inglês e revisões em português brasileiro. As fontes, o manual de referência, as regras de diálogos e os marcadores de arquivo pertencem ao projeto da obra. [Repositório de Re:Zero](https://github.com/lfquerobin/rezero-webnovel)
