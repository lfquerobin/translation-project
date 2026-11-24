# Implementação do plano de evolução

## Progresso em 24/11/2026

| Fase | Estado | Evidência ou ponto de retomada |
| --- | --- | --- |
| 0 · Fundação | Concluída | Seis testes de caracterização passaram no verificador original. A matriz multiplataforma está configurada. |
| 1 · EPUB | Concluída | Interface legada, diagnósticos JSON, limites ZIP/XML e alinhamento v2 exercitados em EPUBs sintéticos. |
| 2 · Registro e revisões | Pendente | Implementar status derivado e migração conservadora a partir do registro central. |
| 3 · Importação | Pendente | Depende de descoberta EPUB reutilizável. |
| 4 · CLI e vistas | Pendente | Depende do contrato do registro e da importação. |
| 5 · Glossário e vozes | Pendente | Depende do registro e das vistas. |
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
