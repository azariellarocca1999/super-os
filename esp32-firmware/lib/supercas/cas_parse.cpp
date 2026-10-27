// cas_parse.cpp -- text -> expression.  Commands (diff, int, solve, det, ...) are evaluated while parsing, so they nest freely.
#include <cctype>
#include <cmath>
#include <cstdlib>

#include "cas_int.h"
#include "cas_internal.h"

namespace cas {

E setOf(const std::vector<E> &items) { return mkFunc("set", items); }
E eqOf(E l, E r) { return mkFunc("eq", {l, r}); }
bool isMatrix(E e) { return e->k == MAT; }

namespace {

struct Parser {
  const std::string &s;
  size_t i = 0;
  explicit Parser(const std::string &text) : s(text) {}

  void ws() {
    while (i < s.size() && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r')) i++;
  }
  bool eat(char c) {
    ws();
    if (i < s.size() && s[i] == c) {
      i++;
      return true;
    }
    return false;
  }
  char peek() {
    ws();
    return i < s.size() ? s[i] : 0;
  }
  E fail(const std::string &m) {
    if (g_err.empty()) g_err = m;
    return nullptr;
  }

  E parseRelation() {
    E l = parseExpr();
    if (!l) return nullptr;
    if (peek() == '=') {
      i++;
      if (i < s.size() && s[i] == '=') i++;
      E r = parseExpr();
      if (!r) return nullptr;
      return eqOf(l, r);
    }
    return l;
  }

  E combine(char op, E a, E b) {
    bool ma = a->k == MAT, mb = b->k == MAT;
    if (!ma && !mb) {
      if (op == '+') return mkAdd({a, b});
      if (op == '-') return sub(a, b);
      if (op == '*') return mkMul({a, b});
      return div(a, b);
    }
    if (op == '+') return ma && mb ? matAdd(a, b) : (g_err = "cannot add a matrix and a scalar", nullptr);
    if (op == '-') return ma && mb ? matAdd(a, neg(b)) : (g_err = "cannot subtract a matrix and a scalar", nullptr);
    if (op == '*') {
      if (ma && mb) return matMul(a, b);
      E m = ma ? a : b, k = ma ? b : a;
      std::vector<E> el;
      for (E c : m->a) el.push_back(mkMul({k, c}));
      return mkMat(m->rows, m->cols, el);
    }
    if (mb) return (g_err = "cannot divide by a matrix (use inv)", nullptr);
    std::vector<E> el;
    for (E c : a->a) el.push_back(div(c, b));
    return mkMat(a->rows, a->cols, el);
  }

  E parseExpr() {
    E l = parseTerm();
    while (l) {
      char c = peek();
      if (c != '+' && c != '-') break;
      i++;
      E r = parseTerm();
      if (!r) return nullptr;
      l = combine(c, l, r);
      if (!l) return nullptr;
    }
    return l;
  }

  bool startsPrimary() {
    char c = peek();
    return isalpha((unsigned char)c) || c == '(' || c == '[' || c == '_';
  }

  E parseTerm() {
    E l = parseUnary();
    while (l) {
      char c = peek();
      if (c == '*' || c == '/') {
        i++;
        E r = parseUnary();
        if (!r) return nullptr;
        l = combine(c, l, r);
      } else if (startsPrimary()) {
        E r = parseUnary();
        if (!r) return nullptr;
        l = combine('*', l, r);
      } else
        break;
      if (!l) return nullptr;
    }
    return l;
  }

  E parseUnary() {
    char c = peek();
    if (c == '-') {
      i++;
      E v = parseUnary();
      if (!v) return nullptr;
      if (v->k == MAT) return combine('*', num(-1), v);
      return neg(v);
    }
    if (c == '+') {
      i++;
      return parseUnary();
    }
    return parsePower();
  }

  E parsePower() {
    E b = parsePostfix();
    if (!b) return nullptr;
    if (peek() == '^' || (peek() == '*' && i + 1 < s.size() && s[i + 1] == '*')) {
      if (s[i] == '*') i++;
      i++;
      E e = parseUnary();
      if (!e) return nullptr;
      return mkPow(b, e);
    }
    return b;
  }

  E parsePostfix() {
    E p = parsePrimary();
    while (p && peek() == '!' && !(i + 1 < s.size() && s[i + 1] == '=')) {
      i++;
      std::vector<E> fa = {p};
      E r = evalCall("fact", fa);
      p = r ? r : mkFunc("fact", fa);
    }
    return p;
  }

  static std::string lower(std::string t) {
    for (auto &c : t) c = (char)tolower((unsigned char)c);
    return t;
  }

  E parseNumber() {
    size_t st = i;
    std::string digits;
    int frac = 0;
    bool dot = false;
    while (i < s.size() && (isdigit((unsigned char)s[i]) || (s[i] == '.' && !dot))) {
      if (s[i] == '.')
        dot = true;
      else {
        digits += s[i];
        if (dot) frac++;
      }
      i++;
    }
    if (digits.empty()) {
      i = st;
      return fail("bad number");
    }
    int ex = 0;
    if (i < s.size() && s[i] == 'E') {
      size_t j = i + 1;
      bool neg_e = false;
      if (j < s.size() && (s[j] == '+' || s[j] == '-')) {
        neg_e = s[j] == '-';
        j++;
      }
      if (j < s.size() && isdigit((unsigned char)s[j])) {
        int v = 0;
        while (j < s.size() && isdigit((unsigned char)s[j])) v = v * 10 + (s[j++] - '0');
        ex = neg_e ? -v : v;
        i = j;
      }
    }
    // exact when it fits
    I128 n = 0;
    bool ok = true;
    for (char c : digits) {
      n = n * 10 + (c - '0');
      if (n > ((I128)1 << 62)) {
        ok = false;
        break;
      }
    }
    int e10 = ex - frac;
    if (ok && e10 >= -18 && e10 <= 18) {
      I128 dd = 1;
      if (e10 > 0) {
        for (int k = 0; k < e10; k++) n *= 10;
      } else
        for (int k = 0; k < -e10; k++) dd *= 10;
      Rat r;
      if (n < ((I128)1 << 62) && ratMake(n, dd, r)) return num(r.n, r.d);
    }
    return real(std::strtod((digits + "E" + std::to_string(e10)).c_str(), nullptr));
  }

  E parseMatrix() {
    // '[' already consumed
    std::vector<std::vector<E>> rows;
    ws();
    if (peek() == '[') {
      while (true) {
        if (!eat('[')) return fail("expected '['");
        std::vector<E> row;
        while (true) {
          E v = parseExpr();
          if (!v) return nullptr;
          row.push_back(v);
          if (eat(',')) continue;
          break;
        }
        if (!eat(']')) return fail("expected ']'");
        rows.push_back(row);
        if (eat(',')) continue;
        break;
      }
    } else {
      std::vector<E> row;
      while (true) {
        E v = parseExpr();
        if (!v) return nullptr;
        row.push_back(v);
        if (eat(',')) continue;
        break;
      }
      rows.push_back(row);
    }
    if (!eat(']')) return fail("expected ']'");
    size_t cols = rows[0].size();
    std::vector<E> el;
    for (auto &r : rows) {
      if (r.size() != cols) return fail("matrix rows differ in length");
      el.insert(el.end(), r.begin(), r.end());
    }
    return mkMat((int)rows.size(), (int)cols, el);
  }

  E parsePrimary() {
    char c = peek();
    if (!c) return fail("unexpected end of expression");
    if (isdigit((unsigned char)c) || c == '.') return parseNumber();
    if (c == '(') {
      i++;
      E v = parseRelation();
      if (!v) return nullptr;
      if (!eat(')')) return fail("missing ')'");
      return v;
    }
    if (c == '[') {
      i++;
      return parseMatrix();
    }
    if (isalpha((unsigned char)c) || c == '_') {
      size_t st = i;
      while (i < s.size() && (isalnum((unsigned char)s[i]) || s[i] == '_')) i++;
      std::string name = lower(s.substr(st, i - st));
      if (name == "arcsin") name = "asin";
      if (name == "arccos") name = "acos";
      if (name == "arctan") name = "atan";
      if (name == "integrate") name = "int";
      if (name == "derivative") name = "diff";
      if (name == "evalf" || name == "n") name = "approx";
      if (name == "infinity" || name == "inf") name = "oo";
      if (peek() == '(') {
        i++;
        std::vector<E> args;
        if (!eat(')')) {
          while (true) {
            E a = parseRelation();
            if (!a) return nullptr;
            args.push_back(a);
            if (eat(',')) continue;
            break;
          }
          if (!eat(')')) return fail("missing ')'");
        }
        E r = evalCall(name, args);
        if (g_err.size() && !r) return nullptr;
        if (r) return r;
        return mkFunc(name, args);
      }
      static const char *oneArg[] = {"sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
                                     "exp", "ln", "log", "sqrt", "cbrt", "abs", "sign", "floor", "ceil", nullptr};
      for (int k = 0; oneArg[k]; k++)
        if (name == oneArg[k]) {
          E a = parsePower();  // sin x, sin x^2 = sin(x^2)
          if (!a) return nullptr;
          return mkFunc(name, {a});
        }
      if (name == "pi" || name == "e" || name == "i" || name == "oo") return sym(name);
      return sym(name);
    }
    return fail(std::string("unexpected character '") + c + "'");
  }
};

}  // namespace

E parse(const std::string &text) {
  g_err.clear();
  Parser p(text);
  E r = p.parseRelation();
  if (!r) return nullptr;
  p.ws();
  if (p.i < text.size()) {
    g_err = std::string("unexpected '") + text[p.i] + "'";
    return nullptr;
  }
  return r;
}

}  // namespace cas
