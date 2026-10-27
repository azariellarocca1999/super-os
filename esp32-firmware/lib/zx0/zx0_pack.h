#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* ZX0 forward "standard" v2 stream -- identical to tools/bin/zx0 and decodable by dzx0_standard on the Z80.
 * Returns a malloc'ed buffer (free() it) or NULL; *out_len receives its size. */
uint8_t *zx0_pack(const uint8_t *in, size_t n, size_t *out_len);
#ifdef __cplusplus
}
#endif
