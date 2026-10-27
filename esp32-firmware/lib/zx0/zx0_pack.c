/* Thin wrapper over Einar Saukas' ZX0 optimal compressor (BSD-3, see LICENSE). */
#include "zx0_pack.h"
#include <stdlib.h>
#include <string.h>
#include "zx0.h"

#define MAX_OFFSET_ZX0 32640

uint8_t *zx0_pack(const uint8_t *in, size_t n, size_t *out_len)
{
    int out_size = 0, delta = 0;
    static const uint8_t nul = 0;
    if (n == 0) {           /* the reference optimizer returns optimal[n - 1] (optimal[-1]) for 0 bytes: send one NUL instead (an empty text) */
        in = &nul;
        n = 1;
    }
    unsigned char *copy = (unsigned char *)malloc(n);
    if (!copy) return NULL;
    memcpy(copy, in, n);
    BLOCK *opt = optimize(copy, (int)n, 0, MAX_OFFSET_ZX0);
    unsigned char *res = compress(opt, copy, (int)n, 0, 0, 1, &out_size, &delta);
    free(copy);
    *out_len = (size_t)out_size;
    return res;
}
