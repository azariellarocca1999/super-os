#!/usr/bin/env python3
"""Screens added in 0.6 / 1.0 (lock, PIN prompt, exam message, notes, launcher second page, Sokoban, Reversi) in three settings: Spanish, English, and
English with the big 6x8 font -> build/test/screens_new.png (a montage, for eyeballing text that overflows or looks wrong).  Not part of the self-test."""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
from PIL import Image, ImageDraw  # noqa: E402
from uidrive import Session  # noqa: E402


def setup(s, english, big):
    if english or big:
        s.press("YEQ", "K6")                  # SETTINGS
        if english:
            s.press("RIGHT")                  # row 0: language
        if big:
            s.press("DOWN", "DOWN", "DOWN", "DOWN", "DOWN", "RIGHT")      # row 5: font
        s.press("CLEAR")


SCREENS = [
    ("home2", ["TRACE", "K9"], 0),
    ("lock", ["GRAPH", "K8"], 0),
    ("pin", ["GRAPH", "K8", "K1", "K1", "K2", "K3", "K4", "K1", "K2", "K3", "K4", "ENTER", "GRAPH", "K8"], 0),
    ("exam", ["GRAPH", "K8", "K2", "K1", "K2", "K3", "K4", "K1", "K2", "K3", "K4", "ENTER", "TRACE", "K1"], 0),
    ("notes", ["WINDOW", "K8", "K1", "ALPHA", "ALPHA", "K1", "K2", "K3", "ENTER"], 0),
    ("sokoban", ["TRACE", "K8"], 400),
    ("reversi", ["TRACE", "K9", "K1"], 400),
]


def main():
    ims, labels = [], []
    for english, big in ((False, False), (True, False), (True, True)):
        for name, keys, wait in SCREENS:
            tag = "sn_%s_%d%d" % (name, english, big)
            s = Session(tag, start=1500)
            setup(s, english, big)
            s.press(*keys)
            s.snap("x", wait=500 + wait)
            s.run(extra_ms=100)
            ims.append(Image.open(s.png("x", 3)))
            labels.append("%s %s%s" % (name, "EN" if english else "ES", " big" if big else ""))
    w, h = ims[0].size
    cols = len(SCREENS)
    rows = len(ims) // cols
    m = Image.new("RGB", (cols * (w + 6) + 6, rows * (h + 18) + 6), (255, 255, 255))
    d = ImageDraw.Draw(m)
    for i, (im, lb) in enumerate(zip(ims, labels)):
        x, y = 6 + (i % cols) * (w + 6), 6 + (i // cols) * (h + 18)
        m.paste(im, (x, y + 12))
        d.text((x, y), lb, fill=(0, 0, 0))
    dst = os.path.join(root, "build", "test", "screens_new.png")
    m.save(dst)
    print(dst, m.size)


if __name__ == "__main__":
    main()
