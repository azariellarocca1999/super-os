// cas_calculus.cpp -- differentiation, symbolic integration, Taylor series and limits.
#include <algorithm>
#include <cmath>

#include "cas_int.h"
#include "cas_internal.h"

namespace cas {

static bool isEuler(E e) { return e->k == SYM && e->s == "e"; }

// ---- differentiation ------------------------------------------------------------------------------------------------------------------
E diff(E f, const std::string &x) {
  switch (f->k) {
    case NUM:
    case REAL:
      return num(0);
    case SYM:
      return num(f->s == x ? 1 : 0);
    case ADD: {
      std::vector<E> t;
      for (E c : f->a) t.push_back(diff(c, x));
      return mkAdd(t);
    }
    case MUL: {
      std::vector<E> t;
      for (size_t i = 0; i < f->a.size(); i++) {
        if (!contains(f->a[i], x)) continue;
        std::vector<E> p;
        for (size_t j = 0; j < f->a.size(); j++) p.push_back(j == i ? diff(f->a[j], x) : f->a[j]);
        t.push_back(mkMul(p));
      }
      return mkAdd(t);
    }
    case POW: {
      E b = f->a[0], e = f->a[1];
      bool cb = contains(b, x), ce = contains(e, x);
      if (!cb && !ce) return num(0);
      if (!ce) return mkMul({e, mkPow(b, sub(e, num(1))), diff(b, x)});
      if (!cb) return mkMul({f, isEuler(b) ? num(1) : func1("ln", b), diff(e, x)});
      return mkMul({f, add(mkMul({diff(e, x), func1("ln", b)}), div(mkMul({e, diff(b, x)}), b))});
    }
    case FUNC: {
      if (f->a.size() == 1) {
        E u = f->a[0];
        if (!contains(u, x)) return num(0);
        const std::string &n = f->s;
        E d = nullptr;
        E one = num(1), half = num(1, 2);
        if (n == "sin") d = func1("cos", u);
        else if (n == "cos") d = neg(func1("sin", u));
        else if (n == "tan") d = mkPow(func1("cos", u), num(-2));
        else if (n == "asin") d = mkPow(sub(one, mkPow(u, num(2))), neg(half));
        else if (n == "acos") d = neg(mkPow(sub(one, mkPow(u, num(2))), neg(half)));
        else if (n == "atan") d = mkPow(add(one, mkPow(u, num(2))), num(-1));
        else if (n == "sinh") d = func1("cosh", u);
        else if (n == "cosh") d = func1("sinh", u);
        else if (n == "tanh") d = mkPow(func1("cosh", u), num(-2));
        else if (n == "asinh") d = mkPow(add(mkPow(u, num(2)), one), neg(half));
        else if (n == "acosh") d = mkPow(sub(mkPow(u, num(2)), one), neg(half));
        else if (n == "atanh") d = mkPow(sub(one, mkPow(u, num(2))), num(-1));
        else if (n == "ln") d = mkPow(u, num(-1));
        else if (n == "log") d = mkPow(mkMul({u, func1("ln", num(10))}), num(-1));
        else if (n == "abs") d = func1("sign", u);
        else if (n == "sign" || n == "floor" || n == "ceil") return num(0);
        if (d) return mkMul({d, diff(u, x)});
        return mkMul({mkFunc(n + "'", {u}), diff(u, x)});
      }
      g_err = "cannot differentiate " + f->s;
      return num(0);
    }
    case MAT: {
      std::vector<E> t;
      for (E c : f->a) t.push_back(diff(c, x));
      return mkMat(f->rows, f->cols, t);
    }
  }
  return num(0);
}
E diffN(E f, const std::string &x, int n) {
  for (int i = 0; i < n && !failed(); i++) f = diff(f, x);
  return simplify(f);
}

E taylor(E f, const std::string &x, E x0, int n) {
  g_asc = true;
  std::vector<E> terms;
  E cur = f;
  int64_t fact = 1;
  E xs = sym(x);
  for (int k = 0; k <= n && !failed(); k++) {
    if (k > 0) {
      cur = diff(cur, x);
      fact *= k;
    }
    E v = simplify(subs(cur, xs, x0));
    if (failed()) return num(0);
    if (!isZero(v)) terms.push_back(mkMul({div(v, num(fact)), mkPow(sub(xs, x0), num(k))}));
  }
  return expand(mkAdd(terms));
}

// ---- integration --------------------------------------------------------------------------------------------------------------------------
namespace {

typedef std::vector<Rat> RP;
static void rt(RP &p) {
  while (p.size() > 1 && p.back().n == 0) p.pop_back();
}
static bool toRP(E e, const std::string &x, RP &out) {
  std::vector<E> c;
  if (!polyCoeffs(e, x, c)) return false;
  out.clear();
  for (E k : c) {
    if (k->k != NUM) return false;
    out.push_back(Rat{k->n, k->d});
  }
  return true;
}
static E fromRP(const RP &p, E xs) {
  std::vector<E> c;
  for (auto &r : p) c.push_back(num(r.n, r.d));
  return fromCoeffs(c, xs);
}
static bool rpDivmod(RP a, const RP &b, RP &q, RP &r) {
  rt(a);
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
  }
  r = a;
  rt(r);
  rt(q);
  return true;
}
static Rat rpEval(const RP &p, Rat x) {
  Rat r{0, 1};
  for (size_t i = p.size(); i-- > 0;) {
    Rat t;
    if (!ratMul(r, x, t) || !ratAdd(t, p[i], r)) return Rat{1, 0};
  }
  return r;
}
static std::vector<int64_t> divs(int64_t n) {
  std::vector<int64_t> d;
  if (n < 0) n = -n;
  for (int64_t i = 1; i * i <= n && i < 100000; i++)
    if (n % i == 0) {
      d.push_back(i);
      if (i != n / i) d.push_back(n / i);
    }
  return d;
}
static bool rationalRoot(const RP &p, Rat &root) {
  if (p.size() < 2) return false;
  if (p[0].n == 0) {
    root = Rat{0, 1};
    return true;
  }
  // scale to integers
  I128 l = 1;
  for (auto &c : p) l = l / gcd128(l, c.d) * c.d;
  if (l > ((I128)1 << 40)) return false;
  int64_t c0 = (int64_t)((I128)p[0].n * (l / p[0].d)), cn = (int64_t)((I128)p.back().n * (l / p.back().d));
  for (int64_t q : divs(cn))
    for (int64_t pp : divs(c0))
      for (int s = 0; s < 2; s++) {
        Rat g;
        if (!ratMake(s ? -pp : pp, q, g)) continue;
        Rat v = rpEval(p, g);
        if (v.d != 0 && v.n == 0) {
          root = g;
          return true;
        }
      }
  return false;
}

struct Ictx {
  std::string x;
  E xs;
  int depth = 0;
  int budget = 0;
};
E integ(E f, Ictx &c);

static bool linearForm(E u, const Ictx &c, E &a, E &b) {
  std::vector<E> co;
  if (!contains(u, c.x)) return false;
  if (!polyCoeffs(u, c.x, co) || co.size() != 2) return false;
  a = co[1];
  b = co[0];
  return true;
}
static bool quadForm(E u, const Ictx &c, E &qa, E &qb, E &qc) {
  std::vector<E> co;
  if (!polyCoeffs(u, c.x, co) || co.size() != 3) return false;
  qa = co[2];
  qb = co[1];
  qc = co[0];
  return true;
}
static E lnAbs(E u) { return func1("ln", func1("abs", u)); }

// sum of the terms of an expression that are free of x
static void splitConst(E f, const Ictx &c, E &k, E &g) {
  std::vector<E> kk, gg;
  std::vector<E> fs = f->k == MUL ? f->a : std::vector<E>{f};
  for (E t : fs) (contains(t, c.x) ? gg : kk).push_back(t);
  k = mkMul(kk);
  g = mkMul(gg);
}

// ---- rational functions: partial fractions ----------------------------------------------------------------------------------------------
static E intQuadPower(RP quad, int k, const Ictx &c, bool &ok);  // 1/Q^k for monic Q

static E rationalIntegral(E f, Ictx &c, bool &ok) {
  ok = false;
  E nE, dE;
  // numerator / denominator
  std::vector<E> nn, dd;
  std::vector<E> fs = f->k == MUL ? f->a : std::vector<E>{f};
  for (E t : fs) {
    if (t->k == POW && t->a[1]->k == NUM && t->a[1]->d == 1 && t->a[1]->n < 0)
      dd.push_back(mkPow(t->a[0], num(-t->a[1]->n)));
    else if (t->k == POW && contains(t, c.x) && !(t->a[1]->k == NUM && t->a[1]->d == 1)) return nullptr;
    else if (t->k == FUNC && contains(t, c.x)) return nullptr;
    else
      nn.push_back(t);
  }
  if (dd.empty()) return nullptr;
  nE = mkMul(nn);
  dE = mkMul(dd);
  RP N, D;
  if (!toRP(nE, c.x, N) || !toRP(dE, c.x, D) || D.size() < 2) return nullptr;
  RP Q, R;
  if (!rpDivmod(N, D, Q, R)) return nullptr;
  E result = num(0);
  if (!(Q.size() == 1 && Q[0].n == 0)) {
    E qi = integ(fromRP(Q, c.xs), c);
    if (!qi) return nullptr;
    result = qi;
  }
  if (R.size() == 1 && R[0].n == 0) {
    ok = true;
    return result;
  }
  // factor D = lead * prod (x - r)^m * prod Q^k
  Rat lead = D.back();
  RP mon = D;
  for (auto &co : mon) {
    Rat o;
    if (!ratDiv(co, lead, o)) return nullptr;
    co = o;
  }
  struct Fac {
    RP poly;
    int mult;
    bool linear;
    Rat root;
  };
  std::vector<Fac> facs;
  RP rem = mon;
  while (rem.size() > 1) {
    Rat r;
    if (!rationalRoot(rem, r)) break;
    RP lin = {Rat{-r.n, r.d}, Rat{1, 1}};
    RP q2, rr;
    if (!rpDivmod(rem, lin, q2, rr)) return nullptr;
    rem = q2;
    bool found = false;
    for (auto &f2 : facs)
      if (f2.linear && ratCmp(f2.root, r) == 0) {
        f2.mult++;
        found = true;
      }
    if (!found) facs.push_back({lin, 1, true, r});
  }
  if (rem.size() == 3) {
    facs.push_back({rem, 1, false, Rat{0, 1}});
  } else if (rem.size() == 5) {  // maybe the square of a quadratic
    RP d1 = {rem[1], Rat{2, 1}, Rat{0, 1}, Rat{0, 1}};
    (void)d1;
    // try rem = (x^2 + p x + q)^2:  p = rem[3]/2, q from rem[2] = p^2 + 2q
    Rat p2, q2, t, pp;
    ratDiv(rem[3], Rat{2, 1}, p2);
    ratMul(p2, p2, pp);
    ratSub(rem[2], pp, t);
    ratDiv(t, Rat{2, 1}, q2);
    RP cand = {q2, p2, Rat{1, 1}};
    RP sq(5);
    for (auto &z : sq) z = Rat{0, 1};
    for (int i = 0; i < 3; i++)
      for (int j = 0; j < 3; j++) {
        Rat m, s;
        ratMul(cand[i], cand[j], m);
        ratAdd(sq[i + j], m, s);
        sq[i + j] = s;
      }
    bool same = true;
    for (int i = 0; i < 5; i++) same = same && ratCmp(sq[i], rem[i]) == 0;
    if (!same) return nullptr;
    facs.push_back({cand, 2, false, Rat{0, 1}});
  } else if (rem.size() != 1)
    return nullptr;
  // partial fractions: unknown coefficient per (factor, power) basis function
  size_t degD = mon.size() - 1;
  struct Basis {
    int fi, j;
    bool second;  // x * (1/Q^j) companion for quadratics
    RP numer;     // D / (factor^j) (times x for the companion)
  };
  std::vector<Basis> bs;
  for (size_t fi = 0; fi < facs.size(); fi++)
    for (int j = 1; j <= facs[fi].mult; j++) {
      // cofactor = mon / factor^j
      RP cof = mon;
      for (int t = 0; t < j; t++) {
        RP q3, r3;
        if (!rpDivmod(cof, facs[fi].poly, q3, r3)) return nullptr;
        cof = q3;
      }
      bs.push_back({(int)fi, j, false, cof});
      if (!facs[fi].linear) {
        RP withx(cof.size() + 1, Rat{0, 1});
        for (size_t i = 0; i < cof.size(); i++) withx[i + 1] = cof[i];
        bs.push_back({(int)fi, j, true, withx});
      }
    }
  if (bs.size() != degD) return nullptr;
  // R/lead = sum u_i * numer_i  (as polynomials of degree < degD)
  RP Rl = R;
  for (auto &co : Rl) {
    Rat o;
    if (!ratDiv(co, lead, o)) return nullptr;
    co = o;
  }
  size_t n = degD;
  std::vector<std::vector<Rat>> M(n, std::vector<Rat>(n + 1, Rat{0, 1}));
  for (size_t col = 0; col < n; col++)
    for (size_t row = 0; row < bs[col].numer.size() && row < n; row++) M[row][col] = bs[col].numer[row];
  for (size_t row = 0; row < Rl.size() && row < n; row++) M[row][n] = Rl[row];
  for (size_t col = 0; col < n; col++) {
    size_t p = col;
    while (p < n && M[p][col].n == 0) p++;
    if (p == n) return nullptr;
    std::swap(M[p], M[col]);
    Rat inv;
    if (!ratDiv(Rat{1, 1}, M[col][col], inv)) return nullptr;
    for (size_t j = col; j <= n; j++)
      if (!ratMul(M[col][j], inv, M[col][j])) return nullptr;
    for (size_t r = 0; r < n; r++)
      if (r != col && M[r][col].n != 0) {
        Rat f = M[r][col];
        for (size_t j = col; j <= n; j++) {
          Rat t, o;
          if (!ratMul(f, M[col][j], t) || !ratSub(M[r][j], t, o)) return nullptr;
          M[r][j] = o;
        }
      }
  }
  std::vector<E> parts;
  for (size_t i = 0; i < bs.size(); i++) {
    Rat u = M[i][n];
    if (u.n == 0) continue;
    const Fac &F = facs[bs[i].fi];
    int j = bs[i].j;
    E coef = num(u.n, u.d);
    if (F.linear) {
      E lx = fromRP(F.poly, c.xs);  // x - r
      if (j == 1)
        parts.push_back(mkMul({coef, lnAbs(lx)}));
      else
        parts.push_back(mkMul({coef, num(1, 1 - j), mkPow(lx, num(1 - j))}));
    } else {
      // (A x) / Q^j  or  C / Q^j  with Q = x^2 + p x + q
      Rat p = F.poly[1];
      E Qe = fromRP(F.poly, c.xs);
      bool ok2 = true;
      if (bs[i].second) {
        // A x/Q^j = (A/2) (2x+p)/Q^j - (A p/2)/Q^j
        E two_x_p = add(mkMul({num(2), c.xs}), num(p.n, p.d));
        E a2 = mkMul({coef, num(1, 2)});
        if (j == 1)
          parts.push_back(mkMul({a2, func1("ln", Qe)}));
        else
          parts.push_back(mkMul({a2, num(1, 1 - j), mkPow(Qe, num(1 - j))}));
        (void)two_x_p;
        Rat ap;
        ratMul(u, p, ap);
        ratDiv(ap, Rat{2, 1}, ap);
        if (ap.n != 0) {
          E base = intQuadPower(F.poly, j, c, ok2);
          if (!ok2) return nullptr;
          parts.push_back(mkMul({num(-ap.n, ap.d), base}));
        }
      } else {
        E base = intQuadPower(F.poly, j, c, ok2);
        if (!ok2) return nullptr;
        parts.push_back(mkMul({coef, base}));
      }
    }
  }
  ok = true;
  return add(result, mkAdd(parts));
}

// integral of 1/Q^k, Q = x^2 + p x + q (monic)
static E intQuadPower(RP quad, int k, const Ictx &c, bool &ok) {
  ok = true;
  Rat p = quad[1], q = quad[0];
  Rat disc;  // 4q - p^2
  Rat p2, fq;
  ratMul(p, p, p2);
  ratMul(q, Rat{4, 1}, fq);
  ratSub(fq, p2, disc);
  E Q = fromRP(quad, c.xs);
  E lin = add(mkMul({num(2), c.xs}), num(p.n, p.d));  // 2x + p
  if (k == 1) {
    if (disc.n > 0) {
      E s = mkPow(num(disc.n, disc.d), num(1, 2));
      return mkMul({num(2), mkPow(s, num(-1)), func1("atan", mkMul({lin, mkPow(s, num(-1))}))});
    }
    if (disc.n == 0) return mkMul({num(-2), mkPow(lin, num(-1))});
    // two real irrational roots: 1/(2s) ln|(x + p/2 - s)/(x + p/2 + s)| with s = sqrt(-disc)/2
    E s = mkMul({num(1, 2), mkPow(num(-disc.n, disc.d), num(1, 2))});
    E xm = add(c.xs, num(p.n, 2 * p.d));
    return mkMul({mkPow(mkMul({num(2), s}), num(-1)), func1("ln", func1("abs", div(sub(xm, s), add(xm, s))))});
  }
  if (disc.n <= 0 || k > 5) {
    ok = false;
    return nullptr;
  }
  // int dx/Q^k = (2x+p) / ((k-1) D Q^(k-1)) + (2 (2k-3) / ((k-1) D)) int dx/Q^(k-1)
  E D = num(disc.n, disc.d);
  E first = div(lin, mkMul({num(k - 1), D, mkPow(Q, num(k - 1))}));
  bool ok2;
  E rest = intQuadPower(quad, k - 1, c, ok2);
  if (!ok2) {
    ok = false;
    return nullptr;
  }
  return add(first, mkMul({div(num(2 * (2 * k - 3)), mkMul({num(k - 1), D})), rest}));
}

// ---- trigonometric products -------------------------------------------------------------------------------------------------------------
static bool trigFactor(E t, const char *fn, E &arg, int &pw) {
  if (isFunc(t, fn)) {
    arg = t->a[0];
    pw = 1;
    return true;
  }
  if (t->k == POW && isFunc(t->a[0], fn) && t->a[1]->k == NUM && t->a[1]->d == 1 && t->a[1]->n >= 1) {
    arg = t->a[0]->a[0];
    pw = (int)t->a[1]->n;
    return true;
  }
  return false;
}

static E trigPowers(E g, Ictx &c, bool &ok) {
  ok = false;
  std::vector<E> fs = g->k == MUL ? g->a : std::vector<E>{g};
  E sa = nullptr, ca = nullptr;
  int m = 0, n = 0;
  E rest = num(1);
  for (E t : fs) {
    E a;
    int p;
    if (trigFactor(t, "sin", a, p)) {
      if (sa && !equal(sa, a)) return nullptr;
      sa = a;
      m += p;
    } else if (trigFactor(t, "cos", a, p)) {
      if (ca && !equal(ca, a)) return nullptr;
      ca = a;
      n += p;
    } else
      return nullptr;
  }
  E u = sa ? sa : ca;
  if (sa && ca && !equal(sa, ca)) return nullptr;
  E la, lb;
  if (!linearForm(u, c, la, lb)) return nullptr;
  E S = func1("sin", u), C = func1("cos", u);
  E y = sym("y_tmp");
  if (m % 2 == 1) {  // sin^m = sin * (1 - cos^2)^((m-1)/2); integrate in w = cos(u)
    E poly = expand(mkMul({mkPow(sub(num(1), mkPow(y, num(2))), num((m - 1) / 2)), mkPow(y, num(n))}));
    std::vector<E> co;
    polyCoeffs(poly, "y_tmp", co);
    std::vector<E> t;
    for (size_t k = 0; k < co.size(); k++) t.push_back(mkMul({co[k], mkPow(C, num((int64_t)k + 1)), num(-1, (int64_t)k + 1)}));
    ok = true;
    return div(mkAdd(t), la);
  }
  if (n % 2 == 1) {
    E poly = expand(mkMul({mkPow(sub(num(1), mkPow(y, num(2))), num((n - 1) / 2)), mkPow(y, num(m))}));
    std::vector<E> co;
    polyCoeffs(poly, "y_tmp", co);
    std::vector<E> t;
    for (size_t k = 0; k < co.size(); k++) t.push_back(mkMul({co[k], mkPow(S, num((int64_t)k + 1)), num(1, (int64_t)k + 1)}));
    ok = true;
    return div(mkAdd(t), la);
  }
  // both even (or one absent): power reduction
  if (m == 0 && n == 0) return nullptr;
  E two_u = mkMul({num(2), u});
  E red;
  if (m >= 2 && n == 0) {
    red = mkMul({mkPow(mkMul({num(1, 2), sub(num(1), func1("cos", two_u))}), num(m / 2))});
  } else if (n >= 2 && m == 0) {
    red = mkPow(mkMul({num(1, 2), add(num(1), func1("cos", two_u))}), num(n / 2));
  } else {
    // sin^m cos^n = (sin cos)^min * ...; use sin*cos = sin(2u)/2 and the remaining even power
    int k = std::min(m, n);
    red = mkMul({mkPow(mkMul({num(1, 2), func1("sin", two_u)}), num(k))});
    if (m - k >= 2) red = mkMul({red, mkPow(mkMul({num(1, 2), sub(num(1), func1("cos", two_u))}), num((m - k) / 2))});
    if (n - k >= 2) red = mkMul({red, mkPow(mkMul({num(1, 2), add(num(1), func1("cos", two_u))}), num((n - k) / 2))});
  }
  red = expand(red);
  E r = integ(red, c);
  if (!r) return nullptr;
  ok = true;
  return r;
}

// product of sin/cos of different linear arguments -> sum
static E trigProductToSum(E g, Ictx &c, bool &ok) {
  ok = false;
  if (g->k != MUL || g->a.size() != 2) return nullptr;
  E A = g->a[0], B = g->a[1];
  bool sA = isFunc(A, "sin"), cA = isFunc(A, "cos"), sB = isFunc(B, "sin"), cB = isFunc(B, "cos");
  if (!((sA || cA) && (sB || cB))) return nullptr;
  E u = A->a[0], v = B->a[0];
  if (equal(u, v)) return nullptr;
  E sum = add(u, v), dif = sub(u, v);
  E h = num(1, 2);
  E expr;
  if (sA && sB) expr = mkMul({h, sub(func1("cos", dif), func1("cos", sum))});
  else if (cA && cB) expr = mkMul({h, add(func1("cos", dif), func1("cos", sum))});
  else if (sA && cB) expr = mkMul({h, add(func1("sin", sum), func1("sin", dif))});
  else expr = mkMul({h, add(func1("sin", sum), func1("sin", neg(dif)))});
  E r = integ(expr, c);
  if (!r) return nullptr;
  ok = true;
  return r;
}

// exp(p x + q) * sin / cos (r x + s)
static E expTrig(E g, Ictx &c, bool &ok) {
  ok = false;
  if (g->k != MUL || g->a.size() != 2) return nullptr;
  E ex = nullptr, tg = nullptr;
  for (E t : g->a) {
    if (t->k == POW && isEuler(t->a[0])) ex = t;
    else if (isFunc(t, "sin") || isFunc(t, "cos")) tg = t;
  }
  if (!ex || !tg) return nullptr;
  E p, q, r, s;
  if (!linearForm(ex->a[1], c, p, q) || !linearForm(tg->a[0], c, r, s)) return nullptr;
  E den = add(mkMul({p, p}), mkMul({r, r}));
  E Sx = func1("sin", tg->a[0]), Cx = func1("cos", tg->a[0]);
  E body = isFunc(tg, "sin") ? sub(mkMul({p, Sx}), mkMul({r, Cx})) : add(mkMul({p, Cx}), mkMul({r, Sx}));
  ok = true;
  return mkMul({ex, body, mkPow(den, num(-1))});
}

// ---- sqrt of a quadratic -----------------------------------------------------------------------------------------------------------------------
static E sqrtQuad(E Q, E power, Ictx &c, bool &ok) {
  ok = false;
  E qa, qb, qc;
  if (!quadForm(Q, c, qa, qb, qc)) return nullptr;
  if (qa->k != NUM) return nullptr;
  bool inv = power->k == NUM && power->n == -1 && power->d == 2;
  bool dir = power->k == NUM && power->n == 1 && power->d == 2;
  if (!inv && !dir) return nullptr;
  // Q = a t^2 + k, t = x + b/(2a)
  E tt = add(c.xs, div(qb, mkMul({num(2), qa})));
  E kk = expand(sub(qc, div(mkMul({qb, qb}), mkMul({num(4), qa}))));
  E sq = mkPow(Q, num(1, 2));
  double av = toDouble(qa);
  if (av > 0) {
    E sa = mkPow(qa, num(1, 2));
    E lnt = func1("ln", func1("abs", add(mkMul({sa, tt}), sq)));
    ok = true;
    if (inv) return div(lnt, sa);
    return add(mkMul({num(1, 2), tt, sq}), mkMul({kk, num(1, 2), mkPow(sa, num(-1)), lnt}));
  }
  if (av < 0 && kk->k == NUM && toDouble(kk) > 0) {
    E sa = mkPow(neg(qa), num(1, 2));
    E sk = mkPow(kk, num(1, 2));
    E as = func1("asin", mkMul({sa, tt, mkPow(sk, num(-1))}));
    ok = true;
    if (inv) return div(as, sa);
    return add(mkMul({num(1, 2), tt, sq}), mkMul({kk, num(1, 2), mkPow(sa, num(-1)), as}));
  }
  return nullptr;
}

// ---- u-substitution ---------------------------------------------------------------------------------------------------------------------------------
static void collectSubexprs(E e, const Ictx &c, std::vector<E> &out) {
  for (E ch : e->a) collectSubexprs(ch, c, out);
  if (e->k == SYM || isNumeric(e) || !contains(e, c.x)) return;
  for (E o : out)
    if (equal(o, e)) return;
  out.push_back(e);
}
// replace b^(c*g) by T^c for every numeric c (the substitution u = b^g must also catch u^-1 = b^(-g) ...)
static E subsPowers(E e, E b, E g, E T) {
  if (e->k == POW && equal(e->a[0], b)) {
    E ratio = simplify(div(e->a[1], g));
    if (ratio->k == NUM) return mkPow(T, ratio);
  }
  if (e->a.empty()) return e;
  switch (e->k) {
    case ADD: {
      std::vector<E> t;
      for (E ch : e->a) t.push_back(subsPowers(ch, b, g, T));
      return mkAdd(t);
    }
    case MUL: {
      std::vector<E> t;
      for (E ch : e->a) t.push_back(subsPowers(ch, b, g, T));
      return mkMul(t);
    }
    case POW:
      return mkPow(subsPowers(e->a[0], b, g, T), subsPowers(e->a[1], b, g, T));
    case FUNC: {
      std::vector<E> t;
      for (E ch : e->a) t.push_back(subsPowers(ch, b, g, T));
      return mkFunc(e->s, t);
    }
    default:
      return e;
  }
}
static E usub(E f, Ictx &c) {
  std::vector<E> cand;
  collectSubexprs(f, c, cand);
  if (cand.size() > 40) return nullptr;
  E T = sym("u_t" + std::to_string(c.depth));
  for (E u : cand) {
    if (u->k == MUL) continue;
    E du = diff(u, c.x);
    if (failed()) {
      g_err.clear();
      continue;
    }
    if (isZero(du)) continue;
    E q = mkMul({f, mkPow(du, num(-1))});
    q = simplify(q);
    E q2 = u->k == POW ? subsPowers(q, u->a[0], u->a[1], T) : subs(q, u, T);
    if (contains(q2, c.x)) continue;
    Ictx c2 = c;
    c2.x = T->s;
    c2.xs = T;
    c2.depth = c.depth + 1;
    E G = integ(q2, c2);
    if (G) return subs(G, T, u);
  }
  return nullptr;
}

// ---- integration by parts ---------------------------------------------------------------------------------------------------------------------------
static bool isTranscendental(E t, const Ictx &c) {
  if (!contains(t, c.x)) return false;
  if (t->k == POW && isEuler(t->a[0])) return true;
  if (t->k == POW && t->a[0]->k == FUNC && t->a[1]->k == NUM && t->a[1]->d == 1) return isTranscendental(t->a[0], c);
  return t->k == FUNC;
}
static E byParts(E g, Ictx &c) {
  std::vector<E> fs = g->k == MUL ? g->a : std::vector<E>{g};
  std::vector<E> poly, tr;
  for (E t : fs) {
    if (!contains(t, c.x)) continue;
    std::vector<E> co;
    bool isPoly = polyCoeffs(t, c.x, co) || (t->k == POW && t->a[0]->k == SYM && t->a[1]->k == NUM);
    if (isPoly)
      poly.push_back(t);
    else
      tr.push_back(t);
  }
  if (tr.size() != 1) return nullptr;
  E T = tr[0];
  E P = mkMul(poly);
  bool logType = false;
  E base = T->k == POW && T->a[0]->k == FUNC ? T->a[0] : T;
  if (base->k == FUNC && (base->s == "ln" || base->s == "log" || base->s == "atan" || base->s == "asin" || base->s == "acos" || base->s == "asinh" || base->s == "acosh" || base->s == "atanh")) logType = true;
  if (!logType) {
    // u = P (differentiate), dv = T
    if (poly.empty()) return nullptr;
    E V = integ(T, c);
    if (!V) return nullptr;
    E rest = mkMul({diff(P, c.x), V});
    E I2 = integ(simplify(rest), c);
    if (!I2) return nullptr;
    return sub(mkMul({P, V}), I2);
  }
  // u = T, dv = P (P = 1 when there is no polynomial factor)
  E V = integ(P, c);
  if (!V) return nullptr;
  E rest = simplify(mkMul({diff(T, c.x), V}));
  E I2 = integ(rest, c);
  if (!I2) return nullptr;
  return sub(mkMul({T, V}), I2);
}

// ---- main driver -----------------------------------------------------------------------------------------------------------------------------------------
static bool isPolyIn(E e, const Ictx &c) {
  std::vector<E> co;
  return polyCoeffs(e, c.x, co);
}

E integSingle(E f, Ictx &c) {
  E a, b;
  if (f->k == SYM) return div(mkPow(f, num(2)), num(2));
  if (f->k == POW) {
    E base = f->a[0], ex = f->a[1];
    if (!contains(ex, c.x)) {
      if (linearForm(base, c, a, b)) {
        if (ex->k == NUM && ex->n == -1 && ex->d == 1) return div(lnAbs(base), a);
        return div(mkPow(base, add(ex, num(1))), mkMul({a, add(ex, num(1))}));
      }
      if (base->k == FUNC && base->a.size() == 1 && ex->k == NUM && ex->d == 1 && ex->n >= 2) {
        E u = base->a[0];
        if (linearForm(u, c, a, b)) {
          int64_t n = ex->n;
          const std::string &nm = base->s;
          if (nm == "sin" || nm == "cos") {
            bool ok;
            E r = trigPowers(f, c, ok);
            if (ok) return r;
          }
          if (nm == "tan") {  // int tan^n = tan^(n-1)/((n-1) a) - int tan^(n-2)
            if (n == 2) return div(sub(base, u), a);
            Ictx c2 = c;
            c2.depth++;
            E rest = integ(mkPow(base, num(n - 2)), c2);
            if (!rest) return nullptr;
            return sub(div(mkPow(base, num(n - 1)), mkMul({a, num(n - 1)})), rest);
          }
        }
      }
      E Qa, Qb, Qc;
      if (quadForm(base, c, Qa, Qb, Qc) && ex->k == NUM && ex->d == 2 && (ex->n == 1 || ex->n == -1)) {
        bool ok;
        E r = sqrtQuad(base, ex, c, ok);
        if (ok) return r;
      }
      return nullptr;
    }
    if (!contains(base, c.x) && linearForm(ex, c, a, b)) {
      if (isEuler(base)) return div(f, a);
      return div(f, mkMul({a, func1("ln", base)}));
    }
    return nullptr;
  }
  if (f->k == FUNC && f->a.size() == 1) {
    E u = f->a[0];
    const std::string &n = f->s;
    if (!linearForm(u, c, a, b)) return nullptr;
    E r = nullptr;
    if (n == "sin") r = neg(func1("cos", u));
    else if (n == "cos") r = func1("sin", u);
    else if (n == "tan") r = neg(lnAbs(func1("cos", u)));
    else if (n == "sinh") r = func1("cosh", u);
    else if (n == "cosh") r = func1("sinh", u);
    else if (n == "tanh") r = func1("ln", func1("cosh", u));
    else if (n == "ln") r = sub(mkMul({u, f}), u);
    else if (n == "log") r = div(sub(mkMul({u, func1("ln", u)}), u), func1("ln", num(10)));
    else if (n == "asin") r = add(mkMul({u, f}), mkPow(sub(num(1), mkPow(u, num(2))), num(1, 2)));
    else if (n == "acos") r = sub(mkMul({u, f}), mkPow(sub(num(1), mkPow(u, num(2))), num(1, 2)));
    else if (n == "atan") r = sub(mkMul({u, f}), mkMul({num(1, 2), func1("ln", add(num(1), mkPow(u, num(2))))}));
    else if (n == "asinh") r = sub(mkMul({u, f}), mkPow(add(mkPow(u, num(2)), num(1)), num(1, 2)));
    else if (n == "acosh") r = sub(mkMul({u, f}), mkPow(sub(mkPow(u, num(2)), num(1)), num(1, 2)));
    else if (n == "atanh") r = add(mkMul({u, f}), mkMul({num(1, 2), func1("ln", sub(num(1), mkPow(u, num(2))))}));
    else if (n == "abs") r = mkMul({num(1, 2), u, f});
    if (r) return div(r, a);
  }
  return nullptr;
}

E integ(E f, Ictx &c) {
  if (c.depth > 14 || ++c.budget > 4000) return nullptr;
  if (!contains(f, c.x)) return mkMul({f, c.xs});
  Ictx d = c;
  d.depth = c.depth + 1;
  d.budget = c.budget;
  switch (f->k) {
    case ADD: {
      std::vector<E> t;
      for (E term : f->a) {
        E r = integ(term, d);
        if (!r) return nullptr;
        t.push_back(r);
      }
      c.budget = d.budget;
      return mkAdd(t);
    }
    case MUL: {
      E k, g;
      splitConst(f, c, k, g);
      if (!isOne(k)) {
        E r = integ(g, d);
        c.budget = d.budget;
        return r ? mkMul({k, r}) : nullptr;
      }
      // x-dependent factors only
      bool ok;
      E r = rationalIntegral(g, d, ok);
      if (ok) return r;
      r = trigPowers(g, d, ok);
      if (ok) return r;
      r = trigProductToSum(g, d, ok);
      if (ok) return r;
      r = expTrig(g, d, ok);
      if (ok) return r;
      // expand products of sums
      E ex = expand(g);
      if (!equal(ex, g) && ex->k == ADD) {
        r = integ(ex, d);
        if (r) return r;
      }
      r = usub(g, d);
      if (r) return r;
      r = byParts(g, d);
      if (r) return r;
      return nullptr;
    }
    default:
      break;
  }
  // single factor
  E r = integSingle(f, d);
  if (r) return r;
  bool ok = false;
  if (f->k == POW) {
    r = rationalIntegral(f, d, ok);
    if (ok) return r;
    r = trigPowers(f, d, ok);
    if (ok) return r;
  }
  r = usub(f, d);
  if (r) return r;
  r = byParts(f, d);
  return r;
}

}  // namespace

E integrate(E f, const std::string &x) {
  Ictx c;
  c.x = x;
  c.xs = sym(x);
  if (f->k == MAT) {
    std::vector<E> t;
    for (E e : f->a) {
      E r = integrate(e, x);
      if (!r) return nullptr;
      t.push_back(r);
    }
    return mkMat(f->rows, f->cols, t);
  }
  E e0 = expand(f);
  E r = integ(f, c);
  if (!r && !equal(e0, f)) {
    Ictx c2;
    c2.x = x;
    c2.xs = sym(x);
    r = integ(e0, c2);
  }
  if (!r) return nullptr;
  g_err.clear();
  return simplify(r);
}

// ---- limits ------------------------------------------------------------------------------------------------------------------------------------------------------
static E recognize(double v) {
  if (!std::isfinite(v)) return real(v);
  double r = std::round(v);
  if (std::fabs(v - r) < 1e-8 * std::max(1.0, std::fabs(v))) return num((int64_t)r);
  for (int64_t d = 2; d <= 1000; d++) {
    double n = v * d;
    double rn = std::round(n);
    if (std::fabs(n - rn) < 1e-8 * d * std::max(1.0, std::fabs(v))) return num((int64_t)rn, d);
  }
  double q = v / M_PI;
  for (int64_t d = 1; d <= 24; d++) {
    double n = q * d;
    double rn = std::round(n);
    if (std::fabs(n - rn) < 1e-8 * d && rn != 0) return mkMul({num((int64_t)rn, d), sym("pi")});
  }
  if (std::fabs(v - M_E) < 2e-6) return sym("e");
  return real(v);
}

static bool numericAt(E f, const std::string &x, double at, double &out) {
  Env env;
  env.set(x, at);
  return evalD(f, env, out) && std::isfinite(out);
}

E limit(E f, const std::string &x, E a, bool *approx) {
  E xs = sym(x);
  bool inf = a->k == SYM && a->s == "oo";
  bool ninf = a->k == MUL && a->a.size() == 2 && isNumeric(a->a[0]) && toDouble(a->a[0]) == -1 && a->a[1]->k == SYM && a->a[1]->s == "oo";
  if (!inf && !ninf) {
    // direct substitution
    std::string saved = g_err;
    E v = subs(f, xs, a);
    if (!failed()) return simplify(v);
    g_err.clear();
    // L'Hopital on num/den
    E fe = together(f);
    std::vector<E> nn, dd;
    std::vector<E> fs = fe->k == MUL ? fe->a : std::vector<E>{fe};
    for (E t : fs) {
      if (t->k == POW && t->a[1]->k == NUM && t->a[1]->n < 0)
        dd.push_back(mkPow(t->a[0], num(-t->a[1]->n, t->a[1]->d)));
      else
        nn.push_back(t);
    }
    E N = mkMul(nn), D = mkMul(dd);
    for (int it = 0; it < 8; it++) {
      g_err.clear();
      E nv = subs(N, xs, a), dv = subs(D, xs, a);
      if (failed()) {
        g_err.clear();
        break;
      }
      if (isZero(dv) && !isZero(nv)) break;  // pole
      if (!isZero(dv)) return simplify(div(nv, dv));
      N = diff(N, x);
      D = diff(D, x);
    }
    g_err.clear();
  }
  // numeric estimate (also handles +-oo and poles)
  double av = 0;
  if (!inf && !ninf) {
    Env e0;
    if (!evalD(a, e0, av)) return num(0);
  }
  const int NS = 4;
  double steps[NS] = {1e-2, 1e-4, 1e-6, 1e-8};
  double lv[NS], rv[NS];
  bool okL = true, okR = true;
  for (int i = 0; i < NS; i++) {
    double L = 0, R = 0;
    if (inf || ninf) {
      double big = (inf ? 1.0 : -1.0) * std::pow(10.0, 3.0 + 2.0 * i);
      okR = okR && numericAt(f, x, big, R);
      okL = false;
      rv[i] = R;
      lv[i] = R;
    } else {
      okL = okL && numericAt(f, x, av - steps[i], L);
      okR = okR && numericAt(f, x, av + steps[i], R);
      lv[i] = L;
      rv[i] = R;
    }
  }
  if (approx) *approx = true;
  if (!okR && !okL) {
    g_err = "limit does not exist";
    return num(0);
  }
  auto converged = [&](double *v) {
    double d = std::fabs(v[NS - 1] - v[NS - 2]);
    if (d <= 1e-5 * std::max(1.0, std::fabs(v[NS - 1]))) return true;
    // slowly decaying to zero
    return std::fabs(v[NS - 1]) < 1e-3 && std::fabs(v[NS - 1]) < std::fabs(v[NS - 2]) && std::fabs(v[NS - 2]) < std::fabs(v[NS - 3]);
  };
  bool cr = okR && converged(rv), cl = okL && converged(lv);
  double vr = rv[NS - 1], vl = lv[NS - 1];
  if (inf || ninf) {
    if (cr) return recognize(std::fabs(vr) < 1e-4 ? 0.0 : vr);
    if (okR && std::fabs(vr) > 1e8) return vr > 0 ? sym("oo") : neg(sym("oo"));
    g_err = "limit does not exist";
    return num(0);
  }
  if (!okL && okR && cr) return recognize(std::fabs(vr) < 1e-4 ? 0.0 : vr);  // one-sided domain
  if (!okR && okL && cl) return recognize(std::fabs(vl) < 1e-4 ? 0.0 : vl);
  if (cr && cl && std::fabs(vr - vl) < 1e-5 * std::max(1.0, std::fabs(vr))) return recognize(std::fabs(vr) < 1e-4 && std::fabs(vl) < 1e-4 ? 0.0 : vr);
  if (okR && okL && std::fabs(vr) > 1e6 && std::fabs(vl) > 1e6 && (vr > 0) == (vl > 0)) return vr > 0 ? sym("oo") : neg(sym("oo"));
  g_err = "limit does not exist (or the two sides differ)";
  return num(0);
}

}  // namespace cas
