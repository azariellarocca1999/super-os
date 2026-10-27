#!/usr/bin/env python3
"""Quick CHIP-8 game probe: python tools/c8try.py game.c8 steps [key schedule]  -> prints registers and the display."""
import sys
sys.path.insert(0, "tools")
import chip8
syms = {}
rom = chip8.assemble(open(sys.argv[1]).read(), sys.argv[1], syms)
c = chip8.Chip8(rom)
n = int(sys.argv[2])
keys = [int(k, 16) for k in sys.argv[3].split(",")] if len(sys.argv) > 3 else []
tick = syms.get("tick", 0)
frames = 0
step = 0
while frames < n and step < 4000000:
    c.keys = 1 << keys[(frames // 20) % len(keys)] if keys else 0
    c.step()
    step += 1
    if step % 12 == 0:
        c.tick60()
    if c.pc == tick:
        frames += 1
print(len(rom), "bytes; V:", c.v, "pc", hex(c.pc))
print(c.text())
