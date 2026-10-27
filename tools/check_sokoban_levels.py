#!/usr/bin/env python3
"""Static check of the Sokoban levels (runs in CI, needs only Python): every level is well formed, fits 16 x 9 and has a solution."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sokoban_lib as L  # noqa: E402

levels = L.load_levels()
bad = 0
if len(levels) != 8:
    print("expected 8 levels (SK_N in sokoban.z80), found", len(levels))
    bad += 1
for i, lv in enumerate(levels, 1):
    problems = L.validate(lv)
    sol = None if problems else L.solve(lv, fast=True)
    if sol is None and not problems:
        problems.append("no solution found")
    print("level %d: %dx%d %s" % (i, max(map(len, lv)), len(lv), ("%d moves" % len(sol)) if sol else "; ".join(problems)))
    bad += bool(problems)
sys.exit(1 if bad else 0)
