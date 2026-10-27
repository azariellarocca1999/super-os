// cas_algebra.cpp -- expand, polynomials, factoring, equation solving, matrices.
#include <algorithm>
#include <cmath>

#include "cas_int.h"
#include "cas_internal.h"

namespace cas {

// ---- expand ------------------------------------------------------------------------------------------------------------
static std::vector<E> addends(E e) {
  if (e->k == ADD) return e->a;
  return {e};
}
static E expandProduct(E a, E b) {
  std::vector<E> out;
  std::vector<E> ta = addends(a), tb = addends(b);
  if (ta.size() * tb.size() > 4000) {
    g_err = "expression too large to expand";
    return mkMul({a, b});
  }
  for (E x : ta)
    for (E y : tb) out.push_back(mkMul({x, y}));
  return mkAdd(out);
}
E expand(E e) {
  switch (e->k) {
    case ADD: {
      std::vector<E> t;
      for (E c : e->a) t.push_back(expand(c));
      return mkAdd(t);
    }
    case MUL: {
      E acc = num(1);
      for (E c : e->a) acc = expandProduct(acc, expand(c));
      return acc;
    }
    case POW: {
      E b = expand(e->a[0]);
      E x = e->a[1];
      if (b->k == ADD && x->k == NUM && x->d == 1 && x->n >= 2 && x->n <= 60) {
        E acc = b;
        for (int64_t k = 1; k < x->n; k++) acc = expandProduct(acc, b);
        return acc;
      }
      if (b->k == MUL && x->k == NUM && x->d == 1) return expand(mkPow(b, x));
      return mkPow(b, expand(x));
    }
    case FUNC: {
      std::vector<E> t;
      for (E c : e->a) t.push_back(expand(c));
      return mkFunc(e->s, t);
    }
    case MAT: {
      std::vector<E> t;
      for (E c : e->a) t.push_back(expand(c));
      return mkMat(e->rows, e->cols, t);
    }
    default:
      return e;
  }
}

// ---- polynomials in one variable ---------------------------------------------------------------------------------------------
bool polyCoeffs(E f, const std::string &x, std::vector<E> &c) {
  f = expand(f);
  c.clear();
  for (E t : addends(f)) {
    int64_t k = 0;
    std::vector<E> coef;
    std::vector<E> factors = t->k == MUL ? t->a : std::vector<E>{t};
    for (E fa : factors) {
      if (!contains(fa, x)) {
        coef.push_back(fa);
        continue;
      }
      if (fa->k == SYM && fa->s == x) {
        k += 1;
        continue;
      }
      if (fa->k == POW && fa->a[0]->k == SYM && fa->a[0]->s == x && fa->a[1]->k == NUM && fa->a[1]->d == 1 && fa->a[1]->n >= 0) {
        k += fa->a[1]->n;
        continue;
      }
      return false;
    }
    if (k > 200) return false;
    if ((int64_t)c.size() <= k) c.resize(k + 1, num(0));
    c[k] = mkAdd({c[k], mkMul(coef)});
  }
  if (c.empty()) c.push_back(num(0));
  while (c.size() > 1 && isZero(c.back())) c.pop_back();
  return true;
}
E fromCoeffs(const std::vector<E> &c, E x) {
  std::vector<E> t;
  for (size_t k = 0; k < c.size(); k++) t.push_back(mkMul({c[k], mkPow(x, num((int64_t)k))}));
  return mkAdd(t);
}

typedef std::vector<Rat> RPoly;  // low -> high
static void rtrim(RPoly &p) {
  while (p.size() > 1 && p.back().n == 0) p.pop_back();
}
static bool toRPoly(const std::vector<E> &c, RPoly &out) {
  out.clear();
  for (E e : c) {
    if (e->k != NUM) return false;
    out.push_back(Rat{e->n, e->d});
  }
  return true;
}
static E fromRPoly(const RPoly &p, E x) {
  std::vector<E> c;
  for (auto &r : p) c.push_back(num(r.n, r.d));
  return fromCoeffs(c, x);
}
static bool rpolyDiv(RPoly a, const RPoly &b, RPoly &q, RPoly &r) {
  rtrim(a);
  q.assign(a.size() >= b.size() ? a.size() - b.size() + 1 : 1, Rat{0, 1});
  while (a.size() >= b.size() && !(a.size() == 1 && a[0].n == 0)) {
    Rat f;
    if (!ratDiv(a.back(), b.back(), f)) return false;
    size_t sh = a.size() - b.size();
    q[sh] = f;
    for (size_t i = 0; i < b.size(); i++) {
      Rat t, o;
      if (!ratMul(f, b[i], t) || !ratSub(a[sh + i], t, o)) return false;
      a[sh + i] = o;
    }
    a.pop_back();
    if (a.empty()) a.push_back(Rat{0, 1});
    if (a.size() < b.size()) break;
  }
  r = a;
  rtrim(r);
  rtrim(q);
  return true;
}
static RPoly rpolyGcd(RPoly a, RPoly b) {
  rtrim(a);
  rtrim(b);
  while (!(b.size() == 1 && b[0].n == 0)) {
    RPoly q, r;
    if (!rpolyDiv(a, b, q, r)) return RPoly{Rat{1, 1}};
    a = b;
    b = r;
  }
  if (a.back().n != 0) {
    Rat inv;
    ratDiv(Rat{1, 1}, a.back(), inv);
    for (auto &c : a) ratMul(c, inv, c);
  }
  return a;
}
static Rat rpolyEval(const RPoly &p, Rat x) {
  Rat r{0, 1};
  for (size_t i = p.size(); i-- > 0;) {
    Rat t;
    if (!ratMul(r, x, t) || !ratAdd(t, p[i], r)) return Rat{1, 0};
  }
  return r;
}
static std::vector<int64_t> divisors(int64_t n) {
  std::vector<int64_t> d;
  if (n < 0) n = -n;
  if (n == 0) return d;
  for (int64_t i = 1; i * i <= n && i < 2000000; i++)
    if (n % i == 0) {
      d.push_back(i);
      if (i != n / i) d.push_back(n / i);
    }
  return d;
}
// primitive integer polynomial and the content that was removed
static Rat makePrimitive(RPoly &p) {
  I128 l = 1;
  for (auto &c : p) l = l / gcd128(l, c.d) * c.d;
  if (l > ((I128)1 << 62)) return Rat{1, 1};
  I128 g = 0;
  for (auto &c : p) g = gcd128(g, (I128)c.n * (l / c.d));
  if (g == 0) return Rat{1, 1};
  if (p.back().n < 0) g = -g;
  for (auto &c : p) {
    I128 v = (I128)c.n * (l / c.d) / g;
    c = Rat{(int64_t)v, 1};
  }
  Rat content;
  ratMake(g, l, content);
  return content;
}
// rational root of an integer polynomial (nonzero constant term assumed); returns false when none
static bool findRationalRoot(const RPoly &p, Rat &root) {
  if (p.size() < 2) return false;
  if (p[0].n == 0) {
    root = Rat{0, 1};
    return true;
  }
  std::vector<int64_t> dn = divisors(p[0].n), dd = divisors(p.back().n);
  if (dn.size() > 4000 || dd.size() > 4000) return false;
  for (int64_t q : dd)
    for (int64_t pp : dn)
      for (int s = 0; s < 2; s++) {
        Rat c{s ? -pp : pp, q};
        Rat g;
        if (!ratMake(c.n, c.d, g)) continue;
        Rat v = rpolyEval(p, g);
        if (v.d != 0 && v.n == 0) {
          root = g;
          return true;
        }
      }
  return false;
}

// ---- factoring -------------------------------------------------------------------------------------------------------------------
static E prodOf(const std::vector<E> &f) {
  if (f.size() == 1) return f[0];
  return mkFunc("prod", f);
}
static E factorInteger(int64_t n) {
  if (n == 0 || n == 1 || n == -1) return num(n);
  std::vector<E> f;
  if (n < 0) {
    f.push_back(num(-1));
    n = -n;
  }
  for (auto &p : factorInt((uint64_t)n)) {
    // raw power so that the product is not multiplied back together
    f.push_back(p.e == 1 ? num(p.p) : mkFunc("pow", {num(p.p), num(p.e)}));
  }
  return prodOf(f);
}
static E factorRPoly(RPoly p, E x) {
  rtrim(p);
  Rat content = makePrimitive(p);
  std::vector<E> out;
  if (!(content.n == 1 && content.d == 1)) out.push_back(num(content.n, content.d));
  std::vector<std::pair<RPoly, int>> linear;
  while (p.size() > 1) {
    Rat r;
    if (!findRationalRoot(p, r)) break;
    RPoly lin = {Rat{-r.n, 1}, Rat{r.d, 1}};  // d*x - n
    RPoly nl = lin;
    makePrimitive(nl);
    RPoly q, rem;
    if (!rpolyDiv(p, nl, q, rem)) break;
    p = q;
    makePrimitive(p);
    bool found = false;
    for (auto &l : linear)
      if (l.first.size() == nl.size() && ratCmp(l.first[0], nl[0]) == 0 && ratCmp(l.first[1], nl[1]) == 0) {
        l.second++;
        found = true;
      }
    if (!found) linear.push_back({nl, 1});
  }
  for (auto &l : linear) {
    E base = fromRPoly(l.first, x);
    out.push_back(l.second == 1 ? base : mkFunc("pow", {base, num(l.second)}));
  }
  if (p.size() > 1) {
    E rest = fromRPoly(p, x);
    out.push_back(rest);
  } else if (p.size() == 1 && !(p[0].n == 1 && p[0].d == 1)) {
    out.insert(out.begin(), num(p[0].n, p[0].d));
  }
  if (out.empty()) return num(1);
  return prodOf(out);
}

E factorExpr(E e) {
  if (e->k == NUM && e->d == 1) return factorInteger(e->n);
  std::vector<std::string> v;
  freeSyms(e, v);
  if (v.empty()) return e;
  E ex = expand(e);
  // single variable polynomial over Q
  if (v.size() == 1) {
    std::vector<E> c;
    RPoly rp;
    if (polyCoeffs(ex, v[0], c) && toRPoly(c, rp) && rp.size() > 1) return factorRPoly(rp, sym(v[0]));
  }
  // common monomial / content of a multivariate sum
  if (ex->k == ADD) {
    std::vector<E> terms = ex->a;
    I128 g = 0;
    bool ok = true;
    std::vector<std::pair<std::string, int64_t>> minexp;
    for (size_t ti = 0; ti < terms.size(); ti++) {
      E t = terms[ti];
      std::vector<E> fs = t->k == MUL ? t->a : std::vector<E>{t};
      std::vector<std::pair<std::string, int64_t>> ex2;
      for (E f : fs) {
        if (f->k == NUM) {
          if (f->d != 1) ok = false;
          g = gcd128(g, f->n);
        } else if (f->k == SYM)
          ex2.push_back({f->s, 1});
        else if (f->k == POW && f->a[0]->k == SYM && f->a[1]->k == NUM && f->a[1]->d == 1 && f->a[1]->n > 0)
          ex2.push_back({f->a[0]->s, f->a[1]->n});
        else
          ok = false;
      }
      if (t->k == SYM || (t->k == POW) || (t->k == MUL && !isNumeric(t->a[0]))) g = gcd128(g, 1);
      if (ti == 0)
        minexp = ex2;
      else {
        for (auto &m : minexp) {
          int64_t here = 0;
          for (auto &q : ex2)
            if (q.first == m.first) here = q.second;
          m.second = std::min(m.second, here);
        }
      }
    }
    if (ok && g == 0) g = 1;
    if (ok && (g > 1 || std::any_of(minexp.begin(), minexp.end(), [](auto &m) { return m.second > 0; }))) {
      std::vector<E> common;
      E divisor = num((int64_t)g);
      for (auto &m : minexp)
        if (m.second > 0) divisor = mkMul({divisor, mkPow(sym(m.first), num(m.second))});
      std::vector<E> rest;
      for (E t : terms) rest.push_back(expand(div(t, divisor)));
      E restSum = mkAdd(rest);
      std::vector<E> fl;
      if (divisor->k == MUL)
        for (E d : divisor->a) fl.push_back(d);
      else
        fl.push_back(divisor);
      fl.push_back(restSum);
      return mkFunc("prod", fl);
    }
  }
  return e;
}

// ---- together / simplify -----------------------------------------------------------------------------------------------------------
static void splitNumDen(E e, E &n, E &d) {
  if (e->k == MUL) {
    std::vector<E> nn, dd;
    for (E f : e->a) {
      if (f->k == POW && f->a[1]->k == NUM && f->a[1]->n < 0)
        dd.push_back(mkPow(f->a[0], num(-f->a[1]->n, f->a[1]->d)));
      else
        nn.push_back(f);
    }
    n = mkMul(nn);
    d = mkMul(dd);
    return;
  }
  if (e->k == POW && e->a[1]->k == NUM && e->a[1]->n < 0) {
    n = num(1);
    d = mkPow(e->a[0], num(-e->a[1]->n, e->a[1]->d));
    return;
  }
  n = e;
  d = num(1);
}
E together(E e) {
  if (e->k == ADD) {
    E N = num(0), D = num(1);
    for (E t : e->a) {
      E tn, td;
      splitNumDen(together(t), tn, td);
      if (equal(D, td)) {
        N = expand(add(N, tn));
      } else {
        N = expand(add(mkMul({N, td}), mkMul({tn, D})));
        D = mkMul({D, td});
      }
    }
    return div(N, D);
  }
  if (e->k == MUL) {
    std::vector<E> t;
    for (E f : e->a) t.push_back(together(f));
    return mkMul(t);
  }
  return e;
}

E simplify(E e) {
  if (e->k == MAT) return expand(e);
  // rebuild canonical form, then try a rational-function normalisation and keep the shorter result
  E canon = mapChildren(e, [](E x, void *) { return simplify(x); }, nullptr);
  std::vector<std::string> v;
  freeSyms(canon, v);
  if (v.size() == 1) {
    E n, d;
    E tg = together(canon);
    splitNumDen(tg, n, d);
    std::vector<E> cn, cd;
    RPoly pn, pd;
    if (!isOne(d) && polyCoeffs(n, v[0], cn) && polyCoeffs(d, v[0], cd) && toRPoly(cn, pn) && toRPoly(cd, pd)) {
      RPoly g = rpolyGcd(pn, pd);
      if (g.size() > 1) {
        RPoly q1, r1, q2, r2;
        if (rpolyDiv(pn, g, q1, r1) && rpolyDiv(pd, g, q2, r2)) {
          E x = sym(v[0]);
          E res = div(fromRPoly(q1, x), fromRPoly(q2, x));
          if (toString(res).size() <= toString(canon).size()) return res;
        }
      }
    }
    E ex = expand(canon);
    if (toString(ex).size() < toString(canon).size()) return ex;
  }
  return canon;
}

// ---- solving ---------------------------------------------------------------------------------------------------------------------------
static E principal(E v) { return expand(v); }
static bool isSym(E e, const char *name) { return e->k == SYM && e->s == name; }

static std::vector<E> quadraticRoots(E a, E b, E c) {
  E D = expand(sub(mkMul({b, b}), mkMul({num(4), a, c})));
  E sq = mkPow(D, num(1, 2));
  std::vector<E> r;
  E twoA = mkMul({num(2), a});
  r.push_back(principal(div(add(neg(b), sq), twoA)));
  if (!isZero(sq)) r.push_back(principal(div(sub(neg(b), sq), twoA)));
  return r;
}

// Durand-Kerner on a real polynomial (low -> high); roots as (re, im)
static std::vector<std::pair<double, double>> numericPolyRoots(const std::vector<double> &c) {
  int n = (int)c.size() - 1;
  std::vector<std::pair<double, double>> z(n);
  double lead = c[n];
  std::vector<double> a(n + 1);
  for (int i = 0; i <= n; i++) a[i] = c[i] / lead;
  double R = 1;
  for (int i = 0; i < n; i++) R = std::max(R, std::fabs(a[i]) + 1);
  for (int i = 0; i < n; i++) {
    double ang = 2 * M_PI * i / n + 0.4;
    z[i] = {R * 0.5 * std::cos(ang), R * 0.5 * std::sin(ang)};
  }
  for (int it = 0; it < 500; it++) {
    double change = 0;
    for (int i = 0; i < n; i++) {
      double pr = 1, pi = 0;  // evaluate monic polynomial at z[i]
      pr = 1;
      pi = 0;
      for (int k = n - 1; k >= 0; k--) {
        double nr = pr * z[i].first - pi * z[i].second + a[k];
        double ni = pr * z[i].second + pi * z[i].first;
        pr = nr;
        pi = ni;
      }
      double dr = 1, di = 0;
      for (int j = 0; j < n; j++)
        if (j != i) {
          double xr = z[i].first - z[j].first, xi = z[i].second - z[j].second;
          double nr = dr * xr - di * xi, ni = dr * xi + di * xr;
          dr = nr;
          di = ni;
        }
      double den = dr * dr + di * di;
      if (den == 0) continue;
      double qr = (pr * dr + pi * di) / den, qi = (pi * dr - pr * di) / den;
      z[i].first -= qr;
      z[i].second -= qi;
      change = std::max(change, std::fabs(qr) + std::fabs(qi));
    }
    if (change < 1e-14) break;
  }
  return z;
}

static E complexE(double re, double im) {
  if (std::fabs(im) < 1e-9 * std::max(1.0, std::fabs(re))) return real(re);
  return mkAdd({real(std::fabs(re) < 1e-12 ? 0 : re), mkMul({real(im), sym("i")})});
}

static std::vector<E> solvePolynomial(const std::vector<E> &c, const std::string &x, bool *numeric) {
  std::vector<E> sols;
  int deg = (int)c.size() - 1;
  if (deg == 1) {
    sols.push_back(principal(div(neg(c[0]), c[1])));
    return sols;
  }
  if (deg == 2) return quadraticRoots(c[2], c[1], c[0]);
  RPoly rp;
  bool rational = toRPoly(c, rp);
  if (rational) {
    // x = 0 roots, rational roots, then the remaining quadratic / numeric
    rtrim(rp);
    RPoly p = rp;
    makePrimitive(p);
    while (p.size() > 1) {
      Rat r;
      if (!findRationalRoot(p, r)) break;
      sols.push_back(num(r.n, r.d));
      RPoly lin = {Rat{-r.n, 1}, Rat{r.d, 1}};
      makePrimitive(lin);
      RPoly q, rem;
      if (!rpolyDiv(p, lin, q, rem)) break;
      p = q;
      makePrimitive(p);
    }
    // deduplicate
    std::vector<E> uniq;
    for (E s : sols) {
      bool dup = false;
      for (E u : uniq) dup = dup || equal(u, s);
      if (!dup) uniq.push_back(s);
    }
    sols = uniq;
    if (p.size() == 3) {
      std::vector<E> cc;
      for (auto &r : p) cc.push_back(num(r.n, r.d));
      for (E s : quadraticRoots(cc[2], cc[1], cc[0])) sols.push_back(s);
    } else if (p.size() == 5 && p[1].n == 0 && p[3].n == 0) {  // biquadratic a y^2 + b y + c, y = x^2
      std::vector<E> cc = {num(p[0].n), num(p[2].n), num(p[4].n)};
      for (E y : quadraticRoots(cc[2], cc[1], cc[0])) {
        E s = mkPow(y, num(1, 2));
        sols.push_back(principal(s));
        if (!isZero(s)) sols.push_back(principal(neg(s)));
      }
    } else if (p.size() > 3) {
      std::vector<double> d;
      for (auto &r : p) d.push_back((double)r.n / (double)r.d);
      for (auto &z : numericPolyRoots(d)) sols.push_back(complexE(z.first, z.second));
      if (numeric) *numeric = true;
    }
    return sols;
  }
  // symbolic coefficients of degree > 2: only the biquadratic and pure-power shapes
  if (deg == 4 && isZero(c[1]) && isZero(c[3])) {
    for (E y : quadraticRoots(c[4], c[2], c[0])) {
      E s = mkPow(y, num(1, 2));
      sols.push_back(principal(s));
      if (!isZero(s)) sols.push_back(principal(neg(s)));
    }
    return sols;
  }
  bool pure = true;
  for (int k = 1; k < deg; k++) pure = pure && isZero(c[k]);
  if (pure) {
    E r = mkPow(div(neg(c[0]), c[deg]), num(1, deg));
    sols.push_back(principal(r));
    if (deg % 2 == 0) sols.push_back(principal(neg(r)));
    return sols;
  }
  g_err = "cannot solve a symbolic polynomial of degree " + std::to_string(deg);
  return sols;
}

static int countOcc(E e, const std::string &x) {
  if (e->k == SYM) return e->s == x ? 1 : 0;
  int n = 0;
  for (E c : e->a) n += countOcc(c, x);
  return n;
}

// peel the single occurrence of x off lhs = rhs
static void isolate(E lhs, E rhs, const std::string &x, std::vector<E> &sols, int depth) {
  if (depth > 12 || sols.size() > 12) return;
  if (lhs->k == SYM && lhs->s == x) {
    sols.push_back(principal(rhs));
    return;
  }
  switch (lhs->k) {
    case ADD: {
      std::vector<E> with, without;
      for (E t : lhs->a) (contains(t, x) ? with : without).push_back(t);
      if (with.size() != 1) return;
      isolate(with[0], sub(rhs, mkAdd(without)), x, sols, depth + 1);
      return;
    }
    case MUL: {
      std::vector<E> with, without;
      for (E t : lhs->a) (contains(t, x) ? with : without).push_back(t);
      if (with.size() != 1) return;
      isolate(with[0], div(rhs, mkMul(without)), x, sols, depth + 1);
      return;
    }
    case POW: {
      E b = lhs->a[0], e = lhs->a[1];
      if (!contains(e, x)) {
        E inv = div(num(1), e);
        if (e->k == NUM && e->d == 1 && e->n % 2 == 0) {
          E r = mkPow(rhs, inv);
          isolate(b, r, x, sols, depth + 1);
          isolate(b, neg(r), x, sols, depth + 1);
        } else
          isolate(b, mkPow(rhs, inv), x, sols, depth + 1);
      } else if (!contains(b, x)) {
        E l = isSym(b, "e") ? func1("ln", rhs) : div(func1("ln", rhs), func1("ln", b));
        isolate(e, l, x, sols, depth + 1);
      }
      return;
    }
    case FUNC: {
      if (lhs->a.size() != 1) return;
      const std::string &f = lhs->s;
      E u = lhs->a[0];
      E pi = sym("pi");
      if (f == "sin") {
        isolate(u, func1("asin", rhs), x, sols, depth + 1);
        isolate(u, sub(pi, func1("asin", rhs)), x, sols, depth + 1);
      } else if (f == "cos") {
        isolate(u, func1("acos", rhs), x, sols, depth + 1);
        isolate(u, neg(func1("acos", rhs)), x, sols, depth + 1);
      } else if (f == "tan")
        isolate(u, func1("atan", rhs), x, sols, depth + 1);
      else if (f == "ln")
        isolate(u, mkPow(sym("e"), rhs), x, sols, depth + 1);
      else if (f == "log")
        isolate(u, mkPow(num(10), rhs), x, sols, depth + 1);
      else if (f == "asin")
        isolate(u, func1("sin", rhs), x, sols, depth + 1);
      else if (f == "acos")
        isolate(u, func1("cos", rhs), x, sols, depth + 1);
      else if (f == "atan")
        isolate(u, func1("tan", rhs), x, sols, depth + 1);
      else if (f == "sinh")
        isolate(u, func1("asinh", rhs), x, sols, depth + 1);
      else if (f == "cosh") {
        isolate(u, func1("acosh", rhs), x, sols, depth + 1);
        isolate(u, neg(func1("acosh", rhs)), x, sols, depth + 1);
      } else if (f == "tanh")
        isolate(u, func1("atanh", rhs), x, sols, depth + 1);
      else if (f == "abs") {
        isolate(u, rhs, x, sols, depth + 1);
        isolate(u, neg(rhs), x, sols, depth + 1);
      }
      return;
    }
    default:
      return;
  }
}

static void sortRoots(std::vector<E> &r) {
  Env env;
  std::vector<std::pair<double, E>> k;
  for (E e : r) {
    double v = 0;
    if (!evalD(approxExpr(e), env, v)) return;  // complex or symbolic: keep the order
    k.push_back({v, e});
  }
  std::stable_sort(k.begin(), k.end(), [](const std::pair<double, E> &a, const std::pair<double, E> &b) { return a.first < b.first; });
  for (size_t i = 0; i < r.size(); i++) r[i] = k[i].second;
}

static E sideDiff(E eq) {
  if (eq->k == FUNC && eq->s == "eq" && eq->a.size() == 2) return sub(eq->a[0], eq->a[1]);
  return eq;
}

std::vector<E> solveEq(E eq, const std::string &x, bool *numeric) {
  std::vector<E> sols;
  E f = expand(sideDiff(eq));
  std::vector<E> c;
  if (polyCoeffs(f, x, c)) {
    if (c.size() == 1) {
      if (!isZero(c[0])) return sols;
      g_err = "every value of " + x + " is a solution";
      return sols;
    }
    return solvePolynomial(c, x, numeric);
  }
  // rational function: solve the numerator
  E n, d;
  splitNumDen(together(sideDiff(eq)), n, d);
  if (!isOne(d) && polyCoeffs(n, x, c) && c.size() > 1) {
    std::vector<E> cand = solvePolynomial(c, x, numeric), ok;
    for (E s : cand) {
      E dv = subs(d, sym(x), s);
      if (!isZero(dv)) ok.push_back(s);
    }
    return ok;
  }
  // isolate x
  if (eq->k == FUNC && eq->s == "eq" && countOcc(f, x) == 1) {
    isolate(eq->a[0], eq->a[1], x, sols, 0);
    if (!sols.empty()) return sols;
  } else if (countOcc(f, x) == 1) {
    isolate(f, num(0), x, sols, 0);
    if (!sols.empty()) return sols;
  }
  // numeric scan
  Env env;
  std::vector<double> roots;
  double lo = -60, hi = 60;
  int N = 6000;
  double prev = 0, prevx = lo;
  bool have = false;
  auto F = [&](double t, double &o) {
    env.v.clear();
    env.set(x, t);
    return evalD(f, env, o) && std::isfinite(o);
  };
  for (int i = 0; i <= N; i++) {
    double t = lo + (hi - lo) * i / N, v;
    if (!F(t, v)) {
      have = false;
      continue;
    }
    if (have && ((prev < 0 && v > 0) || (prev > 0 && v < 0) || v == 0)) {
      double a = prevx, b = t, fa = prev, fb = v;
      if (v == 0)
        roots.push_back(t);
      else {
        for (int it = 0; it < 80; it++) {
          double m = 0.5 * (a + b), fm;
          if (!F(m, fm)) break;
          if ((fa < 0) == (fm < 0)) {
            a = m;
            fa = fm;
          } else {
            b = m;
            fb = fm;
          }
        }
        double r = 0.5 * (a + b), fr;
        if (F(r, fr) && std::fabs(fr) < 1e-6 * std::max(1.0, std::max(std::fabs(fa), std::fabs(fb)) + 1.0)) roots.push_back(r);
      }
    }
    prev = v;
    prevx = t;
    have = true;
  }
  std::vector<double> uniq;
  for (double r : roots) {
    bool dup = false;
    for (double u : uniq) dup = dup || std::fabs(u - r) < 1e-7;
    if (!dup) uniq.push_back(r);
  }
  for (double r : uniq) sols.push_back(real(std::fabs(r) < 1e-12 ? 0 : r));
  if (numeric) *numeric = true;
  return sols;
}

// ---- linear / substitution systems -------------------------------------------------------------------------------------------------
static bool solveLinear(const std::vector<E> &eqs, const std::vector<std::string> &vars, std::vector<E> &out, std::string &status) {
  size_t n = vars.size(), m = eqs.size();
  std::vector<std::vector<E>> A(m, std::vector<E>(n + 1));
  for (size_t i = 0; i < m; i++) {
    E f = expand(sideDiff(eqs[i]));
    E rest = f;
    for (size_t j = 0; j < n; j++) {
      E co = expand(diff(f, vars[j]));
      for (auto &v : vars)
        if (contains(co, v)) return false;
      A[i][j] = co;
      rest = subs(rest, sym(vars[j]), num(0));
    }
    A[i][n] = neg(expand(rest));
  }
  size_t row = 0;
  std::vector<int> pivotCol(n, -1);
  for (size_t col = 0; col < n && row < m; col++) {
    size_t p = row;
    while (p < m && isZero(A[p][col])) p++;
    if (p == m) continue;
    std::swap(A[p], A[row]);
    E inv = div(num(1), A[row][col]);
    for (size_t j = col; j <= n; j++) A[row][j] = expand(mkMul({A[row][j], inv}));
    for (size_t i = 0; i < m; i++)
      if (i != row && !isZero(A[i][col])) {
        E f = A[i][col];
        for (size_t j = col; j <= n; j++) A[i][j] = expand(sub(A[i][j], mkMul({f, A[row][j]})));
      }
    pivotCol[col] = (int)row;
    row++;
  }
  for (size_t i = row; i < m; i++)
    if (!isZero(A[i][n])) {
      status = "no solution";
      return true;
    }
  for (size_t j = 0; j < n; j++)
    if (pivotCol[j] < 0) {
      status = "infinitely many solutions";
      return true;
    }
  out.clear();
  for (size_t j = 0; j < n; j++) out.push_back(A[pivotCol[j]][n]);
  return true;
}

std::string solveSystem(const std::vector<E> &eqs, const std::vector<std::string> &vars) {
  std::vector<E> sol;
  std::string status;
  if (solveLinear(eqs, vars, sol, status)) {
    if (!status.empty()) return status;
    std::vector<E> items;
    for (size_t j = 0; j < vars.size(); j++) items.push_back(eqOf(sym(vars[j]), sol[j]));
    return toString(setOf(items));
  }
  // substitution: find an equation that is linear in some variable
  if (vars.size() == 2 && eqs.size() == 2) {
    for (int ei = 0; ei < 2; ei++)
      for (int vi = 0; vi < 2; vi++) {
        E f = expand(sideDiff(eqs[ei]));
        std::vector<E> c;
        if (!polyCoeffs(f, vars[vi], c) || c.size() != 2) continue;
        E vexpr = expand(div(neg(c[0]), c[1]));
        if (contains(vexpr, vars[vi])) continue;
        E other = subs(sideDiff(eqs[1 - ei]), sym(vars[vi]), vexpr);
        const std::string &ov = vars[1 - vi];
        std::vector<E> roots = solveEq(other, ov);
        if (roots.empty()) continue;
        std::string out = "{";
        for (size_t r = 0; r < roots.size(); r++) {
          E val = expand(subs(vexpr, sym(ov), roots[r]));
          out += (r ? ", " : "") + std::string("{") + vars[vi] + " = " + toString(val) + ", " + ov + " = " + toString(roots[r]) + "}";
        }
        return out + "}";
      }
  }
  return "cannot solve this system";
}

// ---- matrices ---------------------------------------------------------------------------------------------------------------------------
static E at(E m, int r, int c) { return m->a[r * m->cols + c]; }
E matTranspose(E m) {
  std::vector<E> el;
  for (int c = 0; c < m->cols; c++)
    for (int r = 0; r < m->rows; r++) el.push_back(at(m, r, c));
  return mkMat(m->cols, m->rows, el);
}
E matAdd(E a, E b) {
  if (a->rows != b->rows || a->cols != b->cols) {
    g_err = "matrix sizes differ";
    return a;
  }
  std::vector<E> el;
  for (size_t i = 0; i < a->a.size(); i++) el.push_back(expand(add(a->a[i], b->a[i])));
  return mkMat(a->rows, a->cols, el);
}
E matMul(E a, E b) {
  if (a->cols != b->rows) {
    g_err = "matrix sizes do not match for multiplication";
    return a;
  }
  std::vector<E> el;
  for (int r = 0; r < a->rows; r++)
    for (int c = 0; c < b->cols; c++) {
      std::vector<E> t;
      for (int k = 0; k < a->cols; k++) t.push_back(mkMul({at(a, r, k), at(b, k, c)}));
      el.push_back(expand(mkAdd(t)));
    }
  return mkMat(a->rows, b->cols, el);
}
static E identity(int n) {
  std::vector<E> el;
  for (int r = 0; r < n; r++)
    for (int c = 0; c < n; c++) el.push_back(num(r == c ? 1 : 0));
  return mkMat(n, n, el);
}
E matDet(E m) {
  int n = m->rows;
  if (n != m->cols) {
    g_err = "determinant needs a square matrix";
    return num(0);
  }
  if (n == 1) return m->a[0];
  if (n == 2) return expand(sub(mkMul({at(m, 0, 0), at(m, 1, 1)}), mkMul({at(m, 0, 1), at(m, 1, 0)})));
  if (n <= 4) {
    std::vector<E> t;
    for (int c = 0; c < n; c++) {
      std::vector<E> el;
      for (int r = 1; r < n; r++)
        for (int k = 0; k < n; k++)
          if (k != c) el.push_back(at(m, r, k));
      E minor = matDet(mkMat(n - 1, n - 1, el));
      E term = mkMul({at(m, 0, c), minor});
      t.push_back(c % 2 ? neg(term) : term);
    }
    return expand(mkAdd(t));
  }
  // Gaussian elimination
  std::vector<std::vector<E>> A(n, std::vector<E>(n));
  for (int r = 0; r < n; r++)
    for (int c = 0; c < n; c++) A[r][c] = at(m, r, c);
  E det = num(1);
  for (int col = 0; col < n; col++) {
    int p = col;
    while (p < n && isZero(A[p][col])) p++;
    if (p == n) return num(0);
    if (p != col) {
      std::swap(A[p], A[col]);
      det = neg(det);
    }
    det = mkMul({det, A[col][col]});
    for (int r = col + 1; r < n; r++) {
      E f = div(A[r][col], A[col][col]);
      for (int c = col; c < n; c++) A[r][c] = expand(sub(A[r][c], mkMul({f, A[col][c]})));
    }
  }
  return expand(det);
}
E matInv(E m) {
  int n = m->rows;
  if (n != m->cols) {
    g_err = "inverse needs a square matrix";
    return m;
  }
  std::vector<std::vector<E>> A(n, std::vector<E>(2 * n));
  for (int r = 0; r < n; r++)
    for (int c = 0; c < n; c++) {
      A[r][c] = at(m, r, c);
      A[r][n + c] = num(r == c ? 1 : 0);
    }
  for (int col = 0; col < n; col++) {
    int p = col;
    while (p < n && isZero(A[p][col])) p++;
    if (p == n) {
      g_err = "singular matrix";
      return m;
    }
    std::swap(A[p], A[col]);
    E inv = div(num(1), A[col][col]);
    for (int c = 0; c < 2 * n; c++) A[col][c] = expand(mkMul({A[col][c], inv}));
    for (int r = 0; r < n; r++)
      if (r != col && !isZero(A[r][col])) {
        E f = A[r][col];
        for (int c = 0; c < 2 * n; c++) A[r][c] = expand(sub(A[r][c], mkMul({f, A[col][c]})));
      }
  }
  std::vector<E> el;
  for (int r = 0; r < n; r++)
    for (int c = 0; c < n; c++) el.push_back(simplify(A[r][n + c]));
  return mkMat(n, n, el);
}
E matPow(E a, int64_t n) {
  if (a->rows != a->cols) {
    g_err = "matrix power needs a square matrix";
    return a;
  }
  if (n < 0) return matPow(matInv(a), -n);
  E r = identity(a->rows), b = a;
  while (n) {
    if (n & 1) r = matMul(r, b);
    n >>= 1;
    if (n) b = matMul(b, b);
  }
  return r;
}
static E matRref(E m, int *rankOut) {
  int R = m->rows, C = m->cols;
  std::vector<std::vector<E>> A(R, std::vector<E>(C));
  for (int r = 0; r < R; r++)
    for (int c = 0; c < C; c++) A[r][c] = at(m, r, c);
  int row = 0;
  for (int col = 0; col < C && row < R; col++) {
    int p = row;
    while (p < R && isZero(A[p][col])) p++;
    if (p == R) continue;
    std::swap(A[p], A[row]);
    E inv = div(num(1), A[row][col]);
    for (int c = 0; c < C; c++) A[row][c] = expand(mkMul({A[row][c], inv}));
    for (int r = 0; r < R; r++)
      if (r != row && !isZero(A[r][col])) {
        E f = A[r][col];
        for (int c = 0; c < C; c++) A[r][c] = expand(sub(A[r][c], mkMul({f, A[row][c]})));
      }
    row++;
  }
  if (rankOut) *rankOut = row;
  std::vector<E> el;
  for (int r = 0; r < R; r++)
    for (int c = 0; c < C; c++) el.push_back(A[r][c]);
  return mkMat(R, C, el);
}
E matEigenvalues(E m) {
  if (m->rows != m->cols) {
    g_err = "eigenvalues need a square matrix";
    return num(0);
  }
  int n = m->rows;
  E lam = sym("l");
  std::vector<E> el;
  for (int r = 0; r < n; r++)
    for (int c = 0; c < n; c++) el.push_back(r == c ? sub(at(m, r, c), lam) : at(m, r, c));
  E cp = matDet(mkMat(n, n, el));
  std::vector<E> roots = solveEq(cp, "l");
  sortRoots(roots);
  return setOf(roots);
}

// ---- command dispatch ---------------------------------------------------------------------------------------------------------------------
static std::string defaultVar(E e) {
  std::vector<std::string> v;
  freeSyms(e, v);
  if (v.empty()) return "x";
  for (auto &s : v)
    if (s == "x") return "x";
  return v[0];
}
static bool symName(E e, std::string &out) {
  if (e->k != SYM) return false;
  out = e->s;
  return true;
}
static int64_t gcdE(int64_t a, int64_t b) { return igcd(a, b); }

E evalCall(const std::string &name, std::vector<E> &a) {
  size_t n = a.size();
  std::string v;
  if (name == "diff") {
    if (n < 1) return (g_err = "diff needs an expression", nullptr);
    std::string var;
    if (!(n >= 2 && symName(a[1], var))) var = defaultVar(a[0]);
    int64_t order = n >= 3 && a[2]->k == NUM ? a[2]->n : 1;
    return diffN(a[0], var, (int)order);
  }
  if (name == "int") {
    if (n < 1) return (g_err = "int needs an expression", nullptr);
    std::string var;
    if (!(n >= 2 && symName(a[1], var))) var = defaultVar(a[0]);
    E F = integrate(a[0], var);
    if (n >= 4) {
      if (F) {
        E hi = subs(F, sym(var), a[3]), lo = subs(F, sym(var), a[2]);
        if (!failed()) return simplify(sub(hi, lo));
        g_err.clear();
      }
      Env env;
      double lo, hi, r;
      if (evalD(a[2], env, lo) && evalD(a[3], env, hi)) {
        r = numericIntegral(a[0], var, lo, hi);
        return real(r);
      }
      return (g_err = "cannot integrate", nullptr);
    }
    if (!F) {
      g_err = "no elementary antiderivative found";
      return nullptr;
    }
    return F;
  }
  if (name == "taylor") {
    if (n < 2) return (g_err = "taylor(f, x, x0, n)", nullptr);
    std::string var;
    symName(a[1], var);
    E x0 = n >= 3 ? a[2] : num(0);
    int order = n >= 4 && a[3]->k == NUM ? (int)a[3]->n : 6;
    return taylor(a[0], var, x0, order);
  }
  if (name == "limit") {
    if (n < 3) return (g_err = "limit(f, x, a)", nullptr);
    std::string var;
    symName(a[1], var);
    bool approx = false;
    E r = limit(a[0], var, a[2], &approx);
    return r;
  }
  if (name == "solve") {
    std::vector<E> eqs;
    std::vector<std::string> vars;
    for (E x : a) {
      if (x->k == SYM && !eqs.empty())
        vars.push_back(x->s);
      else
        eqs.push_back(x);
    }
    if (eqs.empty()) return (g_err = "solve needs an equation", nullptr);
    if (eqs.size() == 1) {
      std::string var = vars.empty() ? defaultVar(sideDiff(eqs[0])) : vars[0];
      bool numeric = false;
      std::vector<E> roots = solveEq(eqs[0], var, &numeric);
      if (roots.empty() && failed()) return nullptr;
      sortRoots(roots);
      std::vector<E> items;
      for (E r : roots) items.push_back(eqOf(sym(var), r));
      return setOf(items);
    }
    if (vars.empty()) {
      for (E q : eqs) freeSyms(q, vars);
    }
    std::string res = solveSystem(eqs, vars);
    return sym(res);  // already formatted text, printed verbatim
  }
  if (name == "simplify") return n >= 1 ? simplify(a[0]) : nullptr;
  if (name == "expand") return n >= 1 ? expand(a[0]) : nullptr;
  if (name == "factor") return n >= 1 ? factorExpr(a[0]) : nullptr;
  if (name == "together") return n >= 1 ? together(a[0]) : nullptr;
  if (name == "approx") return n >= 1 ? approxExpr(a[0]) : nullptr;
  if (name == "subs") {
    if (n < 3) return (g_err = "subs(f, x, value)", nullptr);
    return subs(a[0], a[1], a[2]);
  }
  if (name == "det" && n == 1 && a[0]->k == MAT) return matDet(a[0]);
  if (name == "inv" && n == 1 && a[0]->k == MAT) return matInv(a[0]);
  if (name == "transpose" && n == 1 && a[0]->k == MAT) return matTranspose(a[0]);
  if (name == "trace" && n == 1 && a[0]->k == MAT) {
    std::vector<E> t;
    for (int i = 0; i < std::min(a[0]->rows, a[0]->cols); i++) t.push_back(at(a[0], i, i));
    return expand(mkAdd(t));
  }
  if (name == "rank" && n == 1 && a[0]->k == MAT) {
    int rk = 0;
    matRref(a[0], &rk);
    return num(rk);
  }
  if (name == "rref" && n == 1 && a[0]->k == MAT) return matRref(a[0], nullptr);
  if (name == "eig" && n == 1 && a[0]->k == MAT) return matEigenvalues(a[0]);
  if (name == "inverse" && n == 1 && a[0]->k == MAT) return matInv(a[0]);
  if ((name == "ncr" || name == "npr") && n == 2 && a[0]->k == NUM && a[1]->k == NUM && a[0]->d == 1 && a[1]->d == 1) {
    int64_t N = a[0]->n, K = a[1]->n;
    if (K < 0 || K > N) return num(0);
    I128 r = 1;
    if (name == "npr") {
      for (int64_t i = 0; i < K; i++) r *= (N - i);
    } else {
      if (K > N - K) K = N - K;
      for (int64_t i = 1; i <= K; i++) r = r * (N - K + i) / i;
    }
    return fits64(r) ? num((int64_t)r) : real((double)r);
  }
  if (name == "fact" && n == 1) {
    if (a[0]->k == NUM && a[0]->d == 1 && a[0]->n >= 0) {
      if (a[0]->n <= 20) {
        int64_t r = 1;
        for (int64_t i = 2; i <= a[0]->n; i++) r *= i;
        return num(r);
      }
      if (a[0]->n <= 170) return real(std::tgamma((double)a[0]->n + 1));
    }
    return nullptr;
  }
  if ((name == "gcd" || name == "lcm") && n == 2 && a[0]->k == NUM && a[1]->k == NUM && a[0]->d == 1 && a[1]->d == 1) {
    int64_t g = gcdE(a[0]->n, a[1]->n);
    if (name == "gcd") return num(g);
    return g ? num(std::llabs(a[0]->n / g * a[1]->n)) : num(0);
  }
  if (name == "mod" && n == 2 && a[0]->k == NUM && a[1]->k == NUM && a[0]->d == 1 && a[1]->d == 1 && a[1]->n != 0) {
    int64_t m = a[1]->n, r = a[0]->n % m;
    if (r != 0 && ((r < 0) != (m < 0))) r += m;
    return num(r);
  }
  if (name == "sum" && n == 4 && a[1]->k == SYM && a[2]->k == NUM && a[3]->k == NUM && a[3]->n - a[2]->n < 2000) {
    std::vector<E> t;
    for (int64_t k = a[2]->n; k <= a[3]->n; k++) t.push_back(subs(a[0], a[1], num(k)));
    return mkAdd(t);
  }
  if (name == "isprime" && n == 1 && a[0]->k == NUM && a[0]->d == 1) {
    int64_t m = a[0]->n;
    if (m < 2) return num(0);
    auto f = factorInt((uint64_t)m);
    return num(f.size() == 1 && f[0].e == 1 ? 1 : 0);
  }
  return nullptr;
}

}  // namespace cas
