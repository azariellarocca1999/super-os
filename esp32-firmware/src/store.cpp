#include "store.h"
#include <ESPmDNS.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <vector>
#include "services.h"

namespace store {
static WiFiServer server(80);
static uint32_t window_until = 0;
static bool server_started = false;

static void drop_parts(const char *dir) {                                      // uploads cut by a reset / power loss
  File d = LittleFS.open(dir);
  if (!d) return;
  std::vector<String> dead;
  for (File f = d.openNextFile(); f; f = d.openNextFile())
    if (String(f.name()).endsWith(".part")) dead.push_back(String(dir) + "/" + f.name());
  for (const String &n : dead) LittleFS.remove(n);
}

void begin() {
  LittleFS.begin(true);
  drop_parts("/store");
  drop_parts("/roms");
}

static bool valid_name(const String &n) {
  if (n.length() < 1 || n.length() > 8) return false;
  for (size_t i = 0; i < n.length(); i++)
    if (!isalnum((unsigned char)n[i]) && n[i] != '_') return false;
  return true;
}

String list() {
  String out;
  File dir = LittleFS.open("/store");
  if (dir) {
    for (File f = dir.openNextFile(); f; f = dir.openNextFile()) {
      String n = f.name();
      if (n.endsWith(".bin")) out += n.substring(0, n.length() - 4) + "|" + String((unsigned)f.size()) + "\n";
      else if (n.endsWith(".c8")) out += n.substring(0, n.length() - 3) + "|" + String((unsigned)f.size()) + "|8\n";   // CHIP-8 game
    }
  }
  return out;
}

bool get(const String &name, uint8_t **data, size_t *len) {
  File f = LittleFS.open("/store/" + name + ".bin");
  if (!f) f = LittleFS.open("/store/" + name + ".c8");
  if (!f) return false;
  *len = f.size();
  *data = (uint8_t *)malloc(*len ? *len : 1);
  if (!*data) return false;
  f.read(*data, *len);
  return true;
}

String start_upload_window(uint32_t seconds) {
  if (!services::wifi_up(10000)) return "NO WIFI: SET IT IN WIFI+API";
  if (!server_started) {
    server.begin();
    MDNS.begin("superos-esp");
    server_started = true;
  }
  window_until = millis() + seconds * 1000UL;
  return "UPLOAD WINDOW " + String(seconds) + " S\nIP " + WiFi.localIP().toString() + "\nSUPEROS-ESP.LOCAL\nPOST /UPLOAD?NAME=XXXX\nTOOLS/OTA_PUSH.PY";
}

bool upload_window_open() { return server_started && (int32_t)(window_until - millis()) > 0; }

// One header line, at most `cap` characters kept, under a deadline shared by the whole request head.  false = deadline / disconnect.
static bool read_line(WiFiClient &c, String &out, size_t cap, uint32_t deadline) {
  out = "";
  while ((int32_t)(deadline - millis()) > 0 && c.connected()) {
    int ch = c.read();
    if (ch < 0) { delay(2); continue; }
    if (ch == '\n') return true;
    if (out.length() < cap) out += (char)ch;                                   // longer lines are truncated, never buffered whole
  }
  return false;
}

// Minimal raw HTTP: POST /upload?name=NAME with Content-Length and a binary body.
void poll() {
  if (!upload_window_open()) return;
  WiFiClient c = server.accept();
  if (!c) return;
  uint32_t head_deadline = millis() + 5000UL;                                  // request line + headers: 5 s in total (slow-loris bound)
  String req;
  bool head_ok = read_line(c, req, 200, head_deadline);
  size_t clen = 0;
  for (int hdrs = 0; head_ok && hdrs < 24; hdrs++) {
    String h;
    head_ok = read_line(c, h, 200, head_deadline);
    if (!head_ok || h.length() <= 1) break;
    h.toLowerCase();
    if (h.startsWith("content-length:")) clen = h.substring(15).toInt();
  }
  if (!head_ok) {
    c.print("HTTP/1.1 408 Request Timeout\r\nContent-Length: 0\r\n\r\n");
    c.stop();
    return;
  }
  int q = req.indexOf("name=");
  String name;
  if (q >= 0) {
    name = req.substring(q + 5);
    int e = name.indexOf(' ');
    int a = name.indexOf('&');
    if (a >= 0 && (e < 0 || a < e)) e = a;
    if (e >= 0) name = name.substring(0, e);
    name.toUpperCase();
  }
  // kind=gb | ch8: ROMs for the streamed games (stored in /roms, listed by CMD_GAME); default: Z80 package in /store
  String kind;
  int kq = req.indexOf("kind=");
  if (kq >= 0) {
    kind = req.substring(kq + 5);
    int e = kind.indexOf(' ');
    int a = kind.indexOf('&');
    if (a >= 0 && (e < 0 || a < e)) e = a;
    if (e >= 0) kind = kind.substring(0, e);
    kind.toLowerCase();
  }
  bool rom = kind == "gb" || kind == "ch8";
  bool game = kind == "game";                                   // CHIP-8 game run by the calculator: /store/NAME.c8
  size_t limit = kind == "gb" ? 1500000u : (kind == "ch8" || game) ? 3584u : 4715u;   // bin: $B000 - userMem, see OTA_MAX in z80-os/ui/ota.z80
  if (!req.startsWith("POST /upload") || !valid_name(name) || clen == 0 || clen > limit || (kind.length() && !rom && !game && kind != "bin")) {
    c.print("HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n");
    c.stop();
    return;
  }
  String path;
  if (rom) { LittleFS.mkdir("/roms"); path = "/roms/" + name + "." + kind; }
  else { LittleFS.mkdir("/store"); path = "/store/" + name + (game ? ".c8" : ".bin"); }
  if (LittleFS.totalBytes() - LittleFS.usedBytes() < clen + 4096) {          // do not fill the file system
    c.print("HTTP/1.1 507 Insufficient Storage\r\nContent-Length: 0\r\n\r\n");
    c.stop();
    return;
  }
  String part = path + ".part";                                                 // the previous version survives a failed upload
  File f = LittleFS.open(part, "w");
  if (!f) {
    c.print("HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n");
    c.stop();
    return;
  }
  uint8_t buf[256];
  size_t got = 0;
  bool wr_ok = true;
  uint32_t deadline = millis() + 15000UL + clen / 20;                         // a stalled client must not block the main loop forever
  while (got < clen && c.connected() && (int32_t)(deadline - millis()) > 0) {
    int n = c.read(buf, min(sizeof buf, clen - got));
    if (n <= 0) { delay(2); continue; }
    if (f.write(buf, n) != (size_t)n) { wr_ok = false; break; }              // file system full / write error
    got += n;
  }
  f.close();
  if (got != clen || !wr_ok) {                                                 // truncated upload: never keep a half file
    LittleFS.remove(part);
    c.print(wr_ok ? "HTTP/1.1 408 Request Timeout\r\nContent-Length: 0\r\n\r\n" : "HTTP/1.1 507 Insufficient Storage\r\nContent-Length: 0\r\n\r\n");
    c.stop();
    return;
  }
  LittleFS.remove(path);
  if (!LittleFS.rename(part, path)) {
    LittleFS.remove(part);
    c.print("HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n");
    c.stop();
    return;
  }
  c.print("HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nOK\n");
  c.stop();
}
}  // namespace store
