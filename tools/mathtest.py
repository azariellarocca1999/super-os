#!/usr/bin/env python3
"""Z80 float library tests: build a throw-away ROM (page 0 = tools/mathtest.z80, page 3 = the math page),
run it on the Tilem core and compare the results with Python's math module.  `python tools/mathtest.py`"""
import math
import os
import re
import struct
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, "tools"))
import fxlib as F

bin_ = os.path.join(root, "tools", "bin")
build = os.path.join(root, "build")
os.makedirs(build, exist_ok=True)
FX_MISC = 0x9E00 + 136


def asm(src, dst):
    r = subprocess.run([sys.executable, "tools/fix_jr.py", "-I", "z80-os", "-I", "build", "-I", "tools", src, dst], capture_output=True, text=True, cwd=root)
    out = r.stdout + r.stderr
    if r.returncode or "error" in out.lower():
        print(out)
        sys.exit("assembly failed: " + src)


def build_page3():
    for g in ("gen_sys", "gen_mathjt", "gen_calckeys", "gen_mstrings"):
        subprocess.run([sys.executable, "tools/%s.py" % g], cwd=root, check=True)
    F.write_consts(os.path.join(build, "consts.inc"))
    asm("z80-os/math/page3.z80", "build/mt_page3.bin")


class Case:
    def __init__(self, fn, a=None, b=None, text=None, ref=None, tol=2e-9, label=None, absol=0.0, err=0):
        self.fn, self.a, self.b, self.text, self.ref, self.tol, self.absol, self.err = fn, a, b, text, ref, tol, absol, err
        self.label = label or "%s(%s,%s)" % (fn, a if text is None else repr(text), b)


def record(c):
    fn = c.fn.upper() if c.fn.startswith(("ev_", "fx_")) else "FX_" + c.fn.upper()
    if c.text is not None:
        data = c.text.encode("latin-1") + b"\0"
        assert len(data) <= 28
        return "    .dw %s\n    .db 2,0\n    .db %s\n" % (fn, ",".join(str(x) for x in data.ljust(28, b"\0")))
    a = F.pack(c.a if c.a is not None else 0)
    b = F.pack(c.b if c.b is not None else 0)
    return "    .dw %s\n    .db 0,0\n    %s\n    %s\n    .fill 16,0\n" % (fn, F.db(a), F.db(b))


def run_cases(cases, ms=4000):
    build_page3()
    assert len(cases) < 250
    inc = "mt_count: .db %d\nmt_vec:\n" % len(cases) + "".join(record(c) for c in cases)
    open(os.path.join(build, "mt_vec.inc"), "w").write(inc)
    asm("tools/mathtest.z80", "build/mt_page0.bin")
    rom = bytearray(b"\xff" * (128 * 16384))
    p0 = open(os.path.join(build, "mt_page0.bin"), "rb").read()
    rom[0:len(p0)] = p0
    p3 = open(os.path.join(build, "mt_page3.bin"), "rb").read()
    assert len(p3) <= 16384, len(p3)
    rom[3 * 16384:3 * 16384 + len(p3)] = p3
    boot = open(os.path.join(build, "devboot.bin"), "rb").read().replace(b"\xC3\x53\x00", b"\xC3\x00\x00")   # this harness starts at $0000 (only the OS models the $0053 entry)
    rom[0x7F * 16384:0x7F * 16384 + len(boot)] = boot
    open(os.path.join(build, "mt.rom"), "wb").write(rom)
    n = len(cases)
    env = dict(os.environ, HZ_DUMP="C000", HZ_DUMPLEN=str(32 * n))
    r = subprocess.run([os.path.join(bin_, "hz80_sim.exe"), os.path.join(build, "mt.rom"), os.path.join(build, "mt"), str(ms)],
                       capture_output=True, text=True, env=env, timeout=600)
    m = re.search(r"MEM \w+:((?: [0-9A-F]{2})+)", r.stdout)
    assert m, r.stdout[-500:] + r.stderr[-300:]
    mem = bytes(int(x, 16) for x in m.group(1).split())
    env2 = dict(os.environ, HZ_DUMP="%X" % FX_MISC, HZ_DUMPLEN="1")
    r2 = subprocess.run([os.path.join(bin_, "hz80_sim.exe"), os.path.join(build, "mt.rom"), os.path.join(build, "mt"), str(ms)],
                        capture_output=True, text=True, env=env2, timeout=600)
    m2 = re.search(r"MEM \w+:((?: [0-9A-F]{2})+)", r2.stdout)
    done = m2 and int(m2.group(1).split()[0], 16) == 0x5A
    return mem, done


def check(cases, ms=4000, verbose=False):
    mem, done = run_cases(cases, ms)
    bad = 0
    if not done:
        print("  [FAIL] test program did not finish within %d ms" % ms)
    for i, c in enumerate(cases):
        rec = mem[i * 32:(i + 1) * 32]
        err = rec[0]
        val = F.unpack(rec[1:7])
        text = rec[7:32].split(b"\0")[0].decode("latin-1")
        ok = True
        why = ""
        if c.err:
            ok = err == c.err
            why = "err=%d want %d" % (err, c.err)
        elif c.ref is not None:
            if isinstance(c.ref, str):
                ok = text == c.ref
                why = "text %r want %r" % (text, c.ref)
            else:
                good = abs(val - c.ref) <= max(c.tol * abs(c.ref), c.absol) and err == 0
                ok = good
                why = "got %.12g want %.12g (err %d)" % (val, c.ref, err)
        if not ok:
            bad += 1
            print("  [FAIL] %s: %s" % (c.label, why))
        elif verbose:
            print("  [ok]   %s: %s" % (c.label, why))
    print("  %d/%d math cases passed" % (len(cases) - bad, len(cases)) + ("" if done else "  (INCOMPLETE RUN)"))
    return bad == 0 and done


def core_cases():
    cs = []
    vals = [(1.5, 2.25), (3.0, -1.0), (0.1, 0.2), (1e10, 3.3), (-7.5, 2.5), (123456.789, 0.001), (1.0, 1.0), (2.0, 3.0), (-0.0001, 5e-5), (1e19, -1e19), (255.0, 0.5)]
    for a, b in vals:
        cs.append(Case("add", a, b, ref=a + b, absol=1e-9 * max(abs(a), abs(b))))
        cs.append(Case("sub", a, b, ref=a - b, absol=1e-9 * max(abs(a), abs(b))))
        cs.append(Case("mul", a, b, ref=a * b))
        cs.append(Case("div", a, b, ref=a / b))
    for a in (2.0, 9.0, 0.25, 1e10, 3.0, 12345.678, 1e-20, 0.5):
        cs.append(Case("sqrt", a, ref=math.sqrt(a)))
    cs.append(Case("sqrt", -4.0, err=1))
    cs.append(Case("div", 1.0, 0.0, err=3))
    cs.append(Case("mul", 1e30, 1e30, err=2))
    for a in (3.7, -3.7, 0.2, -0.2, 100.0, -100.0, 12345.5, -12345.5):
        cs.append(Case("floor", a, ref=float(math.floor(a))))
        cs.append(Case("trunc", a, ref=float(math.trunc(a))))
    return cs


def fmt9(x, nd=9):
    """reference text for a value, same rules as the Z80 code"""
    if x == 0:
        return "0"
    s = "-" if x < 0 else ""
    x = abs(x)
    t = "%.*e" % (nd - 1, x)
    mant, ex = t.split("e")
    ex = int(ex)
    digs = mant.replace(".", "").rstrip("0") or "0"
    if 0 <= ex <= 9:
        ip = digs[:ex + 1].ljust(ex + 1, "0")
        fp = digs[ex + 1:]
        return s + ip + ("." + fp if fp else "")
    if -4 <= ex < 0:
        return s + "0." + "0" * (-ex - 1) + digs
    return s + digs[0] + ("." + digs[1:] if len(digs) > 1 else "") + "E" + str(ex)


def conv_cases():
    cs = []
    for x in (0.0, 1.0, -1.0, 0.5, 123.456, 1234567.0, 0.1, 0.001, 0.0001, 0.00001234, 3.14159265358979, 1e9, 1e10, 123456789.0, 1234567890.0, 2.5e-7, 9.9999999999, 99999.99999999, 1e38, 1.5e-30, -42.125, 100.0, 0.99999999999, 7.0e-3, 65536.0):
        v = F.unpack(F.pack(x))
        cs.append(Case("tostr", x, ref=fmt9(v), label="tostr(%r)" % x))
    ee = chr(0xF3)
    for t, v in (("0", 0.0), ("1", 1.0), ("12.5", 12.5), (".5", 0.5), ("5.", 5.0), ("123456789", 123456789.0), ("0.001", 0.001), ("1@5", 1e5), ("1.5@-3", 1.5e-3), ("12345678901", 12345678901.0), ("0.00000123", 1.23e-6), ("3.14159265", 3.14159265), ("1@38", 1e38), ("1@-30", 1e-30)):
        cs.append(Case("fromstr", text=t.replace("@", ee), ref=v, tol=3e-9, label="fromstr(%s)" % t))
    cs.append(Case("fromstr", text="abc", err=0, ref=0.0, label="fromstr(abc)"))
    return cs


def expr_cases():
    cs = []

    def e(text, ref, tol=5e-9, absol=1e-9, deg=False, err=0, vars_=None):
        cs.append(Case("ev_eval", text=F.tokenize(text), ref=ref, tol=tol, absol=absol, err=err, label="eval(%s)" % text))
    e("1+2*3", 7.0)
    e("(1+2)*3", 9.0)
    e("2^10", 1024.0)
    e("2^3^2", 512.0)
    e("-2^2", -4.0)
    e("2^-2", 0.25)
    e("10/4", 2.5)
    e("1-2-3", -4.0)
    e("8/2/2", 2.0)
    e("3.5*2", 7.0)
    e("100%", 1.0)
    e("5!", 120.0)
    e("2*3!", 12.0)
    e("sin(pi/6)", 0.5)
    e("cos(0)", 1.0)
    e("tan(pi/4)", 1.0)
    e("2pi", 2 * math.pi)
    e("pi*2", 2 * math.pi)
    e("e^1", math.e)
    e("ln(e)", 1.0)
    e("log(1000)", 3.0)
    e("sqrt(2)", math.sqrt(2))
    e("sqrt(16)+sqrt(9)", 7.0)
    e("2(3+4)", 14.0)
    e("(2)(3)", 6.0)
    e("exp(1)", math.e)
    e("abs(-3.5)", 3.5)
    e("floor(-2.5)", -3.0)
    e("ceil(2.1)", 3.0)
    e("int(-2.7)", -2.0)
    e("frac(2.75)", 0.75)
    e("sign(-9)", -1.0)
    e("round(3.14159,2)", 3.14)
    e("mod(17,5)", 2.0)
    e("nCr(5,2)", 10.0)
    e("nPr(5,2)", 20.0)
    e("min(3,7)", 3.0)
    e("max(3,7)", 7.0)
    e("cbrt(27)", 3.0, tol=5e-9)
    e("cbrt(-8)", -2.0, tol=5e-9)
    e("10^(2)", 100.0)
    e("1E3+1", 1001.0)
    e("1.5E-3*2", 0.003)
    e("sin(cos(0))", math.sin(1.0))
    e("sqrt(sin(1)^2+cos(1)^2)", 1.0)
    e("atan(1)*4", math.pi)
    e("2*(3+(4-1)*2)", 18.0)
    e("1/3+1/3+1/3", 1.0, tol=2e-9)
    e("sin(30)", math.sin(30.0), tol=5e-9)
    e("1/0", None, err=3)
    e("2+", None, err=4)
    e("(2+3", 5.0)
    e("sqrt(-1)", None, err=1)
    e("3+*4", None, err=4)
    e("", None, err=4)
    return cs


def deg_cases():
    cs = [Case("fx_init")]
    for t, v in (("sin(30)", 0.5), ("cos(60)", 0.5), ("tan(45)", 1.0), ("asin(0.5)", 30.0), ("acos(0)", 90.0), ("atan(1)", 45.0), ("sin(90)", 1.0), ("cos(180)", -1.0), ("sin(45)^2", 0.5)):
        cs.append(Case("ev_evald", text=F.tokenize(t), ref=v, tol=5e-9, absol=1e-9, label="deg " + t))
    cs.append(Case("ev_eval", text=F.tokenize("A+1"), ref=1.0, label="var A cleared"))
    return cs


def fn_cases():
    cs = []
    for x in (0.0, 1.0, -1.0, 0.5, 2.5, -3.7, 10.0, 20.0, -20.0, 0.001, 50.0, -60.0, 85.0):
        cs.append(Case("exp", x, ref=math.exp(x), tol=5e-9))
    for x in (1.0, 2.0, 10.0, 0.5, 0.1, 100.0, 1234.5678, 1e-5, 1e30, 2.718281828, 0.9999, 1.0001):
        cs.append(Case("ln", x, ref=math.log(x), tol=5e-9, absol=3e-10))
    cs.append(Case("ln", 0.0, err=1))
    cs.append(Case("ln", -1.0, err=1))
    for x in (1.0, 10.0, 100.0, 12345.0, 0.001, 2.0):
        cs.append(Case("log10", x, ref=math.log10(x), tol=5e-9, absol=3e-10))
    for x in (8.0, 1.0, 1000.0):
        cs.append(Case("log2", x, ref=math.log2(x), tol=5e-9, absol=3e-10))
    for x in (0.0, 0.5, 1.0, 1.5707963, 2.0, 3.14159265, -1.0, -2.5, 10.0, 100.0, 355.0, 1000.0, 20000.0, 0.01, 6.2831853):
        cs.append(Case("sin", x, ref=math.sin(x), tol=5e-9, absol=3e-9))
        cs.append(Case("cos", x, ref=math.cos(x), tol=5e-9, absol=3e-9))
    for x in (0.5, 1.0, -1.0, 1.2, 2.0, 3.0, 100.0):
        cs.append(Case("tan", x, ref=math.tan(x), tol=1e-8, absol=3e-9))
    for x in (0.0, 0.5, 1.0, -1.0, 2.0, 10.0, 100.0, -0.2, 0.1):
        cs.append(Case("atan", x, ref=math.atan(x), tol=5e-9, absol=3e-10))
    for x in (0.0, 0.5, -0.5, 1.0, -1.0, 0.9, 0.1):
        cs.append(Case("asin", x, ref=math.asin(x), tol=5e-9, absol=3e-10))
        cs.append(Case("acos", x, ref=math.acos(x), tol=5e-9, absol=3e-10))
    cs.append(Case("asin", 1.5, err=1))
    for x in (0.5, 1.0, -2.0, 5.0):
        cs.append(Case("sinh", x, ref=math.sinh(x), tol=1e-8))
        cs.append(Case("cosh", x, ref=math.cosh(x), tol=1e-8))
        cs.append(Case("tanh", x, ref=math.tanh(x), tol=1e-8))
        cs.append(Case("asinh", x, ref=math.asinh(x), tol=1e-8))
    for x in (1.5, 3.0, 10.0):
        cs.append(Case("acosh", x, ref=math.acosh(x), tol=1e-8))
    for x in (0.5, -0.5, 0.9):
        cs.append(Case("atanh", x, ref=math.atanh(x), tol=1e-8))
    for a, b in ((2.0, 10.0), (2.0, 0.5), (10.0, -3.0), (-2.0, 3.0), (-2.0, 4.0), (1.5, 2.5), (9.0, 0.5), (2.0, -1.0), (7.0, 0.0), (0.0, 3.0), (3.0, 30.0), (1.0001, 10000.0), (5.0, 1.5), (2.0, 100.0)):
        cs.append(Case("pow", a, b, ref=F.unpack(F.pack(a)) ** F.unpack(F.pack(b)), tol=3e-6 if a == 1.0001 else 3e-8))
    cs.append(Case("pow", -2.0, 0.5, err=1))
    for n in (0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 33.0):
        cs.append(Case("fact", n, ref=float(math.factorial(int(n))), tol=5e-9))
    cs.append(Case("fact", 34.0, err=2))
    cs.append(Case("fact", -1.0, err=1))
    for a, b in ((7.0, 3.0), (-7.0, 3.0), (7.5, 2.0), (10.0, 5.0)):
        cs.append(Case("mod", a, b, ref=math.fmod(a, b) if a * b > 0 else a - b * math.floor(a / b), tol=1e-8, absol=1e-8))
    return cs


def run_all(verbose=False):
    ok = True
    for g in ("core", "fn", "conv", "expr", "deg"):
        print("math group %s" % g)
        ok = check(globals()[g + "_cases"](), verbose=verbose) and ok
    return ok


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "all"
    if which == "all":
        sys.exit(0 if run_all("-v" in sys.argv) else 1)
    sys.exit(0 if check(globals()[which + "_cases"](), verbose="-v" in sys.argv) else 1)
