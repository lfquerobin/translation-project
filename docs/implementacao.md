# Implementação do plano de evolução

## Progresso em 24/11/2026

| Fase | Estado | Evidência ou ponto de retomada |
| --- | --- | --- |
| 0 · Fundação | Concluída | Seis testes de caracterização passaram no verificador original. A matriz multiplataforma está configurada. |
| 1 · EPUB | Concluída | Interface legada, diagnósticos JSON, limites ZIP/XML e alinhamento v2 exercitados em EPUBs sintéticos. |
| 2 · Registro e revisões | Concluída | Esquemas centrais, status derivado, invalidações e migração central v1 exercitados com registros sintéticos. |
| 3 · Importação | Concluída | Descoberta, confirmação, reexecução e confronto de edições validados com EPUB sintético. |
| 4 · CLI e vistas | Concluída | Wheel e comando instalado conferidos a partir de outro diretório. Vistas e verificações cobertas por testes. |
| 5 · Glossário e vozes | Concluída | Esquemas opcionais, alertas contextuais e vistas integrados à CLI. |
| 6 · Memória | Pendente | Depende da estabilização dos registros. |
| 7 · Instruções e painel | Pendente | Preservar o guia editorial central. |
| 8 · CI e integração | Em andamento | Matriz Windows/Linux com Python 3.10 e 3.14 configurada. |

## Diagnóstico inicial

- O comando legado `python -B tools/verificar_epub.py --help` funciona no Windows com Python 3.14.7. Um inventário sem unidades é entrada inválida para um volume EPUB. O estado de projeto em preparação é um requisito separado do registro de obra.
- O verificador conta parágrafos XHTML com texto e blocos Markdown separados por linhas em branco. Ampliar esses tipos no inventário v1 alteraria a numeração editorial das divisões cadastradas.
- A leitura ZIP carece de limites e verificação de colisões. O resolvedor interno normaliza caminhos antes de verificar sua contenção. O parser Markdown legado reconhece apenas links em linha e pode interpretar exemplos em código.
- O índice atual contém Re:Zero. A descrição do snapshot no plano está desatualizada. Nenhum repositório de obra faz parte desta implementação.
- As configurações compartilháveis do Obsidian continuam disponíveis para versionamento. Arquivos locais de IDE e estado de workspace ficam ignorados.

## Fase 0

- Adicionados `.gitignore`, `.gitattributes`, `pyproject.toml`, fixtures e testes `unittest` sem dependências externas. A política de atributo se restringe ao repositório central.
- `python -B -m unittest discover -s tests -v` passou com seis testes no Windows, Python 3.14.7, antes de alterar o verificador. Foram exercitados códigos 0, 1 e 2, nomes NFC e NFD, espaços, UTF-8, CRLF/LF e ausência de escritas.
- `git diff --check` passou. A matriz da fase 8 contempla Windows/Linux com Python 3.10 e 3.14. A execução local foi no Windows. O verificador legado não detectava colisões e a defesa será exercitada na fase 1.

## Fase 1

- `src/translation_project/epub.py` lê manifesto, spine, nav/NCX e conteúdo em ordem. Aplica limites do ZIP, rejeita colisões e XML com DOCTYPE e mantém itens não lineares no spine. `markdown.py` reconhece links e imagens no subconjunto editorial, com HTML opcional.
- `tools/verificar_epub.py` continua como entrada do verificador. `verificador_epub.py` preserva os parágrafos numerados do v1, oferece alinhamento explícito v2, registra diagnósticos estáveis e confere bytes das imagens. Os IDs posicionais de alinhamento duram enquanto a estrutura da unidade estiver estável.
- `python -B -m unittest discover -s tests -v` passou com 14 testes. Os oito novos testes incluem capítulos em múltiplas páginas, imagens isoladas e repetidas, união/divisão, capa e extra, listas, tabelas, ruby, notas, navegação divergente, links por referência, japonês, colisões Unicode, traversal, limite ZIP e rejeição de DTD. Os seis testes legados continuam passando.
- A documentação em `docs/registro-e-verificador.md` descreve o subconjunto Markdown. Variantes de extensões, mídia sem extração e revisão visual exigem conferência manual. A matriz remota permanece sem execução nesta sessão.

## Fase 2

- `registro.py` valida caminhos, IDs, vínculos, estados, escopo e evidências. Calcula o estado por unidade e volume em leitura. SHA-256 cobre os bytes salvos e as fontes locais declaradas. Uma renomeação conserva evidência de conteúdo e invalida a conferência de formato. A validação de conjunto inclui os arquivos que a obra cadastrar.
- `migracao.py` preserva campos do schema central v1, registra revisões antigas como históricas e mantém cotejo de escopo incerto sem desdobrar o campo legado. O registro de invalidações acrescenta eventos sem modificar a evidência anterior. A CLI de leitura é `python -m src.translation_project`. As operações de escrita exigem uma cópia nova explícita.
- A primeira tentativa de criação exclusiva por hard link não funcionou na sandbox do Windows. A publicação da cópia agora usa renomeação sem substituição no Windows e hard link no Linux. O teste confirma que a cópia existente e o registro original ficam intactos.
- `python -B -m unittest discover -s tests -q` passou com 22 testes. Os oito novos casos incluem restauração, renomeação, fonte trocada, revisão parcial, motivo para inaplicabilidade, histórico de migração, projeto e volume vazios e alteração de sumário.
- Os contratos em `schemas/` descrevem inventários v1/v2 e registro de projeto v2. A validação semântica é independente de dependências de schema. A migração automática se limita ao formato central. O schema do glossário entra com a fase 5. O cálculo usa hash bruto e não tenta inferir equivalência semântica.

## Fase 3

- `importacao.py` usa o manifesto, nav e spine para descobrir ocorrências e sugerir agrupamentos. Confirmações são vinculadas ao SHA-256 da edição e precisam cobrir o spine integralmente em ordem. Capas em formato de imagem entram na extração de eventos.
- `importar` e `inventario gerar` têm dry-run por padrão. A opção de escrita pode criar proposta, inventário v2, imagens e esqueleto vazio de tradução. A criação é exclusiva por arquivo, com conferência prévia de colisões e reaproveitamento de bytes idênticos. Se houver falha de disco durante a operação, a reexecução reaproveita o que foi gravado. A gravação do inventário vem por último.
- `python -B -m unittest discover -s tests -q` passou com 25 testes. Os novos testes cobrem repetição de páginas e imagens, capa, extra não linear, navegação, reexecução, preservação de edição manual, diagnóstico de registros incompletos e comparação de edições. A verificação do esqueleto confirma que ele permanece pendente de tradução e alinhamento.
- `docs/traduzir-epub.md` documenta confirmação e reexecução. O inventário registra inspeções pendentes e nunca preenche texto traduzido ou atribui equivalência editorial.

## Fase 4

- `pyproject.toml` empacota os modelos e disponibiliza `traducao`. `python -B -m src.translation_project` continua disponível sem instalação ou rede. `init` é local e preserva arquivos existentes. `verificar` confere convenções configuráveis, links, cabeçalhos, datas, rótulos, multiplicidade de falas, arquivos órfãos e vistas desatualizadas.
- `vistas.py` protege as vistas editadas à mão com identificação e hash do conteúdo gerado. As substituições são atômicas por arquivo. A validação de entrega combina revisão registrada, conferência de conjunto e EPUB quando configurado.
- A suíte passou com 29 testes. O teste inicial da wheel instalada com `--target` não encontrou os modelos porque os caminhos no RECORD apontavam para fora do diretório alvo. A localização inclui agora o diretório de dados da instalação por alvo. Depois de reconstruir e instalar a wheel, `traducao init --estruturado --dry-run` funcionou de outro diretório.
- Comandos e convenções foram atualizados nos guias existentes. Projetos sem registro estruturado mantêm os modelos Markdown e suas ferramentas locais.

## Fase 5

- `editorial.py` valida glossário e vozes optativos, com IDs e escopo. Alertas usam palavras inteiras, flexões registradas, contexto de linha, edição e intervalo narrativo. A busca de termos alterados retorna ocorrências candidatas e deixa o texto intacto.
- O glossário e as vozes usam os schemas v1 de `schemas/`. A geração optativa de `GLOSSÁRIO.md` e `VOZES.md` preserva referências e histórico. Os dados canônicos permanecem em JSON, e a proteção de vistas impede perda de notas em arquivos manuais.
- A suíte passou com 33 testes. Os quatro novos casos exercitam contexto, flexão, Unicode NFD, citações, versões anteriores de termos, homônimas, referências de exemplos e preservação de notas e histórico. A fase 4 já exercita falas idênticas tratadas como ocorrências distintas.
- A validação terminológica é uma busca configurável e exige leitura de contexto. Ela não infere flexões ou falantes e não aplica substituições.
