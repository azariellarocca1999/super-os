#!/usr/bin/env python3
"""Milestone 4 screenshots -> docs/screens/milestone4.png (game menu, the six CHIP-8 games, streamed maze 3D and Game Boy)."""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
from PIL import Image  # noqa: E402
from uidrive import Session, KEYS, kc, out  # noqa: E402

ESP = {"HZ_BRIDGE": "python " + os.path.join(root, "bridge_pc", "virtual_esp.py"), "HZ_LINKMODE": "line", "HZ_OFFLINE": "1",
       "HZ_BRIDGE_LOG": os.path.join(out, "esp_shots4.log")}
shots = []


def hold(s, name, ms):
    code = KEYS[name]
    s.ev += ["%d:down:%s" % (s.t, kc(code)), "%d:up:%s" % (s.t + ms, kc(code))]
    s.t += ms + 100


def game(tag, pack, index, wait, keys=(), env=None, menu=False):
    s = Session(tag, start=1500)
    s.press("TRACE", *{"K8": ["K9", "K2"], "K9": ["K9", "K3"]}[pack])      # page 2 of the GAMES tab: 2 = CLASSIC menu, 3 = STREAM
    if menu:
        s.snap("menu", wait=3500 if env else 400)
    elif env:
        s.t += 3500                                          # wake the ESP32 and list the titles
    for _ in range(index):
        s.press("DOWN")
    s.press("ENTER")
    for name, ms in keys:
        s.t += 300
        hold(s, name, ms)
    s.snap("shot", wait=wait)
    s.press("CLEAR")
    s.run(extra_ms=300, env=env)
    for ev in s.ev:
        if ":snap:" in ev:
            shots.append((s, ev.split(":snap:")[1]))


def main():
    game("m4_pong", "K8", 0, 2500, [("K8", 700)], menu=True)
    game("m4_breakout", "K8", 1, 4000, [("K6", 500)])
    game("m4_snake", "K8", 2, 3000, [("K6", 600)])
    game("m4_inv", "K8", 3, 3500, [("K6", 700)])
    game("m4_dodge", "K8", 4, 3000, [("K4", 600)])
    game("m4_simon", "K8", 5, 3500)
    game("m4_maze", "K9", 0, 1500, [("K8", 500)], env=ESP, menu=True)
    game("m4_gb", "K9", 1, 5000, env=ESP)
    ims = [Image.open(s.png(n, 3)) for s, n in shots]
    w, h = ims[0].size
    cols = 4
    rows = (len(ims) + cols - 1) // cols
    m = Image.new("RGB", (cols * (w + 10), rows * (h + 10)), (255, 255, 255))
    for i, im in enumerate(ims):
        m.paste(im, ((i % cols) * (w + 10), (i // cols) * (h + 10)))
    os.makedirs(os.path.join(root, "docs", "screens"), exist_ok=True)
    dst = os.path.join(root, "docs", "screens", "milestone4.png")
    m.save(dst)
    print(dst, m.size, len(ims), "screens")


if __name__ == "__main__":
    main()
