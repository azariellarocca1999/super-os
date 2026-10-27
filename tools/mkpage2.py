#!/usr/bin/env python3
"""Build flash page 2 (assets): fonts + ZX0 file table + compressed files.

Layout (bank A view, $4000-based):
  $4000 font3 (320)  $4140 font5 (448)  $4300 file table (16 x 16)  $4400.. data
Entry: name[8] page[1] offset[2] clen[2] ulen[2] flags[1]
"""
import os
import struct
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
build = os.path.join(root, "build")
assets = os.path.join(build, "assets")
zx0 = os.path.join(root, "tools", "bin", "zx0.exe")


def compress(data, name):
    src = os.path.join(assets, name + ".raw")
    dst = os.path.join(assets, name + ".zx0")
    open(src, "wb").write(data)
    if os.path.exists(dst):
        os.remove(dst)
    subprocess.run([zx0, "-f", src, dst], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return open(dst, "rb").read()


def main():
    os.makedirs(assets, exist_ok=True)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gen_assets
    import content
    gen_assets.main(assets)
    page = bytearray(b"\xff" * 16384)
    f3 = open(os.path.join(assets, "font3.bin"), "rb").read()
    f5 = open(os.path.join(assets, "font5.bin"), "rb").read()
    page[0:320] = f3
    page[0x140:0x140 + 448] = f5
    pos = 0x400
    table = bytearray()
    for name, data in content.files():
        comp = compress(data, name.lower())
        assert pos + len(comp) < 16384, "page 2 overflow"
        page[pos:pos + len(comp)] = comp
        table += name.encode().ljust(8, b"\0")[:8] + bytes([2]) + struct.pack("<HHH", 0x4000 + pos, len(comp), len(data)) + b"\0"
        print("  %-8s %5d -> %5d bytes @%04X" % (name, len(data), len(comp), 0x4000 + pos))
        pos += len(comp)
    assert len(table) <= 256
    page[0x300:0x300 + len(table)] = table
    for i in range(len(table), 256):
        page[0x300 + i] = 0
    open(os.path.join(build, "page2.bin"), "wb").write(page)
    print("  page2 used: %d / 16384" % pos)


if __name__ == "__main__":
    main()
