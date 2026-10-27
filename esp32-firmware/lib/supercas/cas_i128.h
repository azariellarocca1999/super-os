// Software 128-bit signed integer for targets without __int128 (the 32-bit Xtensa ESP32-S3).
// Only what the CAS needs: + - * / % comparisons, shifts, conversions.  The host tests also build with -DCAS_SOFT128 to check it.
#pragma once
#include <cstdint>

namespace cas {

struct SoftI128 {
  uint64_t hi = 0, lo = 0;  // magnitude
  bool neg = false;

  SoftI128() {}
  SoftI128(int v) { set((int64_t)v); }
  SoftI128(long v) { set((int64_t)v); }
  SoftI128(long long v) { set((int64_t)v); }
  SoftI128(unsigned v) { lo = v; }
  SoftI128(unsigned long v) { lo = v; }
  SoftI128(unsigned long long v) { lo = v; }
  void set(int64_t v) {
    neg = v < 0;
    lo = neg ? (uint64_t)0 - (uint64_t)v : (uint64_t)v;
    hi = 0;
  }
  bool isZero() const { return hi == 0 && lo == 0; }

  // magnitude helpers
  static int cmpMag(const SoftI128 &a, const SoftI128 &b) {
    if (a.hi != b.hi) return a.hi < b.hi ? -1 : 1;
    if (a.lo != b.lo) return a.lo < b.lo ? -1 : 1;
    return 0;
  }
  static SoftI128 addMag(const SoftI128 &a, const SoftI128 &b) {
    SoftI128 r;
    r.lo = a.lo + b.lo;
    r.hi = a.hi + b.hi + (r.lo < a.lo ? 1 : 0);
    return r;
  }
  static SoftI128 subMag(const SoftI128 &a, const SoftI128 &b) {  // |a| >= |b|
    SoftI128 r;
    r.lo = a.lo - b.lo;
    r.hi = a.hi - b.hi - (a.lo < b.lo ? 1 : 0);
    return r;
  }
  static SoftI128 mulMag(const SoftI128 &a, const SoftI128 &b) {  // truncated to 128 bits
    uint64_t a0 = a.lo & 0xFFFFFFFFu, a1 = a.lo >> 32, b0 = b.lo & 0xFFFFFFFFu, b1 = b.lo >> 32;
    uint64_t p00 = a0 * b0, p01 = a0 * b1, p10 = a1 * b0, p11 = a1 * b1;
    uint64_t mid = (p00 >> 32) + (p01 & 0xFFFFFFFFu) + (p10 & 0xFFFFFFFFu);
    SoftI128 r;
    r.lo = (p00 & 0xFFFFFFFFu) | (mid << 32);
    r.hi = p11 + (p01 >> 32) + (p10 >> 32) + (mid >> 32) + a.hi * b.lo + a.lo * b.hi;
    return r;
  }
  static void divmodMag(const SoftI128 &a, const SoftI128 &b, SoftI128 &q, SoftI128 &r) {
    q = SoftI128();
    r = SoftI128();
    for (int i = 127; i >= 0; i--) {
      // r = (r << 1) | bit i of a
      r.hi = (r.hi << 1) | (r.lo >> 63);
      r.lo = (r.lo << 1) | (i >= 64 ? (a.hi >> (i - 64)) & 1 : (a.lo >> i) & 1);
      if (cmpMag(r, b) >= 0) {
        r = subMag(r, b);
        if (i >= 64)
          q.hi |= (uint64_t)1 << (i - 64);
        else
          q.lo |= (uint64_t)1 << i;
      }
    }
  }
  static SoftI128 signedAdd(const SoftI128 &a, const SoftI128 &b) {
    SoftI128 r;
    if (a.neg == b.neg) {
      r = addMag(a, b);
      r.neg = a.neg;
    } else if (cmpMag(a, b) >= 0) {
      r = subMag(a, b);
      r.neg = a.neg;
    } else {
      r = subMag(b, a);
      r.neg = b.neg;
    }
    if (r.isZero()) r.neg = false;
    return r;
  }

  SoftI128 operator-() const {
    SoftI128 r = *this;
    if (!r.isZero()) r.neg = !r.neg;
    return r;
  }
  friend SoftI128 operator+(const SoftI128 &a, const SoftI128 &b) { return signedAdd(a, b); }
  friend SoftI128 operator-(const SoftI128 &a, const SoftI128 &b) { return signedAdd(a, -b); }
  friend SoftI128 operator*(const SoftI128 &a, const SoftI128 &b) {
    SoftI128 r = mulMag(a, b);
    r.neg = !r.isZero() && (a.neg != b.neg);
    return r;
  }
  friend SoftI128 operator/(const SoftI128 &a, const SoftI128 &b) {
    SoftI128 q, r;
    if (b.isZero()) return q;
    divmodMag(a, b, q, r);
    q.neg = !q.isZero() && (a.neg != b.neg);
    return q;
  }
  friend SoftI128 operator%(const SoftI128 &a, const SoftI128 &b) {
    SoftI128 q, r;
    if (b.isZero()) return r;
    divmodMag(a, b, q, r);
    r.neg = !r.isZero() && a.neg;
    return r;
  }
  SoftI128 operator<<(int s) const {
    SoftI128 r = *this;
    if (s >= 64) {
      r.hi = r.lo << (s - 64);
      r.lo = 0;
    } else if (s > 0) {
      r.hi = (r.hi << s) | (r.lo >> (64 - s));
      r.lo <<= s;
    }
    return r;
  }
  SoftI128 &operator+=(const SoftI128 &b) { return *this = *this + b; }
  SoftI128 &operator-=(const SoftI128 &b) { return *this = *this - b; }
  SoftI128 &operator*=(const SoftI128 &b) { return *this = *this * b; }
  SoftI128 &operator/=(const SoftI128 &b) { return *this = *this / b; }
  SoftI128 &operator%=(const SoftI128 &b) { return *this = *this % b; }
  SoftI128 &operator++() { return *this += SoftI128(1); }
  SoftI128 &operator--() { return *this -= SoftI128(1); }

  static int cmp(const SoftI128 &a, const SoftI128 &b) {
    if (a.isZero() && b.isZero()) return 0;
    if (a.neg != b.neg) return a.neg ? -1 : 1;
    int c = cmpMag(a, b);
    return a.neg ? -c : c;
  }
  friend bool operator<(const SoftI128 &a, const SoftI128 &b) { return cmp(a, b) < 0; }
  friend bool operator>(const SoftI128 &a, const SoftI128 &b) { return cmp(a, b) > 0; }
  friend bool operator<=(const SoftI128 &a, const SoftI128 &b) { return cmp(a, b) <= 0; }
  friend bool operator>=(const SoftI128 &a, const SoftI128 &b) { return cmp(a, b) >= 0; }
  friend bool operator==(const SoftI128 &a, const SoftI128 &b) { return cmp(a, b) == 0; }
  friend bool operator!=(const SoftI128 &a, const SoftI128 &b) { return cmp(a, b) != 0; }

  explicit operator bool() const { return !isZero(); }
  explicit operator uint64_t() const { return lo; }
  explicit operator int64_t() const { return neg ? (int64_t)((uint64_t)0 - lo) : (int64_t)lo; }
  explicit operator double() const {
    double m = (double)hi * 18446744073709551616.0 + (double)lo;
    return neg ? -m : m;
  }
};

}  // namespace cas
