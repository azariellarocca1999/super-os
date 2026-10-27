// Game Boy core: Peanut-GB (MIT, https://github.com/deltabeard/Peanut-GB) rendered to the calculator screen, 96x64 1-bit.
// 160x144 -> 96x64 by box-averaging the 4-level pixels and ordered dithering.  No sound.  The ROM is supplied by the user.
#include <string.h>
#include <stdlib.h>
#define ENABLE_SOUND 0
#define ENABLE_LCD 1
#define PEANUT_GB_HIGH_LCD_ACCURACY 0
#include "peanut_gb.h"
#include "superplay.h"

namespace superplay {
namespace {
class GbCore : public Core {
 public:
  GbCore(const uint8_t *rom, size_t len, const char *nm) : rom_(rom), len_(len), ok_(false), frames_acc_(0) {
    strncpy(nm_, nm, sizeof nm_ - 1);
    nm_[sizeof nm_ - 1] = 0;
    memset(acc_, 0, sizeof acc_);
    memset(cnt_, 0, sizeof cnt_);
    memset(ram_, 0xFF, sizeof ram_);
    if (gb_init(&gb_, &GbCore::rom_read, &GbCore::ram_read, &GbCore::ram_write, &GbCore::err, this) == GB_INIT_NO_ERROR) {
      gb_init_lcd(&gb_, &GbCore::line);
      ok_ = true;
    }
  }
  const char *name() const override { return nm_; }
  bool ok() const { return ok_; }

  void step(uint16_t keys, uint32_t dt_us, uint8_t *fb) override {
    if (!ok_) { fb_clear(fb); return; }
    // joypad bits are active low: 0 A, 1 B, 2 Select, 3 Start, 4 Right, 5 Left, 6 Up, 7 Down
    uint8_t j = 0xFF;
    if (keys & (1 << 5)) j &= (uint8_t)~(1 << 0);       // 5 / ENTER = A
    if (keys & (1 << 7)) j &= (uint8_t)~(1 << 1);       // 7 (calculator 1) = B
    if (keys & (1 << 1)) j &= (uint8_t)~(1 << 2);       // 1 (calculator 7) = Select
    if (keys & (1 << 9)) j &= (uint8_t)~(1 << 3);       // 9 (calculator 3) = Start
    if (keys & (1 << 6)) j &= (uint8_t)~(1 << 4);       // 6 = Right
    if (keys & (1 << 4)) j &= (uint8_t)~(1 << 5);       // 4 = Left
    if (keys & (1 << 2)) j &= (uint8_t)~(1 << 6);       // 2 = Up
    if (keys & (1 << 8)) j &= (uint8_t)~(1 << 7);       // 8 = Down
    gb_.direct.joypad = j;
    frames_acc_ += (uint64_t)dt_us * 60;                // run as many 60 fps frames as the game time asks for (1..6)
    int n = (int)(frames_acc_ / 1000000);
    frames_acc_ %= 1000000;
    if (n < 1) n = 1;
    if (n > 6) n = 6;
    for (int k = 0; k < n; k++) {
      if (k == n - 1) { memset(acc_, 0, sizeof acc_); memset(cnt_, 0, sizeof cnt_); }
      gb_run_frame(&gb_);
    }
    fb_clear(fb);
    for (int y = 0; y < FB_H; y++)
      for (int x = 0; x < FB_W; x++) {
        int c = cnt_[y][x];
        float dark = c ? (float)acc_[y][x] / (3.0f * c) : 0.0f;       // 0 = white .. 1 = black
        if (dark * 16.0f > BAYER4[y & 3][x & 3] + 0.5f) fb_set(fb, x, y, true);
      }
  }

 private:
  struct gb_s gb_;
  const uint8_t *rom_;
  size_t len_;
  bool ok_;
  uint64_t frames_acc_;
  uint16_t acc_[FB_H][FB_W];
  uint8_t cnt_[FB_H][FB_W];
  uint8_t ram_[32768];
  char nm_[16];

  static uint8_t rom_read(struct gb_s *gb, const uint_fast32_t a) {
    GbCore *s = (GbCore *)gb->direct.priv;
    return a < s->len_ ? s->rom_[a] : 0xFF;
  }
  static uint8_t ram_read(struct gb_s *gb, const uint_fast32_t a) { return ((GbCore *)gb->direct.priv)->ram_[a & 0x7FFF]; }
  static void ram_write(struct gb_s *gb, const uint_fast32_t a, const uint8_t v) { ((GbCore *)gb->direct.priv)->ram_[a & 0x7FFF] = v; }
  static void err(struct gb_s *gb, const enum gb_error_e e, const uint16_t v) { (void)gb; (void)e; (void)v; }
  static void line(struct gb_s *gb, const uint8_t *pixels, const uint_fast8_t y) {
    GbCore *s = (GbCore *)gb->direct.priv;
    int oy = y * FB_H / 144;
    for (int x = 0; x < 160; x++) {
      int ox = x * FB_W / 160;
      s->acc_[oy][ox] = (uint16_t)(s->acc_[oy][ox] + (pixels[x] & 3));
      if (s->cnt_[oy][ox] < 255) s->cnt_[oy][ox]++;
    }
  }
};
}  // namespace

Core *make_gb(const uint8_t *rom, size_t len, const char *name) {
  GbCore *c = new GbCore(rom, len, name);
  if (!c->ok()) { delete c; return nullptr; }
  return c;
}
}  // namespace superplay
