# Snatcher — Tradução não oficial para Português (PT-BR)

Tradução de fãs de **Snatcher** (Konami, 1988; roteiro e direção de Hideo Kojima) para o português do Brasil.

> **Status: BETA 0.1.** Esta versão traduz os diálogos e menus da versão **Mega CD (USA)**. Ainda há pendências conhecidas (veja abaixo). Relatos de erro são bem-vindos.

## O que este projeto distribui

**Somente um patch** (xdelta/BPS), que você aplica sobre a sua própria cópia legal da versão americana do Mega CD. Este repositório **não contém o jogo**, imagens, nem o texto extraído dele.

> ✅ O patch da versão Beta 0.1 está disponível na página de [releases](../../releases/tag/v0.1-beta).

## Requisitos

- Uma cópia legítima de **Snatcher (USA)** para Mega CD, dump Redump (1 `.cue` + 21 `.bin`).
- Para aplicar o patch: o **xdelta3** (instruções de uso na página do release).
- Para testes no hardware: Mega Drive com Mega EverDrive Pro (ou emulador compatível).

## Pendências conhecidas (Beta 0.1)

- Os três trechos de letra de música (SP02) continuam em inglês.
- Gráficos com texto ("NEW GAME", "LOG IN" e o teclado do JORDAN) ainda estão em inglês.
- Os textos ainda não passaram por revisão completa; podem existir falhas de tradução e de layout.

## Como relatar um problema

Abra uma [issue](../../issues/new/choose) usando o modelo "Relato de erro na tradução". Inclua a cena onde o problema aconteceu e, se possível, uma foto da tela.

## Ferramentas (`tools/`)

- `snatcher_sp.py` — extrai e insere os textos dos arquivos `SP*.BIN` e `SUBCODE.BIN` (comandos: `testar`, `extrair`, `inserir`, `marcar`, `encher`, `demo`, `previa`).
- `snatcher_iso.py` — lista e monta a imagem BIN/CUE de teste (comandos: `listar`, `montar`).
- `dis68k.py` — desmontador de 68000, usado na engenharia reversa.

Exemplo de uso (PowerShell, com a pasta `Original` contendo os arquivos extraídos):

```powershell
python tools\snatcher_sp.py inserir Original texto modificado
```

## Documentação

- `docs/glossario-ptbr.md` — decisões de tradução e padrão de termos.

## Créditos e aviso legal

**Projeto e curadoria:** Rafael "Riris" Barbosa ([@HeresAChallenger](https://github.com/HeresAChallenger)), que teve a iniciativa, define as decisões de tradução e conduz o projeto.

**Coautoria:** Claude (Anthropic), que fez a maior parte do trabalho técnico e de tradução bruta, incluindo as ferramentas de apoio.

Snatcher é uma obra de Konami e Hideo Kojima. Este é um projeto de fãs, sem fins comerciais e sem qualquer vínculo com a Konami. Não distribuímos o jogo nem arquivos derivados dele. Use o patch apenas com uma cópia legítima do jogo que você possui.
