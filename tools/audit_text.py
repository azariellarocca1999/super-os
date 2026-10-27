#!/usr/bin/env python3
"""Text overflow audit: every UI string (Spanish and English) must fit the screen.
The 4x6 font has 24 columns (the 6x8 font 16), titles sit in a bar of 24 columns.  Prints the strings that are too long and exits 1 if any
string exceeds 24 columns.   python tools/audit_text.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_strings as G  # noqa: E402

MAX = 24
bad = 0
long16 = []
for name, es, en in G.S:
    for lang, t in (("ES", G.clean(es)), ("EN", G.clean(en))):
        if len(t) > MAX:
            print("TOO LONG (%d > %d)  STR_%s [%s] %r" % (len(t), MAX, name, lang, t))
            bad += 1
        elif len(t) > 16:
            long16.append((name, lang, len(t)))
# string literals written directly in the sources (games, UI pages): "text" inside .db lines
import re  # noqa: E402

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
n_lit = 0
for sub in ("games", "ui"):
    d = os.path.join(root, "z80-os", sub)
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".z80"):
            continue
        for ln, line in enumerate(open(os.path.join(d, fn), encoding="utf-8"), 1):
            if ".db" not in line:
                continue
            for lit in re.findall(r'"([^"]*)"', line.split(";")[0]):
                n_lit += 1
                limit = 22 if line.split(":")[0] in ("glp_h", "glo_h", "g2_h_win") else MAX   # overlay hints sit inside a box: 22 columns
                if len(lit) > limit:
                    print("TOO LONG (%d > %d)  z80-os/%s/%s:%d %r" % (len(lit), limit, sub, fn, ln, lit))
                    bad += 1
print("%d strings + %d source literals checked, %d too long for the 24-column screen; %d are longer than 16 columns (clipped only when the 6x8 font is selected)" % (
    len(G.S), n_lit, bad, len(long16)))
sys.exit(1 if bad else 0)
