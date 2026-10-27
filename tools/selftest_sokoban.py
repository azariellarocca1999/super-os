#!/usr/bin/env python3
"""Sokoban on the headless emulator: every level is solved with the keys the solver found (sokoban_lib.py), one after the other in one session;
the level-cleared overlay, the progress in the best-score slot, the wrap-around after the last level and the restart key are checked.
Called from selftest.py; `python tools/selftest_sokoban.py` runs only this part."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
import sokoban_lib as L  # noqa: E402
from uidrive import Session, parse_mem, pbm_text  # noqa: E402

check = S.check


def lit(tag, name, y0=0, y1=64):
    p = pbm_text(tag, name)
    return sum(sum(p[y]) for y in range(y0, y1))


def run(check_fn=None):
    global check
    if check_fn:
        check = check_fn
    print("== 29. Sokoban: all levels solved in the emulator")
    levels = L.load_levels()
    sols = [L.solve(lv) for lv in levels]
    s = Session("sk_all", start=1500)
    s.press("TRACE", "K8")
    s.t += 600
    for i, sol in enumerate(sols, 1):
        s.snap("l%d" % i, wait=200)
        for k in sol:
            s.press(k)
            s.t += 130
        s.snap("done%d" % i, wait=500)
        s.press("ENTER")                     # leave the level-cleared overlay
        s.t += 600
    s.snap("wrap", wait=300)
    out = s.run(extra_ms=100, env={"HZ_DUMP": "8700", "HZ_DUMPLEN": "64"})
    m = parse_mem(out)
    best = m[0x16] | m[0x17] << 8
    check("SOKOBAN: all 8 levels solve with the solver's keys (best score = 8 levels cleared)", best == 8, "(best=%d)" % best)
    check("SOKOBAN: each level shows its own board, then the cleared overlay",
          all(lit("sk_all", "l%d" % i, 8, 64) > 150 and lit("sk_all", "done%d" % i, 14, 50) > 100 for i in range(1, 9)),
          "(lit %s)" % [lit("sk_all", "l%d" % i, 8, 64) for i in range(1, 9)])
    check("SOKOBAN: after the last level the game wraps back to level 1 (same board as at the start)",
          lit("sk_all", "wrap", 8, 64) == lit("sk_all", "l1", 8, 64), "(lit %d vs %d)" % (lit("sk_all", "wrap", 8, 64), lit("sk_all", "l1", 8, 64)))
    s.png("l8", 4)

    s = Session("sk_rs", start=1500)
    s.press("TRACE", "K8")
    s.t += 600
    s.press("RIGHT")
    s.t += 300
    s.press("ENTER")                         # restart the level
    s.t += 400
    out = s.run(extra_ms=100, env={"HZ_DUMP": "A440", "HZ_DUMPLEN": "8"})
    m = parse_mem(out)
    check("SOKOBAN: 2ND / ENTER restarts the level (moves 0, player back at (7,4))", m[3] == 0 and m[0] == 7 and m[1] == 4, "(x=%d y=%d moves=%d)" % (m[0], m[1], m[3]))


if __name__ == "__main__":
    run()
    print("RESULT: %d/%d" % (sum(S.results), len(S.results)))
    sys.exit(0 if all(S.results) else 1)
