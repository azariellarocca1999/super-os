#!/usr/bin/env python3
"""Convert hz80_sim PBM (P1, 96x64) to a scaled LCD-green PNG (no dependencies)."""
import struct
import sys
import zlib


def main(src, dst, scale=6):
    toks = open(src).read().split()
    w, h = int(toks[1]), int(toks[2])
    px = toks[3:]
    bg, fg = (176, 190, 160), (28, 36, 24)
    raw = bytearray()
    for y in range(h):
        row = bytearray()
        for x in range(w):
            row += bytes(fg if px[y * w + x] == "1" else bg) * scale
        for _ in range(scale):
            raw += b"\x00" + row

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    open(dst, "wb").write(png)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6)
