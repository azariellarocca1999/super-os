#include "superplay.h"
#include <string.h>

namespace superplay {
const uint8_t BAYER4[4][4] = {{0, 8, 2, 10}, {12, 4, 14, 6}, {3, 11, 1, 9}, {15, 7, 13, 5}};

size_t encode_frame(const uint8_t *prev, const uint8_t *cur, uint8_t *out, bool full) {
  if (full || !prev) {
    out[0] = 2;
    memcpy(out + 1, cur, FB_BYTES);
    return 1 + FB_BYTES;
  }
  uint8_t bitmap[12] = {0};
  int n = 0;
  uint8_t *tiles = out + 13;
  for (int t = 0; t < 96; t++) {
    int ty = t / 12, tx = t % 12;
    bool diff = false;
    for (int r = 0; r < 8; r++)
      if (prev[(ty * 8 + r) * 12 + tx] != cur[(ty * 8 + r) * 12 + tx]) { diff = true; break; }
    if (!diff) continue;
    bitmap[t >> 3] |= (uint8_t)(1 << (t & 7));
    for (int r = 0; r < 8; r++) *tiles++ = cur[(ty * 8 + r) * 12 + tx];
    n++;
  }
  if (n == 0) { out[0] = 0; return 1; }
  out[0] = 1;
  memcpy(out + 1, bitmap, 12);
  return 13 + (size_t)n * 8;
}

void apply_frame(uint8_t *fb, const uint8_t *d, size_t len) {
  if (!len) return;
  if (d[0] == 2 && len >= 1 + FB_BYTES) { memcpy(fb, d + 1, FB_BYTES); return; }
  if (d[0] != 1 || len < 13) return;
  const uint8_t *tiles = d + 13;
  for (int t = 0; t < 96; t++) {
    if (!(d[1 + (t >> 3)] >> (t & 7) & 1)) continue;
    int ty = t / 12, tx = t % 12;
    for (int r = 0; r < 8; r++) fb[(ty * 8 + r) * 12 + tx] = *tiles++;
  }
}

void Player::start(Core *c) {
  delete core_;
  core_ = c;
  have_prev_ = false;
  fb_clear(cur_);
  fb_clear(prev_);
}
void Player::stop() {
  delete core_;
  core_ = nullptr;
}
size_t Player::frame(uint16_t keys, uint32_t dt_us, bool want_full, uint8_t *out) {
  if (!core_) return 0;
  memcpy(prev_, cur_, FB_BYTES);
  core_->step(keys, dt_us, cur_);
  size_t n = encode_frame(prev_, cur_, out, want_full || !have_prev_);
  have_prev_ = true;
  return n;
}
}  // namespace superplay
