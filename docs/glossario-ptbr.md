# Glossário e padrão de tradução — Snatcher PT-BR

Status: **v1.3 (14/11/2026)**. Decisões aplicadas; itens em aberto são marcados com ❓.

## 1. Termos do universo
| Termo original | Decisão | Observação |
|---|---|---|
| Snatcher | **Snatcher** (mantido) | No texto, plural "SNATCHERS" |
| JUNKER | **JUNKER** (mantido, sigla) | Plural **os JUNKERs**; "QG" para Headquarters |
| bioroid | **bioroide** | "replicante" só na expansão da sigla |
| Metal Gear | **Metal Gear** | Nome próprio |
| navigator | **navegador** | Robô assistente do JUNKER |
| runner | **runner** (mantido) | Investigador JUNKER de campo |
| Catastrophe | **Catástrofe** | |
| Turbocycle | **Turbocycle** (masculino: "o Turbocycle") | |
| Junker's Eye | **Junker's Eye** (mantido) | Sistema de treino |
| blaster / Justifier | **blaster** / **JUSTIFIER** | |
| JUNKER I.D. | **ID JUNKER** | |
| JORDAN | **JORDAN** | Nomes de busca sem acento, maiúsculos |
| Fact File | **Ficha** | Telas do JORDAN |
| bounty hunter | **caçador de recompensas** | |

### Sigla JUNKER ✅
Tradução adaptada, mantendo as letras J-U-N-K-E-R:

> **J**unta **U**ltrassecreta de / **N**eo **K**obe para **E**liminação / de **R**eplicantes.

O K vem de **K**obe; "Replicantes" é homenagem deliberada a Blade Runner e só aparece na expansão da sigla. No resto do jogo, usa-se "bioroide".

### Sigla JORDAN ✅
**JUNKER On-line: Rede de Dados e Acesso Nacional** (J-O-R-D-A-N: **J**UNKER, **O**n-line, **R**ede, **D**ados, **A**cesso, **N**acional).

## 2. Tratamento entre personagens
- "você" como padrão.
- "senhor/senhora" só para subordinados, atendentes, porteiros e P.A.
- Títulos abreviados: Sr. Seed, Sr. Togo, Srta. Hayasaka.
- Gillian ↔ Jamie e Mika: informal. Gillian → Chefe: "senhor".

## 3. Comandos de menu (máx. 32 caracteres; infinitivo, maiúsculas)
Não unificar strings de menu: o jogo identifica o item pela posição/offset.
- "ABOUT X" → **SOBRE X**. "SAVE 1–4" → **ARQUIVO 1–4**. "USE X" → **USAR X**. VIDEOPHONE → **VIDEOFONE**.
- ❓ Conferir "USE LIGHT" (em fala: **USAR LUZ**), IR/MOVER, ABRIR/FECHAR nos demais textos.

## 4. Nomes de falantes (máx. 24 caracteres)
| Original | Decisão |
|---|---|
| Chief | Chefe |
| Driver | Motorista |
| Employee | Funcionário |
| Man / Woman | Homem / Mulher |
| Passerby | **Pedestre** |
| P.A. | **Sistema de som** |
| Doorman | Porteiro |
| Customer | Cliente |
| Parrot | Papagaio |

Nomes próprios (Gillian, Mika, Jamie, Harry, Napoleon, Katrina, Metal Gear, Random etc.) são mantidos.

## 5. Estilo
- Tom noir e ficção científica, coloquial sem gíria datada; humor de Kojima preservado.
- Referências (Contra, Castlevania etc.): manter nomes originais.
- Piadas intraduzíveis: adaptar o efeito.

## 6. Regras técnicas (validadas no hardware)
- Diálogo: janela de 4 linhas; textos mais longos paginam sozinhos. Até **33 caracteres por linha**.
- JORDAN: até 7 linhas de ~26 caracteres. Menu: até 32. Nome de falante: até 24.
- Acentos suportados: `áàâãéêíóôõúç ÁÀÂÃÉÊÍÓÔÕÚÇ`.
- Nomes pesquisáveis no JORDAN: sem acento, maiúsculos (teclado só A–Z, `-`, `.`, `'`).
- Não traduzir: `SNATCHER_01`–`SNATCHER_04` (nomes de save na BRAM) e SP01 (debug).
- Códigos de controle (`{BR}`, `{PAG}`, `{TECLA1/2/3}`, `{C0}`–`{C6}`) são preservados.
