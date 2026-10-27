#!/usr/bin/env python3
"""Compose the 2 MB TI-83 Plus SE flash image (128 pages of 16 KB) from per-page binaries."""
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
build = os.path.join(root, "build")
PAGES, PS = 128, 16384


def main():
    rom = bytearray(b"\xff" * (PAGES * PS))
    layout = {0: "page0.bin", 1: "page1.bin", 2: "page2.bin"}
    for f in sorted(os.listdir(build)):                    # extra pages: pagexNN.bin (hex page number)
        if f.startswith("pagex") and f.endswith(".bin"):
            layout[int(f[5:-4], 16)] = f
    for pg, name in sorted(layout.items()):
        data = open(os.path.join(build, name), "rb").read()
        if len(data) > PS:
            sys.exit("%s is %d bytes: exceeds one 16 KB page" % (name, len(data)))
        rom[pg * PS:pg * PS + len(data)] = data
        print("  page %02X <- %-12s %5d bytes (%2.0f%%)" % (pg, name, len(data), 100.0 * len(data) / PS))
    unlock = open(os.path.join(build, "flashunlock.bin"), "rb").read()
    assert unlock == bytes([0, 0, 0xED, 0x56, 0xF3, 0xD3, 0x14, 0xC9]), unlock.hex()
    rom[0x7C * PS + 0x3FF0:0x7C * PS + 0x3FF8] = unlock    # privileged page: flash unlock routine
    boot = open(os.path.join(build, "devboot.bin"), "rb").read()
    rom[0x7F * PS:0x7F * PS + len(boot)] = boot            # DEV ROM ONLY: stand-in boot page
    open(os.path.join(build, "superos.rom"), "wb").write(rom)
    print("  ROM: %d KB; pages used: %d; free flash: %d KB" % (len(rom) // 1024, len(layout), (PAGES - len(layout) - 4) * 16))


if __name__ == "__main__":
    main()
