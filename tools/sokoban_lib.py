"""Sokoban helpers: parse z80-os/games/sokoban_levels.inc, validate the levels and solve them into key presses (used by selftest_sokoban.py and
check_sokoban_levels.py, which also runs in CI)."""
import os
import re
from collections import deque

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = {"RIGHT": (1, 0), "LEFT": (-1, 0), "DOWN": (0, 1), "UP": (0, -1)}


def load_levels(path=None):
    path = path or os.path.join(root, "z80-os", "games", "sokoban_levels.inc")
    levels, cur = [], []
    for line in open(path):
        m = re.match(r'\s*\.db\s+"(.*)",0\s*$', line)
        if m:
            cur.append(m.group(1))
        elif re.match(r"\s*\.db\s+0\s*(;.*)?$", line):
            if cur:
                levels.append(cur)
                cur = []
    return levels


def parse(level):
    walls, goals, boxes, player = set(), set(), set(), None
    for y, row in enumerate(level):
        for x, c in enumerate(row):
            if c == "#":
                walls.add((x, y))
            if c in ".*+":
                goals.add((x, y))
            if c in "$*":
                boxes.add((x, y))
            if c in "@+":
                player = (x, y)
    return walls, goals, boxes, player


def validate(level):
    """Problems of a level as a list of strings (empty = fine): size, one player, boxes == goals, closed by walls."""
    bad = []
    w, h = max(len(r) for r in level), len(level)
    if w > 16 or h > 9:
        bad.append("size %dx%d exceeds 16x9" % (w, h))
    walls, goals, boxes, player = parse(level)
    if player is None:
        bad.append("no player")
    if len(goals) != len(boxes) or not boxes:
        bad.append("%d boxes for %d goals" % (len(boxes), len(goals)))
    if "".join(level).count("@") + "".join(level).count("+") != 1:
        bad.append("not exactly one player")
    if any(ch not in "#.$*@+ " for r in level for ch in r):
        bad.append("unknown character")
    if player:                                   # the area the player can reach must be enclosed by walls
        seen, q = {player}, deque([player])
        while q:
            x, y = q.popleft()
            for dx, dy in DIRS.values():
                n = (x + dx, y + dy)
                if n in walls or n in seen:
                    continue
                if not (0 <= n[1] < len(level) and 0 <= n[0] < len(level[n[1]])):
                    bad.append("open to the outside at %s" % (n,))
                    return bad
                seen.add(n)
                q.append(n)
    return bad


def _reach(walls, boxes, start):
    """cell -> (previous cell, key) for everything the player can walk to."""
    prev = {start: None}
    q = deque([start])
    while q:
        c = q.popleft()
        for k, (dx, dy) in DIRS.items():
            n = (c[0] + dx, c[1] + dy)
            if n in walls or n in boxes or n in prev:
                continue
            prev[n] = (c, k)
            q.append(n)
    return prev


def _path(prev, dst):
    keys = []
    while prev[dst]:
        dst, k = prev[dst]
        keys.append(k)
    return keys[::-1]


def solve(level, limit=400000):
    """Shortest-push solution as a list of key names (None when there is none within the limit)."""
    walls, goals, boxes, player = parse(level)
    goals = frozenset(goals)
    start = frozenset(boxes)
    pr = _reach(walls, start, player)
    seen = {(start, min(pr))}
    q = deque([(start, player, [])])
    while q:
        bx, pl, keys = q.popleft()
        if bx == goals:
            return keys
        pr = _reach(walls, bx, pl)
        for b in bx:
            for k, (dx, dy) in DIRS.items():
                src, dst = (b[0] - dx, b[1] - dy), (b[0] + dx, b[1] + dy)
                if src not in pr or dst in walls or dst in bx:
                    continue
                nb = frozenset((bx - {b}) | {dst})
                key = (nb, min(_reach(walls, nb, b)))
                if key in seen:
                    continue
                seen.add(key)
                if len(seen) > limit:
                    return None
                q.append((nb, b, keys + _path(pr, src) + [k]))
    return None
