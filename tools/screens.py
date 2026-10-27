#!/usr/bin/env python3
"""Render documentation screenshots (docs/screens/overview.png) from the emulator."""
import os
import struct
import sys
import zlib

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
import selftest as t  # noqa: E402

ESC = {"HZ_BRIDGE": "python " + os.path.join(root, "bridge_pc", "virtual_esp.py"), "HZ_LINKMODE": "line", "HZ_OFFLINE": "1"}
SHOTS = []


def shot(name, ev, ms, env=None):
    t.run("sc_" + name, ms, ev + ["%d:snap:a" % (ms - 100)], env)
    SHOTS.append(name)


shot("home", [], 1500)
shot("tab_sys", t.tap(1000, t.GRAPH), 1700)
store = os.path.join(root, "build", "test", "store")
os.makedirs(store, exist_ok=True)
open(os.path.join(store, "HELLO.bin"), "wb").write(open(os.path.join(root, "build", "demo.bin"), "rb").read())
ESC2 = dict(ESC, HZ_STORE_DIR=store)
shot("ota_list", t.tap(1000, t.GRAPH) + t.tap(1400, t.kc(19)) + t.tap(2200, t.kc(34)), 6200, ESC2)
shot("diag_menu", t.tap(1000, t.GRAPH) + t.tap(1400, t.kc(36)), 2000)
shot("diag_link", t.tap(1000, t.GRAPH) + t.tap(1400, t.kc(36)) + t.tap(2200, t.kc(34)) + t.tap(3400, t.ENTER), 9500, ESC)
shot("diag_ram", t.tap(1000, t.GRAPH) + t.tap(1400, t.kc(36)) + t.tap(2200, t.kc(35)), 8500)
shot("diag_flash", t.tap(1000, t.GRAPH) + t.tap(1400, t.kc(36)) + t.tap(2200, t.kc(27)) + t.tap(3000, t.ENTER), 9500)
shot("diag_esp", t.tap(1000, t.GRAPH) + t.tap(1400, t.kc(36)) + t.tap(2200, t.kc(19)), 8500, ESC)
shot("chat", t.tap(1000, t.kc(34)) + t.type_keys(1500, [35, 18, 27, 27, 19])[0] + t.tap(3000, t.ENTER), 9000, ESC)

names = SHOTS
S, G, cols = 4, 8, 3
rows = (len(names) + cols - 1) // cols
W, H = cols * (96 * S + G) + G, rows * (64 * S + G) + G
bg, fg = (176, 190, 160), (28, 36, 24)
img = [[(230, 230, 230)] * W for _ in range(H)]
for i, n in enumerate(names):
    d = t.pbm("sc_%s_a" % n)
    ox, oy = G + (i % cols) * (96 * S + G), G + (i // cols) * (64 * S + G)
    for y in range(64):
        for x in range(96):
            c = fg if d[y][x] else bg
            for dy in range(S):
                row = img[oy + y * S + dy]
                for dx in range(S):
                    row[ox + x * S + dx] = c
raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in img)


def ch(tp, d):
    c = struct.pack(">I", len(d)) + tp + d
    return c + struct.pack(">I", zlib.crc32(tp + d) & 0xFFFFFFFF)


os.makedirs(os.path.join(root, "docs", "screens"), exist_ok=True)
open(os.path.join(root, "docs", "screens", "overview.png"), "wb").write(
    b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 9)) + ch(b"IEND", b""))
print("docs/screens/overview.png", W, H)
