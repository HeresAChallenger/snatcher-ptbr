#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snatcher_sp.py (v5) — Extrator/insersor de texto dos arquivos SP*.BIN
do Snatcher (Mega CD, versão USA).

Projeto: Tradução Snatcher PT-BR

Uso:
  python snatcher_sp.py testar   <pasta_original>
  python snatcher_sp.py extrair  <pasta_original> <pasta_texto>
  python snatcher_sp.py inserir  <pasta_original> <pasta_texto> <pasta_saida>
  python snatcher_sp.py marcar   <pasta_original> <pasta_saida>
  python snatcher_sp.py encher   <arquivo_sp> <arquivo_saida> [bytes_livres]
  python snatcher_sp.py demo     <pasta_texto>
  python snatcher_sp.py previa   <pasta_original> <arquivo.png>   (precisa do Pillow)

ACENTOS (v4): o texto em <PT> pode usar á à â ã é ê í ó ô õ ú ç (e maiúsculas).
A fonte do jogo (8x8, largura variável) fica no SUBCODE.BIN e só tem 102
caracteres; o "inserir" grava uma cópia ampliada da fonte no fim do SUBCODE.BIN
(com 24 letras acentuadas, códigos 0x86-0x9D) e aponta o jogo para ela.
"demo" coloca algumas frases de teste com acentos no SP06.txt.

NOMES (v5): os nomes de quem fala ("Mika", "Chief"...) ficam no SUBCODE.BIN.
O "extrair" gera também NOMES.txt (mesmo formato dos SP); o "inserir" grava
os nomes traduzidos de volta. Máximo de 24 caracteres por nome.

Formato ORIGINAL do SP*.BIN:
  0x0000 .. fim do código   bytecode do script
  ...    .. 0x37FF          preenchimento 0xFF (espaço desperdiçado)
  0x3800 .. fim             bloco de texto; cada string termina em 0xFF

Formato COMPACTO (gerado por "inserir", v3):
  O texto começa logo depois do código, aproveitando o espaço vazio.
  Como o jogo original procura o texto num endereço fixo ($1E000), o
  "inserir" também gera um SUBCODE.BIN modificado: nos 4 pontos em que o
  jogo usava o endereço fixo, ele passa a LER o endereço do próprio arquivo
  SP (4 bytes guardados no offset 0x37FC). Por isso:
    - "inserir" sempre gera os 38 SP + SUBCODE.BIN, que só funcionam JUNTOS;
    - nunca misture SP compacto com SUBCODE original (nem o contrário).

Os ponteiros são achados lendo o bytecode instrução por instrução, com a
tabela de comandos do próprio jogo (SUBCODE.BIN, endereço $16CDC).

Limites impostos pelo jogo:
  - o SP é carregado em $1A800 e o programa da cena em $28000
    -> o arquivo não pode passar de 0xD800 (55.296) bytes (27 setores, que
       é também o espaço reservado para cada SP no CD);
  - itens de menu (comando 38) são lidos com índice de 16 bits COM sinal
    -> precisam ficar a menos de 0x8000 bytes do início do texto;
  - itens de menu são copiados para um buffer de 32 caracteres.
"""
import re
import sys
from pathlib import Path

BASE = 0x3800
SETOR = 2048
TAM_MAX = 0xD800       # $28000 - $1A800
MENU_MAX_OFFSET = 0x8000
MENU_MAX_CHARS = 32

# Tabela de comandos do script (tipo dos 3 operandos), copiada de SUBCODE.BIN.
# Tipos: 0/7 = nada; 4 = outro comando aninhado; 8 = salto (2 bytes logo após
# o comando); 2 = PONTEIRO DE TEXTO (2 bytes); 1,3,5,6 = valor de 2 bytes.
TAB = [
    (4, 0, 0), (4, 1, 0), (1, 3, 0), (1, 1, 0), (6, 0, 0), (6, 0, 0), (4, 4, 0), (4, 1, 0),
    (1, 4, 0), (1, 1, 0), (6, 0, 0), (4, 0, 0), (5, 7, 0), (6, 0, 0), (1, 0, 0), (6, 0, 0),
    (4, 5, 0), (4, 3, 0), (1, 3, 0), (1, 0, 0), (1, 0, 0), (3, 0, 0), (1, 3, 0), (1, 3, 0),
    (4, 4, 8), (1, 4, 8), (4, 4, 0), (1, 4, 0), (1, 3, 0), (1, 4, 0), (3, 3, 0), (3, 4, 0),
    (3, 2, 0), (6, 5, 0), (6, 3, 0), (6, 6, 0), (6, 4, 0), (4, 4, 0), (4, 8, 0), (4, 7, 0),
    (4, 3, 0), (1, 3, 0), (1, 3, 0), (5, 0, 0), (4, 0, 0), (0, 0, 0), (4, 0, 0), (1, 0, 0),
    (4, 0, 0), (4, 4, 0), (4, 1, 0), (1, 1, 0), (3, 4, 0), (3, 7, 0), (7, 4, 0), (7, 7, 0),
    (2, 4, 0), (7, 0, 0), (7, 0, 0), (5, 0, 0), (3, 0, 0), (6, 0, 0), (1, 4, 0), (1, 4, 0),
    (1, 4, 0), (6, 0, 0), (4, 0, 0), (4, 0, 0), (2, 0, 0), (6, 0, 0), (7, 0, 0), (7, 0, 0),
    (7, 0, 0), (7, 0, 0), (3, 0, 0),
]

CARGA_SP = 0x1A800     # endereço de memória onde o jogo carrega o SP
SLOT = 0x37FC          # offset (no SP) do ponteiro para o início do texto
# Pontos do SUBCODE.BIN que usam o endereço fixo do texto ($1E000):
#   (offset no arquivo, bytes originais, bytes novos)
#   lea ($1E000).l,An  ->  movea.l ($1DFFC).l,An   (mesmo tamanho)
_END_SLOT = (CARGA_SP + SLOT).to_bytes(4, "big")
PATCH_SUBCODE = [
    (0x3ACE, bytes.fromhex("41f90001e000"), b"\x20\x79" + _END_SLOT),
    (0x3F24, bytes.fromhex("41f90001e000"), b"\x20\x79" + _END_SLOT),
    (0x4704, bytes.fromhex("43f90001e000"), b"\x22\x79" + _END_SLOT),
    (0x66D0, bytes.fromhex("43f90001e000"), b"\x22\x79" + _END_SLOT),
]

# Códigos de controle -> etiquetas legíveis no arquivo de texto
# (confirmados no código do jogo, rotinas $13AD0 e $13BC8)
CODIGOS = {
    0xF2: "{BR}",       # quebra de linha
    0xF6: "{PAG}",      # nova página
    0xF4: "{F4}",       # liga um modo de exibição (efeito a confirmar)
    0xEC: "{TECLA1}",   # nome de botão (A/B/C conforme a configuração do controle)
    0xEE: "{TECLA2}",
    0xF0: "{TECLA3}",
    0xF8: "{C0}",       # F8-FE = troca a cor do texto para a cor 0-6
    0xF9: "{C1}",       # cor normal das falas
    0xFA: "{C2}",
    0xFB: "{C3}",       # destaque (vermelho) nas falas
    0xFC: "{C4}",
    0xFD: "{C5}",
    0xFE: "{C6}",       # cor normal do JORDAN
}
ETIQUETAS = {v: k for k, v in CODIGOS.items()}
# nomes usados nas versões antigas da ferramenta (ainda aceitos na leitura)
ETIQUETAS.update({"{BTN}": 0xF9, "{COR0}": 0xFE, "{COR1}": 0xFA, "{COR2}": 0xFC})

# ---------------------------------------------------------------- fonte
# Letras acentuadas: ocupam os códigos 0x86, 0x87, ... (o jogo desenha o
# glifo de número "código - 0x20"; a fonte original vai até o código 0x85).
ACENTUADAS = "áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ"
PRIMEIRO_CODIGO = 0x86
MAPA_EXTRA = {ch: PRIMEIRO_CODIGO + i for i, ch in enumerate(ACENTUADAS)}

FONTE_OFF, FONTE_GLIFOS = 0x777C, 102     # SUBCODE.BIN: glifos 8x8 ($14B7C)
LARG_OFF = 0x7AAC                          # SUBCODE.BIN: larguras ($14EAC)
SUB_CARGA = 0xD400                         # endereço de carga do SUBCODE.BIN
SUB_TAM_ORIG = 53110
SUB_TAM_MAX = CARGA_SP - SUB_CARGA         # não pode invadir a área do SP

_BASE_LETRA = dict(zip(ACENTUADAS, "aaaaeeiooouc" + "AAAAEEIOOOUC"))
_TIPO = dict(zip(ACENTUADAS, ["agudo", "grave", "circ", "til", "agudo", "circ", "agudo",
                              "agudo", "circ", "til", "agudo", "cedilha"] * 2))
# coluna central de cada letra-base (0 = pixel mais à esquerda)
_CENTRO = {"a": 2, "e": 2, "i": 1, "o": 2, "u": 2, "c": 2,
           "A": 3, "E": 3, "I": 2, "O": 3, "U": 3, "C": 3}
# maiúsculas: linhas (das 7) retiradas para abrir espaço para o acento.
# O "A" perde 3 linhas: como termina em ponta, precisa de uma linha vazia
# entre a letra e o acento, senão o acento se confunde com a ponta.
_CORTA = {"A": (1, 3, 5), "E": (2, 4), "I": (2, 3), "O": (3, 4), "U": (2, 3), "C": (3, 4)}
# desenho dos acentos: (linha, coluna em relação ao centro)
_ACENTO = {
    "agudo": [(0, 1), (1, 0)],
    "grave": [(0, -1), (1, 0)],
    "circ":  [(0, 0), (1, -1), (1, 1)],
    "til":   [(0, -1), (0, 0), (0, 2), (1, -2), (1, 1)],
}


def glifo_acentuado(letra, glifo_base):
    """glifo_base: 8 bytes da letra sem acento. Devolve os 8 bytes com acento."""
    base = _BASE_LETRA[letra]
    g = list(glifo_base)
    if base.isupper() and _TIPO[letra] != "cedilha":
        resto = [g[r] for r in range(7) if r not in _CORTA[base]]
        g = [0] * (7 - len(resto)) + resto + [g[7]]
    elif base == "i":
        g[0] = g[1] = 0          # tira o pingo
    c = _CENTRO[base]
    if _TIPO[letra] == "cedilha":
        g[7] |= 0x80 >> c
    else:
        for linha, dx in _ACENTO[_TIPO[letra]]:
            g[linha] |= 0x80 >> (c + dx)
    return bytes(g)


def fonte_ampliada(sub):
    """Devolve (glifos, larguras) com a fonte original + letras acentuadas."""
    glifos = bytearray(sub[FONTE_OFF:FONTE_OFF + FONTE_GLIFOS * 8])
    largs = bytearray(sub[LARG_OFF:LARG_OFF + FONTE_GLIFOS])
    assert PRIMEIRO_CODIGO - 0x20 == FONTE_GLIFOS
    for letra in ACENTUADAS:
        n = ord(_BASE_LETRA[letra]) - 0x20
        glifos += glifo_acentuado(letra, glifos[n * 8:n * 8 + 8])
        largs.append(largs[n])
    return bytes(glifos), bytes(largs)


class ErroScript(Exception):
    pass


# ---------------------------------------------------------------- bytecode
def _instrucao(d, pos, fim, ptrs):
    """Lê uma instrução (com as aninhadas). Devolve a posição seguinte."""
    if pos >= fim:
        raise ErroScript(f"instrução passa do fim do código em {pos:04X}")
    op = d[pos]
    if op >= len(TAB):
        raise ErroScript(f"comando desconhecido {op:02X} em {pos:04X}")
    tipos = TAB[op]
    p = pos + 1
    if 8 in tipos:
        p += 2  # destino do salto (offset dentro do código; não muda)
    for t in tipos:
        if t in (0, 7, 8):
            continue
        if t == 4:
            p = _instrucao(d, p, fim, ptrs)
        else:
            if t == 2:
                ptrs.append((p, (d[p] << 8) | d[p + 1], op))
            p += 2
    return p


def analisar(dados):
    """Separa código e texto; lista strings e ponteiros exatos."""
    if len(dados) <= BASE or dados[BASE - 1] != 0xFF:
        return None
    fim_codigo = BASE
    while fim_codigo > 0 and dados[fim_codigo - 1] == 0xFF:
        fim_codigo -= 1

    ptrs = []
    pos = 0
    while pos < fim_codigo:
        if dados[pos] == 0x00 and pos == fim_codigo - 1:
            break  # byte 00 final (terminador)
        pos = _instrucao(dados, pos, BASE, ptrs)
    if pos > fim_codigo + 1:
        # a última instrução terminou em bytes FF válidos (operando)
        fim_codigo = pos

    texto = dados[BASE:]
    ultimo_ff = texto.rfind(b"\xff")
    corpo, cauda = texto[:ultimo_ff + 1], texto[ultimo_ff + 1:]
    strings = []
    ini = 0
    for i, b in enumerate(corpo):
        if b == 0xFF:
            strings.append((ini, corpo[ini:i]))
            ini = i + 1
    inicios = {ini for ini, _ in strings}

    fora = [(p, v, op) for p, v, op in ptrs if v not in inicios]
    if fora:
        p, v, op = fora[0]
        raise ErroScript(f"{len(fora)} ponteiro(s) não caem no início de uma string "
                         f"(ex.: comando {op:02X} em {p:04X} -> {v:04X})")
    referenciadas = {v for _, v, _ in ptrs}
    return {
        "fim_codigo": fim_codigo,
        "strings": strings,
        "cauda": cauda,
        "ponteiros": ptrs,
        "menu": {v for _, v, op in ptrs if op == 0x38},
        "sem_ref": [ini for ini, _ in strings if ini not in referenciadas],
    }


# ---------------------------------------------------------------- texto
def bytes_para_texto(b):
    inv = {v: k for k, v in MAPA_EXTRA.items()}
    out = []
    for x in b:
        if x in CODIGOS:
            out.append(CODIGOS[x])
            if x in (0xF2, 0xF6):
                out.append("\n")
        elif x in inv:
            out.append(inv[x])
        elif 0x20 <= x < 0x7F and chr(x) not in "{}":
            out.append(chr(x))
        else:
            out.append("{%02X}" % x)
    return "".join(out)


def texto_para_bytes(s, origem=""):
    s = s.replace("\r", "").replace("\n", "")
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == "{":
            j = s.find("}", i)
            if j < 0:
                raise ValueError(f"{origem}: etiqueta sem fechar")
            tag = s[i:j + 1]
            if tag in ETIQUETAS:
                out.append(ETIQUETAS[tag])
            elif re.fullmatch(r"\{[0-9A-Fa-f]{2}\}", tag):
                out.append(int(tag[1:3], 16))
            else:
                raise ValueError(f"{origem}: etiqueta desconhecida {tag}")
            i = j + 1
            continue
        if c in MAPA_EXTRA:
            out.append(MAPA_EXTRA[c])
        elif 0x20 <= ord(c) < 0x7F:
            out.append(ord(c))
        else:
            raise ValueError(f"{origem}: caractere sem mapeamento na fonte: '{c}'")
        i += 1
    if 0xFF in out:
        raise ValueError(f"{origem}: a string não pode conter {{FF}}")
    return bytes(out)


def visiveis(b):
    return sum(1 for x in b if x < 0xF0)


# ---------------------------------------------------------------- montagem
def montar(dados, a, novas, enchimento=None):
    """novas: lista de bytes, uma por string, na mesma ordem.
    enchimento: (indice, bytes) -> string extra inserida ANTES da string de índice dado.
    Devolve (arquivo, avisos)."""
    avisos = []
    if a["sem_ref"]:
        # strings que nenhum comando aponta: só é seguro se nada antes delas mexer
        primeira = min(a["sem_ref"])
        if enchimento is not None:
            raise ValueError("há strings sem referência; não é seguro inserir enchimento")
        for (ini, b0), b1 in zip(a["strings"], novas):
            if ini <= primeira and len(b0) != len(b1):
                raise ValueError("há strings sem referência; mudar tamanhos antes delas é inseguro")
    bloco = bytearray()
    novo_ini = {}
    for n, ((ini, _), b) in enumerate(zip(a["strings"], novas)):
        if enchimento is not None and n == enchimento[0]:
            bloco += enchimento[1] + b"\xff"
        novo_ini[ini] = len(bloco)
        bloco += b + b"\xff"
    bloco += a["cauda"]
    saida = bytearray(dados[:BASE]) + bloco
    for pos, alvo, _ in a["ponteiros"]:
        v = novo_ini[alvo]
        if v > 0xFFFF:
            raise ValueError(f"offset de texto passou de 0xFFFF ({v:X})")
        saida[pos] = v >> 8
        saida[pos + 1] = v & 0xFF

    if len(saida) > TAM_MAX:
        raise ValueError(f"arquivo com {len(saida)} bytes; o jogo só comporta {TAM_MAX} "
                         f"(excede em {len(saida) - TAM_MAX})")
    for (ini, b0), b1 in zip(a["strings"], novas):
        if ini in a["menu"]:
            if novo_ini[ini] >= MENU_MAX_OFFSET:
                raise ValueError(f"item de menu foi parar depois do offset 0x8000 ({novo_ini[ini]:04X})")
            if b0 != b1 and visiveis(b1) > MENU_MAX_CHARS:
                avisos.append(f"item de menu com mais de {MENU_MAX_CHARS} caracteres: "
                              f"{bytes_para_texto(b1)[:40]}")
    return bytes(saida), avisos


def montar_compacto(dados, a, novas):
    """Monta o SP no formato compacto. Devolve (arquivo, avisos, base)."""
    avisos = []
    base = ((a["fim_codigo"] + 1) & ~1) + 2
    if base > SLOT - 2:
        raise ValueError("código grande demais para o formato compacto")
    # ordem: itens de menu primeiro (precisam ficar perto do início), depois o resto
    ordem = [i for i, (ini, _) in enumerate(a["strings"]) if ini in a["menu"]]
    ordem += [i for i, (ini, _) in enumerate(a["strings"]) if ini not in a["menu"]]
    # região 1: da base até o SLOT; região 2: de 0x3800 em diante
    r1, r2 = bytearray(), bytearray()
    cap1 = SLOT - base
    pos = {}
    for i in ordem:
        b = novas[i] + b"\xff"
        if len(r1) + len(b) <= cap1:
            pos[i] = base + len(r1)
            r1 += b
        else:
            pos[i] = BASE + len(r2)
            r2 += b
    saida = bytearray(dados[:a["fim_codigo"]])
    saida += b"\xff" * (base - len(saida))
    saida += r1 + b"\xff" * (cap1 - len(r1))
    saida += (CARGA_SP + base).to_bytes(4, "big")
    saida += r2
    if len(saida) % 2:
        saida.append(0)
    if len(saida) > TAM_MAX:
        raise ValueError(f"arquivo com {len(saida)} bytes; o jogo só comporta {TAM_MAX} "
                         f"(excede em {len(saida) - TAM_MAX})")
    indice = {ini: i for i, (ini, _) in enumerate(a["strings"])}
    for p, alvo, _ in a["ponteiros"]:
        v = pos[indice[alvo]] - base
        saida[p] = v >> 8
        saida[p + 1] = v & 0xFF
    for i, (ini, b0) in enumerate(a["strings"]):
        if ini in a["menu"]:
            if pos[i] - base >= MENU_MAX_OFFSET:
                raise ValueError("item de menu ficou longe demais do início do texto")
            if visiveis(novas[i]) > MENU_MAX_CHARS:
                avisos.append(f"item de menu com mais de {MENU_MAX_CHARS} caracteres: "
                              f"{bytes_para_texto(novas[i])[:40]}")
    # conferência: lê o arquivo pronto do jeito que o jogo lê
    saida = bytes(saida)
    b_lida = int.from_bytes(saida[SLOT:SLOT + 4], "big") - CARGA_SP
    for p, alvo, _ in a["ponteiros"]:
        ini = b_lida + ((saida[p] << 8) | saida[p + 1])
        fim = saida.index(b"\xff", ini)
        if saida[ini:fim] != novas[indice[alvo]]:
            raise ValueError(f"conferência falhou no ponteiro em {p:04X}")
    return saida, avisos, base


# ---------------------------------------------------------------- nomes
NOMES_TAB = 0x6152          # SUBCODE.BIN: tabela de offsets (word com sinal) -> $13552
NOMES_QTD = 48
NOMES_INI = 0x5F9F          # início do bloco de nomes (logo após o byte FF do nome vazio)
NOMES_MAX = 24              # buffer de cópia em $9759 (rotina $136E6)
FONTE_ANTIGA = (0x777C, 0x7B12)   # área livre depois que a fonte é movida


def ler_nomes(sub):
    """Devolve lista de (prefixo, bytes) para os 48 nomes. Índice 0 = vazio."""
    nomes = []
    for i in range(NOMES_QTD):
        w = int.from_bytes(sub[NOMES_TAB + 2 * i:NOMES_TAB + 2 * i + 2], "big", signed=True)
        o = NOMES_TAB + w
        fim = sub.index(0xFF, o)
        b = sub[o:fim]
        if b and b[0] < 0x80:
            nomes.append((b[0], b[1:]))
        else:
            nomes.append((None, b))
    return nomes


def extrair_nomes(sub, pasta_txt):
    linhas = ["# NOMES.txt — nomes de quem fala (SUBCODE.BIN). Máx. 24 caracteres.",
              "# Traduza apenas o bloco <PT>. Pode usar acentos.", ""]
    for n, (pre, b) in enumerate(ler_nomes(sub)):
        if n == 0:
            continue
        t = bytes_para_texto(b)
        linhas += [f"### {n:04d} | NOME", "<EN>", t, "<PT>", t, "<FIM>", ""]
    (pasta_txt / "NOMES.txt").write_text("\n".join(linhas), encoding="utf-8")
    print(f"NOMES.txt: {NOMES_QTD - 1} nomes")


def gravar_nomes(d, pasta_txt):
    """d: bytearray do SUBCODE já com a fonte movida. Reescreve os nomes."""
    arq = pasta_txt / "NOMES.txt"
    if not arq.exists():
        return 0
    trad = ler_traducao(arq)
    nomes = ler_nomes(bytes(d))
    novos = []
    mudou = 0
    for n, (pre, b) in enumerate(nomes):
        if n == 0:
            novos.append(b"")
            continue
        if n not in trad:
            raise ValueError(f"NOMES.txt: bloco {n:04d} não encontrado")
        nb = texto_para_bytes(trad[n][1], f"NOMES.txt bloco {n:04d}")
        if visiveis(nb) > NOMES_MAX:
            raise ValueError(f"NOMES.txt bloco {n:04d}: mais de {NOMES_MAX} caracteres")
        mudou += nb != b
        novos.append(bytes([pre]) + nb if pre is not None else nb)
    # região 1: bloco original; região 2: área da fonte antiga (já livre)
    regioes = [[NOMES_INI, NOMES_TAB], list(FONTE_ANTIGA)]
    for a, b in regioes:
        d[a:b] = b"\xff" * (b - a)
    pos_vazio = NOMES_INI - 1          # o FF antes do bloco serve de nome vazio
    offs = [pos_vazio - NOMES_TAB]
    r = 0
    for nb in novos[1:]:
        while regioes[r][0] + len(nb) + 1 > regioes[r][1]:
            r += 1
            if r >= len(regioes):
                raise ValueError("nomes não cabem no espaço disponível")
        o = regioes[r][0]
        d[o:o + len(nb)] = nb
        d[o + len(nb)] = 0xFF
        regioes[r][0] = o + len(nb) + 1
        offs.append(o - NOMES_TAB)
    for i, w in enumerate(offs):
        d[NOMES_TAB + 2 * i:NOMES_TAB + 2 * i + 2] = w.to_bytes(2, "big", signed=True)
    return mudou


def patch_subcode(dados, pasta_txt=None):
    """SUBCODE.BIN novo: base do texto lida do SP + fonte ampliada com acentos."""
    if len(dados) != SUB_TAM_ORIG:
        raise ValueError(f"SUBCODE.BIN com {len(dados)} bytes; esperado {SUB_TAM_ORIG} "
                         f"(use o arquivo ORIGINAL)")
    d = bytearray(dados)
    glifos, largs = fonte_ampliada(dados)
    end_fonte = SUB_CARGA + len(d)
    end_largs = end_fonte + len(glifos)
    patches = list(PATCH_SUBCODE) + [
        # lea ($14B7C).l,A5 -> fonte nova ; lea ($14EAC).l,A5 -> larguras novas
        (0x6AB8, bytes.fromhex("4bf900014b7c"), b"\x4b\xf9" + end_fonte.to_bytes(4, "big")),
        (0x6B94, bytes.fromhex("4bf900014eac"), b"\x4b\xf9" + end_largs.to_bytes(4, "big")),
    ]
    for off, antes, depois in patches:
        if bytes(d[off:off + 6]) != antes:
            raise ValueError(f"SUBCODE.BIN diferente do esperado no offset {off:X} "
                             f"(versão errada do jogo ou arquivo já modificado)")
        d[off:off + 6] = depois
    d += glifos + largs
    if pasta_txt is not None:
        n = gravar_nomes(d, pasta_txt)
        if n:
            print(f"NOMES: {n} nome(s) traduzido(s)")
    if len(d) > SUB_TAM_MAX:
        raise ValueError(f"SUBCODE.BIN ficou com {len(d)} bytes; máximo {SUB_TAM_MAX}")
    return bytes(d)


# ---------------------------------------------------------------- comandos
def testar(pasta_orig):
    """Lê o bytecode e reinsere sem alterar nada; o resultado precisa ser idêntico."""
    ok = falhas = 0
    maior_codigo = 0
    print(f"{'arquivo':<10} {'result.':<9} {'strings':>7} {'pont.':>6} {'s/ref':>5} "
          f"{'fim cód.':>8} {'tamanho':>8} {'livre':>6}")
    for arq in sorted(pasta_orig.glob("SP*.BIN")):
        dados = arq.read_bytes()
        try:
            a = analisar(dados)
            if a is None:
                print(f"{arq.name:<10} ignorado (sem bloco de texto)")
                continue
            novas = [texto_para_bytes(bytes_para_texto(b)) for _, b in a["strings"]]
            novo, _ = montar(dados, a, novas)
            igual = novo == dados
        except (ErroScript, ValueError) as e:
            print(f"{arq.name:<10} ERRO: {e}")
            falhas += 1
            continue
        ok += igual
        falhas += not igual
        maior_codigo = max(maior_codigo, a["fim_codigo"])
        print(f"{arq.name:<10} {'OK' if igual else 'DIFERENTE':<9} {len(a['strings']):>7} "
              f"{len(a['ponteiros']):>6} {len(a['sem_ref']):>5} {a['fim_codigo']:>8X} "
              f"{len(dados):>8} {TAM_MAX - len(dados):>6}")
    print(f"\nResultado: {ok} idênticos, {falhas} com problema")
    print(f"Maior fim de código: 0x{maior_codigo:X}  (base do texto: 0x{BASE:X}; "
          f"limite do arquivo: {TAM_MAX} bytes)")
    return falhas


def extrair(pasta_orig, pasta_txt):
    pasta_txt.mkdir(parents=True, exist_ok=True)
    sub = pasta_orig / "SUBCODE.BIN"
    if sub.exists():
        extrair_nomes(sub.read_bytes(), pasta_txt)
    for arq in sorted(pasta_orig.glob("SP*.BIN")):
        dados = arq.read_bytes()
        try:
            a = analisar(dados)
        except ErroScript as e:
            print(f"{arq.name}: ERRO: {e}")
            continue
        if a is None:
            print(f"{arq.name}: ignorado (sem bloco de texto)")
            continue
        tipo = {}
        for _, alvo, op in a["ponteiros"]:
            tipo.setdefault(alvo, set()).add("MENU" if op == 0x38 else "FALA")
        linhas = [
            f"# {arq.name} — {len(a['strings'])} strings",
            "# Traduza apenas o bloco <PT>. Quebras de linha do arquivo são ignoradas;",
            "# use {BR} para quebrar linha no jogo. Não apague as etiquetas {..}.",
            f"# MENU = item de menu (máx. {MENU_MAX_CHARS} caracteres). FALA = texto de diálogo.",
            "",
        ]
        for n, (ini, b) in enumerate(a["strings"]):
            t = "+".join(sorted(tipo.get(ini, {"SEM-REFERENCIA"})))
            txt = bytes_para_texto(b)
            linhas += [f"### {n:04d} | {ini:04X} | {t}", "<EN>", txt, "<PT>", txt, "<FIM>", ""]
        (pasta_txt / (arq.stem + ".txt")).write_text("\n".join(linhas), encoding="utf-8")
        print(f"{arq.name}: {len(a['strings'])} strings, {len(a['ponteiros'])} ponteiros")


def ler_traducao(caminho):
    conteudo = caminho.read_text(encoding="utf-8-sig").replace("\r", "")
    blocos = re.findall(r"^### (\d{4}) \|.*?\n<EN>\n(.*?)\n<PT>\n(.*?)\n<FIM>", conteudo, re.S | re.M)
    return {int(n): (en, pt) for n, en, pt in blocos}


def inserir(pasta_orig, pasta_txt, pasta_saida):
    """Gera os 38 SP no formato compacto + SUBCODE.BIN modificado."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    sub = pasta_orig / "SUBCODE.BIN"
    if not sub.exists():
        print("ERRO: SUBCODE.BIN não encontrado na pasta original")
        return 1
    try:
        sub_novo = patch_subcode(sub.read_bytes(), pasta_txt)
    except ValueError as e:
        print(f"ERRO: {e}")
        return 1
    erros = 0
    prontos = {}
    print(f"{'arquivo':<10} {'antes':>7} {'depois':>7} {'livre':>6} {'uso':>5}  traduzidas")
    for arq in sorted(pasta_orig.glob("SP*.BIN")):
        dados = arq.read_bytes()
        txt = pasta_txt / (arq.stem + ".txt")
        try:
            a = analisar(dados)
            if a is None:
                continue
            novas = [b for _, b in a["strings"]]
            mudadas = 0
            if txt.exists():
                trad = ler_traducao(txt)
                for n, (ini, b) in enumerate(a["strings"]):
                    if n not in trad:
                        raise ValueError(f"bloco {n:04d} não encontrado em {txt.name} (extraia de novo?)")
                    novas[n] = texto_para_bytes(trad[n][1], f"{txt.name} bloco {n:04d}")
                    mudadas += novas[n] != b
            novo, avisos, _ = montar_compacto(dados, a, novas)
        except (ErroScript, ValueError) as e:
            print(f"{arq.name:<10} ERRO: {e}")
            erros += 1
            continue
        prontos[arq.name] = novo
        print(f"{arq.name:<10} {len(dados):>7} {len(novo):>7} {TAM_MAX - len(novo):>6} "
              f"{100 * len(novo) // TAM_MAX:>4}%  {mudadas}")
        for av in avisos:
            print(f"   aviso: {av}")
    if erros:
        print(f"\n{erros} arquivo(s) com erro. NADA foi gravado (os arquivos só funcionam em conjunto).")
        return erros
    for nome, conteudo in prontos.items():
        (pasta_saida / nome).write_bytes(conteudo)
    (pasta_saida / "SUBCODE.BIN").write_bytes(sub_novo)
    print(f"\nGravados {len(prontos)} SP + SUBCODE.BIN em {pasta_saida}")
    return 0


def marcar(pasta_orig, pasta_saida):
    """Troca as 3 primeiras letras de cada frase pelo nº do arquivo (ex.: '06|')."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    for arq in sorted(pasta_orig.glob("SP*.BIN")):
        dados = bytearray(arq.read_bytes())
        try:
            a = analisar(bytes(dados))
        except ErroScript as e:
            print(f"{arq.name}: ERRO: {e}")
            continue
        if a is None:
            continue
        marca = f"{arq.stem[2:4]}|".encode("ascii")
        n = 0
        for ini, b in a["strings"]:
            vis = [i for i, x in enumerate(b) if 0x21 <= x < 0x7F]
            if len(vis) < 4:
                continue
            for k, i in enumerate(vis[:3]):
                dados[BASE + ini + i] = marca[k]
            n += 1
        (pasta_saida / arq.name).write_bytes(bytes(dados))
        print(f"{arq.name}: {n} frases marcadas com '{marca.decode()}'")


def encher(entrada, saida, livres=64):
    """TESTE: infla o arquivo até sobrar só 'livres' bytes antes do limite."""
    dados = entrada.read_bytes()
    a = analisar(dados)
    if a is None:
        raise ValueError("arquivo sem bloco de texto")
    n = TAM_MAX - livres - len(dados) - 1
    if n <= 0:
        raise ValueError("o arquivo já está no limite")
    # insere depois do último item de menu (menus precisam ficar no começo)
    ultimo_menu = max((i for i, (ini, _) in enumerate(a["strings"]) if ini in a["menu"]), default=-1)
    novas = [b for _, b in a["strings"]]
    novo, _ = montar(dados, a, novas, enchimento=(ultimo_menu + 1, b"." * n))
    saida.write_bytes(novo)
    print(f"{entrada.name}: {len(dados)} -> {len(novo)} bytes "
          f"({-(-len(dados) // SETOR)} -> {-(-len(novo) // SETOR)} setores); "
          f"enchimento de {n} bytes antes da string {ultimo_menu + 1:04d}")


DEMO = [
    # (trecho que identifica o bloco no <EN>, texto novo do <PT>)
    ("Welcome to Junker Headquarters.",
     "Bem-vindo à sede dos JUNKERs.{BR}Em que posso ajudá-lo?"),
    ("The Junkers are a special task",
     "áàâãéêíóôõúç ÁÀÂÃÉÊÍÓÔÕÚÇ{BR}Não há solução fácil, você vê?{BR}"
     "{C3}É ótimo! Ação e coração.{C1}"),
]
DEMO_NOMES = {"Gillian": "Gillian (Gí)", "Mika": "Mika Slayton", "Chief": "Chefe Cunningham"}
DEMO_MENU = {"INVESTIGATE": "INVESTIGAÇÃO", "LOOK": "OLHAR", "ENTER": "ENTRAR"}


def demo(pasta_txt):
    """TESTE: coloca frases com acentos no começo do SP06 (recepção da Mika)."""
    arq = pasta_txt / "SP06.txt"
    conteudo = arq.read_text(encoding="utf-8-sig").replace("\r", "")
    feitos = 0

    def troca(m):
        nonlocal feitos
        en = m.group(2)
        en_plano = en.replace("\n", "")
        for trecho, novo in DEMO:
            if en.startswith(trecho):
                feitos += 1
                return f"{m.group(1)}{en}\n<PT>\n{novo}\n<FIM>"
        if "MENU" in m.group(1) and en_plano in DEMO_MENU:
            feitos += 1
            return f"{m.group(1)}{en}\n<PT>\n{DEMO_MENU[en_plano]}\n<FIM>"
        return m.group(0)

    novo = re.sub(r"^(### \d{4} \|[^\n]*\n<EN>\n)(.*?)\n<PT>\n(.*?)\n<FIM>", troca, conteudo,
                  flags=re.S | re.M)
    arq.write_text(novo, encoding="utf-8")
    print(f"SP06.txt: {feitos} blocos alterados (esperado: {len(DEMO) + len(DEMO_MENU)})")
    nomes = pasta_txt / "NOMES.txt"
    if nomes.exists():
        t = nomes.read_text(encoding="utf-8-sig").replace("\r", "")
        for en, pt in DEMO_NOMES.items():
            t = t.replace(f"<EN>\n{en}\n<PT>\n{en}\n", f"<EN>\n{en}\n<PT>\n{pt}\n")
        nomes.write_text(t, encoding="utf-8")
        print(f"NOMES.txt: {len(DEMO_NOMES)} nomes de teste")
    return 0 if feitos == len(DEMO) + len(DEMO_MENU) else 1


def previa(pasta_orig, saida):
    """Desenha a fonte ampliada num PNG, para conferir os acentos no PC."""
    try:
        from PIL import Image
    except ImportError:
        print("Este comando precisa do Pillow:  python -m pip install pillow")
        return 1
    glifos, largs = fonte_ampliada((pasta_orig / "SUBCODE.BIN").read_bytes())
    linhas = ["Ação, coração, você, três, até, à noite,", "só, avô, põe, úmido, índio, fácil, possível.",
              "É ÀS ÓTIMO ÁGUA ÍNDICE ÚLTIMO AÇÃO Ê Â Õ", ACENTUADAS]
    img = Image.new("L", (330, len(linhas) * 10 + 4), 0)
    px = img.load()
    for n, texto in enumerate(linhas):
        x = 2
        for ch in texto:
            g = (MAPA_EXTRA.get(ch) or ord(ch)) - 0x20
            for r in range(8):
                for k in range(8):
                    if glifos[g * 8 + r] & (0x80 >> k) and x + k < img.width:
                        px[x + k, 2 + n * 10 + r] = 255
            x += largs[g]
    img.resize((img.width * 4, img.height * 4), Image.NEAREST).save(saida)
    print(f"Prévia gravada em {saida}")
    return 0


def main():
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "testar":
        sys.exit(1 if testar(Path(args[1])) else 0)
    elif len(args) == 3 and args[0] == "extrair":
        extrair(Path(args[1]), Path(args[2]))
    elif len(args) == 4 and args[0] == "inserir":
        sys.exit(1 if inserir(Path(args[1]), Path(args[2]), Path(args[3])) else 0)
    elif len(args) == 3 and args[0] == "marcar":
        marcar(Path(args[1]), Path(args[2]))
    elif len(args) == 2 and args[0] == "demo":
        sys.exit(demo(Path(args[1])))
    elif len(args) == 3 and args[0] == "previa":
        sys.exit(previa(Path(args[1]), Path(args[2])))
    elif len(args) in (3, 4) and args[0] == "encher":
        try:
            encher(Path(args[1]), Path(args[2]), int(args[3]) if len(args) == 4 else 64)
        except (ErroScript, ValueError) as e:
            print(f"ERRO: {e}")
            sys.exit(1)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
