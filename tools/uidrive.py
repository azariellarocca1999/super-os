#!/usr/bin/env python3
"""Drive the emulator with firmware key codes (names or numbers) and take snapshots: helper for UI checks.
Usage in Python:  from uidrive import Session; s = Session("tag"); s.press("WINDOW","1"); s.type("2+3"); s.snap("a"); s.run()"""
import os
import re
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
sim = os.path.join(root, "tools", "bin", "hz80_sim.exe")
rom = os.path.join(root, "build", "superos.rom")
out = os.path.join(root, "build", "test")
os.makedirs(out, exist_ok=True)

KEYS = dict(DOWN=1, LEFT=2, RIGHT=3, UP=4, ENTER=9, PLUS=10, MINUS=11, MUL=12, DIV=13, POW=14, CLEAR=15, NEG=17, K3=18, K6=19, K9=20, RPAR=21,
            TAN=22, VARS=23, DOT=25, K2=26, K5=27, K8=28, LPAR=29, COS=30, PRGM=31, STAT=32, K0=33, K1=34, K4=35, K7=36, COMMA=37, SIN=38,
            APPS=39, X=40, STO=42, LN=43, LOG=44, SQ=45, INV=46, MATH=47, ALPHA=48, GRAPH=49, TRACE=50, ZOOM=51, WINDOW=52, YEQ=53,
            SND=54, MODE=55, DEL=56)
CHARS = {"0": "K0", "1": "K1", "2": "K2", "3": "K3", "4": "K4", "5": "K5", "6": "K6", "7": "K7", "8": "K8", "9": "K9", "+": "PLUS", "-": "MINUS",
         "*": "MUL", "/": "DIV", "^": "POW", "(": "LPAR", ")": "RPAR", ".": "DOT", ",": "COMMA", "X": "X"}


def kc(code):
    return "%d.%d" % ((code - 1) // 8, (code - 1) % 8)


class Session:
    def __init__(self, tag, start=1500, step=130, hold=50):
        self.tag, self.t, self.step, self.hold, self.ev = tag, start, step, hold, []

    def key(self, name):
        code = KEYS[name] if isinstance(name, str) else name
        self.ev += ["%d:down:%s" % (self.t, kc(code)), "%d:up:%s" % (self.t + self.hold, kc(code))]
        self.t += self.step

    def press(self, *names):
        for n in names:
            self.key(n)

    def type(self, text):
        for ch in text:
            self.key(CHARS[ch])

    def second(self, name):
        self.key("SND")
        self.key(name)

    def snap(self, name, wait=250):
        self.t += wait
        self.ev.append("%d:snap:%s" % (self.t, name))
        self.t += 100

    def run(self, extra_ms=300, env=None):
        total = self.t + extra_ms
        r = subprocess.run([sim, rom, os.path.join(out, self.tag), str(total)] + self.ev, capture_output=True, text=True,
                           env=dict(os.environ, **(env or {})), timeout=900)
        return r.stdout

    def png(self, name, scale=5):
        src = os.path.join(out, self.tag + "_" + name + ".pbm")
        if not os.path.exists(src):
            src = os.path.join(out, self.tag + ".pbm")
        dst = os.path.join(out, self.tag + "_" + name + ".png")
        subprocess.run([sys.executable, os.path.join(root, "tools", "pbm2png.py"), src, dst, str(scale)])
        return dst


def pbm_text(tag, name=None):
    p = os.path.join(out, tag + ("_" + name if name else "") + ".pbm")
    toks = open(p).read().split()
    return [[int(toks[3 + y * 96 + x]) for x in range(96)] for y in range(64)]


def parse_mem(stdout):
    m = re.search(r"MEM \w+:((?: [0-9A-F]{2})+)", stdout)
    return bytes(int(x, 16) for x in m.group(1).split()) if m else b""


def cstr(b, off=0):
    return b[off:].split(b"\0")[0].decode("latin-1")


# math RAM map (z80-os/math/mathram.inc, edit.z80, graph.z80)
M_BASE = 0x9E00
ED_BASE = M_BASE + 0x160
C_HIST = ED_BASE + 250
GR_BASE = ED_BASE + 420
