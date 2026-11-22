# Criar um projeto de tradução

Use um repositório próprio para cada obra ou versão em trabalho. O [guia editorial](../AGENTS.md) orienta a tradução e a revisão. Esta página descreve a estrutura inicial e o que registrar em cada arquivo.

## 1. Preparar o repositório

1. Crie ou clone o repositório da obra. Copie os arquivos de [modelos/projeto](../modelos/projeto/) para a raiz dele, mantendo os nomes. Preencha os campos que já podem ser confirmados e indique os que estão a definir.
2. Identifique a edição ou versão, o idioma de origem e o idioma de destino. Registre a fonte original e, se usada, a intermediária em `LINKS.md`. Uma obra pode ficar em preparação até que essas fontes sejam definidas.
3. No `AGENTS.md` local, mantenha o link para o guia geral e escreva as convenções da obra. Registre a divisão dos textos, os nomes dos arquivos, o cabeçalho, as marcas de diálogo e a forma de indicar status e pendências.
4. Adicione a obra ao [índice do projeto principal](../projetos/README.md), com o link do repositório, a versão quando conhecida e a situação atual.

## 2. Arquivos iniciais

| Arquivo | Conteúdo mínimo | Quando atualizar |
| --- | --- | --- |
| `README.md` | Obra, versão ou edição, idiomas, situação e links para as instruções e os registros da obra. Se houver ferramenta, indique o comando e de onde deve ser executado. | Ao decidir a edição, publicar unidades ou mudar a estrutura. |
| `AGENTS.md` | Link e instrução explícita para ler o guia geral. Convenções de títulos, caminhos, cabeçalhos, diálogos, pensamentos, separadores, notas, status e revisão da obra. | Ao definir uma convenção ou mudar o fluxo editorial. |
| `LINKS.md` | Fontes originais, intermediárias e auxiliares, com idioma, edição, crédito quando conhecido, escopo e limites de uso. | Ao confirmar fontes, trocar links ou atualizar referências. |
| `GLOSSÁRIO.md` | Termo original, forma adotada, contexto, versão ou unidade, fonte e situação da decisão. Se uma escolha mudar, registre a anterior, o motivo e as unidades afetadas. | Ao confirmar, corrigir ou deixar em aberto uma decisão reutilizável. |
| `VOZES.md` | Exemplos contextualizados por personagem ou voz narrativa, com interlocutor, situação, original e tradução adotada. Distinga exemplos conferidos de observações auxiliares. | Ao confirmar um padrão de fala ou ajustar um exemplo. |
| `ACOMPANHAMENTO.md` | Uma entrada por unidade, com caminho, fontes e estados de cobertura, cotejo com cada fonte, naturalidade, falantes quando houver e formato. Registre data e escopo das etapas realizadas. | Ao adicionar, revisar ou renomear uma unidade. |
| `PENDÊNCIAS.md` | Um registro por ocorrência, com unidade, trecho, motivo, fonte e próximo passo. Para falante incerto, inclua original e candidatos. Registre anonimato narrativo separadamente. | Ao abrir, investigar ou resolver uma dúvida. Preserve a evidência da resolução. |

As tabelas podem começar vazias. Uma unidade futura só deve constar como traduzida ou revisada depois da etapa correspondente.

## 3. Organizar os textos e referências

- Escolha pastas que representem a divisão real da obra. Uma light novel pode usar `Volume 01/`, e uma web novel pode usar `Arco 01/`. Crie pastas quando houver material para salvar.
- Defina como a numeração e os marcadores aparecem nos nomes dos arquivos e o que significam. Guarde o estado de revisão no acompanhamento. Use no título o que foi confirmado na fonte e preserve suas aspas e pontuação, observadas as restrições do sistema de arquivos.
- Antes do corpo, registre o título, o link da fonte usada, a data de publicação e o crédito. Distingua autor, tradutor e responsável pela postagem. Se a fonte omitir data ou crédito, indique a ausência. Se a obra usar uma fonte intermediária, identifique seu idioma no crédito.
- Use `Referências/` quando houver capturas ou materiais auxiliares locais. Documente procedência, data, versão, conteúdo e limites de uso num README. Ao salvar capturas, conserve as anteriores e indique a mais recente em `LINKS.md`. Respeite as condições de uso ao decidir o que guardar ou publicar.

Um cabeçalho em Markdown pode seguir este formato. Use os dados reais da unidade e ajuste as convenções locais conforme a obra.

```markdown
**Título: <título confirmado>**
**Link: <link da fonte usada>**
**Data de publicação: <data da fonte ou indicação de ausência>**
**Traduzido por: <crédito da fonte e idioma, quando necessário>**
```

Para edições em EPUB, consulte o [guia de conversão para Markdown](traduzir-epub.md) para catalogar o volume e preservar a sequência de leitura e as imagens.

## 4. Adotar automação quando for útil

O modelo inicial usa Markdown como registro de trabalho. Se o volume de capítulos ou o número de revisões justificar automação, escolha um registro estruturado como fonte de verdade e gere as vistas de acompanhamento e pendências a partir dele. O [guia de registro e verificador](registro-e-verificador.md) mostra a estrutura e as verificações sugeridas.

## Conferência antes da primeira entrega

- A edição e as fontes da unidade foram identificadas e registradas.
- As convenções locais estão concretas o suficiente para salvar e conferir a unidade.
- O texto integral foi salvo e seu caminho está no acompanhamento.
- As revisões e pendências refletem o trabalho real. Se algum cotejo ficou pendente, a entrega identifica a fonte ou o trecho indisponível.
- Os links locais abrem. Se houver vistas geradas, elas conferem com o registro. A sincronização segue o fluxo autorizado para o repositório da obra.
