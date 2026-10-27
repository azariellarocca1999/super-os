#!/usr/bin/env python3
"""Turn out-of-range JR into JP on the lines spasm reports (error SE120).  Usage: fix_jr.py <spasm args>"""
import re
import subprocess
import sys

root = __file__.rsplit("tools", 1)[0]
for _ in range(12):
    r = subprocess.run([root + "tools/bin/spasm.exe"] + sys.argv[1:], capture_output=True, text=True)
    out = r.stdout + r.stderr
    errs = re.findall(r"^(\S+?):(\d+): error SE120", out, re.M)
    if not errs:
        print(out[-600:] if "error" in out.lower() else "assembled OK")
        break
    for path, ln in errs:
        lines = open(path).read().split("\n")
        i = int(ln) - 1
        m = re.match(r"(\s*)jr(\s+(?:n?[zc],)?)(.*)", lines[i])
        if not m:
            print("cannot fix", path, ln, lines[i])
            sys.exit(1)
        lines[i] = "%sjp%s%s" % (m.group(1), m.group(2), m.group(3))
        open(path, "w").write("\n".join(lines))
    print("fixed", len(errs), "jumps")
