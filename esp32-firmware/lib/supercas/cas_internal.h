// Internal declarations shared between the CAS translation units.
#pragma once
#include "cas.h"

namespace cas {
// evaluates a command / function call at parse time; nullptr = not a command (becomes an ordinary function node)
E evalCall(const std::string &name, std::vector<E> &args);
bool isMatrix(E e);
E setOf(const std::vector<E> &items);   // FUNC "set"
E eqOf(E l, E r);                       // FUNC "eq"
E ratToE(int64_t n, int64_t d);
}  // namespace cas
