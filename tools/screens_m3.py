#!/usr/bin/env python3
"""Milestone 3 screenshots -> docs/screens/milestone3.png (calculator, grapher, trace, table, CAS, 3D, periodic table, converter, Wikipedia)."""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
from PIL import Image  # noqa: E402
from uidrive import Session, out  # noqa: E402

ESP = {"HZ_BRIDGE": "python " + os.path.join(root, "bridge_pc", "virtual_esp.py"), "HZ_LINKMODE": "line", "HZ_OFFLINE": "1",
       "HZ_BRIDGE_LOG": os.path.join(out, "esp_shots.log")}
shots = []


def grab(tag, builder, env=None):
    s = Session(tag, start=1500)
    builder(s)
    s.run(extra_ms=300, env=env)
    return s


def calc(s):
    s.press("WINDOW", "K1")
    s.t += 700
    s.type("2+3*4"); s.press("ENTER")
    s.second("SIN"); s.type("0.5)"); s.press("ENTER")
    s.press("MATH", "ENTER"); s.type("-7.5)"); s.press("ENTER")
    s.snap("calc", wait=300)


def graph(s):
    s.press("WINDOW", "K2")
    s.snap("graph", wait=3500)
    s.press("RIGHT", "RIGHT", "RIGHT", "RIGHT")
    s.snap("trace", wait=500)
    s.press("GRAPH")
    s.t += 4000
    s.second("GRAPH")
    s.snap("table", wait=900)


def cas(s):
    s.press("WINDOW", "K3")
    s.t += 800
    s.press("MATH", "DOWN", "ENTER")                         # int(
    s.type("X"); s.press("MUL"); s.second("LN"); s.type("X^2)"); s.type(",X)")
    s.snap("cas_input", wait=200)
    s.press("ENTER")
    s.snap("cas_result", wait=6500)
    s.press("CLEAR")
    s.press("CLEAR")
    s.press("CLEAR")


def surface(s):
    s.press("WINDOW", "K3")
    s.t += 800
    s.press("MATH")
    for _ in range(20):
        s.press("DOWN")
    s.press("ENTER")
    s.press("SIN"); s.type("X)"); s.press("MUL"); s.press("COS"); s.press("ALPHA", "K1"); s.type(")")
    s.press("COMMA"); s.press("NEG"); s.type("3,3"); s.press("COMMA"); s.press("NEG"); s.type("3,3)")
    s.press("ENTER")
    s.snap("surface", wait=7000)


def ptable(s):
    s.press("WINDOW", "K5")
    s.t += 900
    s.press("DOWN", "DOWN", "RIGHT", "RIGHT")
    s.snap("ptable", wait=300)
    s.press("ENTER")
    s.snap("pt_detail", wait=300)


def conv(s):
    s.press("WINDOW", "K6", "DOWN", "DOWN", "DOWN", "ENTER")
    s.t += 400
    s.press("K3", "DEL"); s.type("100"); s.press("ENTER")
    s.snap("conv", wait=400)


def consts(s):
    s.press("WINDOW", "K7")
    s.t += 900
    s.press("DOWN", "DOWN", "DOWN")
    s.snap("consts", wait=300)


def main():
    for tag, fn, env in (("shot_calc", calc, None), ("shot_graph", graph, None), ("shot_cas", cas, ESP), ("shot_3d", surface, ESP),
                         ("shot_pt", ptable, None), ("shot_conv", conv, None), ("shot_const", consts, None)):
        s = grab(tag, fn, env)
        for ev in s.ev:
            if ":snap:" in ev:
                shots.append((s, ev.split(":snap:")[1]))
    ims = [Image.open(s.png(n, 3)) for s, n in shots]
    w, h = ims[0].size
    cols = 4
    rows = (len(ims) + cols - 1) // cols
    m = Image.new("RGB", (cols * (w + 10), rows * (h + 10)), (255, 255, 255))
    for i, im in enumerate(ims):
        m.paste(im, ((i % cols) * (w + 10), (i // cols) * (h + 10)))
    os.makedirs(os.path.join(root, "docs", "screens"), exist_ok=True)
    dst = os.path.join(root, "docs", "screens", "milestone3.png")
    m.save(dst)
    print(dst, m.size, len(ims), "screens")


if __name__ == "__main__":
    main()
