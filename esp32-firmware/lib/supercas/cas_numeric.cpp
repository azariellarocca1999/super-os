// cas_numeric.cpp -- numeric evaluation, numeric integration, the 3D surface renderer and the text command front end.
#include <algorithm>
#include <cmath>
#include <cstring>

#include "cas_int.h"
#include "cas_internal.h"

namespace cas {

void Env::set(const std::string &k, double x) {
  for (auto &p : v)
    if (p.first == k) {
      p.second = x;
      return;
    }
  v.push_back({k, x});
}

static bool fnD(const std::string &n, double x, double &o) {
  if (n == "sin") o = std::sin(x);
  else if (n == "cos") o = std::cos(x);
  else if (n == "tan") o = std::tan(x);
  else if (n == "asin") o = std::asin(x);
  else if (n == "acos") o = std::acos(x);
  else if (n == "atan") o = std::atan(x);
  else if (n == "sinh") o = std::sinh(x);
  else if (n == "cosh") o = std::cosh(x);
  else if (n == "tanh") o = std::tanh(x);
  else if (n == "asinh") o = std::asinh(x);
  else if (n == "acosh") o = std::acosh(x);
  else if (n == "atanh") o = std::atanh(x);
  else if (n == "ln") o = std::log(x);
  else if (n == "log") o = std::log10(x);
  else if (n == "abs") o = std::fabs(x);
  else if (n == "sign") o = x > 0 ? 1 : x < 0 ? -1 : 0;
  else if (n == "floor") o = std::floor(x);
  else if (n == "ceil") o = std::ceil(x);
  else if (n == "fact") o = std::tgamma(x + 1);
  else return false;
  return !std::isnan(o);
}

bool evalD(E e, const Env &env, double &out) {
  switch (e->k) {
    case NUM:
      out = (double)e->n / (double)e->d;
      return true;
    case REAL:
      out = e->r;
      return true;
    case SYM: {
      for (auto &p : env.v)
        if (p.first == e->s) {
          out = p.second;
          return true;
        }
      if (e->s == "pi") out = M_PI;
      else if (e->s == "e") out = M_E;
      else if (e->s == "oo") out = INFINITY;
      else return false;
      return true;
    }
    case ADD: {
      double s = 0;
      for (E c : e->a) {
        double v;
        if (!evalD(c, env, v)) return false;
        s += v;
      }
      out = s;
      return true;
    }
    case MUL: {
      double s = 1;
      for (E c : e->a) {
        double v;
        if (!evalD(c, env, v)) return false;
        s *= v;
      }
      out = s;
      return true;
    }
    case POW: {
      double b, x;
      if (!evalD(e->a[0], env, b) || !evalD(e->a[1], env, x)) return false;
      out = std::pow(b, x);
      return !std::isnan(out);
    }
    case FUNC: {
      if (e->a.size() == 1) {
        double v;
        if (!evalD(e->a[0], env, v)) return false;
        return fnD(e->s, v, out);
      }
      return false;
    }
    default:
      return false;
  }
}

// adaptive Simpson
static double simpson(E f, const std::string &x, double a, double b, double fa, double fm, double fb, double whole, double eps, int depth) {
  Env env;
  auto F = [&](double t) {
    env.v.clear();
    env.set(x, t);
    double o = 0;
    evalD(f, env, o);
    return o;
  };
  double m = 0.5 * (a + b), lm = 0.5 * (a + m), rm = 0.5 * (m + b);
  double flm = F(lm), frm = F(rm);
  double left = (m - a) / 6 * (fa + 4 * flm + fm), right = (b - m) / 6 * (fm + 4 * frm + fb);
  if (depth <= 0 || std::fabs(left + right - whole) <= 15 * eps) return left + right + (left + right - whole) / 15;
  return simpson(f, x, a, m, fa, flm, fm, left, eps / 2, depth - 1) + simpson(f, x, m, b, fm, frm, fb, right, eps / 2, depth - 1);
}
double numericIntegral(E f, const std::string &x, double a, double b) {
  if (a == b) return 0;
  double sign = 1;
  if (a > b) {
    std::swap(a, b);
    sign = -1;
  }
  Env env;
  auto F = [&](double t) {
    env.v.clear();
    env.set(x, t);
    double o = 0;
    evalD(f, env, o);
    return o;
  };
  double fa = F(a), fb = F(b), fm = F(0.5 * (a + b));
  double whole = (b - a) / 6 * (fa + 4 * fm + fb);
  return sign * simpson(f, x, a, b, fa, fm, fb, whole, 1e-10, 22);
}

static E approxRec(E e, void *) {
  if (e->k == NUM) return real((double)e->n / (double)e->d);
  if (e->k == SYM) {
    if (e->s == "pi") return real(M_PI);
    if (e->s == "e") return real(M_E);
    return e;
  }
  if (e->a.empty()) return e;
  return mapChildren(e, approxRec, nullptr);
}
E approxExpr(E e) { return approxRec(e, nullptr); }

// ---- 3D surface -----------------------------------------------------------------------------------------------------------------
namespace {
struct P2 {
  double x, y;
};
struct Quad {
  P2 p[4];
  double depth;
};
inline void setPix(uint8_t *bm, int x, int y, bool on) {
  if (x < 0 || x >= 96 || y < 0 || y >= 64) return;
  uint8_t m = (uint8_t)(0x80 >> (x & 7));
  if (on)
    bm[y * 12 + (x >> 3)] |= m;
  else
    bm[y * 12 + (x >> 3)] &= (uint8_t)~m;
}
void lineBm(uint8_t *bm, int x0, int y0, int x1, int y1) {
  int dx = std::abs(x1 - x0), sx = x0 < x1 ? 1 : -1, dy = -std::abs(y1 - y0), sy = y0 < y1 ? 1 : -1, err = dx + dy;
  while (true) {
    setPix(bm, x0, y0, true);
    if (x0 == x1 && y0 == y1) break;
    int e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      x0 += sx;
    }
    if (e2 <= dx) {
      err += dx;
      y0 += sy;
    }
  }
}
void fillQuad(uint8_t *bm, const P2 *p) {
  double ymin = 1e9, ymax = -1e9;
  for (int i = 0; i < 4; i++) {
    ymin = std::min(ymin, p[i].y);
    ymax = std::max(ymax, p[i].y);
  }
  for (int y = (int)std::ceil(ymin); y <= (int)std::floor(ymax); y++) {
    double xs[8];
    int n = 0;
    for (int i = 0; i < 4; i++) {
      P2 a = p[i], b = p[(i + 1) % 4];
      if ((a.y <= y && b.y > y) || (b.y <= y && a.y > y)) xs[n++] = a.x + (y - a.y) * (b.x - a.x) / (b.y - a.y);
    }
    std::sort(xs, xs + n);
    for (int k = 0; k + 1 < n; k += 2)
      for (int x = (int)std::ceil(xs[k]); x <= (int)std::floor(xs[k + 1]); x++) setPix(bm, x, y, false);
  }
}
}  // namespace

bool plot3d(E f, double x0, double x1, double y0, double y1, uint8_t *bm) {
  const int N = 14;
  std::memset(bm, 0, 768);
  static double z[N + 1][N + 1];
  Env env;
  double zmin = 1e300, zmax = -1e300;
  for (int j = 0; j <= N; j++)
    for (int i = 0; i <= N; i++) {
      env.v.clear();
      env.set("x", x0 + (x1 - x0) * i / N);
      env.set("y", y0 + (y1 - y0) * j / N);
      double v;
      if (!evalD(f, env, v) || !std::isfinite(v)) v = NAN;
      z[j][i] = v;
      if (!std::isnan(v)) {
        zmin = std::min(zmin, v);
        zmax = std::max(zmax, v);
      }
    }
  if (zmin > zmax) return false;
  double zr = zmax - zmin;
  if (zr < 1e-12) zr = 1;
  double az = 0.62, el = 0.55;
  double ca = std::cos(az), sa = std::sin(az), ce = std::cos(el), se = std::sin(el);
  auto proj = [&](int i, int j, double zz, double &depth) {
    double X = 2.0 * i / N - 1, Y = 2.0 * j / N - 1, Z = (zz - zmin) / zr * 1.2 - 0.6;
    double xr = X * ca - Y * sa, yr = X * sa + Y * ca;
    depth = yr;
    return P2{xr, -(Z * ce + yr * se)};
  };
  // bounding box of the projected grid
  double minx = 1e9, maxx = -1e9, miny = 1e9, maxy = -1e9;
  for (int j = 0; j <= N; j += N)
    for (int i = 0; i <= N; i += N)
      for (int zi = 0; zi < 2; zi++) {
        double d;
        P2 p = proj(i, j, zi ? zmax : zmin, d);
        minx = std::min(minx, p.x);
        maxx = std::max(maxx, p.x);
        miny = std::min(miny, p.y);
        maxy = std::max(maxy, p.y);
      }
  double sx = 90.0 / (maxx - minx), sy = 58.0 / (maxy - miny), sc = std::min(sx, sy);
  double ox = 48 - sc * (minx + maxx) / 2, oy = 32 - sc * (miny + maxy) / 2;
  std::vector<Quad> quads;
  for (int j = 0; j < N; j++)
    for (int i = 0; i < N; i++) {
      double zz[4] = {z[j][i], z[j][i + 1], z[j + 1][i + 1], z[j + 1][i]};
      if (std::isnan(zz[0]) || std::isnan(zz[1]) || std::isnan(zz[2]) || std::isnan(zz[3])) continue;
      int ii[4] = {i, i + 1, i + 1, i}, jj[4] = {j, j, j + 1, j + 1};
      Quad q;
      q.depth = 0;
      for (int k = 0; k < 4; k++) {
        double d;
        P2 p = proj(ii[k], jj[k], zz[k], d);
        q.p[k] = P2{ox + sc * p.x, oy + sc * p.y};
        q.depth += d / 4;
      }
      quads.push_back(q);
    }
  std::sort(quads.begin(), quads.end(), [](const Quad &a, const Quad &b) { return a.depth > b.depth; });  // far first
  for (auto &q : quads) {
    fillQuad(bm, q.p);
    for (int k = 0; k < 4; k++) {
      P2 a = q.p[k], b = q.p[(k + 1) % 4];
      lineBm(bm, (int)std::lround(a.x), (int)std::lround(a.y), (int)std::lround(b.x), (int)std::lround(b.y));
    }
  }
  return true;
}

// ---- text front end ------------------------------------------------------------------------------------------------------------------------
static std::string trim(const std::string &s) {
  size_t a = 0, b = s.size();
  while (a < b && isspace((unsigned char)s[a])) a++;
  while (b > a && isspace((unsigned char)s[b - 1])) b--;
  return s.substr(a, b - a);
}
static int topLevelArgs(const std::string &s) {  // number of commas at depth 1 + 1
  int depth = 0, n = 1;
  for (char c : s) {
    if (c == '(' || c == '[') depth++;
    else if (c == ')' || c == ']') depth--;
    else if (c == ',' && depth == 1) n++;
  }
  return n;
}
static bool hasFreeSymbols(E e) {
  std::vector<std::string> v;
  freeSyms(e, v);
  return !v.empty();
}

std::string runCommand(const std::string &textIn) {
  reset();
  std::string text = trim(textIn);
  if (text.empty()) return "";
  E r = parse(text);
  if (!r) return "ERROR: " + g_err;
  if (failed()) return "ERROR: " + g_err;
  std::string out = toString(r);
  std::string low;
  for (char c : text) low += (char)tolower((unsigned char)c);
  if (low.compare(0, 4, "int(") == 0 && topLevelArgs(text) <= 2 && r->k != SYM) out += " + C";
  // numeric companion for exact constants
  if (r->k != NUM && r->k != REAL && r->k != MAT && !(r->k == SYM) && !hasFreeSymbols(r) && low.compare(0, 7, "approx(") != 0) {
    E ap = approxExpr(r);
    if (!failed()) {
      std::string as = toString(ap);
      if (as != out) out += "\n~ " + as;
    }
  }
  return out;
}

bool runPlot3d(const std::string &textIn, uint8_t *bm, std::string &err) {
  reset();
  std::string text = trim(textIn);
  E r = parse(text);
  if (!r) {
    err = g_err;
    return false;
  }
  if (r->k != FUNC || r->s != "plot3d" || r->a.size() < 1) {
    err = "use plot3d(f(x,y), x0, x1, y0, y1)";
    return false;
  }
  double v[4] = {-3, 3, -3, 3};
  Env e0;
  for (size_t i = 1; i < r->a.size() && i <= 4; i++) {
    double t;
    if (!evalD(r->a[i], e0, t)) {
      err = "bad range";
      return false;
    }
    v[i - 1] = t;
  }
  if (!(v[1] > v[0]) || !(v[3] > v[2])) {
    err = "empty range";
    return false;
  }
  if (!plot3d(r->a[0], v[0], v[1], v[2], v[3], bm)) {
    err = "the function has no finite values in that range";
    return false;
  }
  return true;
}

}  // namespace cas
