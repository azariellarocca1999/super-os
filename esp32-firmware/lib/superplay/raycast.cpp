// "MAZE 3D": an original DDA raycaster written for Super-OS (no id Software code or assets).
// 96x64 1-bit output: walls are ordered-dithered by distance, brick pattern on '=' walls, dotted floor.
#include <math.h>
#include <string.h>
#include "superplay.h"

namespace superplay {
namespace {
const char *const MAP[16] = {
    "################",
    "#..............#",
    "#.####..#####..#",
    "#.#..#..#...#..#",
    "#.#..=..#...#..#",
    "#.#..#..#...#..#",
    "#.##=#..##=###.#",
    "#..............#",
    "#.#####.######.#",
    "#.#...#......#.#",
    "#.#...=..##..#.#",
    "#.#...#..##..#.#",
    "#.##=##......#.#",
    "#.............##",
    "#..###..=...#..#",
    "################",
};
inline char cell(int x, int y) { return (x < 0 || y < 0 || x > 15 || y > 15) ? '#' : MAP[y][x]; }
inline bool solid(int x, int y) { return cell(x, y) != '.'; }

class Raycast : public Core {
 public:
  Raycast() : px_(7.5f), py_(7.5f), pa_(0.0f), minimap_(false), prev_keys_(0), t_(0) {}
  const char *name() const override { return "MAZE 3D"; }
  void step(uint16_t keys, uint32_t dt_us, uint8_t *fb) override {
    float dt = dt_us / 1e6f;
    if (dt > 0.25f) dt = 0.25f;
    const float move = 3.2f * dt, turn = 2.4f * dt;
    if (keys & (1 << 4)) pa_ -= turn;                // 4 = turn left
    if (keys & (1 << 6)) pa_ += turn;                // 6 = turn right
    float dx = cosf(pa_), dy = sinf(pa_);
    float vx = 0, vy = 0;
    if (keys & (1 << 2)) { vx += dx * move; vy += dy * move; }      // 2 = forward
    if (keys & (1 << 8)) { vx -= dx * move; vy -= dy * move; }      // 8 = back
    if (keys & (1 << 1)) { vx += dy * move; vy -= dx * move; }      // 1 = strafe left
    if (keys & (1 << 3)) { vx -= dy * move; vy += dx * move; }      // 3 = strafe right
    const float r = 0.22f;                                          // collision radius
    if (!solid((int)(px_ + vx + (vx > 0 ? r : -r)), (int)py_)) px_ += vx;
    if (!solid((int)px_, (int)(py_ + vy + (vy > 0 ? r : -r)))) py_ += vy;
    if ((keys & (1 << 5)) && !(prev_keys_ & (1 << 5))) minimap_ = !minimap_;   // 5 = map
    prev_keys_ = keys;
    t_ += dt_us;
    render(fb);
  }

 private:
  float px_, py_, pa_;
  bool minimap_;
  uint16_t prev_keys_;
  uint32_t t_;

  void render(uint8_t *fb) {
    fb_clear(fb);
    const float dirx = cosf(pa_), diry = sinf(pa_);
    const float planex = -diry * 0.95f, planey = dirx * 0.95f;      // ~87 degree field of view
    for (int x = 0; x < FB_W; x++) {
      float camx = 2.0f * (x + 0.5f) / FB_W - 1.0f;
      float rx = dirx + planex * camx, ry = diry + planey * camx;
      int mx = (int)floorf(px_), my = (int)floorf(py_);
      float ddx = rx == 0 ? 1e30f : fabsf(1.0f / rx), ddy = ry == 0 ? 1e30f : fabsf(1.0f / ry);
      int sx, sy;
      float sdx, sdy;
      if (rx < 0) { sx = -1; sdx = (px_ - mx) * ddx; } else { sx = 1; sdx = (mx + 1.0f - px_) * ddx; }
      if (ry < 0) { sy = -1; sdy = (py_ - my) * ddy; } else { sy = 1; sdy = (my + 1.0f - py_) * ddy; }
      int side = 0;
      for (int guard = 0; guard < 40; guard++) {
        if (sdx < sdy) { sdx += ddx; mx += sx; side = 0; } else { sdy += ddy; my += sy; side = 1; }
        if (solid(mx, my)) break;
      }
      float dist = side == 0 ? (mx - px_ + (1 - sx) * 0.5f) / rx : (my - py_ + (1 - sy) * 0.5f) / ry;
      if (dist < 0.05f) dist = 0.05f;
      float wallx = side == 0 ? py_ + dist * ry : px_ + dist * rx;
      wallx -= floorf(wallx);
      int h = (int)(FB_H * 0.65f / dist);
      int y0 = FB_H / 2 - h / 2, y1 = FB_H / 2 + h / 2;
      bool brick = cell(mx, my) == '=';
      float shade = 0.92f - 0.085f * dist - (side ? 0.22f : 0.0f);
      if (shade < 0.12f) shade = 0.12f;
      if (shade > 1.0f) shade = 1.0f;
      for (int y = 0; y < FB_H; y++) {
        bool on;
        if (y >= y0 && y < y1) {
          float s = shade;
          if (brick) {                                                // brick courses: mortar lines stay light
            float ty = (float)(y - y0) / (float)(h > 0 ? h : 1) * 4.0f;
            float row = floorf(ty);
            float fy = ty - row;
            float u = wallx * 2.0f + ((int)row & 1) * 0.5f;
            float fx = u - floorf(u);
            if (fy < 0.12f || fx < 0.06f) s *= 0.2f;
          }
          on = s * 16.0f > BAYER4[y & 3][x & 3] + 0.5f;
        } else if (y >= y1) {                                         // floor: sparse dots fading with distance
          float rowd = (FB_H * 0.45f) / (float)(y - FB_H / 2 + 1);
          float fs = 0.30f - 0.03f * rowd;
          on = fs > 0 && fs * 16.0f > BAYER4[y & 3][x & 3] + 0.5f;
        } else {
          on = false;                                                 // ceiling: clear
        }
        if (on) fb_set(fb, x, y, true);
      }
    }
    if (minimap_) {                                                   // 16x16 map in the corner, player blinks
      for (int y = 0; y < 18; y++)
        for (int x = 0; x < 18; x++) fb_set(fb, x, y, false);
      for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++)
          if (solid(x, y)) fb_set(fb, 1 + x, 1 + y, true);
      if ((t_ / 250000) & 1) fb_set(fb, 1 + (int)px_, 1 + (int)py_, true); else fb_set(fb, 1 + (int)px_, 1 + (int)py_, false);
    }
  }
};
}  // namespace

Core *make_raycast() { return new Raycast(); }
}  // namespace superplay
