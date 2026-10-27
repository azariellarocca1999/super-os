#!/usr/bin/env python3
"""Duplicate-name check for the Z80 sources.  spasm-ng labels are global, case-insensitive and a label may silently share its name with an
`.equ` (the later one wins and jumps land in the wrong place: this once sent Snake into RAM).  Scans every .z80 / .inc / .asm file that is
assembled together per page and reports names defined more than once.   python tools/check_labels.py   (exit 1 on duplicates)"""
import os
import re
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = {
    "page0": ["z80-os/kernel/page0.z80"],
    "page1": ["z80-os/ui/page1.z80"],
    "page3": ["z80-os/math/page3.z80"],
    "page4": ["z80-os/apps/page4.z80"],
    "page5": ["z80-os/games/page5.z80"],
}
INC = re.compile(r'^\s*#include\s+"([^"]+)"')
LAB = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")
EQU = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s+\.equ\b", re.I)


def find(rel, base):
    for d in (os.path.join(root, "z80-os"), os.path.join(root, "build"), os.path.dirname(base), root):
        p = os.path.join(d, rel)
        if os.path.exists(p):
            return p
    return None


def walk(path, seen, defs):
    if path in seen:
        return
    seen.add(path)
    for n, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        m = INC.match(line)
        if m:
            q = find(m.group(1), path)
            if q:
                walk(q, seen, defs)
            continue
        m = LAB.match(line) or EQU.match(line)
        if m:
            defs.setdefault(m.group(1).lower(), []).append((os.path.relpath(path, root), n))


ALLOWED = {"ui_entry"}          # UI_ENTRY (equ) and the ui_entry label are the same address on purpose
bad = 0
for name, entries in PAGES.items():
    defs = {}
    walk(os.path.join(root, entries[0]), set(), defs)
    for k, v in sorted(defs.items()):
        if len(v) > 1 and k not in ALLOWED:
            bad += 1
            print("%s: '%s' defined %d times: %s" % (name, k, len(v), ", ".join("%s:%d" % x for x in v)))
print("check_labels: %d duplicated names" % bad)
sys.exit(1 if bad else 0)
