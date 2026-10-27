#!/usr/bin/env python3
"""Generate z80-os/games/sokoban_levels.inc.

Every level is built by playing backwards (random "pulls" from the solved position, so it is solvable by construction) in a
hand-drawn room, and then proven solvable again with a push-based BFS solver.  Of many random tries the one that needs the most
pushes is kept.  Seeded, so the output is reproducible.  Max size 16 x 9 (the playfield is 6-pixel cells on a 96x64 screen).

Characters: # wall, space floor, . goal, $ box, * box on goal, @ player, + player on goal.
"""
import os
import random
import sys
from collections import deque

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROOMS = [
    ["########",
     "#      #",
     "#      #",
     "#      #",
     "########"],
    ["#########",
     "#       #",
     "#       #",
     "#       #",
     "#       #",
     "#########"],
    ["##########",
     "#        #",
     "#   ##   #",
     "#   ##   #",
     "#        #",
     "##########"],
    ["###########",
     "#         #",
     "#  #   #  #",
     "#         #",
     "#  #   #  #",
     "#         #",
     "###########"],
    ["############",
     "#    #     #",
     "#    #     #",
     "#          #",
     "#    #     #",
     "#    #     #",
     "############"],
    ["#############",
     "#     #     #",
     "#  #     #  #",
     "#     #     #",
     "#           #",
     "#  #     #  #",
     "#############"],
    ["##############",
     "#      #     #",
     "#  ##     ## #",
     "#      #     #",
     "#   #     #  #",
     "#      #     #",
     "##############"],
    ["###############",
     "#     #       #",
     "#  #     ##   #",
     "#     #       #",
     "#  ## # # ##  #",
     "#     #       #",
     "#   #    #    #",
     "###############"],
]
BOXES = [1, 2, 2, 3, 3, 3, 4, 4]
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def floor_cells(room):
    return [(x, y) for y, row in enumerate(room) for x, c in enumerate(row) if c == " "]


def reverse_play(room, nbox, rng, steps):
    free = set(floor_cells(room))
    goals = rng.sample(sorted(free), nbox)
    boxes = set(goals)
    rest = sorted(free - boxes)
    player = rng.choice(rest)
    for _ in range(steps):
        dx, dy = rng.choice(DIRS)
        nx, ny = player[0] + dx, player[1] + dy
        if (nx, ny) not in free or (nx, ny) in boxes:
            continue
        back = (player[0] - dx, player[1] - dy)
        if back in boxes and rng.random() < 0.8:      # pull the box behind the player
            boxes.remove(back)
            boxes.add(player)
        player = (nx, ny)
    return goals, boxes, player


def reach(room, boxes, player):
    seen = {player}
    q = deque([player])
    while q:
        x, y = q.popleft()
        for dx, dy in DIRS:
            n = (x + dx, y + dy)
            if n not in seen and room[n[1]][n[0]] != "#" and n not in boxes:
                seen.add(n)
                q.append(n)
    return seen


def solve(room, goals, boxes, player, limit=250000):
    """Push-based BFS -> number of pushes of the shortest solution, or None."""
    goals = frozenset(goals)
    start = (frozenset(boxes), player)
    r0 = reach(room, start[0], player)
    seen = {(start[0], min(r0))}
    q = deque([(start[0], player, 0)])
    while q:
        bx, pl, d = q.popleft()
        if bx == goals:
            return d
        rr = reach(room, bx, pl)
        for b in bx:
            for dx, dy in DIRS:
                src = (b[0] - dx, b[1] - dy)
                dst = (b[0] + dx, b[1] + dy)
                if src not in rr or room[dst[1]][dst[0]] == "#" or dst in bx:
                    continue
                nb = frozenset((bx - {b}) | {dst})
                key = (nb, min(reach(room, nb, b)))
                if key in seen:
                    continue
                seen.add(key)
                if len(seen) > limit:
                    return None
                q.append((nb, b, d + 1))
    return None


def render(room, goals, boxes, player):
    out = []
    for y, row in enumerate(room):
        line = ""
        for x, c in enumerate(row):
            if c == "#":
                line += "#"
                continue
            g, b, p = (x, y) in goals, (x, y) in boxes, (x, y) == player
            line += "*" if g and b else "$" if b else "+" if g and p else "@" if p else "." if g else " "
        out.append(line.rstrip())
    return out


def main():
    rng = random.Random(83)
    levels = []
    for i, room in enumerate(ROOMS):
        best = None
        tries = 150 if i < 5 else 90
        for _ in range(tries):
            goals, boxes, player = reverse_play(room, BOXES[i], rng, 160 + 40 * i)
            if set(goals) == set(boxes):
                continue
            moved = len(set(boxes) - set(goals))
            if moved < BOXES[i] - (1 if BOXES[i] > 2 else 0):
                continue
            pushes = solve(room, goals, boxes, player)
            if pushes is None:
                continue
            if best is None or pushes > best[0]:
                best = (pushes, render(room, set(goals), boxes, player))
        if best is None:
            sys.exit("no level for room %d" % i)
        print("level %d: %d boxes, %d pushes" % (i + 1, BOXES[i], best[0]))
        levels.append(best[1])
    lines = ["; GENERATED by tools/gen_sokoban.py (seeded; every level is solvable, proven by a BFS solver)\n", "sk_levels:\n"]
    for lv in levels:
        for row in lv:
            lines.append('    .db "%s",0\n' % row)
        lines.append("    .db 0\n")
    lines.append("    .db 0                       ; end of the list\n")
    open(os.path.join(root, "z80-os", "games", "sokoban_levels.inc"), "w").write("".join(lines))
    print("levels:", len(levels))


if __name__ == "__main__":
    main()
