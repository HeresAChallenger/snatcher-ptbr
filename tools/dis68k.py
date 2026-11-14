#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dis68k.py — Disassembler simples de Motorola 68000 (Mega Drive / Mega CD).

Projeto: Tradução Snatcher PT-BR

Uso:
  python dis68k.py <arquivo> <endereco_base_hex> <inicio_hex> <fim_hex>

Exemplo (SUBCODE.BIN é carregado em 0xD400):
  python dis68k.py SUBCODE.BIN D400 163A0 16590
"""
import sys

CC = ["T", "F", "HI", "LS", "CC", "CS", "NE", "EQ", "VC", "VS", "PL", "MI", "GE", "LT", "GT", "LE"]
SZ = ["b", "w", "l"]


class Dis:
    def __init__(self, data, base):
        self.d = data
        self.base = base

    def u16(self):
        o = self.pc - self.base
        v = (self.d[o] << 8) | self.d[o + 1]
        self.pc += 2
        return v

    def s16(self):
        v = self.u16()
        return v - 0x10000 if v & 0x8000 else v

    def u32(self):
        return (self.u16() << 16) | self.u16()

    def imm(self, size):
        if size == 0:
            return "#$%02X" % (self.u16() & 0xFF)
        if size == 1:
            return "#$%04X" % self.u16()
        return "#$%08X" % self.u32()

    def ea(self, mode, reg, size):
        if mode == 0:
            return "D%d" % reg
        if mode == 1:
            return "A%d" % reg
        if mode == 2:
            return "(A%d)" % reg
        if mode == 3:
            return "(A%d)+" % reg
        if mode == 4:
            return "-(A%d)" % reg
        if mode == 5:
            return "%d(A%d)" % (self.s16(), reg)
        if mode == 6:
            return self.idx("A%d" % reg, None)
        if reg == 0:
            v = self.u16()
            return "($%04X).w" % v if v < 0x8000 else "($FFFF%04X).w" % v
        if reg == 1:
            return "($%08X).l" % self.u32()
        if reg == 2:
            p = self.pc
            return "$%X(PC)" % (p + self.s16())
        if reg == 3:
            return self.idx("PC", self.pc)
        if reg == 4:
            return self.imm(size)
        return "?ea"

    def idx(self, breg, pcbase):
        e = self.u16()
        disp = e & 0xFF
        if disp & 0x80:
            disp -= 0x100
        r = "%s%d.%s" % ("A" if e & 0x8000 else "D", (e >> 12) & 7, "l" if e & 0x800 else "w")
        if pcbase is not None:
            return "$%X(PC,%s)" % (pcbase + disp, r)
        return "%d(%s,%s)" % (disp, breg, r)

    def one(self, addr):
        self.pc = addr
        try:
            txt = self.decode()
        except IndexError:
            txt = "???"
        return addr, self.pc - addr, txt

    def movem_list(self, mask, predec):
        names = []
        for i in range(16):
            if mask & (1 << i):
                n = 15 - i if predec else i
                names.append(("D%d" % n) if n < 8 else ("A%d" % (n - 8)))
        return "/".join(names)

    def decode(self):
        op = self.u16()
        top = op >> 12
        mode, reg = (op >> 3) & 7, op & 7
        r9 = (op >> 9) & 7
        opm = (op >> 6) & 7

        if top == 0:
            if op & 0x0100:
                if mode == 1:  # MOVEP
                    return "movep ..."
                names = ["btst", "bchg", "bclr", "bset"]
                return "%s D%d,%s" % (names[(op >> 6) & 3], r9, self.ea(mode, reg, 0))
            if r9 == 4:
                names = ["btst", "bchg", "bclr", "bset"]
                b = self.u16() & 0xFF
                return "%s #%d,%s" % (names[(op >> 6) & 3], b, self.ea(mode, reg, 0))
            names = ["ori", "andi", "subi", "addi", None, "eori", "cmpi", None]
            size = (op >> 6) & 3
            if names[r9] is None or size == 3:
                return "dc.w $%04X" % op
            if mode == 7 and reg == 4:
                return "%s %s,%s" % (names[r9], self.imm(1 if size else 0), "SR" if size else "CCR")
            i = self.imm(size)
            return "%s.%s %s,%s" % (names[r9], SZ[size], i, self.ea(mode, reg, size))

        if top in (1, 2, 3):
            size = {1: 0, 3: 1, 2: 2}[top]
            src = self.ea(mode, reg, size)
            dmode, dreg = (op >> 6) & 7, r9
            dst = self.ea(dmode, dreg, size)
            return "move%s.%s %s,%s" % ("a" if dmode == 1 else "", SZ[size], src, dst)

        if top == 4:
            if op == 0x4E71:
                return "nop"
            if op == 0x4E75:
                return "rts"
            if op == 0x4E73:
                return "rte"
            if op == 0x4E77:
                return "rtr"
            if op == 0x4E70:
                return "reset"
            if op == 0x4E72:
                return "stop #$%04X" % self.u16()
            if (op & 0xFFF0) == 0x4E40:
                return "trap #%d" % (op & 15)
            if (op & 0xFFF8) == 0x4E50:
                return "link A%d,#%d" % (reg, self.s16())
            if (op & 0xFFF8) == 0x4E58:
                return "unlk A%d" % reg
            if (op & 0xFFF0) == 0x4E60:
                return "move usp"
            if (op & 0xFFC0) == 0x4E80:
                return "jsr %s" % self.ea(mode, reg, 2)
            if (op & 0xFFC0) == 0x4EC0:
                return "jmp %s" % self.ea(mode, reg, 2)
            if (op & 0xF1C0) == 0x41C0:
                return "lea %s,A%d" % (self.ea(mode, reg, 2), r9)
            if (op & 0xF1C0) == 0x4180:
                return "chk %s,D%d" % (self.ea(mode, reg, 1), r9)
            if (op & 0xFFF8) == 0x4840:
                return "swap D%d" % reg
            if (op & 0xFFC0) == 0x4840:
                return "pea %s" % self.ea(mode, reg, 2)
            if (op & 0xFFB8) == 0x4880:
                return "ext.%s D%d" % ("l" if op & 0x40 else "w", reg)
            if (op & 0xFB80) == 0x4880:
                size = 2 if op & 0x40 else 1
                mask = self.u16()
                if op & 0x0400:
                    return "movem.%s %s,%s" % (SZ[size], self.ea(mode, reg, size), self.movem_list(mask, False))
                return "movem.%s %s,%s" % (SZ[size], self.movem_list(mask, mode == 4), self.ea(mode, reg, size))
            if (op & 0xFFC0) == 0x40C0:
                return "move.w SR,%s" % self.ea(mode, reg, 1)
            if (op & 0xFFC0) == 0x44C0:
                return "move.w %s,CCR" % self.ea(mode, reg, 1)
            if (op & 0xFFC0) == 0x46C0:
                return "move.w %s,SR" % self.ea(mode, reg, 1)
            if (op & 0xFFC0) == 0x4800:
                return "nbcd %s" % self.ea(mode, reg, 0)
            if (op & 0xFFC0) == 0x4AC0:
                return "tas %s" % self.ea(mode, reg, 0)
            size = (op >> 6) & 3
            names = {0x40: "negx", 0x42: "clr", 0x44: "neg", 0x46: "not", 0x4A: "tst"}
            hi = op >> 8
            if hi in names and size != 3:
                return "%s.%s %s" % (names[hi], SZ[size], self.ea(mode, reg, size))
            return "dc.w $%04X" % op

        if top == 5:
            size = (op >> 6) & 3
            if size == 3:
                cc = CC[(op >> 8) & 15]
                if mode == 1:
                    p = self.pc
                    return "db%s D%d,$%X" % (cc.lower(), reg, p + self.s16())
                return "s%s %s" % (cc.lower(), self.ea(mode, reg, 0))
            q = r9 or 8
            return "%s.%s #%d,%s" % ("subq" if op & 0x100 else "addq", SZ[size], q, self.ea(mode, reg, size))

        if top == 6:
            cc = (op >> 8) & 15
            p = self.pc
            disp = op & 0xFF
            if disp == 0:
                disp = self.s16()
            elif disp & 0x80:
                disp -= 0x100
            name = "bra" if cc == 0 else "bsr" if cc == 1 else "b" + CC[cc].lower()
            return "%s $%X" % (name, p + disp)

        if top == 7:
            v = op & 0xFF
            if v & 0x80:
                v -= 0x100
            return "moveq #%d,D%d" % (v, r9)

        if top in (8, 0xC):
            name = "or" if top == 8 else "and"
            if opm == 3:
                return "%s %s,D%d" % ("divu" if top == 8 else "mulu", self.ea(mode, reg, 1), r9)
            if opm == 7:
                return "%s %s,D%d" % ("divs" if top == 8 else "muls", self.ea(mode, reg, 1), r9)
            if top == 0xC and (op & 0x1F8) == 0x140:
                return "exg D%d,D%d" % (r9, reg)
            if top == 0xC and (op & 0x1F8) == 0x148:
                return "exg A%d,A%d" % (r9, reg)
            if top == 0xC and (op & 0x1F8) == 0x188:
                return "exg D%d,A%d" % (r9, reg)
            if (op & 0x1F0) == 0x100:
                return "%s ..." % ("sbcd" if top == 8 else "abcd")
            size = opm & 3
            e = self.ea(mode, reg, size)
            if opm & 4:
                return "%s.%s D%d,%s" % (name, SZ[size], r9, e)
            return "%s.%s %s,D%d" % (name, SZ[size], e, r9)

        if top in (9, 0xD):
            name = "sub" if top == 9 else "add"
            if opm in (3, 7):
                size = 1 if opm == 3 else 2
                return "%sa.%s %s,A%d" % (name, SZ[size], self.ea(mode, reg, size), r9)
            size = opm & 3
            if opm & 4 and mode in (0, 1):
                return "%sx.%s ..." % (name, SZ[size])
            e = self.ea(mode, reg, size)
            if opm & 4:
                return "%s.%s D%d,%s" % (name, SZ[size], r9, e)
            return "%s.%s %s,D%d" % (name, SZ[size], e, r9)

        if top == 0xB:
            if opm in (3, 7):
                size = 1 if opm == 3 else 2
                return "cmpa.%s %s,A%d" % (SZ[size], self.ea(mode, reg, size), r9)
            size = opm & 3
            if opm & 4:
                if mode == 1:
                    return "cmpm.%s (A%d)+,(A%d)+" % (SZ[size], reg, r9)
                return "eor.%s D%d,%s" % (SZ[size], r9, self.ea(mode, reg, size))
            return "cmp.%s %s,D%d" % (SZ[size], self.ea(mode, reg, size), r9)

        if top == 0xE:
            names = ["as", "ls", "rox", "ro"]
            dr = "l" if op & 0x100 else "r"
            size = (op >> 6) & 3
            if size == 3:
                return "%s%s.w %s" % (names[(op >> 9) & 3], dr, self.ea(mode, reg, 1))
            n = names[(op >> 3) & 3]
            if op & 0x20:
                return "%s%s.%s D%d,D%d" % (n, dr, SZ[size], r9, reg)
            return "%s%s.%s #%d,D%d" % (n, dr, SZ[size], r9 or 8, reg)

        return "dc.w $%04X" % op

    def listar(self, ini, fim):
        a = ini
        out = []
        while a < fim:
            addr, n, txt = self.one(a)
            o = addr - self.base
            hx = self.d[o:o + n].hex()
            out.append("%06X  %-20s %s" % (addr, hx, txt))
            a += n
        return "\n".join(out)


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    data = open(sys.argv[1], "rb").read()
    base = int(sys.argv[2], 16)
    print(Dis(data, base).listar(int(sys.argv[3], 16), int(sys.argv[4], 16)))


if __name__ == "__main__":
    main()
