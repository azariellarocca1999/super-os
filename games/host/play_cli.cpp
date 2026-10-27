// Host build of the streamed-games engine (same sources as the ESP32 firmware) for the virtual ESP32 and the tests.
//   play_cli [roms_dir]       commands on stdin, answers on stdout (binary frames):
//     L                         -> "<n>\n<name>\n..."   titles: built-ins first, then *.gb / *.ch8 found in roms_dir
//     S <i>                     -> "OK\n" | "ERR\n"      start title i
//     F <keys> <dt_us> <full>   -> u16 length LE + frame data (see superplay.h)
//     Q                         quit
#include <stdio.h>
#include <string.h>
#include <string>
#include <vector>
#include <algorithm>
#include <dirent.h>
#include <fcntl.h>
#include <io.h>
#include "superplay.h"

using namespace superplay;

struct Title {
  std::string name;
  int kind;                 // 0 raycast, 1 chip8, 2 gb
  std::vector<uint8_t> rom;
};

static std::string up10(std::string s) {
  size_t dot = s.rfind('.');
  if (dot != std::string::npos) s = s.substr(0, dot);
  std::string o;
  for (char c : s) {
    if (c >= 'a' && c <= 'z') c = (char)(c - 32);
    if (c == '_' || c == ' ') c = '-';
    o += c;
  }
  return o.substr(0, 10);
}

int main(int argc, char **argv) {
  _setmode(_fileno(stdout), _O_BINARY);
  _setmode(_fileno(stdin), _O_BINARY);
  std::vector<Title> titles;
  titles.push_back({"MAZE 3D", 0, {}});
  if (argc > 1) {
    std::vector<std::string> files;
    if (DIR *d = opendir(argv[1])) {
      while (dirent *e = readdir(d)) files.push_back(e->d_name);
      closedir(d);
    }
    std::sort(files.begin(), files.end());
    for (auto &f : files) {
      size_t dot = f.rfind('.');
      if (dot == std::string::npos) continue;
      std::string ext = f.substr(dot);
      int kind = (ext == ".gb") ? 2 : (ext == ".ch8") ? 1 : 0;
      if (!kind) continue;
      std::string path = std::string(argv[1]) + "/" + f;
      FILE *fp = fopen(path.c_str(), "rb");
      if (!fp) continue;
      Title t;
      t.name = up10(f);
      t.kind = kind;
      uint8_t buf[4096];
      size_t n;
      while ((n = fread(buf, 1, sizeof buf, fp)) > 0) t.rom.insert(t.rom.end(), buf, buf + n);
      fclose(fp);
      titles.push_back(std::move(t));
    }
  }
  Player player;
  static uint8_t out[FB_BYTES + 8];
  char line[128];
  while (fgets(line, sizeof line, stdin)) {
    if (line[0] == 'Q') break;
    if (line[0] == 'L') {
      printf("%d\n", (int)titles.size());
      for (auto &t : titles) printf("%s\n", t.name.c_str());
      fflush(stdout);
    } else if (line[0] == 'S') {
      int i = atoi(line + 2);
      Core *c = nullptr;
      if (i >= 0 && i < (int)titles.size()) {
        Title &t = titles[i];
        if (t.kind == 0) c = make_raycast();
        else if (t.kind == 1) c = make_chip8(t.rom.data(), t.rom.size(), t.name.c_str());
        else c = make_gb(t.rom.data(), t.rom.size(), t.name.c_str());
      }
      if (c) { player.start(c); printf("OK\n"); } else printf("ERR\n");
      fflush(stdout);
    } else if (line[0] == 'F') {
      unsigned keys = 0, dt = 0, full = 0;
      sscanf(line + 2, "%u %u %u", &keys, &dt, &full);
      size_t n = player.running() ? player.frame((uint16_t)keys, dt, full != 0, out) : 0;
      uint8_t hdr[2] = {(uint8_t)(n & 255), (uint8_t)(n >> 8)};
      fwrite(hdr, 1, 2, stdout);
      fwrite(out, 1, n, stdout);
      fflush(stdout);
    }
  }
  return 0;
}
