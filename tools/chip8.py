#!/usr/bin/env python3
"""CHIP-8 toolchain for Super-OS: assembler + reference interpreter (the Z80 interpreter in z80-os/games/chip8.z80 is tested against it).

Semantics implemented (same on the Z80, on the ESP32 and here):
  * 4 KB memory, programs load at $200, built-in hex font at $050 (5 bytes per digit)
  * 64x32 monochrome display, sprites XOR, start coordinates wrap, pixels past the edge are clipped
  * 8xy6 / 8xyE shift Vy into Vx; Fx55 / Fx65 leave I = I + x + 1; Bnnn = nnn + V0; logic ops leave VF alone
  * Fx0A waits for a key press; timers count down at 60 Hz
  * no SCHIP instructions
Assembler syntax: one instruction per line, `label:`, `name .equ value`, `db a,b,..` (numbers: 12, 0x1F, 0b1010_0000), `;` comments.
"""
import re
import sys

FONT = [0xF0, 0x90, 0x90, 0x90, 0xF0, 0x20, 0x60, 0x20, 0x20, 0x70, 0xF0, 0x10, 0xF0, 0x80, 0xF0, 0xF0, 0x10, 0xF0, 0x10, 0xF0,
        0x90, 0x90, 0xF0, 0x10, 0x10, 0xF0, 0x80, 0xF0, 0x10, 0xF0, 0xF0, 0x80, 0xF0, 0x90, 0xF0, 0xF0, 0x10, 0x20, 0x40, 0x40,
        0xF0, 0x90, 0xF0, 0x90, 0xF0, 0xF0, 0x90, 0xF0, 0x10, 0xF0, 0xF0, 0x90, 0xF0, 0x90, 0x90, 0xE0, 0x90, 0xE0, 0x90, 0xE0,
        0xF0, 0x80, 0x80, 0x80, 0xF0, 0xE0, 0x90, 0x90, 0x90, 0xE0, 0xF0, 0x80, 0xF0, 0x80, 0xF0, 0xF0, 0x80, 0xF0, 0x80, 0x80]
FONT_ADDR = 0x50
LOAD = 0x200


# ------------------------------------------------------------------------------------------------ assembler
def _num(tok, syms):
    tok = tok.strip()
    if re.fullmatch(r"-?0b[01_]+", tok):
        return int(tok.replace("_", ""), 2)
    if re.fullmatch(r"-?0x[0-9a-fA-F]+", tok):
        return int(tok, 16)
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    if tok in syms:
        return syms[tok]
    raise KeyError(tok)


def assemble(src, name="?", syms_out=None):
    lines = []
    for n, raw in enumerate(src.splitlines(), 1):
        line = raw.split(";")[0].strip()
        if line:
            lines.append((n, line))
    syms = {}
    for it in range(2):                      # pass 0 collects labels (unknown symbols = 0), pass 1 emits
        out = bytearray()
        for n, line in lines:
            try:
                m = re.match(r"^(\w+)\s+\.equ\s+(.+)$", line)
                if m:
                    try:
                        syms[m.group(1)] = _num(m.group(2), syms)
                    except KeyError:
                        syms[m.group(1)] = 0
                    continue
                while True:
                    m = re.match(r"^(\w+):\s*(.*)$", line)
                    if not m:
                        break
                    syms[m.group(1)] = LOAD + len(out)
                    line = m.group(2)
                if not line:
                    continue
                out += _ins(line, syms, it)
            except Exception as e:
                raise SystemExit("%s:%d: %s: %s (%s)" % (name, n, line, e, type(e).__name__))
    if syms_out is not None:
        syms_out.update(syms)
    return bytes(out)


def _ins(line, syms, final):
    mn, _, rest = line.partition(" ")
    mn = mn.lower()
    a = [x.strip() for x in rest.split(",")] if rest.strip() else []

    def val(t):
        try:
            return _num(t, syms)
        except KeyError:
            if not final:
                return 0
            raise

    if mn == "db":
        return bytes(val(x) & 0xFF for x in a)
    isv = lambda t: re.fullmatch(r"[vV][0-9a-fA-F]", t) is not None
    r = lambda t: int(t[1], 16)
    w = lambda x: bytes([(x >> 8) & 0xFF, x & 0xFF])
    if mn == "cls":
        return w(0x00E0)
    if mn == "ret":
        return w(0x00EE)
    if mn == "jp":
        if len(a) == 2:
            return w(0xB000 | val(a[1]) & 0xFFF)
        return w(0x1000 | val(a[0]) & 0xFFF)
    if mn == "call":
        return w(0x2000 | val(a[0]) & 0xFFF)
    if mn in ("se", "sne"):
        base = (0x3000, 0x5000) if mn == "se" else (0x4000, 0x9000)
        if isv(a[1]):
            return w(base[1] | r(a[0]) << 8 | r(a[1]) << 4)
        return w(base[0] | r(a[0]) << 8 | val(a[1]) & 0xFF)
    if mn == "ld":
        d, s = a[0].lower(), a[1].lower()
        if isv(d):
            if isv(s):
                return w(0x8000 | r(d) << 8 | r(s) << 4)
            if s == "dt":
                return w(0xF007 | r(d) << 8)
            if s == "k":
                return w(0xF00A | r(d) << 8)
            if s == "[i]":
                return w(0xF065 | r(d) << 8)
            return w(0x6000 | r(d) << 8 | val(a[1]) & 0xFF)
        if d == "i":
            return w(0xA000 | val(a[1]) & 0xFFF)
        if d == "dt":
            return w(0xF015 | r(s) << 8)
        if d == "st":
            return w(0xF018 | r(s) << 8)
        if d == "f":
            return w(0xF029 | r(s) << 8)
        if d == "b":
            return w(0xF033 | r(s) << 8)
        if d == "[i]":
            return w(0xF055 | r(s) << 8)
        raise ValueError("ld")
    if mn == "add":
        if a[0].lower() == "i":
            return w(0xF01E | r(a[1]) << 8)
        if isv(a[1]):
            return w(0x8004 | r(a[0]) << 8 | r(a[1]) << 4)
        return w(0x7000 | r(a[0]) << 8 | val(a[1]) & 0xFF)
    ops = {"or": 1, "and": 2, "xor": 3, "sub": 5, "subn": 7}
    if mn in ops:
        return w(0x8000 | r(a[0]) << 8 | r(a[1]) << 4 | ops[mn])
    if mn in ("shr", "shl"):
        y = r(a[1]) if len(a) > 1 else r(a[0])
        return w(0x8000 | r(a[0]) << 8 | y << 4 | (6 if mn == "shr" else 0xE))
    if mn == "rnd":
        return w(0xC000 | r(a[0]) << 8 | val(a[1]) & 0xFF)
    if mn == "drw":
        return w(0xD000 | r(a[0]) << 8 | r(a[1]) << 4 | val(a[2]) & 0xF)
    if mn == "skp":
        return w(0xE09E | r(a[0]) << 8)
    if mn == "sknp":
        return w(0xE0A1 | r(a[0]) << 8)
    raise ValueError("unknown mnemonic")


# ------------------------------------------------------------------------------------------------ reference interpreter
class Chip8:
    def __init__(self, rom, seed=1):
        self.m = bytearray(4096)
        self.m[FONT_ADDR:FONT_ADDR + 80] = bytes(FONT)
        self.m[LOAD:LOAD + len(rom)] = rom
        self.v = [0] * 16
        self.i = 0
        self.pc = LOAD
        self.sp = []
        self.dt = self.st = 0
        self.d = [[0] * 64 for _ in range(32)]
        self.keys = 0                        # bitmask of held keys
        self.rng = 0xACE1                    # 16-bit Galois LFSR, 8 steps per RND (same code on the Z80 and on the ESP32)
        self.dirty = False

    def rnd(self):
        x = self.rng
        for _ in range(8):
            x = (x >> 1) ^ (0xB400 if x & 1 else 0)
        self.rng = x
        return x & 255

    def step(self):
        m, v = self.m, self.v
        self.pc &= 0xFFF
        op = m[self.pc] << 8 | m[(self.pc + 1) & 0xFFF]
        self.pc = (self.pc + 2) & 0xFFF
        x, y, n, kk, nnn = op >> 8 & 15, op >> 4 & 15, op & 15, op & 255, op & 0xFFF
        t = op >> 12
        if t == 0:
            if op == 0x00E0:
                self.d = [[0] * 64 for _ in range(32)]
                self.dirty = True
            elif op == 0x00EE:
                self.pc = self.sp.pop()
        elif t == 1:
            self.pc = nnn
        elif t == 2:
            self.sp.append(self.pc)
            self.pc = nnn
        elif t == 3:
            if v[x] == kk:
                self.pc += 2
        elif t == 4:
            if v[x] != kk:
                self.pc += 2
        elif t == 5:
            if v[x] == v[y]:
                self.pc += 2
        elif t == 6:
            v[x] = kk
        elif t == 7:
            v[x] = (v[x] + kk) & 255
        elif t == 8:
            a, b = v[x], v[y]
            if n == 0:
                v[x] = b
            elif n == 1:
                v[x] = a | b
            elif n == 2:
                v[x] = a & b
            elif n == 3:
                v[x] = a ^ b
            elif n == 4:
                s = a + b
                v[x] = s & 255
                v[15] = 1 if s > 255 else 0
            elif n == 5:
                v[x] = (a - b) & 255
                v[15] = 1 if a >= b else 0
            elif n == 6:
                v[x] = b >> 1
                v[15] = b & 1
            elif n == 7:
                v[x] = (b - a) & 255
                v[15] = 1 if b >= a else 0
            elif n == 14:
                v[x] = (b << 1) & 255
                v[15] = b >> 7
        elif t == 9:
            if v[x] != v[y]:
                self.pc += 2
        elif t == 10:
            self.i = nnn
        elif t == 11:
            self.pc = (nnn + v[0]) & 0xFFF
        elif t == 12:
            v[x] = self.rnd() & kk
        elif t == 13:
            px, py = v[x] & 63, v[y] & 31
            v[15] = 0
            for r in range(n):
                yy = py + r
                if yy > 31:
                    break
                bits = m[(self.i + r) & 0xFFF]
                for c in range(8):
                    xx = px + c
                    if xx > 63:
                        break
                    if bits >> (7 - c) & 1:
                        if self.d[yy][xx]:
                            v[15] = 1
                        self.d[yy][xx] ^= 1
            self.dirty = True
        elif t == 14:
            held = self.keys >> (v[x] & 15) & 1
            if (kk == 0x9E and held) or (kk == 0xA1 and not held):
                self.pc += 2
        elif t == 15:
            if kk == 0x07:
                v[x] = self.dt
            elif kk == 0x0A:                 # no key held: run this instruction again
                if self.keys:
                    v[x] = (self.keys & -self.keys).bit_length() - 1
                else:
                    self.pc -= 2
            elif kk == 0x15:
                self.dt = v[x]
            elif kk == 0x18:
                self.st = v[x]
            elif kk == 0x1E:
                self.i = (self.i + v[x]) & 0xFFF
            elif kk == 0x29:
                self.i = FONT_ADDR + 5 * (v[x] & 15)
            elif kk == 0x33:
                m[self.i] = v[x] // 100
                m[self.i + 1] = v[x] // 10 % 10
                m[self.i + 2] = v[x] % 10
            elif kk == 0x55:
                for r in range(x + 1):
                    m[self.i + r] = v[r]
                self.i += x + 1
            elif kk == 0x65:
                for r in range(x + 1):
                    v[r] = m[self.i + r]
                self.i += x + 1
        self.pc &= 0xFFF

    def tick60(self):
        if self.dt:
            self.dt -= 1
        if self.st:
            self.st -= 1

    def run(self, instrs, per_tick=12):
        for k in range(instrs):
            self.step()
            if (k + 1) % per_tick == 0:
                self.tick60()

    def text(self):
        return "\n".join("".join("#" if p else "." for p in row) for row in self.d)

    def display_bytes(self):
        out = bytearray()
        for row in self.d:
            for b in range(8):
                out.append(sum(row[b * 8 + c] << (7 - c) for c in range(8)))
        return bytes(out)


if __name__ == "__main__":
    rom = assemble(open(sys.argv[1]).read(), sys.argv[1])
    c = Chip8(rom)
    c.run(int(sys.argv[2]) if len(sys.argv) > 2 else 2000)
    print(c.text())
