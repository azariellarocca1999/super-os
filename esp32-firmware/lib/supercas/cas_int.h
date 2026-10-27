// Integer helpers shared by the CAS sources (exact arithmetic on int64 with 128-bit intermediates).
#pragma once
#include <cmath>
#include <cstdint>
#include <vector>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#ifndef M_E
#define M_E 2.71828182845904523536
#endif

#include "cas_i128.h"

namespace cas {
#if defined(__SIZEOF_INT128__) && !defined(CAS_SOFT128)
typedef __int128 I128;
#else
typedef SoftI128 I128;  // 32-bit targets (ESP32-S3): software 128-bit integer
#endif

inline int64_t igcd(int64_t a, int64_t b) {
  if (a < 0) a = -a;
  if (b < 0) b = -b;
  while (b) {
    int64_t t = a % b;
    a = b;
    b = t;
  }
  return a;
}
inline I128 gcd128(I128 a, I128 b) {
  if (a < 0) a = -a;
  if (b < 0) b = -b;
  while (b) {
    I128 t = a % b;
    a = b;
    b = t;
  }
  return a;
}
inline bool fits64(I128 v) { return v >= (I128)INT64_MIN + 1 && v <= (I128)INT64_MAX; }

struct Rat {
  int64_t n = 0, d = 1;
};
// n/d with overflow detection; returns false when the result does not fit
inline bool ratMake(I128 n, I128 d, Rat &out) {
  if (d == 0) return false;
  if (d < 0) {
    n = -n;
    d = -d;
  }
  I128 g = gcd128(n, d);
  if (g > 1) {
    n /= g;
    d /= g;
  }
  if (!fits64(n) || !fits64(d)) return false;
  out.n = (int64_t)n;
  out.d = (int64_t)d;
  return true;
}
inline bool ratAdd(Rat a, Rat b, Rat &o) { return ratMake((I128)a.n * b.d + (I128)b.n * a.d, (I128)a.d * b.d, o); }
inline bool ratSub(Rat a, Rat b, Rat &o) { return ratMake((I128)a.n * b.d - (I128)b.n * a.d, (I128)a.d * b.d, o); }
inline bool ratMul(Rat a, Rat b, Rat &o) { return ratMake((I128)a.n * b.n, (I128)a.d * b.d, o); }
inline bool ratDiv(Rat a, Rat b, Rat &o) { return b.n != 0 && ratMake((I128)a.n * b.d, (I128)a.d * b.n, o); }
inline bool ratPowInt(Rat b, int64_t e, Rat &o) {
  bool inv = e < 0;
  uint64_t k = inv ? (uint64_t)(-e) : (uint64_t)e;
  Rat r{1, 1}, x = b;
  while (k) {
    if (k & 1 && !ratMul(r, x, r)) return false;
    k >>= 1;
    if (k && !ratMul(x, x, x)) return false;
  }
  if (inv) {
    if (r.n == 0) return false;
    return ratMake(r.d, r.n, o);
  }
  o = r;
  return true;
}
inline int ratCmp(Rat a, Rat b) {
  I128 l = (I128)a.n * b.d, r = (I128)b.n * a.d;
  return l < r ? -1 : l > r ? 1 : 0;
}

// prime factorisation by trial division (the cofactor that remains after `limit` is reported as a single "prime")
struct PF {
  int64_t p;
  int e;
};
inline std::vector<PF> factorInt(uint64_t n, uint64_t limit = 2000000ULL) {
  std::vector<PF> f;
  if (n < 2) return f;
  for (uint64_t p = 2; p <= limit && p * p <= n; p += (p == 2 ? 1 : 2)) {
    if (n % p == 0) {
      int e = 0;
      while (n % p == 0) {
        n /= p;
        e++;
      }
      f.push_back({(int64_t)p, e});
    }
  }
  if (n > 1) f.push_back({(int64_t)n, 1});
  return f;
}
inline I128 ipow128(int64_t b, int e) {
  I128 r = 1;
  for (int i = 0; i < e; i++) {
    r *= b;
    if (r > ((I128)1 << 100)) return r;
  }
  return r;
}
}  // namespace cas
