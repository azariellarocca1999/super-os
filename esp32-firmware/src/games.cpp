#include "games.h"
#include <LittleFS.h>
#include <vector>
#include "superplay.h"
#include "dmg_acid2.h"

namespace games {
struct Title {
  String name;
  int kind;       // 0 maze, 1 chip8 file, 2 gb file, 3 built-in gb
  String path;
};
static std::vector<Title> titles;
static superplay::Player player;
static uint8_t *rom_buf = nullptr;
static uint32_t last_us = 0;
static bool have_last = false;

static String short_name(String f) {
  int dot = f.lastIndexOf('.');
  if (dot > 0) f = f.substring(0, dot);
  f.toUpperCase();
  f.replace('_', '-');
  f.replace(' ', '-');
  return f.substring(0, 10);
}

String list() {
  titles.clear();
  titles.push_back({"MAZE 3D", 0, ""});
  titles.push_back({"DMG-ACID2", 3, ""});
  File dir = LittleFS.open("/roms");
  if (dir) {
    for (File f = dir.openNextFile(); f && titles.size() < 10; f = dir.openNextFile()) {
      String n = f.name();
      String l = n;
      l.toLowerCase();
      int kind = l.endsWith(".gb") ? 2 : l.endsWith(".ch8") ? 1 : 0;
      if (kind) titles.push_back({short_name(n), kind, "/roms/" + n});
    }
  }
  String out;
  for (auto &t : titles) out += t.name + "\n";
  return out;
}

void stop() {
  player.stop();
  if (rom_buf) { free(rom_buf); rom_buf = nullptr; }
  have_last = false;
}
bool running() { return player.running(); }

bool start(int index) {
  stop();
  if (titles.empty()) list();
  if (index < 0 || index >= (int)titles.size()) return false;
  Title &t = titles[index];
  superplay::Core *c = nullptr;
  if (t.kind == 0) {
    c = superplay::make_raycast();
  } else if (t.kind == 3) {
    c = superplay::make_gb(DMG_ACID2, sizeof DMG_ACID2, t.name.c_str());
  } else {
    File f = LittleFS.open(t.path);
    if (!f) return false;
    size_t n = f.size();
    rom_buf = (uint8_t *)(psramFound() ? ps_malloc(n ? n : 1) : malloc(n ? n : 1));
    if (!rom_buf) return false;
    f.read(rom_buf, n);
    c = t.kind == 1 ? superplay::make_chip8(rom_buf, n, t.name.c_str()) : superplay::make_gb(rom_buf, n, t.name.c_str());
  }
  if (!c) { stop(); return false; }
  player.start(c);
  return true;
}

size_t frame(uint16_t keys, bool want_full, uint8_t *out) {
  uint32_t now = micros();
  uint32_t dt = have_last ? now - last_us : 100000;
  if (dt > 250000) dt = 250000;
  last_us = now;
  have_last = true;
  return player.frame(keys, dt, want_full, out);
}
}  // namespace games
