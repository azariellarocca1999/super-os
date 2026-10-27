#!/usr/bin/env python3
"""CHIP-8 interpreter tests: the Z80 interpreter (flash page 5) against the Python reference (tools/chip8.py), instruction by instruction
on the same programs.  `python tools/c8test.py`"""
import os
import re
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
import chip8  # noqa: E402

build = os.path.join(root, "build")
sim = os.path.join(root, "tools", "bin", "hz80_sim.exe")


def dump(rom, addr, n, ms):
    env = dict(os.environ, HZ_DUMP="%X" % addr, HZ_DUMPLEN=str(n))
    r = subprocess.run([sim, rom, os.path.join(build, "c8t"), str(ms)], capture_output=True, text=True, env=env, timeout=900)
    m = re.search(r"MEM \w+:((?: [0-9A-F]{2})+)", r.stdout)
    assert m, r.stdout[-300:] + r.stderr[-300:]
    return bytes(int(x, 16) for x in m.group(1).split())


def z80_run(rom_bytes, count, keymask, ms=None):
    inc = "c8_len: .dw %d\nc8_count: .dw %d\nc8_keymask: .dw %d\nc8_rom:\n    .db %s\n" % (
        len(rom_bytes), count, keymask, ",".join(str(b) for b in rom_bytes))
    open(os.path.join(build, "c8_rom.inc"), "w").write(inc)
    r = subprocess.run([sys.executable, "tools/fix_jr.py", "-I", "z80-os", "-I", "build", "tools/c8test.z80", "build/c8_page0.bin"],
                       capture_output=True, text=True, cwd=root)
    if r.returncode or "error" in (r.stdout + r.stderr).lower():
        sys.exit(r.stdout + r.stderr)
    img = bytearray(b"\xff" * (128 * 16384))
    p0 = open(os.path.join(build, "c8_page0.bin"), "rb").read()
    img[:len(p0)] = p0
    p5 = open(os.path.join(build, "pagex05.bin"), "rb").read()
    img[5 * 16384:5 * 16384 + len(p5)] = p5
    boot = open(os.path.join(build, "devboot.bin"), "rb").read().replace(b"\xC3\x53\x00", b"\xC3\x00\x00")   # this harness starts at $0000 (only the OS models the $0053 entry)
    img[0x7F * 16384:0x7F * 16384 + len(boot)] = boot
    path = os.path.join(build, "c8t.rom")
    open(path, "wb").write(img)
    ms = ms or 150 + count // 3
    st = dump(path, 0xA000, 0x200, ms)
    mem = dump(path, 0xC000, 4096, ms)
    return st, mem


def compare(name, rom, count, keymask=0):
    ref = chip8.Chip8(rom)
    ref.keys = keymask
    ref.run(count)
    st, mem = z80_run(rom, count, keymask)
    errs = []
    if st[0x5F] != 0x5A:
        errs.append("the test program did not finish")
    if list(st[0:16]) != ref.v:
        errs.append("V: z80 %s ref %s" % (list(st[0:16]), ref.v))
    if st[0x42] | st[0x43] << 8 != ref.i:
        errs.append("I %x vs %x" % (st[0x42] | st[0x43] << 8, ref.i))
    if st[0x40] | st[0x41] << 8 != ref.pc:
        errs.append("PC %x vs %x" % (st[0x40] | st[0x41] << 8, ref.pc))
    if st[0x44] != 2 * len(ref.sp):
        errs.append("SP %d vs %d" % (st[0x44], 2 * len(ref.sp)))
    if (st[0x45], st[0x46]) != (ref.dt, ref.st):
        errs.append("timers %s vs %s" % ((st[0x45], st[0x46]), (ref.dt, ref.st)))
    if st[0x100:0x200] != ref.display_bytes():
        errs.append("display differs (%d bytes)" % sum(a != b for a, b in zip(st[0x100:0x200], ref.display_bytes())))
    if mem[:4096] != bytes(ref.m):
        errs.append("memory differs at %s" % [hex(i) for i in range(4096) if mem[i] != ref.m[i]][:6])
    print("  [%s] %s (%d instructions)%s" % ("FAIL" if errs else "PASS", name, count, "" if not errs else ": " + "; ".join(errs)))
    return not errs


def main():
    subprocess.run([sys.executable, "tools/gen_c8.py"], cwd=root, check=True, capture_output=True)
    fails = 0
    ok = compare
    cases = []
    opt = chip8.assemble(open(os.path.join(root, "games", "chip8", "optest.c8")).read(), "optest")
    cases.append(("opcode test ROM", opt, 3000, 0))
    cases.append(("opcode test ROM, key 5 held", opt, 3000, 1 << 5))
    for g in ("pong", "breakout", "snake", "invaders", "dodge", "simon"):
        rom = chip8.assemble(open(os.path.join(root, "games", "chip8", g + ".c8")).read(), g)
        for n, km in ((4000, 0), (30000, (1 << 6) | (1 << 5)), (30000, 1 << 4)):
            cases.append(("game %s keys=%x" % (g, km), rom, n, km))
    for name, rom, n, km in cases:
        if not ok(name, rom, n, km):
            fails += 1
    print("RESULT: %d/%d interpreter comparisons passed" % (len(cases) - fails, len(cases)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
