// CHIP-8 core for streamed play of user ROMs (same semantics as tools/chip8.py and z80-os/games/chip8.z80).
#include <string.h>
#include "superplay.h"

namespace superplay {
namespace {
const uint8_t FONT[80] = {0xF0, 0x90, 0x90, 0x90, 0xF0, 0x20, 0x60, 0x20, 0x20, 0x70, 0xF0, 0x10, 0xF0, 0x80, 0xF0, 0xF0, 0x10, 0xF0, 0x10, 0xF0,
                          0x90, 0x90, 0xF0, 0x10, 0x10, 0xF0, 0x80, 0xF0, 0x10, 0xF0, 0xF0, 0x80, 0xF0, 0x90, 0xF0, 0xF0, 0x10, 0x20, 0x40, 0x40,
                          0xF0, 0x90, 0xF0, 0x90, 0xF0, 0xF0, 0x90, 0xF0, 0x10, 0xF0, 0xF0, 0x90, 0xF0, 0x90, 0x90, 0xE0, 0x90, 0xE0, 0x90, 0xE0,
                          0xF0, 0x80, 0x80, 0x80, 0xF0, 0xE0, 0x90, 0x90, 0x90, 0xE0, 0xF0, 0x80, 0xF0, 0x80, 0xF0, 0xF0, 0x80, 0xF0, 0x80, 0x80};

class Chip8Core : public Core {
 public:
  Chip8Core(const uint8_t *rom, size_t len, const char *nm) {
    memset(m, 0, sizeof m);
    memcpy(m + 0x50, FONT, 80);
    if (len > 4096 - 0x200) len = 4096 - 0x200;
    memcpy(m + 0x200, rom, len);
    memset(v, 0, sizeof v);
    memset(d, 0, sizeof d);
    pc = 0x200; i = 0; sp = 0; dt = st = 0; rng = 0xACE1; keys = 0; yield = false; ipsAcc = timAcc = 0;
    strncpy(nm_, nm, sizeof nm_ - 1);
    nm_[sizeof nm_ - 1] = 0;
  }
  const char *name() const override { return nm_; }

  void step(uint16_t k, uint32_t dt_us, uint8_t *fb) override {
    keys = k;
    if (dt_us > 250000) dt_us = 250000;
    ipsAcc += (uint64_t)dt_us * 700;          // 700 instructions per second
    timAcc += (uint64_t)dt_us * 60;           // 60 Hz timers
    int n = (int)(ipsAcc / 1000000);
    ipsAcc %= 1000000;
    yield = false;
    for (int c = 0; c < n && !yield; c++) exec();
    int ticks = (int)(timAcc / 1000000);
    timAcc %= 1000000;
    while (ticks-- > 0) {
      if (dt) dt--;
      if (st) st--;
    }
    render(fb);
  }

 private:
  uint8_t m[4096], v[16], d[32][8];
  uint16_t pc, i, stack[16], keys;
  int sp;
  uint8_t dt, st;
  uint16_t rng;
  bool yield;
  uint64_t ipsAcc, timAcc;
  char nm_[16];

  uint8_t rnd() {
    for (int k = 0; k < 8; k++) rng = (uint16_t)((rng >> 1) ^ ((rng & 1) ? 0xB400 : 0));
    return (uint8_t)rng;
  }
  void skip() { pc = (pc + 2) & 0xFFF; }
  void exec() {
    pc &= 0xFFF;
    uint16_t op = (uint16_t)(m[pc] << 8 | m[(pc + 1) & 0xFFF]);
    pc = (pc + 2) & 0xFFF;
    int x = op >> 8 & 15, y = op >> 4 & 15, n = op & 15, kk = op & 255, nnn = op & 0xFFF;
    switch (op >> 12) {
      case 0:
        if (op == 0x00E0) memset(d, 0, sizeof d);
        else if (op == 0x00EE && sp > 0) pc = stack[--sp];
        break;
      case 1: pc = (uint16_t)nnn; break;
      case 2: if (sp < 16) stack[sp++] = pc; pc = (uint16_t)nnn; break;
      case 3: if (v[x] == kk) skip(); break;
      case 4: if (v[x] != kk) skip(); break;
      case 5: if (v[x] == v[y]) skip(); break;
      case 6: v[x] = (uint8_t)kk; break;
      case 7: v[x] = (uint8_t)(v[x] + kk); break;
      case 8: {
        uint8_t a = v[x], b = v[y];
        int s;
        switch (n) {
          case 0: v[x] = b; break;
          case 1: v[x] = a | b; break;
          case 2: v[x] = a & b; break;
          case 3: v[x] = a ^ b; break;
          case 4: s = a + b; v[x] = (uint8_t)s; v[15] = s > 255; break;
          case 5: v[x] = (uint8_t)(a - b); v[15] = a >= b; break;
          case 6: v[x] = b >> 1; v[15] = b & 1; break;
          case 7: v[x] = (uint8_t)(b - a); v[15] = b >= a; break;
          case 14: v[x] = (uint8_t)(b << 1); v[15] = b >> 7; break;
        }
        break;
      }
      case 9: if (v[x] != v[y]) skip(); break;
      case 10: i = (uint16_t)nnn; break;
      case 11: pc = (uint16_t)((nnn + v[0]) & 0xFFF); break;
      case 12: v[x] = rnd() & kk; break;
      case 13: {
        int px = v[x] & 63, py = v[y] & 31;
        v[15] = 0;
        for (int r = 0; r < n; r++) {
          int yy = py + r;
          if (yy > 31) break;
          uint8_t bits = m[(i + r) & 0xFFF];
          for (int c = 0; c < 8; c++) {
            int xx = px + c;
            if (xx > 63) break;
            if (bits >> (7 - c) & 1) {
              uint8_t &byte = d[yy][xx >> 3];
              uint8_t mask = (uint8_t)(0x80 >> (xx & 7));
              if (byte & mask) v[15] = 1;
              byte ^= mask;
            }
          }
        }
        break;
      }
      case 14: {
        bool held = keys >> (v[x] & 15) & 1;
        if ((kk == 0x9E && held) || (kk == 0xA1 && !held)) skip();
        break;
      }
      case 15:
        switch (kk) {
          case 0x07: v[x] = dt; yield = true; break;
          case 0x0A:
            if (keys) { int b = 0; while (!(keys >> b & 1)) b++; v[x] = (uint8_t)b; }
            else pc = (uint16_t)((pc - 2) & 0xFFF);
            break;
          case 0x15: dt = v[x]; break;
          case 0x18: st = v[x]; break;
          case 0x1E: i = (uint16_t)((i + v[x]) & 0xFFF); break;
          case 0x29: i = (uint16_t)(0x50 + 5 * (v[x] & 15)); break;
          case 0x33: m[i & 0xFFF] = v[x] / 100; m[(i + 1) & 0xFFF] = v[x] / 10 % 10; m[(i + 2) & 0xFFF] = v[x] % 10; break;
          case 0x55: for (int r = 0; r <= x; r++) m[(i + r) & 0xFFF] = v[r]; i = (uint16_t)((i + x + 1) & 0xFFF); break;
          case 0x65: for (int r = 0; r <= x; r++) v[r] = m[(i + r) & 0xFFF]; i = (uint16_t)((i + x + 1) & 0xFFF); break;
        }
        break;
    }
  }
  void render(uint8_t *fb) {
    fb_clear(fb);
    for (int r = 0; r < 32; r++)
      for (int b = 0; b < 8; b++) {
        fb[(2 * r) * 12 + 2 + b] = d[r][b];
        fb[(2 * r + 1) * 12 + 2 + b] = d[r][b];
      }
    if (st) { fb[0] = fb[12] = 0xFF; }
  }
};
}  // namespace

Core *make_chip8(const uint8_t *rom, size_t len, const char *name) { return new Chip8Core(rom, len, name); }
}  // namespace superplay
