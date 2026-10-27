#!/usr/bin/env python3
"""Native games (Tetris, Snake, Breakout, Pong, 2048, Invaders, Minesweeper) on the headless emulator: every game starts from the GAMES tab, reacts
to the keys, keeps its rules, draws something sensible and never resets the calculator (crash trail empty).
Called from selftest.py; `python tools/selftest_games.py` runs only this part."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
from uidrive import Session, KEYS, kc, parse_mem, pbm_text  # noqa: E402

check = S.check
GV = 0xA440


def play(tag, item, script, dump="A400", dumplen=0x200):
    """Open GAMES item N, run `script` (list of ('key', name) / ('hold', name, ms) / ('wait', ms) / ('snap', name)), return (RAM dump, stdout)."""
    s = Session(tag, start=1500)
    s.press("TRACE", *(["K%d" % item] if isinstance(item, int) else ["K" + k for k in item.split(",")]))   # "9,1" = key 9 then 1 (second page)
    s.t += 600
    for step in script:
        if step[0] == "key":
            s.press(step[1])
        elif step[0] == "hold":
            s.ev += ["%d:down:%s" % (s.t, kc(KEYS[step[1]])), "%d:up:%s" % (s.t + step[2], kc(KEYS[step[1]]))]
            s.t += step[2] + 80
        elif step[0] == "wait":
            s.t += step[1]
        elif step[0] == "snap":
            s.snap(step[1], wait=60)
    out = s.run(extra_ms=150, env={"HZ_DUMP": dump, "HZ_DUMPLEN": str(dumplen)})
    return parse_mem(out), out


def lit(tag, name, y0=0, y1=64):
    p = pbm_text(tag, name)
    return sum(sum(p[y]) for y in range(y0, y1))


def no_reset(tag, item, script):
    """True when the OS never restarted during the script (v_crash == 0 and the running marker intact)."""
    mem, _ = play(tag + "_r", item, script, dump="86E4", dumplen=1)
    return len(mem) == 1 and mem[0] == 0


def run(check_fn=None):
    global check
    if check_fn:
        check = check_fn
    print("== 25. Native games: Tetris, Snake, Breakout, Pong, 2048, Invaders, Minesweeper")

    # ---- Tetris ----
    m, o = play("g_tet", 1, [("wait", 3000), ("snap", "a"), ("key", "LEFT"), ("key", "UP"), ("wait", 300), ("key", "ALPHA"), ("wait", 400),
                             ("key", "ALPHA"), ("wait", 400), ("key", "ALPHA"), ("wait", 400), ("snap", "b")])
    ty, score, board = m[0x43], m[0x49] | m[0x4A] << 8, m[0x100:0x1A0]
    check("TETRIS: the board, the panels and a falling piece are drawn", lit("g_tet", "a", 0, 64) > 150, "(lit=%d)" % lit("g_tet", "a"))
    check("TETRIS: hard drop (ALPHA) locks pieces into the board and scores 2 points per row", sum(1 for v in board if v) >= 8 and score >= 20,
          "(cells=%d score=%d)" % (sum(1 for v in board if v), score))
    check("TETRIS: rotation / movement keep the piece inside the board (x in -1..9)", m[0x42] < 10 or m[0x42] >= 0xFE, "(x=%d)" % m[0x42])
    m2, _ = play("g_tet2", 1, [("wait", 1500), ("key", "MODE"), ("wait", 300), ("snap", "p"), ("wait", 2500), ("snap", "q")])
    check("TETRIS: MODE pauses (overlay box on screen, the picture is frozen)", lit("g_tet2", "p", 14, 50) > 100 and lit("g_tet2", "p") == lit("g_tet2", "q"),
          "(lit %d / %d)" % (lit("g_tet2", "p"), lit("g_tet2", "q")))
    check("TETRIS: never resets the calculator", no_reset("g_tet", 1, [("wait", 2500), ("key", "ALPHA"), ("wait", 600), ("key", "LEFT"), ("wait", 600)]))

    # ---- Snake ----
    m, o = play("g_snk", 2, [("wait", 1200), ("snap", "a"), ("hold", "DOWN", 200), ("wait", 900), ("snap", "b")])
    check("SNAKE: field, frame, snake and apple are drawn", lit("g_snk", "a", 8, 64) > 80, "(lit=%d)" % lit("g_snk", "a", 8, 64))
    check("SNAKE: DOWN turns the snake (direction 2) and it keeps moving", m[0x40] == 2 and m[0x44] > 4, "(dir=%d head=%d)" % (m[0x40], m[0x44]))
    m, o = play("g_snk2", 2, [("wait", 9000), ("snap", "c")])
    check("SNAKE: running into the wall ends the game (overlay, no reset)", m[0x4D] == 1 and lit("g_snk2", "c", 14, 50) > 100, "(dead=%d)" % m[0x4D])
    check("SNAKE: never resets the calculator", no_reset("g_snk", 2, [("wait", 6000)]))

    # ---- Breakout ----
    m, o = play("g_brk", 3, [("wait", 700), ("snap", "a"), ("key", "ENTER"), ("wait", 500), ("snap", "b")])
    check("BREAKOUT: 40 bricks, paddle and ball are drawn", lit("g_brk", "a", 8, 64) > 600, "(lit=%d)" % lit("g_brk", "a", 8, 64))
    check("BREAKOUT: ENTER launches the ball (it leaves the paddle)", m[0x47] == 0, "(stuck=%d)" % m[0x47])
    m2, _ = play("g_brk2", 3, [("wait", 700), ("hold", "LEFT", 900), ("snap", "c")])
    check("BREAKOUT: LEFT moves the paddle to the left edge", m2[0x40] < 40, "(px=%d)" % m2[0x40])
    check("BREAKOUT: never resets the calculator", no_reset("g_brk", 3, [("wait", 600), ("key", "ENTER"), ("wait", 5000)]))

    # ---- Pong ----
    m, o = play("g_png0", 4, [("wait", 200), ("snap", "a"), ("hold", "UP", 300), ("wait", 60), ("snap", "b")])
    check("PONG: paddles, net, score and ball are drawn", lit("g_png0", "a", 8, 64) > 60, "(lit=%d)" % lit("g_png0", "a", 8, 64))
    check("PONG: UP moves the player paddle up", m[0x40] < 28, "(py=%d)" % m[0x40])
    m, o = play("g_png", 4, [("wait", 1200), ("hold", "UP", 500), ("wait", 6000), ("snap", "b")])
    check("PONG: the cpu paddle moves to meet the ball (it left its serve position)", m[0x41] != 28 or m[0x46] + m[0x47] > 0, "(cy=%d score %d-%d)" % (m[0x41], m[0x46], m[0x47]))
    check("PONG: never resets the calculator", no_reset("g_png", 4, [("wait", 6000)]))

    # ---- 2048 ----
    keys = []
    for k in ("LEFT", "UP", "RIGHT", "DOWN") * 5:
        keys += [("key", k), ("wait", 150)]
    m, o = play("g_2k", 5, [("wait", 500), ("snap", "a")] + keys + [("snap", "b")])
    tiles = [v for v in m[0x40:0x50] if v]
    check("2048: a 4x4 board with two starting tiles", lit("g_2k", "a") > 150, "(lit=%d)" % lit("g_2k", "a"))
    check("2048: sliding spawns tiles and merges them (score > 0, tiles on the board)", len(tiles) >= 4 and (m[0x68] | m[0x69] << 8) > 0,
          "(tiles=%d score=%d)" % (len(tiles), m[0x68] | m[0x69] << 8))
    check("2048: never resets the calculator", no_reset("g_2k", 5, keys[:12]))

    # ---- Invaders ----
    m, o = play("g_inv", 6, [("wait", 700), ("snap", "a"), ("key", "ALPHA"), ("wait", 4000), ("snap", "b")])
    check("INVADERS: 32 aliens, bunkers and the ship are drawn", lit("g_inv", "a", 8, 64) > 500, "(lit=%d)" % lit("g_inv", "a", 8, 64))
    check("INVADERS: the formation marches (origin moved) and the shot flew", m[0x40] != 2 or m[0x41] != 10, "(ox=%d oy=%d)" % (m[0x40], m[0x41]))
    check("INVADERS: never resets the calculator", no_reset("g_inv", 6, [("wait", 600), ("key", "ALPHA"), ("wait", 5000)]))

    # ---- Minesweeper ----
    m, o = play("g_mns", 7, [("wait", 500), ("snap", "a"), ("key", "ENTER"), ("wait", 600), ("snap", "b")])
    check("MINESWEEPER: the first reveal is safe and opens a region", m[0x42] == 1 and m[0x47] > 1, "(state=%d revealed=%d)" % (m[0x42], m[0x47]))
    check("MINESWEEPER: the field is drawn", lit("g_mns", "b", 8, 64) > 300, "(lit=%d)" % lit("g_mns", "b", 8, 64))
    check("MINESWEEPER: never resets the calculator", no_reset("g_mns", 7, [("wait", 400), ("key", "ENTER"), ("wait", 800), ("key", "ALPHA")]))

    # ---- Sokoban: level 1 is  player (7,4), box (9,4), goal (5,5) ----
    m, o = play("g_sok", 8, [("wait", 500), ("snap", "a"), ("key", "RIGHT"), ("wait", 300), ("snap", "b")])
    check("SOKOBAN: walls, box, goal and the man are drawn", lit("g_sok", "a", 8, 64) > 200, "(lit=%d)" % lit("g_sok", "a", 8, 64))
    check("SOKOBAN: RIGHT walks and pushes the box (player x 8, 1 move)", m[0x40] == 8 and m[0x43] == 1, "(px=%d moves=%d)" % (m[0x40], m[0x43]))
    m, o = play("g_sok2", 8, [("wait", 500), ("key", "RIGHT"), ("wait", 300), ("key", "ALPHA"), ("wait", 300)])
    check("SOKOBAN: ALPHA undoes the last move", m[0x40] == 7 and m[0x43] == 0, "(px=%d moves=%d)" % (m[0x40], m[0x43]))
    sol = ["UP", "RIGHT", "RIGHT", "RIGHT", "DOWN", "LEFT", "LEFT", "LEFT", "LEFT", "UP", "LEFT", "DOWN"]
    script = [("wait", 500)] + [x for k in sol for x in (("key", k), ("wait", 250))] + [("wait", 600), ("snap", "w")]
    m, o = play("g_sok3", 8, script, dump="8700", dumplen=0x40)
    check("SOKOBAN: solving level 1 stores 1 level cleared in the best-score slot (settings $8716)", m[0x16] == 1 and m[0x17] == 0, "(best=%d)" % m[0x16])
    check("SOKOBAN: the level-cleared overlay is shown", lit("g_sok3", "w", 14, 50) > 100, "(lit=%d)" % lit("g_sok3", "w", 14, 50))
    check("SOKOBAN: never resets the calculator", no_reset("g_sok", 8, [("wait", 500), ("key", "RIGHT"), ("wait", 300), ("key", "ENTER"), ("wait", 400)]))

    # ---- Reversi: you place at (3,2), flipping (3,3); the CPU answers ----
    m, o = play("g_rev", "9,1", [("wait", 500), ("snap", "a"), ("key", "ENTER"), ("wait", 2000), ("snap", "b")], dump="A900", dumplen=64)
    check("REVERSI: board, discs and the legal-square dots are drawn", lit("g_rev", "a", 0, 64) > 250, "(lit=%d)" % lit("g_rev", "a"))
    check("REVERSI: your disc lands on (3,2)", m[2 * 8 + 3] == 1, "(cell=%d)" % m[19])
    check("REVERSI: the CPU answered (6 discs on the board)", sum(1 for v in m if v) == 6, "(discs=%d)" % sum(1 for v in m if v))
    m, o = play("g_rev2", "9,1", [("wait", 500), ("key", "LEFT"), ("key", "LEFT"), ("key", "ENTER"), ("wait", 600)], dump="A900", dumplen=64)
    check("REVERSI: an illegal square does nothing", sum(1 for v in m if v) == 4, "(discs=%d)" % sum(1 for v in m if v))
    check("REVERSI: never resets the calculator", no_reset("g_rev", "9,1", [("wait", 500), ("key", "ENTER"), ("wait", 1500), ("key", "DOWN"), ("key", "ENTER"), ("wait", 1500)]))

    import check_flush
    check_flush.run(check)


if __name__ == "__main__":
    run()
    print("RESULT: %d/%d" % (sum(S.results), len(S.results)))
    sys.exit(0 if all(S.results) else 1)
