#!/usr/bin/env python3
"""Screenshots of the native games -> docs/screens/games.png (menu + nine games) and one PNG per game in docs/screens/."""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
from PIL import Image  # noqa: E402
from uidrive import Session, KEYS, kc  # noqa: E402

shots = []


def hold(s, name, ms):
    s.ev += ["%d:down:%s" % (s.t, kc(KEYS[name])), "%d:up:%s" % (s.t + ms, kc(KEYS[name]))]
    s.t += ms + 80


def game(tag, item, script, wait):
    s = Session(tag, start=1500)
    s.press("TRACE", *(["K%d" % item] if isinstance(item, int) else ["K" + k for k in item.split(",")]))   # "9,1" = second page, item 1
    s.t += 500
    for step in script:
        if step[0] == "key":
            s.press(step[1])
        elif step[0] == "hold":
            hold(s, step[1], step[2])
        elif step[0] == "wait":
            s.t += step[1]
    s.snap("shot", wait=wait)
    s.run(extra_ms=200)
    shots.append((tag, s, "shot"))


def main():
    s = Session("sg_menu", start=1500)
    s.press("TRACE")
    s.snap("shot", wait=400)
    s.run(extra_ms=200)
    shots.append(("menu", s, "shot"))
    tet = [("key", k) if k != "W" else ("wait", 250) for k in ("LEFT", "W", "ALPHA", "W", "RIGHT", "RIGHT", "W", "ALPHA", "W", "UP", "W", "ALPHA", "W", "LEFT", "LEFT", "LEFT", "W", "ALPHA", "W", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "W", "ALPHA")]
    game("tetris", 1, tet, 900)
    game("snake", 2, [("wait", 600), ("hold", "DOWN", 150), ("wait", 1000), ("hold", "RIGHT", 150), ("wait", 700)], 100)
    game("breakout", 3, [("wait", 500), ("key", "ENTER"), ("wait", 900)], 100)
    game("pong", 4, [("wait", 2400)], 100)
    mv = []
    for k in ("LEFT", "UP", "RIGHT", "DOWN") * 6:
        mv += [("key", k), ("wait", 120)]
    game("g2048", 5, mv, 200)
    game("invaders", 6, [("wait", 600), ("hold", "RIGHT", 300), ("key", "ALPHA"), ("wait", 1500)], 100)
    game("mines", 7, [("wait", 500), ("key", "ENTER"), ("wait", 700), ("key", "RIGHT"), ("key", "RIGHT"), ("key", "ALPHA"), ("wait", 200)], 100)
    game("sokoban", 8, [("wait", 500), ("key", "UP"), ("wait", 150), ("key", "RIGHT"), ("wait", 150), ("key", "RIGHT"), ("wait", 150), ("key", "RIGHT"), ("wait", 300)], 100)
    game("reversi", "9,1", [("wait", 500), ("key", "ENTER"), ("wait", 1500), ("key", "RIGHT"), ("wait", 200)], 100)
    ims = [Image.open(s.png(n, 3)) for _tag, s, n in shots]
    w, h = ims[0].size
    cols = 5
    rows = (len(ims) + cols - 1) // cols
    m = Image.new("RGB", (cols * (w + 8) + 8, rows * (h + 8) + 8), (255, 255, 255))
    for i, im in enumerate(ims):
        m.paste(im, (8 + (i % cols) * (w + 8), 8 + (i // cols) * (h + 8)))
    os.makedirs(os.path.join(root, "docs", "screens"), exist_ok=True)
    dst = os.path.join(root, "docs", "screens", "games.png")
    m.save(dst)
    for (tag, s, n), im in zip(shots, ims):
        Image.open(s.png(n, 4)).save(os.path.join(root, "docs", "screens", "game_%s.png" % tag))
    print(dst, m.size, len(ims), "screens")


if __name__ == "__main__":
    main()
