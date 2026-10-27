"""Reference rules for the native Reversi (z80-os/games/reversi.z80), used by selftest_reversi.py and by the CI static checks.

Board: 64 cells, index y * 8 + x; 0 empty, 1 you (moves first), 2 CPU.
"""

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
# weight by distance from the nearest edge (fx, fy), as rv_wt in the Z80 code
WT = [[120, 8, 60, 50], [8, 2, 20, 20], [60, 20, 40, 35], [50, 20, 35, 30]]


def start():
    b = [0] * 64
    b[27] = b[36] = 2
    b[28] = b[35] = 1
    return b


def flips(b, x, y, pl):
    """Cells that playing (x, y) as `pl` would flip ([] = illegal)."""
    if b[y * 8 + x]:
        return []
    opp = 3 - pl
    out = []
    for dx, dy in DIRS:
        cx, cy, run = x + dx, y + dy, []
        while 0 <= cx < 8 and 0 <= cy < 8 and b[cy * 8 + cx] == opp:
            run.append(cy * 8 + cx)
            cx += dx
            cy += dy
        if run and 0 <= cx < 8 and 0 <= cy < 8 and b[cy * 8 + cx] == pl:
            out += run
    return out


def moves(b, pl):
    return [(x, y) for y in range(8) for x in range(8) if flips(b, x, y, pl)]


def play(b, x, y, pl):
    f = flips(b, x, y, pl)
    assert f, "illegal move"
    nb = list(b)
    for i in f:
        nb[i] = pl
    nb[y * 8 + x] = pl
    return nb


def value(b, x, y, pl=2):
    """What the CPU scores a square: 2 * flips + positional weight (the game adds 0..3 of noise)."""
    fx, fy = min(x, 7 - x), min(y, 7 - y)
    return 2 * len(flips(b, x, y, pl)) + WT[fy][fx]


def cpu_outcomes(b):
    """Every board the calculator may leave after you moved: the CPU plays (noise 0..3 on the scores), and keeps playing while you must pass.
    Returns a list of (board, [(x, y) the CPU played, ...])."""
    res = []

    def rec(board, played):
        cm = moves(board, 2)
        if not cm:
            res.append((board, played))
            return
        best = max(value(board, x, y) for x, y in cm)
        for x, y in cm:
            if value(board, x, y) + 3 < best:        # the noise cannot make it win
                continue
            nb = play(board, x, y, 2)
            if moves(nb, 1) or not moves(nb, 2):
                res.append((nb, played + [(x, y)]))
            else:
                rec(nb, played + [(x, y)])
    rec(b, [])
    return res


def score(b):
    return b.count(1), b.count(2)
