#!/usr/bin/env python3
"""Emulator power/performance measurements for docs/PERF.md.  `python tools/perf_measure.py` prints a table of the CPU time spent in HALT
(= low power) per scenario, from the emulator's own slice counters.  Higher HALT % = lower consumption (on real hardware HALT draws less than running)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uidrive import Session  # noqa: E402

SCEN = {
    "launcher idle (home screen)": [],
    "calculator editor idle": ["WINDOW", "K1"],
    "calculator editor, typing": "TYPING",
    "grapher (Y1=sin(X) plotted, idle)": ["WINDOW", "K2", "GRAPH"],
    "periodic table idle": ["WINDOW", "K5"],
    "CHIP-8 PONG running": ["TRACE", "K1", "ENTER"],
    "CHIP-8 SNAKE running": ["TRACE", "K1", "DOWN", "DOWN", "ENTER"],
    "waiting for an absent ESP32 (5 s wake wait)": ["ZOOM", "K1", "K2", "ENTER"],
    "native TETRIS playing": ["TRACE", "K1"],
    "native SNAKE playing": ["TRACE", "K2"],
    "native BREAKOUT (ball stuck)": ["TRACE", "K3"],
    "native PONG playing": ["TRACE", "K4"],
    "native 2048 waiting": ["TRACE", "K5"],
    "native INVADERS playing": ["TRACE", "K6"],
    "native MINESWEEPER waiting": ["TRACE", "K7"],
}


def measure(name, keys, ms=8000):
    s = Session("perf", start=1500)
    if keys == "TYPING":
        s.press("WINDOW", "K1")
        for _ in range(30):
            s.press("K1")
    else:
        s.press(*keys)
    s.t = max(s.t, 2000)
    out = s.run(extra_ms=ms - s.t if ms > s.t else 500)
    m = re.search(r"halted_pct=([\d.]+)", out)
    k = re.search(r"speed_khz=(\d+)", out)
    return (float(m[1]) if m else -1.0), (int(k[1]) if k else 0)


def main():
    rows = []
    for name, keys in SCEN.items():
        h, khz = measure(name, keys)
        rows.append((name, h, khz))
        print("%-48s HALT %5.1f %%  (CPU %d kHz)" % (name, h, khz))
    return rows


if __name__ == "__main__":
    main()
