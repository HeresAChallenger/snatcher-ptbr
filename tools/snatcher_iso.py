#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
snatcher_iso.py — Monta uma imagem de teste do Snatcher (Mega CD) com
arquivos modificados, no formato BIN/CUE (compatível com Mega EverDrive Pro
e emuladores).

Projeto: Tradução Snatcher PT-BR

Uso:
  python snatcher_iso.py listar  <iso>
  python snatcher_iso.py montar  <iso_original> <cue_original> <pasta_modificados> <pasta_saida>

O comando "montar":
  1. copia a ISO da trilha de dados (setores de 2048 bytes) e substitui, no
     mesmo lugar, cada arquivo de <pasta_modificados>. O arquivo pode crescer
     para o espaço vazio que há depois dele (cada SP tem 27 setores reservados
     no disco); o tamanho é corrigido no diretório;
  2. copia a Track 01 .bin original (setores de 2352 bytes) e regrava apenas
     os setores que mudaram, recalculando EDC/ECC (códigos de correção de erro);
  3. copia as faixas de áudio e gera um .cue novo.

Antes de gravar, o EDC/ECC é conferido contra setores do .bin original; se não
bater, o processo para. Nenhum arquivo original é alterado.
"""
import re
import shutil
import sys
from pathlib import Path

SETOR = 2048
RAW = 2352

# ---------------------------------------------------------------- EDC/ECC
ECC_F = [0] * 256
ECC_B = [0] * 256
EDC = [0] * 256
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xFF
    ECC_F[_i] = _j
    ECC_B[_i ^ _j] = _i
    _e = _i
    for _ in range(8):
        _e = (_e >> 1) ^ (0xD8018001 if _e & 1 else 0)
    EDC[_i] = _e


SYNC = b"\x00" + b"\xff" * 10 + b"\x00"


def _bcd(v):
    return (v // 10) * 16 + v % 10


def _edc(dados):
    e = 0
    for x in dados:
        e = (e >> 8) ^ EDC[(e ^ x) & 0xFF]
    return e


def _ecc_bloco(setor, maj_n, min_n, maj_mult, min_inc, destino):
    src = 0x0C
    tam = maj_n * min_n
    for maj in range(maj_n):
        idx = (maj >> 1) * maj_mult + (maj & 1)
        a = b = 0
        for _ in range(min_n):
            t = setor[src + idx]
            idx += min_inc
            if idx >= tam:
                idx -= tam
            a ^= t
            b ^= t
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        setor[destino + maj] = a
        setor[destino + maj + maj_n] = a ^ b


def recalcular_mode1(setor):
    """setor: bytearray de 2352 bytes (Mode 1). Recalcula EDC e ECC no lugar."""
    setor[0x810:0x814] = _edc(setor[0:0x810]).to_bytes(4, "little")
    setor[0x814:0x81C] = b"\x00" * 8
    _ecc_bloco(setor, 86, 24, 2, 86, 0x81C)   # P
    _ecc_bloco(setor, 52, 43, 86, 88, 0x8C8)  # Q


def conferir_ecc(bin_orig, amostras=64):
    """Confere o algoritmo contra setores reais do .bin original."""
    total = bin_orig.stat().st_size // RAW
    passo = max(1, total // amostras)
    with open(bin_orig, "rb") as f:
        for lba in range(16, total, passo):
            f.seek(lba * RAW)
            orig = f.read(RAW)
            if orig[15] != 1:
                continue
            s = bytearray(orig)
            recalcular_mode1(s)
            if bytes(s) != orig:
                return False, lba
    return True, None


# ---------------------------------------------------------------- ISO9660
def ler_raiz(iso):
    """Lê o diretório raiz. Devolve {NOME: (pos_registro, lba, tamanho)}."""
    with open(iso, "rb") as f:
        f.seek(16 * SETOR)
        pvd = f.read(SETOR)
        if pvd[1:6] != b"CD001":
            raise ValueError("não parece uma ISO9660 (assinatura CD001 ausente no setor 16)")
        raiz = pvd[156:156 + 34]
        lba = int.from_bytes(raiz[2:6], "little")
        tam = int.from_bytes(raiz[10:14], "little")
        f.seek(lba * SETOR)
        dados = f.read(tam)
    arquivos = {}
    pos = 0
    while pos < len(dados):
        n = dados[pos]
        if n == 0:
            pos = (pos // SETOR + 1) * SETOR
            continue
        reg = dados[pos:pos + n]
        nlen = reg[32]
        nome = reg[33:33 + nlen]
        if nome not in (b"\x00", b"\x01") and not reg[25] & 0x02:
            nome = nome.decode("ascii").split(";")[0].upper()
            arquivos[nome] = (lba * SETOR + pos,
                              int.from_bytes(reg[2:6], "little"),
                              int.from_bytes(reg[10:14], "little"))
        pos += n
    return arquivos


def listar(iso):
    """Mostra onde cada arquivo fica no disco, os espaços entre eles e o fim."""
    arqs = sorted(ler_raiz(iso).items(), key=lambda x: x[1][1])
    total = Path(iso).stat().st_size // SETOR
    anterior = None
    with open(iso, "rb") as f:
        def vazio(lba, n):
            f.seek(lba * SETOR)
            resto = n
            while resto > 0:
                bloco = f.read(min(resto, 512) * SETOR)
                if bloco.strip(b"\x00"):
                    return False
                resto -= 512
            return True
        for nome, (_, lba, tam) in arqs:
            setores = -(-tam // SETOR)
            if anterior is not None and lba > anterior:
                n = lba - anterior
                print(f"{'  (espaço)':<14} LBA {anterior:6d}  {n:5d} setores  "
                      f"{'vazio' if vazio(anterior, n) else 'COM DADOS'}")
            print(f"{nome:<14} LBA {lba:6d}  {tam:9d} bytes  {setores:5d} setores  "
                  f"folga {setores * SETOR - tam:5d}")
            anterior = max(anterior or 0, lba + setores)
        n = total - anterior
        print(f"{'  (fim)':<14} LBA {anterior:6d}  {n:5d} setores  "
              f"{'vazio' if n > 0 and vazio(anterior, n) else 'COM DADOS' if n > 0 else '-'}")
    print(f"Total da ISO: {total} setores; primeiro arquivo no LBA {arqs[0][1][1]}")


def substituir(iso_saida, pasta_mod):
    """Troca arquivos no mesmo lugar. Um arquivo pode crescer para dentro do
    espaço vazio que existe logo depois dele (até o início do próximo arquivo).
    O jogo lê posição e tamanho do diretório do CD, então basta atualizá-lo."""
    arquivos = ler_raiz(iso_saida)
    total = Path(iso_saida).stat().st_size // SETOR
    inicios = sorted(lba for _, lba, _ in arquivos.values())
    erros = 0
    with open(iso_saida, "r+b") as f:
        for arq in sorted(pasta_mod.iterdir()):
            if not arq.is_file():
                continue
            nome = arq.name.upper()
            if nome not in arquivos:
                print(f"  ignorado: {arq.name} não existe na ISO")
                continue
            pos_reg, lba, tam_orig = arquivos[nome]
            novo = arq.read_bytes()
            set_orig = -(-tam_orig // SETOR)
            set_novo = -(-len(novo) // SETOR)
            proximo = min((x for x in inicios if x > lba), default=total)
            if set_novo > proximo - lba:
                print(f"  ERRO {nome}: precisa de {set_novo} setores, mas só há {proximo - lba} "
                      f"até o próximo arquivo")
                erros += 1
                continue
            if set_novo > set_orig:
                f.seek((lba + set_orig) * SETOR)
                if f.read((set_novo - set_orig) * SETOR).strip(b"\x00"):
                    print(f"  ERRO {nome}: o espaço depois do arquivo não está vazio")
                    erros += 1
                    continue
            f.seek(lba * SETOR)
            f.write(novo + b"\x00" * (max(set_novo, set_orig) * SETOR - len(novo)))
            if len(novo) != tam_orig:
                f.seek(pos_reg + 10)
                f.write(len(novo).to_bytes(4, "little") + len(novo).to_bytes(4, "big"))
            marca = "" if len(novo) == tam_orig else f" ({len(novo) - tam_orig:+d} bytes"
            if len(novo) != tam_orig:
                marca += f", {set_orig} -> {set_novo} setores)" if set_novo != set_orig else ")"
            print(f"  substituído: {nome}{marca}")
    return erros


# ---------------------------------------------------------------- BIN/CUE
def ler_cue(cue):
    texto = Path(cue).read_text(encoding="utf-8", errors="replace")
    arquivos = re.findall(r'^\s*FILE\s+"(.+?)"', texto, re.M)
    return texto, arquivos


def gravar_bin(iso_orig, iso_novo, bin_orig, bin_novo):
    shutil.copy2(bin_orig, bin_novo)
    mudados = 0
    with open(iso_orig, "rb") as fo, open(iso_novo, "rb") as fn, open(bin_novo, "r+b") as fb:
        lba = 0
        while True:
            a = fo.read(SETOR)
            b = fn.read(SETOR)
            if not a:
                break
            if a != b:
                fb.seek(lba * RAW)
                s = bytearray(fb.read(RAW))
                if s[0:12] != SYNC or s[15] != 1:
                    # setor sem cabeçalho no dump: cria (sync + tempo MSF + modo 1)
                    m = lba + 150
                    s[0:12] = SYNC
                    s[12:16] = bytes([_bcd(m // 4500), _bcd((m // 75) % 60), _bcd(m % 75), 1])
                s[16:16 + SETOR] = b
                recalcular_mode1(s)
                fb.seek(lba * RAW)
                fb.write(s)
                mudados += 1
            lba += 1
    return mudados


def montar(iso_orig, cue_orig, pasta_mod, pasta_saida):
    pasta_saida.mkdir(parents=True, exist_ok=True)
    pasta_cd = Path(cue_orig).parent
    texto_cue, arquivos_cue = ler_cue(cue_orig)
    bin_orig = pasta_cd / arquivos_cue[0]
    nome_bin = "Snatcher PT-BR (Track 01).bin"

    print("Conferindo o cálculo de EDC/ECC no .bin original...")
    ok, lba = conferir_ecc(bin_orig)
    if not ok:
        print(f"ERRO: EDC/ECC não confere no setor {lba}. Nada foi gravado.")
        return 1
    print("  OK")

    iso_temp = pasta_saida / "_temp_track01.iso"
    shutil.copy2(iso_orig, iso_temp)
    print("Substituindo arquivos:")
    erros = substituir(iso_temp, pasta_mod)

    print("Gerando a Track 01 em formato BIN (2352)...")
    n = gravar_bin(iso_orig, iso_temp, bin_orig, pasta_saida / nome_bin)
    print(f"  {n} setores regravados")
    iso_temp.unlink()

    print("Copiando faixas de áudio (só na primeira vez) e gerando o .cue...")
    for audio in arquivos_cue[1:]:
        destino = pasta_saida / audio
        if not destino.exists():
            shutil.copy2(pasta_cd / audio, destino)
    novo_cue = texto_cue.replace(f'"{arquivos_cue[0]}"', f'"{nome_bin}"', 1)
    cue_saida = pasta_saida / "Snatcher PT-BR.cue"
    cue_saida.write_text(novo_cue, encoding="utf-8")

    print(f"\nPronto: {cue_saida}")
    if erros:
        print(f"ATENÇÃO: {erros} arquivo(s) não couberam e ficaram com o conteúdo original.")
    return 1 if erros else 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "listar":
        listar(Path(sys.argv[2]))
    elif len(sys.argv) == 6 and sys.argv[1] == "montar":
        sys.exit(montar(Path(sys.argv[2]), Path(sys.argv[3]),
                        Path(sys.argv[4]), Path(sys.argv[5])))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
