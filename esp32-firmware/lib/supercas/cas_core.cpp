// cas_core.cpp -- expression nodes, canonical constructors, comparison, printing.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <deque>

#include "cas.h"
#include "cas_int.h"

namespace cas {

std::string g_err;
bool g_asc = false;
static std::deque<Node> g_pool;
bool failed() { return !g_err.empty(); }
void reset() {
  g_pool.clear();
  g_err.clear();
  g_asc = false;
}
static Node *alloc(Kind k) {
  g_pool.emplace_back();
  Node *n = &g_pool.back();
  n->k = k;
  return n;
}

// ---- numbers ------------------------------------------------------------------------------------------------------
E num(int64_t n, int64_t d) {
  if (d == 0) {
    g_err = "division by zero";
    d = 1;
    n = 0;
  }
  if (d < 0) {
    n = -n;
    d = -d;
  }
  int64_t g = igcd(n, d);
  if (g > 1) {
    n /= g;
    d /= g;
  }
  Node *p = alloc(NUM);
  p->n = n;
  p->d = d;
  return p;
}
static E numR(Rat r) { return num(r.n, r.d); }
E real(double v) {
  Node *p = alloc(REAL);
  p->r = v;
  return p;
}
E sym(const std::string &name) {
  Node *p = alloc(SYM);
  p->s = name;
  return p;
}
bool isNum(E e) { return e->k == NUM; }
bool isInt(E e) { return e->k == NUM && e->d == 1; }
bool isZero(E e) { return (e->k == NUM && e->n == 0) || (e->k == REAL && e->r == 0.0); }
bool isOne(E e) { return (e->k == NUM && e->n == 1 && e->d == 1) || (e->k == REAL && e->r == 1.0); }
bool isNumeric(E e) { return e->k == NUM || e->k == REAL; }
double toDouble(E e) { return e->k == NUM ? (double)e->n / (double)e->d : e->r; }
static Rat ratOf(E e) { return Rat{e->n, e->d}; }
static bool isSym(E e, const char *name) { return e->k == SYM && e->s == name; }
bool isFunc(E e, const char *name) { return e->k == FUNC && e->s == name; }

// numeric accumulator: exact until a REAL or an overflow appears
struct Nm {
  bool real = false;
  Rat q{1, 1};
  double x = 1;
  double val() const { return real ? x : (double)q.n / (double)q.d; }
};
static Nm nmOf(E e) {
  Nm m;
  if (e->k == REAL) {
    m.real = true;
    m.x = e->r;
  } else
    m.q = ratOf(e);
  return m;
}
static Nm nmMul(Nm a, Nm b) {
  Nm r;
  if (!a.real && !b.real) {
    Rat o;
    if (ratMul(a.q, b.q, o)) {
      r.q = o;
      return r;
    }
  }
  r.real = true;
  r.x = a.val() * b.val();
  return r;
}
static Nm nmAdd(Nm a, Nm b) {
  Nm r;
  if (!a.real && !b.real) {
    Rat o;
    if (ratAdd(a.q, b.q, o)) {
      r.q = o;
      return r;
    }
  }
  r.real = true;
  r.x = a.val() + b.val();
  return r;
}
static bool nmZero(const Nm &m) { return m.real ? m.x == 0.0 : m.q.n == 0; }
static bool nmOne(const Nm &m) { return m.real ? m.x == 1.0 : (m.q.n == 1 && m.q.d == 1); }
static E nmE(const Nm &m) { return m.real ? real(m.x) : numR(m.q); }

// ---- comparison ------------------------------------------------------------------------------------------------------
int cmp(E a, E b) {
  if (a == b) return 0;
  if (a->k != b->k) return a->k < b->k ? -1 : 1;
  switch (a->k) {
    case NUM: {
      I128 l = (I128)a->n * b->d, r = (I128)b->n * a->d;
      return l < r ? -1 : l > r ? 1 : 0;
    }
    case REAL:
      return a->r < b->r ? -1 : a->r > b->r ? 1 : 0;
    case SYM: {
      int c = a->s.compare(b->s);
      return c < 0 ? -1 : c > 0 ? 1 : 0;
    }
    case FUNC: {
      int c = a->s.compare(b->s);
      if (c) return c < 0 ? -1 : 1;
    }  // fallthrough
    default: {
      if (a->a.size() != b->a.size()) return a->a.size() < b->a.size() ? -1 : 1;
      if (a->k == MAT && (a->rows != b->rows)) return a->rows < b->rows ? -1 : 1;
      for (size_t i = 0; i < a->a.size(); i++) {
        int c = cmp(a->a[i], b->a[i]);
        if (c) return c;
      }
      return 0;
    }
  }
}
bool equal(E a, E b) { return cmp(a, b) == 0; }

// ---- raw builders (operands already canonical) ------------------------------------------------------------------------------
static E rawMul(std::vector<E> f) {
  if (f.size() == 1) return f[0];
  Node *p = alloc(MUL);
  p->a = std::move(f);
  return p;
}
static E rawAdd(std::vector<E> f) {
  if (f.size() == 1) return f[0];
  Node *p = alloc(ADD);
  p->a = std::move(f);
  return p;
}
static E rawPow(E b, E e) {
  Node *p = alloc(POW);
  p->a = {b, e};
  return p;
}
E mkMat(int rows, int cols, std::vector<E> el) {
  Node *p = alloc(MAT);
  p->rows = rows;
  p->cols = cols;
  p->a = std::move(el);
  return p;
}

static void splitCoef(E t, Nm &c, E &rest) {
  if (t->k == MUL && isNumeric(t->a[0])) {
    c = nmOf(t->a[0]);
    std::vector<E> r(t->a.begin() + 1, t->a.end());
    rest = rawMul(r);
  } else {
    c = Nm();
    rest = t;
  }
}

// ---- sums ----------------------------------------------------------------------------------------------------------------------
E mkAdd(std::vector<E> terms) {
  Nm constant;
  constant.q = Rat{0, 1};
  struct Item {
    E rest;
    Nm c;
  };
  std::vector<Item> items;
  std::vector<E> stack(terms.rbegin(), terms.rend());
  while (!stack.empty()) {
    E t = stack.back();
    stack.pop_back();
    if (t->k == ADD) {
      for (size_t i = t->a.size(); i-- > 0;) stack.push_back(t->a[i]);
      continue;
    }
    if (t->k == MUL && t->a.size() == 2 && isNumeric(t->a[0]) && t->a[1]->k == ADD) {  // c*(a+b) -> c*a + c*b
      E cf = t->a[0];
      for (size_t i = t->a[1]->a.size(); i-- > 0;) stack.push_back(mkMul({cf, t->a[1]->a[i]}));
      continue;
    }
    if (isNumeric(t)) {
      constant = nmAdd(constant, nmOf(t));
      continue;
    }
    Nm c;
    E rest;
    splitCoef(t, c, rest);
    bool merged = false;
    for (auto &it : items)
      if (equal(it.rest, rest)) {
        it.c = nmAdd(it.c, c);
        merged = true;
        break;
      }
    if (!merged) items.push_back({rest, c});
  }
  // sin^2 + cos^2 = 1 (equal coefficients)
  for (size_t i = 0; i < items.size(); i++) {
    E r = items[i].rest;
    if (r->k != POW || !isFunc(r->a[0], "sin") || !(r->a[1]->k == NUM && r->a[1]->n == 2 && r->a[1]->d == 1)) continue;
    for (size_t j = 0; j < items.size(); j++) {
      if (j == i) continue;
      E q = items[j].rest;
      if (q->k == POW && isFunc(q->a[0], "cos") && equal(q->a[0]->a[0], r->a[0]->a[0]) && q->a[1]->k == NUM && q->a[1]->n == 2 && q->a[1]->d == 1 &&
          !items[i].c.real && !items[j].c.real && ratCmp(items[i].c.q, items[j].c.q) == 0) {
        constant = nmAdd(constant, items[i].c);
        items[i].c = Nm();
        items[i].c.q = Rat{0, 1};
        items[j].c = items[i].c;
        break;
      }
    }
  }
  std::vector<E> out;
  for (auto &it : items) {
    if (nmZero(it.c)) continue;
    if (nmOne(it.c)) {
      out.push_back(it.rest);
      continue;
    }
    std::vector<E> f;
    f.push_back(nmE(it.c));
    if (it.rest->k == MUL)
      f.insert(f.end(), it.rest->a.begin(), it.rest->a.end());
    else
      f.push_back(it.rest);
    out.push_back(rawMul(f));
  }
  std::sort(out.begin(), out.end(), [](E a, E b) { return cmp(a, b) < 0; });
  if (!nmZero(constant)) out.insert(out.begin(), nmE(constant));
  if (out.empty()) return num(0);
  return rawAdd(out);
}

// ---- products ---------------------------------------------------------------------------------------------------------------------
static E ratPowE(Rat b, Rat e);
static bool positiveConst(E b) { return (b->k == NUM && b->n > 0) || isSym(b, "e") || isSym(b, "pi"); }

E mkMul(std::vector<E> f) {
  static int depth = 0;
  Nm c;
  struct BE {
    E b, e;
  };
  std::vector<BE> v;
  std::vector<E> stack(f.rbegin(), f.rend());
  while (!stack.empty()) {
    E t = stack.back();
    stack.pop_back();
    if (t->k == MUL) {
      for (size_t i = t->a.size(); i-- > 0;) stack.push_back(t->a[i]);
      continue;
    }
    if (isNumeric(t)) {
      c = nmMul(c, nmOf(t));
      continue;
    }
    E b = t, e = nullptr;
    if (t->k == POW) {
      b = t->a[0];
      e = t->a[1];
    }
    bool merged = false;
    for (auto &x : v)
      if (equal(x.b, b)) {
        x.e = mkAdd({x.e ? x.e : num(1), e ? e : num(1)});
        merged = true;
        break;
      }
    if (!merged) v.push_back({b, e ? e : num(1)});
  }
  if (nmZero(c)) return num(0);
  std::vector<E> out;
  bool again = false;
  for (auto &x : v) {
    E p = mkPow(x.b, x.e);
    if (isNumeric(p))
      c = nmMul(c, nmOf(p));
    else if (p->k == MUL) {
      again = true;
      for (E ch : p->a) {
        if (isNumeric(ch))
          c = nmMul(c, nmOf(ch));
        else
          out.push_back(ch);
      }
    } else
      out.push_back(p);
  }
  if (nmZero(c)) return num(0);
  if (again && depth < 4) {
    depth++;
    std::vector<E> all = out;
    all.push_back(nmE(c));
    E r = mkMul(all);
    depth--;
    return r;
  }
  std::sort(out.begin(), out.end(), [](E a, E b) { return cmp(a, b) < 0; });
  if (!nmOne(c) || out.empty()) out.insert(out.begin(), nmE(c));
  return rawMul(out);
}

// ---- powers -------------------------------------------------------------------------------------------------------------------------
static int64_t floorDiv(int64_t a, int64_t b) {
  int64_t q = a / b;
  if ((a % b != 0) && ((a < 0) != (b < 0))) q--;
  return q;
}

// b^(r/q) for rational b > 0 (0 < r < q): coefficient * radical
static E radical(Rat b, int64_t r, int64_t q) {
  if (b.n == 0) return num(0);
  if (b.n < 0) {
    Rat pb{-b.n, b.d};
    if (q == 2 && r == 1) return mkMul({sym("i"), radical(pb, r, q)});
    if (q % 2 == 1) {
      E pos = radical(pb, r, q);
      return (r % 2 == 0) ? pos : neg(pos);
    }
    return rawPow(numR(b), num(r, q));
  }
  I128 rad = (I128)b.n * ipow128(b.d, (int)(q - 1));
  if (rad > ((I128)1 << 62)) return rawPow(numR(b), num(r, q));
  std::vector<PF> pf = factorInt((uint64_t)rad);
  I128 coef = 1, inner = 1;
  for (auto &p : pf) {
    int64_t T = (int64_t)p.e * r;
    int64_t k = T / q, rem = T % q;
    coef *= ipow128(p.p, (int)k);
    inner *= ipow128(p.p, (int)rem);
    if (coef > ((I128)1 << 62) || inner > ((I128)1 << 62)) return rawPow(numR(b), num(r, q));
  }
  Rat cr;
  I128 dd = ipow128(b.d, (int)r);
  if (!ratMake(coef, dd, cr)) return rawPow(numR(b), num(r, q));
  E rest = inner == 1 ? nullptr : rawPow(num((int64_t)inner), num(1, q));
  if (!rest) return numR(cr);
  if (cr.n == 1 && cr.d == 1) return rest;
  return rawMul({numR(cr), rest});
}

static E ratPowE(Rat b, Rat e) {
  if (e.d == 1) {
    if (b.n == 0 && e.n < 0) {
      g_err = "division by zero";
      return num(0);
    }
    Rat o;
    if (ratPowInt(b, e.n, o)) return numR(o);
    return real(std::pow((double)b.n / b.d, (double)e.n));
  }
  int64_t q = e.d;
  int64_t m = floorDiv(e.n, q);
  int64_t r = e.n - m * q;
  if (b.n == 0) {
    if (m < 0) {
      g_err = "division by zero";
      return num(0);
    }
    return num(0);
  }
  Rat bm;
  if (!ratPowInt(b, m, bm)) return real(std::pow((double)b.n / b.d, (double)e.n / (double)e.d));
  E rad = radical(b, r, q);
  // bm * rad without going through mkMul (which would simplify the radical again and recurse)
  if (bm.n == 1 && bm.d == 1) return rad;
  if (rad->k == NUM) {
    Rat o;
    if (ratMul(bm, ratOf(rad), o)) return numR(o);
    return real((double)bm.n / bm.d * (double)rad->n / rad->d);
  }
  if (rad->k == MUL && rad->a[0]->k == NUM) {
    Rat o;
    if (ratMul(bm, ratOf(rad->a[0]), o)) {
      std::vector<E> f(rad->a.begin() + 1, rad->a.end());
      if (o.n == 1 && o.d == 1) return rawMul(f);
      f.insert(f.begin(), numR(o));
      return rawMul(f);
    }
  }
  return rawMul({numR(bm), rad});
}

static E realPow(double b, double e) {
  double v = std::pow(b, e);
  if (std::isnan(v)) {
    g_err = "complex or undefined result";
    return num(0);
  }
  return real(v);
}

E mkPow(E b, E e) {
  if (isZero(e)) return num(1);
  if (isOne(e)) return b;
  if (isOne(b)) return num(1);
  if (b->k == MAT) return e->k == NUM && e->d == 1 ? matPow(b, e->n) : rawPow(b, e);
  if (isNumeric(b) && isNumeric(e)) {
    if (b->k == NUM && e->k == NUM) return ratPowE(ratOf(b), ratOf(e));
    return realPow(toDouble(b), toDouble(e));
  }
  if (isZero(b)) {
    if (e->k == NUM && e->n > 0) return num(0);
    if (e->k == NUM && e->n < 0) {
      g_err = "division by zero";
      return num(0);
    }
  }
  if (isSym(b, "i") && e->k == NUM && e->d == 1) {
    int64_t k = ((e->n % 4) + 4) % 4;
    if (k == 0) return num(1);
    if (k == 1) return b;
    if (k == 2) return num(-1);
    return neg(b);
  }
  if (isSym(b, "e")) {
    if (isFunc(e, "ln")) return e->a[0];
    if (e->k == MUL) {
      for (size_t i = 0; i < e->a.size(); i++)
        if (isFunc(e->a[i], "ln")) {
          std::vector<E> rest;
          for (size_t j = 0; j < e->a.size(); j++)
            if (j != i) rest.push_back(e->a[j]);
          return mkPow(e->a[i]->a[0], mkMul(rest));
        }
    }
  }
  if (b->k == POW) {
    E b2 = b->a[0], e2 = b->a[1];
    if (isInt(e) || positiveConst(b2) || (isInt(e2) && false)) return mkPow(b2, mkMul({e2, e}));
    if (isInt(e2) && e2->n % 2 != 0 && false) return mkPow(b2, mkMul({e2, e}));
  }
  if (b->k == MUL) {
    if (isInt(e)) {
      std::vector<E> f;
      for (E ch : b->a) f.push_back(mkPow(ch, e));
      return mkMul(f);
    }
    if (isNumeric(b->a[0]) && b->a[0]->k == NUM && b->a[0]->n > 0 && e->k == NUM) {
      std::vector<E> rest(b->a.begin() + 1, b->a.end());
      E cp = mkPow(b->a[0], e);
      return mkMul({cp, mkPow(rawMul(rest), e)});
    }
  }
  return rawPow(b, e);
}

E neg(E a) { return mkMul({num(-1), a}); }
E sub(E a, E b) { return mkAdd({a, neg(b)}); }
E div(E a, E b) { return mkMul({a, mkPow(b, num(-1))}); }
E powi(E b, int64_t e) { return mkPow(b, num(e)); }

// ---- functions -----------------------------------------------------------------------------------------------------------------------
static E sinPi(Rat k) {  // sin(k*pi) for the k that have simple closed forms, else nullptr
  // reduce to [0, 2)
  int64_t whole = floorDiv(k.n, 2 * k.d);
  Rat r;
  if (!ratSub(k, Rat{2 * whole, 1}, r)) return nullptr;
  bool negative = false;
  Rat one{1, 1};
  if (ratCmp(r, one) >= 0) {
    negative = true;
    ratSub(r, one, r);
  }
  Rat half{1, 2};
  if (ratCmp(r, half) > 0) ratSub(one, r, r);
  E v = nullptr;
  if (r.n == 0)
    v = num(0);
  else if (r.n == 1 && r.d == 6)
    v = num(1, 2);
  else if (r.n == 1 && r.d == 4)
    v = mkMul({num(1, 2), mkPow(num(2), num(1, 2))});
  else if (r.n == 1 && r.d == 3)
    v = mkMul({num(1, 2), mkPow(num(3), num(1, 2))});
  else if (r.n == 1 && r.d == 2)
    v = num(1);
  if (!v) return nullptr;
  return negative ? neg(v) : v;
}
static bool piMultiple(E x, Rat &k) {
  if (isNumeric(x) && isZero(x)) {
    k = Rat{0, 1};
    return true;
  }
  if (isSym(x, "pi")) {
    k = Rat{1, 1};
    return true;
  }
  if (x->k == MUL && x->a.size() == 2 && x->a[0]->k == NUM && isSym(x->a[1], "pi")) {
    k = ratOf(x->a[0]);
    return true;
  }
  return false;
}
static bool isOddFn(const std::string &n) {
  return n == "sin" || n == "tan" || n == "asin" || n == "atan" || n == "sinh" || n == "tanh" || n == "asinh" || n == "atanh";
}
static bool isEvenFn(const std::string &n) { return n == "cos" || n == "cosh"; }

static bool numericFn(const std::string &name, double x, double &out) {
  if (name == "sin") out = std::sin(x);
  else if (name == "cos") out = std::cos(x);
  else if (name == "tan") out = std::tan(x);
  else if (name == "asin") out = std::asin(x);
  else if (name == "acos") out = std::acos(x);
  else if (name == "atan") out = std::atan(x);
  else if (name == "sinh") out = std::sinh(x);
  else if (name == "cosh") out = std::cosh(x);
  else if (name == "tanh") out = std::tanh(x);
  else if (name == "asinh") out = std::asinh(x);
  else if (name == "acosh") out = std::acosh(x);
  else if (name == "atanh") out = std::atanh(x);
  else if (name == "ln") out = std::log(x);
  else if (name == "log") out = std::log10(x);
  else if (name == "abs") out = std::fabs(x);
  else if (name == "sign") out = x > 0 ? 1 : x < 0 ? -1 : 0;
  else if (name == "floor") out = std::floor(x);
  else if (name == "ceil") out = std::ceil(x);
  else return false;
  return true;
}

E mkFunc(const std::string &name, std::vector<E> args) {
  if (args.size() == 1) {
    E x = args[0];
    if (name == "sqrt") return mkPow(x, num(1, 2));
    if (name == "cbrt") return mkPow(x, num(1, 3));
    if (name == "exp") return mkPow(sym("e"), x);
    if (x->k == MAT) {
      std::vector<E> el;
      for (E c : x->a) el.push_back(mkFunc(name, {c}));
      return mkMat(x->rows, x->cols, el);
    }
    if (x->k == REAL) {
      double o;
      if (numericFn(name, x->r, o)) {
        if (std::isnan(o)) {
          g_err = "domain error in " + name;
          return num(0);
        }
        return real(o);
      }
    }
    if (name == "ln") {
      if (isOne(x)) return num(0);
      if (isSym(x, "e")) return num(1);
      if (x->k == POW && isSym(x->a[0], "e")) return x->a[1];
      if (x->k == NUM && x->n <= 0) {
        g_err = "ln of a non-positive number";
        return num(0);
      }
    } else if (name == "log") {
      if (isOne(x)) return num(0);
      if (x->k == NUM && x->d == 1 && x->n == 10) return num(1);
    } else if (name == "abs") {
      if (x->k == NUM) return num(x->n < 0 ? -x->n : x->n, x->d);
      if (isFunc(x, "abs")) return x;
      if (x->k == MUL && isNumeric(x->a[0]) && toDouble(x->a[0]) < 0) return mkMul({neg(x->a[0]), mkFunc("abs", {mkMul(std::vector<E>(x->a.begin() + 1, x->a.end()))})});
    } else if (name == "sign") {
      if (x->k == NUM) return num(x->n > 0 ? 1 : x->n < 0 ? -1 : 0);
    } else if (name == "floor" || name == "ceil") {
      if (x->k == NUM) {
        int64_t f = floorDiv(x->n, x->d);
        if (name == "ceil" && x->n % x->d != 0) f++;
        return num(f);
      }
    } else if (name == "sin" || name == "cos" || name == "tan") {
      Rat k;
      if (piMultiple(x, k)) {
        E v = nullptr;
        if (name == "sin") v = sinPi(k);
        else if (name == "cos") {
          Rat k2;
          if (ratAdd(k, Rat{1, 2}, k2)) v = sinPi(k2);
        } else {
          E s = sinPi(k);
          Rat k2;
          E c = ratAdd(k, Rat{1, 2}, k2) ? sinPi(k2) : nullptr;
          if (s && c && !isZero(c)) v = div(s, c);
        }
        if (v) return v;
      }
    } else if (name == "atan") {
      if (isZero(x)) return num(0);
      if (isOne(x)) return mkMul({num(1, 4), sym("pi")});
      if (x->k == NUM && x->n == -1 && x->d == 1) return mkMul({num(-1, 4), sym("pi")});
      if (equal(x, mkPow(num(3), num(1, 2)))) return mkMul({num(1, 3), sym("pi")});
      if (equal(x, mkPow(num(3), num(-1, 2)))) return mkMul({num(1, 6), sym("pi")});
    } else if (name == "asin" || name == "acos") {
      E as = nullptr;
      if (isZero(x)) as = num(0);
      else if (isOne(x)) as = mkMul({num(1, 2), sym("pi")});
      else if (x->k == NUM && x->n == 1 && x->d == 2) as = mkMul({num(1, 6), sym("pi")});
      else if (equal(x, mkMul({num(1, 2), mkPow(num(2), num(1, 2))}))) as = mkMul({num(1, 4), sym("pi")});
      else if (equal(x, mkMul({num(1, 2), mkPow(num(3), num(1, 2))}))) as = mkMul({num(1, 3), sym("pi")});
      if (as) return name == "asin" ? as : sub(mkMul({num(1, 2), sym("pi")}), as);
    } else if (name == "sinh" || name == "tanh" || name == "asinh" || name == "atanh") {
      if (isZero(x)) return num(0);
    } else if (name == "cosh") {
      if (isZero(x)) return num(1);
    } else if (name == "acosh") {
      if (isOne(x)) return num(0);
    }
    // odd / even symmetry: pull a negative numeric coefficient out
    if ((isOddFn(name) || isEvenFn(name)) && x->k == MUL && isNumeric(x->a[0]) && toDouble(x->a[0]) < 0) {
      E inner = mkFunc(name, {neg(x)});
      return isOddFn(name) ? neg(inner) : inner;
    }
  }
  Node *p = alloc(FUNC);
  p->s = name;
  p->a = std::move(args);
  return p;
}
E func1(const std::string &name, E x) { return mkFunc(name, {x}); }

// ---- queries / traversal -----------------------------------------------------------------------------------------------------------
bool contains(E e, const std::string &var) {
  if (e->k == SYM) return e->s == var;
  for (E c : e->a)
    if (contains(c, var)) return true;
  return false;
}
void freeSyms(E e, std::vector<std::string> &out) {
  if (e->k == SYM) {
    if (e->s == "pi" || e->s == "e" || e->s == "i" || e->s == "oo") return;
    if (std::find(out.begin(), out.end(), e->s) == out.end()) out.push_back(e->s);
    return;
  }
  for (E c : e->a) freeSyms(c, out);
}
E mapChildren(E e, E (*fn)(E, void *), void *ctx) {
  switch (e->k) {
    case ADD: {
      std::vector<E> t;
      for (E c : e->a) t.push_back(fn(c, ctx));
      return mkAdd(t);
    }
    case MUL: {
      std::vector<E> t;
      for (E c : e->a) t.push_back(fn(c, ctx));
      return mkMul(t);
    }
    case POW:
      return mkPow(fn(e->a[0], ctx), fn(e->a[1], ctx));
    case FUNC: {
      std::vector<E> t;
      for (E c : e->a) t.push_back(fn(c, ctx));
      return mkFunc(e->s, t);
    }
    case MAT: {
      std::vector<E> t;
      for (E c : e->a) t.push_back(fn(c, ctx));
      return mkMat(e->rows, e->cols, t);
    }
    default:
      return e;
  }
}
struct SubsCtx {
  E from, to;
};
static E subsRec(E e, void *p) {
  SubsCtx *c = (SubsCtx *)p;
  if (equal(e, c->from)) return c->to;
  if (e->a.empty()) return e;
  return mapChildren(e, subsRec, p);
}
E subs(E e, E from, E to) {
  SubsCtx c{from, to};
  return subsRec(e, &c);
}

// ---- printing --------------------------------------------------------------------------------------------------------------------------
static std::string numStr(int64_t n, int64_t d) {
  char b[48];
  if (d == 1) snprintf(b, sizeof b, "%lld", (long long)n);
  else snprintf(b, sizeof b, "%lld/%lld", (long long)n, (long long)d);
  return b;
}
static std::string realStr(double v) {
  char b[48];
  if (std::isinf(v)) return v > 0 ? "oo" : "-oo";
  snprintf(b, sizeof b, "%.10g", v);
  std::string s = b;
  size_t pos = s.find("e");
  if (pos != std::string::npos) {
    std::string m = s.substr(0, pos), x = s.substr(pos + 1);
    if (x[0] == '+') x = x.substr(1);
    size_t z = 0;
    bool negx = false;
    if (x[0] == '-') {
      negx = true;
      x = x.substr(1);
    }
    while (z + 1 < x.size() && x[z] == '0') z++;
    s = m + "E" + (negx ? "-" : "") + x.substr(z);
  }
  return s;
}
static void monoExps(E t, std::vector<std::pair<std::string, double>> &out) {
  if (t->k == SYM) {
    out.push_back({t->s, 1});
  } else if (t->k == POW && t->a[0]->k == SYM && t->a[1]->k == NUM) {
    out.push_back({t->a[0]->s, (double)t->a[1]->n / (double)t->a[1]->d});
  } else if (t->k == MUL) {
    for (E c : t->a) monoExps(c, out);
  }
}
// true when a should print before b: higher total degree first, then lexicographic on the symbol exponents (x^2, x*y, y^2)
static double termDegree(E t);
static bool monoBefore(E a, E b) {
  double da = termDegree(a), db = termDegree(b);
  if (da != db) return da > db;
  std::vector<std::pair<std::string, double>> ea, eb;
  monoExps(a, ea);
  monoExps(b, eb);
  std::vector<std::string> names;
  for (auto &p : ea) names.push_back(p.first);
  for (auto &p : eb) names.push_back(p.first);
  std::sort(names.begin(), names.end());
  names.erase(std::unique(names.begin(), names.end()), names.end());
  for (auto &n : names) {
    double xa = 0, xb = 0;
    for (auto &p : ea) if (p.first == n) xa += p.second;
    for (auto &p : eb) if (p.first == n) xb += p.second;
    if (xa != xb) return xa > xb;
  }
  return false;
}
static double termDegree(E t) {
  switch (t->k) {
    case SYM:
      return 1;
    case POW:
      if (t->a[1]->k == NUM && (t->a[0]->k == SYM || t->a[0]->k == POW || t->a[0]->k == MUL)) return termDegree(t->a[0]) * toDouble(t->a[1]);
      return 0.5;
    case MUL: {
      double d = 0;
      for (E c : t->a) d += termDegree(c);
      return d;
    }
    default:
      return 0;
  }
}

static std::string str(E e, int parent);
// precedence: 1 add, 2 mul, 3 pow, 4 atom
static std::string paren(const std::string &s, bool need) { return need ? "(" + s + ")" : s; }

static bool negativeTerm(E t) {
  if (t->k == NUM) return t->n < 0;
  if (t->k == REAL) return t->r < 0;
  if (t->k == MUL && isNumeric(t->a[0])) return toDouble(t->a[0]) < 0;
  return false;
}
static std::string strMul(E e, int parent) {
  bool negative = false;
  std::vector<std::string> numer, denom;
  Nm c;
  std::vector<E> rest;
  for (E f : e->a) {
    if (isNumeric(f))
      c = nmMul(c, nmOf(f));
    else
      rest.push_back(f);
  }
  std::string coefNum, coefDen;
  if (!c.real) {
    if (c.q.n < 0) {
      negative = true;
      c.q.n = -c.q.n;
    }
    if (c.q.n != 1) coefNum = numStr(c.q.n, 1);
    if (c.q.d != 1) coefDen = numStr(c.q.d, 1);
  } else {
    double v = c.x;
    if (v < 0) {
      negative = true;
      v = -v;
    }
    coefNum = realStr(v);
  }
  if (!coefNum.empty()) numer.push_back(coefNum);
  std::vector<std::string> dn;
  for (E f : rest) {
    if (f->k == POW && f->a[1]->k == NUM && f->a[1]->n < 0) {
      E pe = mkPow(f->a[0], num(-f->a[1]->n, f->a[1]->d));
      dn.push_back(str(pe, 3));
    } else if (f->k == POW && f->a[1]->k == MUL && isNumeric(f->a[1]->a[0]) && toDouble(f->a[1]->a[0]) < 0 && false) {
    } else
      numer.push_back(str(f, 2));
  }
  if (!coefDen.empty()) dn.insert(dn.begin(), coefDen);
  std::string s;
  if (numer.empty()) s = "1";
  for (size_t i = 0; i < numer.size(); i++) s += (i ? "*" : "") + numer[i];
  if (!dn.empty()) {
    std::string d;
    for (size_t i = 0; i < dn.size(); i++) d += (i ? "*" : "") + dn[i];
    if (dn.size() > 1) d = "(" + d + ")";
    s += "/" + d;
  }
  if (negative) s = "-" + s;
  return paren(s, parent > (negative ? 1 : 2));
}

static std::string str(E e, int parent) {
  switch (e->k) {
    case NUM: {
      std::string s = numStr(e->n, e->d);
      bool need = (e->n < 0 && parent > 1) || (e->d != 1 && parent > 2);
      return paren(s, need);
    }
    case REAL: {
      std::string s = realStr(e->r);
      return paren(s, e->r < 0 && parent > 1);
    }
    case SYM:
      return e->s;
    case FUNC: {
      if (e->s == "prod") {
        std::string s;
        for (size_t i = 0; i < e->a.size(); i++) {
          E f = e->a[i];
          std::string fs = str(f, 3);
          if (f->k == ADD || (f->k == NUM && f->n < 0)) fs = "(" + str(f, 0) + ")";
          s += (i ? "*" : "") + fs;
        }
        return paren(s, parent > 2);
      }
      if (e->s == "pow" && e->a.size() == 2) {
        E b = e->a[0];
        std::string bs = str(b, 3);
        if (b->k == ADD || b->k == MUL || (b->k == NUM && b->n < 0)) bs = "(" + str(b, 0) + ")";
        return paren(bs + "^" + str(e->a[1], 3), parent > 3);
      }
      if (e->s == "eq" && e->a.size() == 2) return paren(str(e->a[0], 0) + " = " + str(e->a[1], 0), parent > 0);
      if (e->s == "set") {
        std::string s = "{";
        for (size_t i = 0; i < e->a.size(); i++) s += (i ? ", " : "") + str(e->a[i], 0);
        return s + "}";
      }
      std::string s = e->s + "(";
      for (size_t i = 0; i < e->a.size(); i++) s += (i ? "," : "") + str(e->a[i], 0);
      return s + ")";
    }
    case MAT: {
      std::string s = "[";
      for (int r = 0; r < e->rows; r++) {
        s += r ? "," : "";
        s += "[";
        for (int c = 0; c < e->cols; c++) s += (c ? "," : "") + str(e->a[r * e->cols + c], 0);
        s += "]";
      }
      return s + "]";
    }
    case ADD: {
      std::vector<E> t = e->a;
      bool complexNum = false;
      for (E c : t) complexNum = complexNum || contains(c, "i");
      if (g_asc)
        std::stable_sort(t.begin(), t.end(), [](E a, E b) { return termDegree(a) < termDegree(b); });
      else if (!complexNum)
        std::stable_sort(t.begin(), t.end(), [](E a, E b) { return monoBefore(a, b); });
      std::string s;
      for (size_t i = 0; i < t.size(); i++) {
        if (negativeTerm(t[i])) {
          E m = neg(t[i]);
          std::string ms = str(m, 1);
          if (m->k == ADD) ms = "(" + ms + ")";
          s += (i ? " - " : "-") + ms;
        } else {
          s += (i ? " + " : "") + str(t[i], 1);
        }
      }
      return paren(s, parent > 1);
    }
    case MUL:
      return strMul(e, parent);
    case POW: {
      E b = e->a[0], x = e->a[1];
      if (isSym(b, "e")) return "exp(" + str(x, 0) + ")";
      if (x->k == NUM && x->n == 1 && x->d == 2) return "sqrt(" + str(b, 0) + ")";
      if (x->k == NUM && x->n == 1 && x->d == 3) return "cbrt(" + str(b, 0) + ")";
      if (x->k == NUM && x->n < 0) {
        E p = mkPow(b, num(-x->n, x->d));
        std::string d = str(p, 3);
        if (p->k == MUL || p->k == ADD) d = "(" + d + ")";
        return paren("1/" + d, parent > 2);
      }
      std::string bs = str(b, 3);
      if (b->k == ADD || b->k == MUL || b->k == POW || (b->k == NUM && (b->d != 1 || b->n < 0)) || (b->k == REAL && b->r < 0)) bs = "(" + str(b, 0) + ")";
      std::string xs = str(x, 3);
      bool simple = (x->k == NUM && x->d == 1 && x->n > 0) || x->k == SYM;
      if (!simple) xs = "(" + str(x, 0) + ")";
      return paren(bs + "^" + xs, parent > 3);
    }
  }
  return "?";
}
std::string toString(E e) { return str(e, 0); }

}  // namespace cas
