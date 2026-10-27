"""Open a native game from the GAMES tab, press some keys, take screenshots.   python tools/game_probe.py ITEM [keys...]
ITEM = 1..9 (position in the GAMES tab).  Keys are names from uidrive.KEYS, 'wait:MS' or 'snap:NAME'.  Writes build/test/gp_*.png"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uidrive import Session  # noqa: E402

item = sys.argv[1]
s = Session("gp", start=1500)
s.press("TRACE", "K" + item)
s.t += 600
for a in sys.argv[2:]:
    if a.startswith("wait:"):
        s.t += int(a[5:])
    elif a.startswith("snap:"):
        s.snap(a[5:], wait=100)
    elif a.startswith("hold:"):                         # hold:KEY:MS
        _, k, ms = a.split(":")
        from uidrive import KEYS, kc
        s.ev += ["%d:down:%s" % (s.t, kc(KEYS[k])), "%d:up:%s" % (s.t + int(ms), kc(KEYS[k]))]
        s.t += int(ms) + 60
    else:
        s.press(a)
out = s.run(extra_ms=200)
for ln in out.splitlines():
    if ln.startswith("SNAP") or "halted_pct" in ln:
        print(ln[:140])
for f in sorted(os.listdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "test"))):
    if f.startswith("gp_") and f.endswith(".pbm"):
        name = f[3:-4]
        s.png(name, 5)
        print("png", name)
