#!/usr/bin/env python3
"""English-language contact sheet of the main screens (to eyeball overflow): build/test/lang_en.png.   python tools/screens_lang.py"""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
from PIL import Image  # noqa: E402
from uidrive import Session, out  # noqa: E402

shots = []


def shot(tag, keys, wait=500, lang=True):
    s = Session(tag, start=1500)
    if lang:
        s.press("YEQ", "K6", "RIGHT", "CLEAR")            # SETTINGS: switch to English, back to the launcher
        s.t += 300
    for k in keys:
        s.press(k)
    s.snap("s", wait=wait)
    s.run(extra_ms=200)
    shots.append(Image.open(s.png("s", 3)))


for name, keys in (
        ("home", []), ("mate", ["WINDOW"]), ("ia", ["ZOOM"]), ("games", ["TRACE"]), ("sys", ["GRAPH"]),
        ("diag", ["GRAPH", "K7"]), ("ota", ["GRAPH", "K6"]), ("classic", ["TRACE", "K9", "K2"]),
        ("tetris_over", ["TRACE", "K1"]), ("pause", ["TRACE", "K3", "MODE"]), ("settings", ["YEQ", "K6"]), ("conv", ["WINDOW", "K6"])):
    shot("lang_" + name, keys, wait=900 if name in ("tetris_over", "pause") else 500)
w, h = shots[0].size
cols = 4
rows = (len(shots) + cols - 1) // cols
m = Image.new("RGB", (cols * (w + 8) + 8, rows * (h + 8) + 8), (255, 255, 255))
for i, im in enumerate(shots):
    m.paste(im, (8 + (i % cols) * (w + 8), 8 + (i // cols) * (h + 8)))
dst = os.path.join(out, "lang_en.png")
m.save(dst)
print(dst, m.size)
