/* Forced into the ZX0 sources by the host test (gcc -include): counts the live heap bytes and can make the N-th allocation fail. */
#ifndef ZX0_COUNT_H
#define ZX0_COUNT_H
#include <stdlib.h>
void *cnt_malloc(size_t n);
void *cnt_calloc(size_t k, size_t n);
void cnt_free(void *p);
#define malloc(n) cnt_malloc(n)
#define calloc(k, n) cnt_calloc(k, n)
#define free(p) cnt_free(p)
#endif
