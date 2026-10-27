#!/usr/bin/env python3
"""Tests of the streamed-games engine (the C++ that runs on the ESP32, built for the PC as tools/bin/play_cli.exe).
  python games/host/play_tests.py"""
import os
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(root, "tools"))
import chip8  # noqa: E402

CLI = os.path.join(root, "tools", "bin", "play_cli.exe")
ROMS = os.path.join(root, "games", "roms")


class Cli:
    def __init__(self, roms=ROMS):
        self.p = subprocess.Popen([CLI, roms], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.fb = bytearray(768)

    def cmd(self, s):
        self.p.stdin.write((s + "\n").encode())
        self.p.stdin.flush()

    def titles(self):
        self.cmd("L")
        n = int(self.p.stdout.readline())
        return [self.p.stdout.readline().decode().strip() for _ in range(n)]

    def start(self, i):
        self.cmd("S %d" % i)
        return self.p.stdout.readline().strip() == b"OK"

    def frame(self, keys=0, dt_us=100000, full=0):
        self.cmd("F %d %d %d" % (keys, dt_us, full))
        n = int.from_bytes(self.p.stdout.read(2), "little")
        data = self.p.stdout.read(n)
        return data

    def apply(self, data):
        if not data:
            return
        if data[0] == 2:
            self.fb[:] = data[1:769]
        elif data[0] == 1:
            pos = 13
            for t in range(96):
                if data[1 + (t >> 3)] >> (t & 7) & 1:
                    ty, tx = divmod(t, 12)
                    for r in range(8):
                        self.fb[(ty * 8 + r) * 12 + tx] = data[pos]
                        pos += 1
            assert pos == len(data), (pos, len(data))

    def step(self, keys=0, dt_us=100000, full=0):
        d = self.frame(keys, dt_us, full)
        self.apply(d)
        return d

    def close(self):
        try:
            self.cmd("Q")
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


def lit(fb):
    return sum(bin(b).count("1") for b in fb)


def px(fb, x, y):
    return fb[y * 12 + (x >> 3)] >> (7 - (x & 7)) & 1


def column_height(fb, x):
    """vertical extent of lit pixels in a column (walls are dense, the floor is sparse dots)"""
    ys = [y for y in range(64) if px(fb, x, y)]
    return (max(ys) - min(ys) + 1) if ys else 0


res = []


def check(name, ok, info=""):
    res.append(bool(ok))
    print("  [%s] %s %s" % ("PASS" if ok else "FAIL", name, info))


def main():
    cli = Cli()
    names = cli.titles()
    check("title list: MAZE 3D first, then the ROMs found in games/roms", names[0] == "MAZE 3D" and "DMG-ACID2" in names, str(names))

    # ---- frame codec
    cli.start(0)
    d0 = cli.step()
    check("first frame is a full frame (type 2, 769 bytes)", d0[0] == 2 and len(d0) == 769)
    d1 = cli.step(keys=0)
    check("an idle frame is a single byte (type 0)", d1 == b"\x00", "(len %d)" % len(d1))
    full = cli.frame(keys=0, full=1)
    check("the full-frame flag resyncs", full[0] == 2 and bytes(full[1:]) == bytes(cli.fb))

    # ---- raycaster
    cli.start(0)
    cli.step()
    base = bytes(cli.fb)
    check("maze: walls are drawn", lit(base) > 400, "(%d lit pixels)" % lit(base))
    heights = []
    for _ in range(2):
        heights.append(column_height(cli.fb, 48))
        for _ in range(3):
            cli.step(keys=1 << 2)
    check("maze: walking forward makes the wall ahead taller", heights[1] >= heights[0], str(heights))
    before = bytes(cli.fb)
    for _ in range(5):
        cli.step(keys=1 << 6)
    check("maze: turning changes the view", bytes(cli.fb) != before)
    # a delta frame costs 13 + 8k bytes
    d = cli.step(keys=1 << 6)
    check("maze: a turning frame is a delta (type 1) that decodes to the exact picture", d[0] == 1 and (len(d) - 13) % 8 == 0,
          "(%d bytes)" % len(d))
    for _ in range(300):
        cli.step(keys=1 << 2)
    check("maze: the player never leaves the map (collisions)", lit(cli.fb) > 100, "(%d lit)" % lit(cli.fb))
    cli.step(keys=1 << 5)
    cli.step(keys=0)
    check("maze: key 5 toggles the minimap (top-left 18x18 corner shows the maze)", sum(px(cli.fb, x, 1) for x in range(18)) >= 16)

    # ---- CHIP-8 core on the ESP32 vs the Python reference (display only: registers are not visible)
    import tempfile
    rom = chip8.assemble(open(os.path.join(root, "games", "chip8", "optest.c8")).read(), "optest")
    ref = chip8.Chip8(rom)
    n = 0
    while True:                                        # stop right before the first Fx07 (the ESP core ends a burst there)
        op = ref.m[ref.pc] << 8 | ref.m[ref.pc + 1]
        if op & 0xF0FF == 0xF007:
            break
        ref.step()
        n += 1
    n -= n % 7
    ref2 = chip8.Chip8(rom)
    ref2.run(n, per_tick=10 ** 9)
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "optest.ch8"), "wb").write(rom)
        c2 = Cli(d)
        t2 = c2.titles()
        c2.start(t2.index("OPTEST"))
        c2.step(dt_us=n // 7 * 10000)
        got = bytes(c2.fb)
        c2.close()
    want = bytearray(768)
    for r in range(32):
        for b in range(8):
            want[(2 * r) * 12 + 2 + b] = want[(2 * r + 1) * 12 + 2 + b] = ref2.display_bytes()[r * 8 + b]
    check("chip-8 on the ESP32: display after %d instructions equals the reference" % n, got == bytes(want))

    # ---- CHIP-8 game from the calculator's packs streamed from the ESP32
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "pong.ch8"), "wb").write(chip8.assemble(open(os.path.join(root, "games", "chip8", "pong.c8")).read(), "pong"))
        c3 = Cli(d)
        t3 = c3.titles()
        c3.start(t3.index("PONG"))
        seen = 0
        for _ in range(60):
            c3.step(dt_us=100000)
            seen = max(seen, lit(c3.fb))
        check("chip-8 pong streams from the ESP32 (paddles and ball drawn)", seen > 100, "(%d lit)" % seen)
        c3.close()

    # ---- Game Boy: dmg-acid2 through Peanut-GB
    cli.start(names.index("DMG-ACID2"))
    for _ in range(40):
        cli.step(dt_us=100000)
    acid = bytes(cli.fb)
    check("game boy: dmg-acid2 renders a picture", 300 < lit(acid) < 4000, "(%d lit)" % lit(acid))
    path = os.path.join(root, "build", "acid2_96x64.pbm")
    with open(path, "w") as f:
        f.write("P1\n96 64\n" + "\n".join(" ".join(str(px(acid, x, y)) for x in range(96)) for y in range(64)) + "\n")
    cli.step(keys=1 << 5)
    cli.close()
    print("RESULT: %d/%d engine checks passed" % (sum(res), len(res)))
    return 0 if all(res) else 1


if __name__ == "__main__":
    sys.exit(main())
