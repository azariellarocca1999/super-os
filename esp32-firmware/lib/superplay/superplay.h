// Streamed games for Super-OS: the ESP32 runs the game, the calculator is a video terminal and gamepad.
// Frame = 96x64 1-bit in the calculator's LCD layout (768 bytes, 12 bytes per row, bit 7 = leftmost pixel, 1 = dark).
// Keys = 16-bit mask, bit n = CHIP-8 key n (the calculator's number pad mirrors the CHIP-8 keypad, arrows = 2/4/6/8, ENTER = 5).
#pragma once
#include <stddef.h>
#include <stdint.h>

namespace superplay {
constexpr int FB_W = 96, FB_H = 64, FB_BYTES = 768;

class Core {
 public:
  virtual ~Core() {}
  virtual const char *name() const = 0;
  // advance the game by dt_us of game time (the calculator paces the stream) and render into fb
  virtual void step(uint16_t keys, uint32_t dt_us, uint8_t *fb) = 0;
};

Core *make_raycast();
Core *make_chip8(const uint8_t *rom, size_t len, const char *name);   // copies the ROM
Core *make_gb(const uint8_t *rom, size_t len, const char *name);      // keeps a pointer to the ROM (must outlive the core)

// ---- frame codec ----------------------------------------------------------------------------------------------
//  [0]                          frame unchanged
//  [1][bitmap x12][8 bytes x n] tiles of 8 rows x 8 pixels that changed (tile t = row_of_tiles * 12 + column, bit t of the
//                               bitmap, LSB first); each tile = the 8 bytes of its column, top row first
//  [2][768 bytes]               full frame
size_t encode_frame(const uint8_t *prev, const uint8_t *cur, uint8_t *out, bool full);
void apply_frame(uint8_t *fb, const uint8_t *data, size_t len);   // inverse (host tests and the reference for the Z80 decoder)

// One running game + delta encoder
class Player {
 public:
  Player() : core_(nullptr), have_prev_(false) {}
  ~Player() { delete core_; }
  void start(Core *c);                       // takes ownership
  bool running() const { return core_ != nullptr; }
  const char *name() const { return core_ ? core_->name() : ""; }
  size_t frame(uint16_t keys, uint32_t dt_us, bool want_full, uint8_t *out);   // step + encode; out >= 769 bytes
  const uint8_t *picture() const { return cur_; }
  void stop();
 private:
  Core *core_;
  bool have_prev_;
  uint8_t cur_[FB_BYTES], prev_[FB_BYTES];
};

// Helpers shared by the cores
inline void fb_clear(uint8_t *fb) { for (int i = 0; i < FB_BYTES; i++) fb[i] = 0; }
inline void fb_set(uint8_t *fb, int x, int y, bool on) {
  if ((unsigned)x >= FB_W || (unsigned)y >= FB_H) return;
  uint8_t m = (uint8_t)(0x80 >> (x & 7));
  uint8_t &b = fb[y * 12 + (x >> 3)];
  if (on) b |= m; else b &= (uint8_t)~m;
}
inline bool fb_get(const uint8_t *fb, int x, int y) { return (fb[y * 12 + (x >> 3)] >> (7 - (x & 7))) & 1; }
extern const uint8_t BAYER4[4][4];           // ordered-dither thresholds 0..15
}  // namespace superplay
