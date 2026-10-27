"""Small Z80 disassembler + boot-flow tracer, used to compare how Super-OS, the official TI OS and KnightOS bring up a TI-83+SE
(which ports they write, in which order).  Reverse engineering for interoperability with the user's own calculator.
  python tools/z80dis.py trace FILE.8xu START [maxinsn]     follow jumps/calls from START in page 0 and list every IN/OUT with its operand
  python tools/z80dis.py dis FILE.8xu START COUNT           linear listing
"""
import sys

R = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
RP = ["BC", "DE", "HL", "SP"]
RP2 = ["BC", "DE", "HL", "AF"]
CC = ["NZ", "Z", "NC", "C", "PO", "PE", "P", "M"]
ALU = ["ADD A,", "ADC A,", "SUB ", "SBC A,", "AND ", "XOR ", "OR ", "CP "]
ROT = ["RLC", "RRC", "RL", "RR", "SLA", "SRA", "SLL", "SRL"]
BLK = [["LDI", "CPI", "INI", "OUTI"], ["LDD", "CPD", "IND", "OUTD"], ["LDIR", "CPIR", "INIR", "OTIR"], ["LDDR", "CPDR", "INDR", "OTDR"]]


def s8(v):
    return v - 256 if v > 127 else v


def disasm(m, a):
    """-> (text, length, kind, target)  kind in None/'jp'/'call'/'jr'/'ret'/'jpcond'/..."""
    op = m[a]
    pre = None
    i = a
    if op in (0xDD, 0xFD):
        pre = "IX" if op == 0xDD else "IY"
        i += 1
        op = m[i]
    x, y, z = op >> 6, (op >> 3) & 7, op & 7
    p, q = y >> 1, y & 1
    n1 = m[i + 1] if i + 1 < len(m) else 0
    n2 = m[i + 2] if i + 2 < len(m) else 0
    nn = n1 | n2 << 8

    def reg(r, disp=None):
        if r == 6 and pre:
            return "(%s%+d)" % (pre, s8(disp))
        if pre and r in (4, 5):
            return pre + ("H" if r == 4 else "L")
        return R[r]

    def hl():
        return pre or "HL"

    def rp(k):
        return hl() if k == 2 else RP[k]

    def rp2(k):
        return hl() if k == 2 else RP2[k]

    if op == 0xCB and not pre:
        c = m[i + 1]
        xx, yy, zz = c >> 6, (c >> 3) & 7, c & 7
        t = ("%s %s" % (ROT[yy], R[zz])) if xx == 0 else ("%s %d,%s" % (["", "BIT", "RES", "SET"][xx], yy, R[zz]))
        return t, (i - a) + 2, None, None
    if op == 0xCB and pre:
        d, c = m[i + 1], m[i + 2]
        xx, yy = c >> 6, (c >> 3) & 7
        t = ("%s (%s%+d)" % (ROT[yy], pre, s8(d))) if xx == 0 else ("%s %d,(%s%+d)" % (["", "BIT", "RES", "SET"][xx], yy, pre, s8(d)))
        return t, (i - a) + 3, None, None
    if op == 0xED:
        c = m[i + 1]
        xx, yy, zz = c >> 6, (c >> 3) & 7, c & 7
        pp, qq = yy >> 1, yy & 1
        e1, e2 = m[i + 2], m[i + 3]
        enn = e1 | e2 << 8
        if xx == 1:
            if zz == 0:
                return ("IN (C)" if yy == 6 else "IN %s,(C)" % R[yy]), (i - a) + 2, "in", None
            if zz == 1:
                return ("OUT (C),0" if yy == 6 else "OUT (C),%s" % R[yy]), (i - a) + 2, "out", None
            if zz == 2:
                return ("%s HL,%s" % ("SBC" if qq == 0 else "ADC", RP[pp])), (i - a) + 2, None, None
            if zz == 3:
                return (("LD (%04X),%s" % (enn, RP[pp])) if qq == 0 else ("LD %s,(%04X)" % (RP[pp], enn))), (i - a) + 4, None, None
            if zz == 4:
                return "NEG", (i - a) + 2, None, None
            if zz == 5:
                return ("RETI" if yy == 1 else "RETN"), (i - a) + 2, "ret", None
            if zz == 6:
                return "IM %d" % [0, 0, 1, 2, 0, 0, 1, 2][yy], (i - a) + 2, None, None
            return ["LD I,A", "LD R,A", "LD A,I", "LD A,R", "RRD", "RLD", "NOP", "NOP"][yy], (i - a) + 2, None, None
        if xx == 2 and zz <= 3 and yy >= 4:
            return BLK[yy - 4][zz], (i - a) + 2, None, None
        return "DB $ED,$%02X" % c, (i - a) + 2, None, None
    if x == 0:
        if z == 0:
            if y == 0:
                return "NOP", (i - a) + 1, None, None
            if y == 1:
                return "EX AF,AF'", (i - a) + 1, None, None
            d = s8(n1)
            t = (i + 2 + d) & 0xFFFF
            if y == 2:
                return "DJNZ %04X" % t, (i - a) + 2, "jrc", t
            if y == 3:
                return "JR %04X" % t, (i - a) + 2, "jr", t
            return "JR %s,%04X" % (CC[y - 4], t), (i - a) + 2, "jrc", t
        if z == 1:
            if q == 0:
                return "LD %s,%04X" % (rp(p), nn), (i - a) + 3, None, None
            return "ADD %s,%s" % (hl(), rp(p)), (i - a) + 1, None, None
        if z == 2:
            tab = [("LD (BC),A", 1), ("LD (DE),A", 1), ("LD (%04X),%s" % (nn, hl()), 3), ("LD (%04X),A" % nn, 3),
                   ("LD A,(BC)", 1), ("LD A,(DE)", 1), ("LD %s,(%04X)" % (hl(), nn), 3), ("LD A,(%04X)" % nn, 3)]
            t, ln = tab[q * 4 + p]
            return t, (i - a) + ln, None, None
        if z == 3:
            return ("INC " if q == 0 else "DEC ") + rp(p), (i - a) + 1, None, None
        if z in (4, 5):
            ln = 2 if (pre and y == 6) else 1
            d = n1 if (pre and y == 6) else 0
            return ("INC " if z == 4 else "DEC ") + reg(y, d), (i - a) + ln, None, None
        if z == 6:
            if pre and y == 6:
                return "LD %s,%02X" % (reg(6, n1), n2), (i - a) + 3, None, None
            return "LD %s,%02X" % (reg(y), n1), (i - a) + 2, None, None
        return ["RLCA", "RRCA", "RLA", "RRA", "DAA", "CPL", "SCF", "CCF"][y], (i - a) + 1, None, None
    if x == 1:
        if y == 6 and z == 6:
            return "HALT", (i - a) + 1, None, None
        if pre and (y == 6 or z == 6):
            d = n1
            return "LD %s,%s" % (reg(y, d) if y == 6 else R[y], reg(z, d) if z == 6 else R[z]), (i - a) + 2, None, None
        return "LD %s,%s" % (reg(y), reg(z)), (i - a) + 1, None, None
    if x == 2:
        if pre and z == 6:
            return ALU[y] + reg(6, n1), (i - a) + 2, None, None
        return ALU[y] + reg(z), (i - a) + 1, None, None
    # x == 3
    if z == 0:
        return "RET %s" % CC[y], (i - a) + 1, "retc", None
    if z == 1:
        if q == 0:
            return "POP " + rp2(p), (i - a) + 1, None, None
        return ["RET", "EXX", "JP (%s)" % hl(), "LD SP,%s" % hl()][p], (i - a) + 1, "ret" if p == 0 else None, None
    if z == 2:
        return "JP %s,%04X" % (CC[y], nn), (i - a) + 3, "jpc", nn
    if z == 3:
        if y == 0:
            return "JP %04X" % nn, (i - a) + 3, "jp", nn
        if y == 2:
            return "OUT (%02X),A" % n1, (i - a) + 2, "out", n1
        if y == 3:
            return "IN A,(%02X)" % n1, (i - a) + 2, "in", n1
        return ["", "", "", "", "EX (SP),%s" % hl(), "EX DE,HL", "DI", "EI"][y], (i - a) + 1, None, None
    if z == 4:
        return "CALL %s,%04X" % (CC[y], nn), (i - a) + 3, "callc", nn
    if z == 5:
        if q == 0:
            return "PUSH " + rp2(p), (i - a) + 1, None, None
        return "CALL %04X" % nn, (i - a) + 3, "call", nn
    if z == 6:
        return ALU[y] + "%02X" % n1, (i - a) + 2, None, None
    return "RST %02X" % (y * 8), (i - a) + 1, "rst", y * 8


def load_page0(path):
    b = open(path, "rb").read()
    t = b[78:].decode("ascii", "replace").replace("\r", "").split("\n")
    d, page, blk = {}, 0, 0
    for ln in t:
        if not ln.startswith(":"):
            continue
        r = bytes.fromhex(ln.split()[0][1:])
        a, ty = (r[1] << 8) | r[2], r[3]
        if ty == 2:
            page = (r[4] << 8) | r[5]
        elif ty == 1:
            blk += 1
        elif blk == 1:
            pg = d.setdefault(page, bytearray(b"\xff" * 0x4000))
            pg[a & 0x3FFF:(a & 0x3FFF) + r[0]] = r[4:4 + r[0]]
    return d


def trace(m, start, maxinsn=400, depth=6):
    """follow the first path from START (conditional branches: fall through), calls entered (depth-limited); report IN/OUT and key loads."""
    out = []
    seen = set()
    count = [0]

    def walk(a, d, a_val):
        while count[0] < maxinsn:
            if (a, d) in seen:
                return
            seen.add((a, d))
            t, ln, kind, tgt = disasm(m, a)
            count[0] += 1
            if t.startswith("LD A,") and not t.startswith("LD A,("):
                try:
                    a_val = int(t.split(",")[1], 16)
                except ValueError:
                    pass
            elif t.startswith("XOR A") or t.startswith("SUB A"):
                a_val = 0
            if kind == "out":
                out.append("%04X  %-16s ; A=%s" % (a, t, ("%02X" % a_val) if a_val is not None else "?"))
            elif kind == "in":
                out.append("%04X  %-16s" % (a, t))
            elif t.startswith(("IM ", "EI", "DI", "HALT", "LD SP")):
                out.append("%04X  %s" % (a, t))
            if kind in ("jp", "jr"):
                a = tgt
                continue
            if kind == "call":
                if d < depth and tgt < 0x4000:
                    out.append("%04X  %s  {" % (a, t))
                    walk(tgt, d + 1, a_val)
                    out.append("      }")
                a += ln
                a_val = None
                continue
            if kind in ("ret",):
                return
            a += ln
    walk(start, 0, None)
    return out


if __name__ == "__main__":
    cmd, f, start = sys.argv[1], sys.argv[2], int(sys.argv[3], 16)
    pg = load_page0(f)[0]
    if cmd == "trace":
        for ln in trace(pg, start, int(sys.argv[4]) if len(sys.argv) > 4 else 400):
            print(ln)
    else:
        a = start
        for _ in range(int(sys.argv[4])):
            t, ln, _k, _t = disasm(pg, a)
            print("%04X  %-24s %s" % (a, " ".join("%02X" % v for v in pg[a:a + ln]), t))
            a += ln
