#!/usr/bin/env python3
"""Super-CAS host tests.  Every symbolic result is verified numerically with an independent Python evaluator
(derivatives by finite differences, antiderivatives by differentiating them, roots by substitution, ...).
Run:  python cas/cas_tests.py        (needs tools/bin/cas_cli.exe: sh cas/build_cas.sh)"""
import cmath
import math
import os
import re
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(root, "tools", "bin", "cas_cli.exe")
results = []


def run_cli(cmds):
    r = subprocess.run([CLI], input="\n".join(cmds) + "\n", capture_output=True, text=True, timeout=300)
    outs = r.stdout.split("\n")
    return [o.replace("\x02", "\n") for o in outs[:len(cmds)]]


FUNCS = {"sin": cmath.sin, "cos": cmath.cos, "tan": cmath.tan, "asin": cmath.asin, "acos": cmath.acos, "atan": cmath.atan,
         "sinh": cmath.sinh, "cosh": cmath.cosh, "tanh": cmath.tanh, "asinh": cmath.asinh, "acosh": cmath.acosh, "atanh": cmath.atanh,
         "ln": cmath.log, "log": lambda z: cmath.log10(z), "exp": cmath.exp, "sqrt": cmath.sqrt, "cbrt": lambda z: z ** (1 / 3),
         "abs": abs, "sign": lambda z: (z > 0) - (z < 0), "pi": math.pi, "e": math.e, "i": 1j}


def pyexpr(s):
    s = s.split("\n")[0].strip()
    s = s.replace("^", "**")
    return s


def ev(s, **vars_):
    env = dict(FUNCS)
    env.update(vars_)
    return eval(pyexpr(s), {"__builtins__": {}}, env)


def check(name, ok, detail=""):
    results.append(ok)
    print("  [%s] %s %s" % ("PASS" if ok else "FAIL", name, detail))


def close(a, b, tol=1e-6):
    a, b = complex(a), complex(b)
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def split_top(s, sep=","):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [t.strip() for t in out]


def numdiff(f, x, h=1e-6):
    return (f(x + h) - f(x - h)) / (2 * h)


def main():
    print("== Super-CAS (host build of the same C++ the ESP32 runs)")
    # ---- arithmetic / simplification -------------------------------------------------------------------------------------------
    simple = [
        ("2+3*4", "14"), ("1/3+1/6", "1/2"), ("2^10", "1024"), ("(-8)^(1/3)", None), ("sqrt(8)", "2*sqrt(2)"), ("sqrt(2)*sqrt(2)", "2"),
        ("sqrt(1/2)", "sqrt(2)/2"), ("sqrt(-4)", "2*i"), ("sin(pi/6)", "1/2"), ("cos(pi/3)", "1/2"), ("sin(pi)", "0"), ("cos(pi)", "-1"),
        ("tan(pi/4)", "1"), ("atan(1)", "pi/4"), ("exp(0)", "1"), ("ln(e)", "1"), ("exp(ln(5))", "5"), ("x+x", "2*x"), ("x*x", "x^2"),
        ("(x+1)-(x+1)", "0"), ("sin(x)^2+cos(x)^2", "1"), ("100!", None), ("5!", "120"), ("ncr(5,2)", "10"), ("gcd(12,18)", "6"),
        ("mod(17,5)", "2"), ("factor(360)", "2^3*3^2*5"), ("factor(x^2-1)", "(x - 1)*(x + 1)"),
        ("factor(x^3-6*x^2+11*x-6)", "(x - 1)*(x - 2)*(x - 3)"), ("expand((x+1)^3)", "x^3 + 3*x^2 + 3*x + 1"),
        ("expand((x+y)^2)", "x^2 + 2*x*y + y^2"), ("det([[1,2],[3,4]])", "-2"), ("inv([[1,2],[3,4]])", "[[-2,1],[3/2,-1/2]]"),
        ("[[1,2],[3,4]]*[[0,1],[1,0]]", "[[2,1],[4,3]]"), ("transpose([[1,2],[3,4]])", "[[1,3],[2,4]]"), ("rank([[1,2],[2,4]])", "1"),
        ("det([[2,0,0],[0,3,0],[0,0,4]])", "24"), ("eig([[2,0],[0,3]])", "{2, 3}"), ("sum(k^2,k,1,10)", "385"),
        ("limit(sin(x)/x,x,0)", "1"), ("limit((x^2-1)/(x-1),x,1)", "2"), ("limit(x*ln(x),x,0)", "0"), ("limit((1-cos(x))/x^2,x,0)", "1/2"),
    ]
    cmds = [c for c, _ in simple]
    outs = run_cli(cmds)
    for (c, want), got in zip(simple, outs):
        if want is None:
            check("exact %s" % c, not got.startswith("ERROR"), "(%s)" % got.split("\n")[0])
        else:
            check("exact %s" % c, got.split("\n")[0] == want, "(%s)" % got.split("\n")[0] if got.split("\n")[0] != want else "")

    # ---- derivatives (finite differences) ---------------------------------------------------------------------------------------
    diffs = ["x^3*sin(x)", "exp(x^2)", "ln(x^2+1)", "sin(x)*cos(x)", "x^x", "sqrt(1+x^2)", "atan(x)", "tan(x)", "exp(sin(x))", "x^2/(x+1)", "asin(x/2)",
             "sinh(x)*x", "ln(sin(x))", "(x^2+1)^(3/2)", "1/(x^3+2)", "x*exp(-x^2)", "cosh(2*x)", "atan(x^2)", "log(x)", "abs(x)*x", "2^x", "sqrt(x)*ln(x)"]
    outs = run_cli(["diff(%s,x)" % f for f in diffs])
    for f, got in zip(diffs, outs):
        try:
            g = lambda x: ev(got, x=x)
            fn = lambda x: ev(f, x=x)
            ok = all(close(g(x), numdiff(fn, x), 1e-5) for x in (0.31, 0.77, 1.23, 1.9))
        except Exception as ex:  # noqa
            ok = False
        check("diff(%s)" % f, ok, "-> %s" % got.split("\n")[0])
    outs = run_cli(["diff(x^5,x,2)", "diff(sin(x),x,4)"])
    check("diff(x^5,x,2) = 20*x^3", outs[0] == "20*x^3", outs[0])
    check("diff(sin(x),x,4) = sin(x)", outs[1] == "sin(x)", outs[1])

    # ---- integrals (differentiate the answer) ---------------------------------------------------------------------------------------
    ints = ["x^2", "x^3+2*x", "sin(x)", "cos(2*x)", "exp(3*x)", "1/x", "1/(2*x+1)", "x*exp(x)", "x^2*exp(x)", "x*sin(x)", "x^2*cos(x)", "ln(x)",
            "x*ln(x)", "atan(x)", "1/(x^2+1)", "1/(x^2+4)", "1/(x^2-1)", "1/(x^2-3*x+2)", "x/(x^2+1)", "(2*x+3)/(x^2+3*x+5)", "1/(x^2+2*x+5)",
            "x*exp(x^2)", "sin(x)*cos(x)", "sin(x)^2", "cos(x)^2", "sin(x)^3", "cos(x)^3*sin(x)", "sin(x)^2*cos(x)^2", "exp(2*x)*sin(x)", "exp(x)*cos(3*x)",
            "sin(2*x)*cos(3*x)", "sqrt(x)", "x*sqrt(x^2+1)", "1/sqrt(1-x^2)", "1/sqrt(x^2+1)", "sqrt(1-x^2)", "1/sqrt(x^2+4)", "tan(x)", "tan(x)^2",
            "(x+1)^5", "(2*x+1)^(1/2)", "1/(x*ln(x))", "exp(x)/(1+exp(x))", "x^3/(x^2+1)", "(x^2+1)/(x^3+3*x)", "1/(x^3+x)", "1/(x^2*(x+1))", "x/((x+1)^2)",
            "1/(x^2+1)^2", "sinh(x)", "cosh(x)*sinh(x)", "asin(x)", "x*atan(x)", "ln(x)^2", "x^2*ln(x)", "exp(x)*x^3", "1/(1+exp(x))", "cos(x)/sin(x)"]
    outs = run_cli(["int(%s,x)" % f for f in ints])
    for f, got in zip(ints, outs):
        if got.startswith("ERROR"):
            check("int(%s)" % f, False, "-> %s" % got)
            continue
        F = re.sub(r" \+ C$", "", got.split("\n")[0])
        try:
            g = lambda x: ev(F, x=x)
            fn = lambda x: ev(f, x=x)
            pts = (0.1, 0.3, 0.5, 0.7) if f in ("1/sqrt(1-x^2)", "sqrt(1-x^2)", "asin(x)") else (0.37, 0.71, 1.13, 1.61)
            ok = all(close(numdiff(g, x), fn(x), 2e-5) for x in pts)
        except Exception as ex:  # noqa
            ok = False
        check("int(%s)" % f, ok, "-> %s" % F)
    defs = [("sin(x)", 0, math.pi, 2), ("x^2", 0, 3, 9), ("exp(x)", 0, 1, math.e - 1), ("1/x", 1, math.e, 1), ("1/(1+x^2)", 0, 1, math.pi / 4),
            ("x*exp(-x)", 0, 2, 1 - 3 * math.exp(-2)), ("sqrt(x)", 0, 4, 16 / 3), ("cos(x)^2", 0, math.pi, math.pi / 2)]
    outs = run_cli(["int(%s,x,%s,%s)" % (f, a, b) for f, a, b, _ in defs])
    for (f, a, b, want), got in zip(defs, outs):
        try:
            ok = close(ev(got.split("\n")[0]), want, 1e-6)
        except Exception:  # noqa
            ok = False
        check("int(%s,x,%s,%s)" % (f, a, b), ok, "-> %s" % got.split("\n")[0])
    outs = run_cli(["int(exp(-x^2),x,0,1)", "int(sin(x)/x,x,1,2)"])
    check("numeric fallback int(exp(-x^2),0,1) = 0.74682413", abs(float(outs[0]) - 0.7468241328) < 1e-7, outs[0])
    check("numeric fallback int(sin(x)/x,1,2)", abs(float(outs[1]) - 0.6593299064) < 1e-7, outs[1])

    # ---- equations ---------------------------------------------------------------------------------------------------------------------
    eqs = ["x^2-2=0", "x^2+x+1=0", "x^3-6*x^2+11*x-6=0", "2*x+3=7", "x^4-5*x^2+4=0", "x^2=9", "3*x^2-12=0", "x^3=8", "a*x+b=c", "x^2+a*x+1=0",
           "exp(x)=5", "ln(x)=2", "sin(x)=1/2", "cos(x)=0", "x^3+x+1=0", "x^5-x-1=0", "cos(x)=x", "exp(x)=3*x", "sqrt(x+1)=3", "2^x=32", "x^2*exp(x)=1",
           "abs(x-1)=2", "1/x=4", "(x+1)/(x-1)=3"]
    outs = run_cli(["solve(%s,x)" % e for e in eqs])
    for e, got in zip(eqs, outs):
        g = got.split("\n")[0]
        if not g.startswith("{"):
            check("solve(%s)" % e, False, "-> %s" % g)
            continue
        sols = [t.split("=", 1)[1].strip() for t in split_top(g[1:-1])] if g != "{}" else []
        lhs, rhs = e.split("=")
        ok = len(sols) > 0
        for s in sols:
            try:
                x = ev(s, a=1.3, b=0.7, c=2.1)
                v = ev(lhs, x=x, a=1.3, b=0.7, c=2.1) - ev(rhs, x=x, a=1.3, b=0.7, c=2.1)
                ok = ok and abs(v) < 1e-6 * max(1, abs(x) ** 3)
            except Exception:  # noqa
                ok = False
        check("solve(%s)" % e, ok, "-> %s" % g)
    outs = run_cli(["solve(x+y=3,x-y=1)", "solve(2*x+3*y=7,x-y=1)", "solve(x+y=2,x*y=1)", "solve(x+y+z=6,x-y=0,y+z=5)", "solve(x+y=1,x+y=2)"])
    check("linear system x+y=3, x-y=1", outs[0] == "{x = 2, y = 1}", outs[0])
    check("linear system 2x+3y=7, x-y=1", outs[1] == "{x = 2, y = 1}", outs[1])
    check("system with a quadratic x+y=2, xy=1", "1" in outs[2] and "ERR" not in outs[2], outs[2])
    check("3x3 linear system", outs[3] == "{x = 1, y = 1, z = 4}", outs[3])
    check("inconsistent system", "no solution" in outs[4], outs[4])

    # ---- series / limits / matrices ----------------------------------------------------------------------------------------------------------
    tays = [("sin(x)", 0, 7, lambda x: math.sin(x)), ("exp(x)", 0, 6, lambda x: math.exp(x)), ("cos(x)", 0, 6, lambda x: math.cos(x)),
            ("ln(1+x)", 0, 6, lambda x: math.log(1 + x)), ("1/(1-x)", 0, 6, lambda x: 1 / (1 - x)), ("atan(x)", 0, 7, lambda x: math.atan(x)),
            ("sqrt(1+x)", 0, 5, lambda x: math.sqrt(1 + x))]
    outs = run_cli(["taylor(%s,x,%s,%d)" % (f, a, n) for f, a, n, _ in tays])
    for (f, a, n, fn), got in zip(tays, outs):
        g = got.split("\n")[0]
        try:
            ok = abs(ev(g, x=0.1) - fn(0.1)) < 0.1 ** (n + 1) * 2 and abs(ev(g, x=0.2) - fn(0.2)) < 0.2 ** (n + 1) * 2
        except Exception:  # noqa
            ok = False
        check("taylor(%s)" % f, ok, "-> %s" % g)
    outs = run_cli(["limit(sin(x)/x,x,0)", "limit((1+1/x)^x,x,oo)", "limit(exp(-x),x,oo)", "limit((x^2+1)/(2*x^2-3),x,oo)", "limit(1/x,x,0)", "limit(tan(x)/x,x,0)",
                    "limit((exp(x)-1)/x,x,0)", "limit(x^2,x,3)", "limit(atan(x),x,oo)", "limit(sqrt(x+1)-sqrt(x),x,oo)"])
    check("limit sin(x)/x", outs[0] == "1", outs[0])
    check("limit (1+1/x)^x = e", outs[1].split("\n")[0] == "e", outs[1])
    check("limit exp(-x) at oo = 0", outs[2].split("\n")[0] in ("0",), outs[2])
    check("limit rational at oo = 1/2", outs[3].split("\n")[0] == "1/2", outs[3])
    check("limit 1/x at 0 does not exist", "ERROR" in outs[4], outs[4])
    check("limit tan(x)/x", outs[5].split("\n")[0] == "1", outs[5])
    check("limit (exp(x)-1)/x", outs[6].split("\n")[0] == "1", outs[6])
    check("limit x^2 at 3", outs[7] == "9", outs[7])
    check("limit atan(x) at oo = pi/2", outs[8].split("\n")[0] == "pi/2", outs[8])
    check("limit sqrt(x+1)-sqrt(x) at oo = 0", outs[9].split("\n")[0] in ("0",), outs[9])
    outs = run_cli(["inv([[2,1],[1,1]])", "det([[1,2,3],[4,5,6],[7,8,10]])", "[[1,2],[3,4]]^2", "[[1,2],[3,4]]*[[1],[1]]", "inv([[1,2],[2,4]])", "eig([[2,1],[1,2]])",
                    "rref([[1,2,3],[4,5,6]])", "trace([[1,2],[3,4]])", "inv([[a,b],[c,d]])", "det([[a,b],[c,d]])", "[[1,2],[3,4]]+[[1,1],[1,1]]", "2*[[1,2],[3,4]]"])
    check("inverse 2x2", outs[0] == "[[1,-1],[-1,2]]", outs[0])
    check("determinant 3x3", outs[1] == "-3", outs[1])
    check("matrix power", outs[2] == "[[7,10],[15,22]]", outs[2])
    check("matrix times column", outs[3] == "[[3],[7]]", outs[3])
    check("singular matrix error", "ERROR" in outs[4], outs[4])
    check("eigenvalues 1 and 3", outs[5] == "{1, 3}", outs[5])
    check("rref", outs[6] == "[[1,0,-1],[0,1,2]]", outs[6])
    check("trace", outs[7] == "5", outs[7])
    check("symbolic 2x2 determinant", outs[9] == "a*d - b*c", outs[9])
    check("matrix sum", outs[10] == "[[2,3],[4,5]]", outs[10])
    check("scalar * matrix", outs[11] == "[[2,4],[6,8]]", outs[11])

    # ---- expand / factor / simplify consistency -------------------------------------------------------------------------------------------------
    rel = ["expand((x+1)^5)", "expand((x-1)*(x+1)*(x^2+1))", "factor(x^4-1)", "factor(2*x^2-8)", "factor(x^3+x^2-x-1)", "simplify((x^2-1)/(x-1))",
           "simplify((x^3-x)/(x^2-1))", "together(1/x+1/(x+1))", "expand((a+b)^3)", "factor(6*x^2+5*x+1)"]
    outs = run_cli(rel)
    for cmdline, got in zip(rel, outs):
        g = got.split("\n")[0]
        inner = cmdline[cmdline.index("(") + 1:-1]
        try:
            ok = all(close(ev(g.replace("^", "**").replace("**", "^"), x=x, a=x + 0.3, b=0.4), ev(inner, x=x, a=x + 0.3, b=0.4), 1e-7) for x in (0.37, 1.9, 2.4))
        except Exception:  # noqa
            ok = False
        check(cmdline, ok, "-> %s" % g)
    check("simplify((x^2-1)/(x-1)) = x + 1", run_cli(["simplify((x^2-1)/(x-1))"])[0] == "x + 1")
    check("factor(x^2-1) multiplicity form", run_cli(["factor(x^2+2*x+1)"])[0] == "(x + 1)^2")

    # ---- errors -------------------------------------------------------------------------------------------------------------------------------------
    outs = run_cli(["1/0", "2+", "sin(", "foo(1,2)", "ln(0)", "diff(", "int(f(x),x)"])
    check("division by zero is an error", outs[0].startswith("ERROR"), outs[0])
    check("syntax error 2+", outs[1].startswith("ERROR"), outs[1])
    check("syntax error sin(", outs[2].startswith("ERROR"), outs[2])
    check("unknown function stays symbolic", outs[3] == "foo(1,2)", outs[3])
    check("ln(0) is an error", outs[4].startswith("ERROR"), outs[4])
    check("incomplete diff( is an error", outs[5].startswith("ERROR"), outs[5])

    # ---- 3D surface --------------------------------------------------------------------------------------------------------------------------------------
    r = subprocess.run([CLI, "--plot3d"], input=b"plot3d(sin(x)*cos(y),-3,3,-3,3)\n", capture_output=True, timeout=60)
    ok = len(r.stdout) == 768
    lit = sum(bin(b).count("1") for b in r.stdout)
    check("plot3d renders a 96x64 bitmap with a wireframe", ok and 300 < lit < 3000, "(bytes=%d, lit pixels=%d)" % (len(r.stdout), lit))
    r2 = subprocess.run([CLI, "--plot3d"], input=b"plot3d(x^2+y^2,-2,2,-2,2)\n", capture_output=True, timeout=60)
    check("plot3d paraboloid differs from the sine surface", len(r2.stdout) == 768 and r2.stdout != r.stdout)

    n = sum(results)
    print("CAS RESULT: %d/%d checks passed" % (n, len(results)))
    return 0 if n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
