"""Run a native game for a while and dump its RAM.   python tools/game_dump.py ITEM MS [hexaddr len]  (default $A400, 96 bytes)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uidrive import Session, parse_mem  # noqa: E402

item, ms = sys.argv[1], int(sys.argv[2])
addr = sys.argv[3] if len(sys.argv) > 3 else "A400"
ln = sys.argv[4] if len(sys.argv) > 4 else "96"
s = Session("gd", start=1500)
s.press("TRACE", "K" + item)
s.t += ms
out = s.run(extra_ms=100, env={"HZ_DUMP": addr, "HZ_DUMPLEN": ln})
m = parse_mem(out)
base = int(addr, 16)
for i in range(0, len(m), 16):
    print("%04X: %s" % (base + i, " ".join("%02X" % v for v in m[i:i + 16])))
