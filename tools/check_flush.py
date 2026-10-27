"""Does gl_flush keep the LCD identical to the frame buffer?  Each native game is played for a few seconds, paused (the picture is then static) and the
emulator's LCD is compared with GBUF1 ($8000).  (While things move the emulator's get_lcd() lags about three frames behind the LCD memory, a
persistence effect that is the same with full-screen blits, so only static pictures can be compared.)   python tools/check_flush.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uidrive import Session, parse_mem, pbm_text  # noqa: E402

GAMES = {1: "TETRIS", 2: "SNAKE", 3: "BREAKOUT", 4: "PONG", 5: "2048", 6: "INVADERS", 7: "MINES"}
KEYSEQ = {1: ["LEFT", "ALPHA", "RIGHT", "UP", "ALPHA"], 2: ["DOWN", "LEFT"], 3: ["ENTER", "LEFT", "RIGHT"], 4: ["UP", "DOWN"],
          5: ["LEFT", "UP", "RIGHT", "DOWN", "LEFT"], 6: ["ALPHA", "LEFT", "RIGHT"], 7: ["ENTER", "RIGHT", "ALPHA"]}


def fb_to_pixels(mem):
    return [[(mem[y * 12 + xb] >> (7 - i)) & 1 for xb in range(12) for i in range(8)] for y in range(64)]


def lcd_vs_buffer(item, before_pause_ms=2500):
    s = Session("cf", start=1500)
    s.press("TRACE", "K%d" % item)
    s.t += 600
    for k in KEYSEQ[item]:
        s.press(k)
        s.t += 400
    s.t += before_pause_ms
    s.press("MODE")                       # pause: the overlay is drawn and nothing moves any more
    s.t += 700
    s.snap("x", wait=0)
    out = s.run(extra_ms=0, env={"HZ_DUMP": "8000", "HZ_DUMPLEN": "768"})
    f = fb_to_pixels(parse_mem(out))
    lcd = pbm_text("cf", "x")
    return sum(1 for y in range(64) for x in range(96) if lcd[y][x] != f[y][x])


def run(check=None):
    bad = 0
    for item, name in GAMES.items():
        d = lcd_vs_buffer(item)
        if check:
            check("%s: the LCD equals the frame buffer after the tile flush (paused picture)" % name, d == 0, "(%d pixels differ)" % d)
        else:
            print("%-9s LCD vs frame buffer: %d pixels differ" % (name, d))
        bad += d != 0
    return bad


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
