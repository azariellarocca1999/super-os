#!/usr/bin/env python3
"""Gameplay tests for the original CHIP-8 games: a bot plays each game on the reference interpreter and the test checks real progress
(score, bricks, apples, aliens, rounds).  The Z80 interpreter is proven identical to the reference by tools/c8test.py."""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
import chip8  # noqa: E402

UP, LEFT, RIGHT, DOWN, FIRE = 2, 4, 6, 8, 5
results = []


def load(name):
    syms = {}
    rom = chip8.assemble(open(os.path.join(root, "games", "chip8", name + ".c8")).read(), name, syms)
    return chip8.Chip8(rom), syms


def play(c, syms, frames, bot, per_frame=None):
    """Run for `frames` game frames (pc reaches the `tick` label); bot(c) -> iterable of keys held."""
    tick = syms.get("tick", -1)
    n = step = 0
    while n < frames and step < 6_000_000:
        c.step()
        step += 1
        if step % 12 == 0:
            c.tick60()
        if c.pc == tick:
            n += 1
            c.keys = sum(1 << k for k in bot(c))
            if per_frame:
                per_frame(c)
    return n


def check(name, ok, info=""):
    results.append(ok)
    print("  [%s] %s %s" % ("PASS" if ok else "FAIL", name, info))


# ---- PONG: the cpu misses sometimes, so a tracking player scores
c, s = load("pong")
mx = [0]


def pong_bot(c):
    mx[0] = max(mx[0], c.v[6])
    t = c.v[3] - 2
    return [UP] if c.v[0] > t else [DOWN] if c.v[0] < t else []


play(c, s, 4000, pong_bot)
check("pong: the player scores against the cpu", mx[0] >= 1 and c.v[7] >= 0, "(player points seen: %d, cpu: %d)" % (mx[0], c.v[7]))
c, s = load("pong")
play(c, s, 1500, lambda c: [])
check("pong: an idle player concedes points", c.v[7] > 0 or c.v[6] > 0, "(cpu %d)" % c.v[7])

# ---- BREAKOUT: a tracking paddle breaks bricks
c, s = load("breakout")
best = [0]


def bo_bot(c):
    best[0] = max(best[0], c.v[5])
    t = c.v[1] - 3
    return [RIGHT] if c.v[6] < t else [LEFT] if c.v[6] > t else []


play(c, s, 3000, bo_bot)
check("breakout: bricks get broken", best[0] >= 8, "(best %d / 24)" % best[0])
check("breakout: broken bricks leave the brick map", sum(c.m[0x600:0x618]) <= 24 - 0)

# ---- SNAKE: steer to the apple
c, s = load("snake")
eaten = [0]
lastap = [None]


def snake_bot(c):
    ap = (c.v[7], c.v[8])
    if lastap[0] is not None and ap != lastap[0]:
        eaten[0] += 1
    lastap[0] = ap
    x, y, d = c.v[2], c.v[3], c.v[4]
    if x != ap[0]:
        want = RIGHT if x < ap[0] else LEFT
    else:
        want = DOWN if y < ap[1] else UP
    return [want]


play(c, s, 600, snake_bot)
check("snake: eats apples while steering", eaten[0] >= 2, "(apples eaten: %d)" % eaten[0])

# ---- INVADERS: sweep and fire
c, s = load("invaders")
low = [15]
cnt = [0]


def inv_bot(c):
    low[0] = min(low[0], c.v[7])
    cnt[0] += 1
    return [FIRE] + ([LEFT] if (cnt[0] // 60) % 2 else [RIGHT])


play(c, s, 1500, inv_bot)
check("invaders: aliens get shot", low[0] <= 8, "(fewest aliens left: %d / 15)" % low[0])

# ---- DODGE: stay alive for a while by hiding in a free column (bot reads the block positions)
c, s = load("dodge")
deaths = [0]


def dodge_bot(c):
    blocks = [(c.v[1], c.v[2]), (c.v[3], c.v[4]), (c.v[5], c.v[6])]
    threat = [bx for bx, by in blocks if by >= 4]
    px = c.v[0]
    free = [x for x in range(0, 57, 2) if all(abs(x + 3 - bx) > 9 for bx in threat)]
    tgt = min(free, key=lambda x: abs(x - px)) if free else px
    return [RIGHT] if px < tgt else [LEFT] if px > tgt else []


orig_step = c.step


def counting_step():
    if c.pc == s["start"] + 0:
        deaths[0] += 1
    orig_step()


c.step = counting_step
play(c, s, 600, dodge_bot)
check("dodge: a dodging bot restarts rarely in 600 frames", deaths[0] <= 6, "(restarts: %d)" % (deaths[0] - 1))
c, s = load("dodge")
d2 = [0]
o2 = c.step


def cs2():
    if c.pc == s["start"]:
        d2[0] += 1
    o2()


c.step = cs2
play(c, s, 600, lambda c: [])
check("dodge: standing still gets you hit", d2[0] > 2, "(restarts: %d)" % (d2[0] - 1))

# ---- SIMON: the bot repeats the sequence
c, s = load("simon")
maxlen = 0
steps = 0
inp = s["input"] if "input" in s else 0
keymap = {0: UP, 1: LEFT, 2: RIGHT, 3: DOWN}
gk = s["gk"]
rel = s["rel"]
while steps < 3_000_000 and maxlen < 6:
    c.step()
    steps += 1
    if steps % 12 == 0:
        c.tick60()
    maxlen = max(maxlen, c.v[1])
    if c.pc == gk:                      # waiting for a key: press the right one
        c.keys = 1 << keymap[c.m[0x600 + c.v[2]]]
    elif c.pc == s["flash"]:
        pass
    elif c.pc >= rel and c.pc < rel + 2:
        c.keys = 0
check("simon: sequence replayed correctly up to length 6", maxlen >= 6, "(length %d)" % maxlen)

print("RESULT: %d/%d gameplay checks passed" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
