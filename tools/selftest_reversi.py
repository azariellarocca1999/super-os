#!/usr/bin/env python3
"""Reversi on the headless emulator against the Python reference rules (reversi_ref.py): a bot plays whole games; after every move the board
the calculator left must be exactly what the rules allow (your flips, then a legal CPU reply that the CPU's scoring could have picked,
passes included); at the end the result overlay, the margin and the best-score slot are checked.
Called from selftest.py; `python tools/selftest_reversi.py` runs only this part."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
import reversi_ref as R  # noqa: E402
from uidrive import Session, parse_mem, pbm_text  # noqa: E402

check = S.check


def lit(tag, name, y0, y1):
    p = pbm_text(tag, name)
    return sum(sum(p[y]) for y in range(y0, y1))


def cursor_keys(cx, cy, x, y):
    keys = []
    dx, dy = (x - cx) % 8, (y - cy) % 8
    keys += ["RIGHT"] * dx if dx <= 4 else ["LEFT"] * (8 - dx)
    keys += ["DOWN"] * dy if dy <= 4 else ["UP"] * (8 - dy)
    return keys


def run_game(tag, strategy, seed):
    rng = random.Random(seed)
    board, hist, waits = R.start(), [], []
    stats = {"moves": 0, "cpu_multi": 0, "bad": None}
    for _ in range(40):
        pm = R.moves(board, 1)
        if not pm:
            break
        if strategy == "greedy":
            best = max(R.value(board, x, y, 1) for x, y in pm)
            x, y = rng.choice([m for m in pm if R.value(board, x=m[0], y=m[1], pl=1) == best])
        else:
            x, y = rng.choice(pm)
        hist.append((x, y))
        s = Session(tag, start=1500)
        s.press("TRACE", "K9", "K1")
        s.t += 600
        cx, cy = 3, 2
        for (hx, hy), w in zip(hist, waits + [0]):
            s.press(*cursor_keys(cx, cy, hx, hy))
            cx, cy = hx, hy
            s.press("ENTER")
            s.t += w if w else 700
        s.t += 500 + 400 * 3
        out = s.run(extra_ms=100, env={"HZ_DUMP": "A900", "HZ_DUMPLEN": "64"})
        obs = list(parse_mem(out))
        mine = R.play(board, x, y, 1)
        match = [(b, p) for b, p in R.cpu_outcomes(mine) if b == obs]
        stats["moves"] += 1
        if not match:
            stats["bad"] = "after your move %d %s: observed %s expected one of %d outcomes" % (len(hist), (x, y), "".join(map(str, obs)), len(R.cpu_outcomes(mine)))
            return board, stats, hist
        played = match[0][1]
        stats["cpu_multi"] += len(played) > 1 or not played
        board = obs
        waits.append(400 * (1 + len(played)) + 500)
    return board, stats, hist


def finish(tag, hist, waits_hint=1500):
    """Replay the whole game once more, then look at the result overlay and the best-score slot ($8718 = s_hisc + 2 * 8)."""
    s = Session(tag + "_end", start=1500)
    s.press("TRACE", "K9", "K1")
    s.t += 600
    cx, cy = 3, 2
    for hx, hy in hist:
        s.press(*cursor_keys(cx, cy, hx, hy))
        cx, cy = hx, hy
        s.press("ENTER")
        s.t += 1600
    s.snap("end", wait=800)
    out = s.run(extra_ms=100, env={"HZ_DUMP": "8718", "HZ_DUMPLEN": "2"})
    return parse_mem(out)


def run(check_fn=None):
    global check
    if check_fn:
        check = check_fn
    print("== 28. Reversi against the reference rules (whole games)")
    for name, strategy, seed in (("greedy", "greedy", 1), ("random", "random", 7)):
        tag = "rvref_" + name
        board, st, hist = run_game(tag, strategy, seed)
        check("REVERSI (%s bot): every position after your move + the CPU's reply is legal and the CPU's pick is among its best scores" % name,
              st["bad"] is None, "(%d moves checked; %s)" % (st["moves"], st["bad"] or "ok"))
        over = not R.moves(board, 1) and not R.moves(board, 2)
        check("REVERSI (%s bot): the game ends when neither side can move" % name, over, "(%d vs %d discs, %d empty)" % (R.score(board) + (board.count(0),)))
        if st["bad"] or not over:
            continue
        mem = finish(tag, hist)
        you, cpu = R.score(board)
        margin = you - cpu if you > cpu else 0
        check("REVERSI (%s bot): the result overlay is shown and the best score = the winning margin (%d)" % (name, margin),
              lit(tag + "_end", "end", 14, 50) > 100 and (mem[0] | mem[1] << 8) == margin, "(best=%d)" % (mem[0] | mem[1] << 8))


if __name__ == "__main__":
    run()
    print("RESULT: %d/%d" % (sum(S.results), len(S.results)))
    sys.exit(0 if all(S.results) else 1)
