// Super-CAS: a small computer algebra system (exact rationals, symbolic differentiation / integration, Taylor series,
// limits, equation solving, polynomial factoring, matrices, numeric fallbacks and a 3D surface renderer).
// Pure C++17 without exceptions or RTTI, so the same sources build for the host (tests, virtual ESP32) and the ESP32-S3 firmware.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace cas {

enum Kind : uint8_t { NUM = 0, REAL = 1, SYM = 2, ADD = 3, MUL = 4, POW = 5, FUNC = 6, MAT = 7 };

struct Node {
  Kind k = NUM;
  int64_t n = 0, d = 1;        // NUM: exact rational n/d (d > 0, lowest terms)
  double r = 0;                // REAL
  std::string s;               // SYM / FUNC name
  std::vector<const Node *> a; // ADD/MUL: operands, POW: {base, exponent}, FUNC: arguments, MAT: row-major elements
  int rows = 0, cols = 0;      // MAT
};
typedef const Node *E;

// ---- memory / errors ---------------------------------------------------------------------------------------------
void reset();                  // drop every node (call between independent commands)
extern std::string g_err;      // last error message ("" = none)
extern bool g_asc;             // print sums in ascending order (series)
bool failed();

// ---- constructors (all results are kept in canonical, auto-simplified form) -----------------------------------------
E num(int64_t n, int64_t d = 1);
E real(double v);
E sym(const std::string &name);
E mkAdd(std::vector<E> t);
E mkMul(std::vector<E> f);
E mkPow(E b, E e);
E mkFunc(const std::string &name, std::vector<E> args);
E mkMat(int rows, int cols, std::vector<E> el);
inline E add(E a, E b) { return mkAdd({a, b}); }
inline E mul(E a, E b) { return mkMul({a, b}); }
E neg(E a);
E sub(E a, E b);
E div(E a, E b);
E powi(E b, int64_t e);
E func1(const std::string &name, E x);

// ---- inspection -------------------------------------------------------------------------------------------------------
bool isNum(E e);               // exact rational constant
bool isInt(E e);
bool isZero(E e);
bool isOne(E e);
bool isNumeric(E e);           // NUM or REAL
double toDouble(E e);          // NUM / REAL only
int cmp(E a, E b);
bool equal(E a, E b);
bool contains(E e, const std::string &var);
bool isFunc(E e, const char *name);
void freeSyms(E e, std::vector<std::string> &out);
E subs(E e, E from, E to);     // structural substitution (rebuilds in canonical form)
E mapChildren(E e, E (*fn)(E, void *), void *ctx);

// ---- text ---------------------------------------------------------------------------------------------------------------
E parse(const std::string &text);                 // nullptr + g_err on error
std::string toString(E e);

// ---- algebra --------------------------------------------------------------------------------------------------------------
E expand(E e);
E simplify(E e);
E together(E e);                                  // common denominator
bool polyCoeffs(E f, const std::string &x, std::vector<E> &c); // f = sum c[k] x^k (c free of x), after expansion
E fromCoeffs(const std::vector<E> &c, E x);
E factorExpr(E e);                                // integers and polynomials over Q
std::vector<E> solveEq(E eq, const std::string &x, bool *numeric = nullptr);
std::string solveSystem(const std::vector<E> &eqs, const std::vector<std::string> &vars);

// ---- calculus -----------------------------------------------------------------------------------------------------------------
E diff(E f, const std::string &x);
E diffN(E f, const std::string &x, int n);
E integrate(E f, const std::string &x);           // nullptr when no antiderivative was found
E taylor(E f, const std::string &x, E x0, int n);
E limit(E f, const std::string &x, E a, bool *approx = nullptr);

// ---- numeric ----------------------------------------------------------------------------------------------------------------------
struct Env {
  std::vector<std::pair<std::string, double>> v;
  void set(const std::string &k, double x);
};
bool evalD(E e, const Env &env, double &out);
double numericIntegral(E f, const std::string &x, double a, double b);
E approxExpr(E e);                                // exact -> REAL where possible

// ---- matrices ----------------------------------------------------------------------------------------------------------------------
E matDet(E m);
E matInv(E m);
E matTranspose(E m);
E matMul(E a, E b);
E matAdd(E a, E b);
E matPow(E a, int64_t n);
E matEigenvalues(E m);

// ---- 3D plot ---------------------------------------------------------------------------------------------------------------------------
// renders z = f(x, y) on a 96x64 1-bit bitmap (12 bytes per row, MSB first = the calculator frame buffer layout)
bool plot3d(E f, double x0, double x1, double y0, double y1, uint8_t *bitmap768);

// ---- command front end ---------------------------------------------------------------------------------------------------------------
// One text command ("diff(sin(x)*x,x)", "solve(x^2-2=0,x)", "int(x*exp(x),x)", "det([[1,2],[3,4]])", ...) -> text result.
std::string runCommand(const std::string &text);
// "plot3d(f(x,y),x0,x1,y0,y1)" -> true and the bitmap when the command is a 3D plot request
bool runPlot3d(const std::string &text, uint8_t *bitmap768, std::string &err);

}  // namespace cas
