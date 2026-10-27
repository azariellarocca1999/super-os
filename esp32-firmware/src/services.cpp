#include "services.h"
#include <ArduinoJson.h>
#include <Preferences.h>
#include <WiFi.h>
#include <time.h>
#include "esp_crt_bundle.h"
#include "esp_random.h"
#include "mbedtls/aes.h"
#include "mbedtls/sha256.h"
#include "esp_http_client.h"

namespace services {
static Preferences nvs;
static String g_ssid, g_pass, g_key, g_tz = "<-03>3";     // Argentina; change with CMD_API_SET extensions later

// Secrets at rest: the Wi-Fi password and the DeepSeek key are stored as "e1:" + hex(IV[16] + AES-256-CTR ciphertext).
// The key is SHA-256(chip eFuse MAC + a fixed salt).  This is OBFUSCATION, not encryption in the security sense: the salt is in this
// public source and the MAC is not secret (the chip sends it in every Wi-Fi frame), so a dump of the flash + the MAC = the plain values.
// It only stops a casual look at an NVS dump.  There is no integrity check: a value sealed on another chip opens as garbage.
// Real protection needs the ESP32-S3 flash encryption eFuses (irreversible, see docs/BRINGUP.md).  The migration below also leaves
// the old plain entry in the NVS log until NVS garbage-collects that page.
static void secret_key(uint8_t key[32]) {
  uint64_t mac = ESP.getEfuseMac();
  static const char salt[] = "super-os/nvs/v1";
  mbedtls_sha256_context c;
  mbedtls_sha256_init(&c);
  mbedtls_sha256_starts(&c, 0);
  mbedtls_sha256_update(&c, (const unsigned char *)&mac, sizeof(mac));
  mbedtls_sha256_update(&c, (const unsigned char *)salt, sizeof(salt) - 1);
  mbedtls_sha256_finish(&c, key);
  mbedtls_sha256_free(&c);
}

static void secret_ctr(uint8_t iv[16], const uint8_t *in, uint8_t *out, size_t n) {
  uint8_t key[32], stream[16];
  size_t off = 0;
  secret_key(key);
  mbedtls_aes_context a;
  mbedtls_aes_init(&a);
  mbedtls_aes_setkey_enc(&a, key, 256);
  mbedtls_aes_crypt_ctr(&a, n, &off, iv, stream, in, out);
  mbedtls_aes_free(&a);
}

static String secret_seal(const String &plain) {
  if (plain.isEmpty()) return plain;
  uint8_t iv[16], iv0[16];
  for (int i = 0; i < 16; i += 4) { uint32_t r = esp_random(); memcpy(iv + i, &r, 4); }
  memcpy(iv0, iv, 16);
  size_t n = plain.length();
  uint8_t *ct = (uint8_t *)malloc(n);
  if (!ct) return plain;
  secret_ctr(iv, (const uint8_t *)plain.c_str(), ct, n);
  String out = "e1:";
  char h[3];
  for (int i = 0; i < 16; i++) { snprintf(h, sizeof h, "%02x", iv0[i]); out += h; }
  for (size_t i = 0; i < n; i++) { snprintf(h, sizeof h, "%02x", ct[i]); out += h; }
  free(ct);
  return out;
}

static int hexv(char c) { return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1; }

// returns true when the stored value was already sealed; plain values (older firmware) are returned as they are
static bool secret_open(const String &stored, String &plain) {
  if (!stored.startsWith("e1:")) { plain = stored; return false; }
  size_t hl = stored.length() - 3;
  if (hl < 34 || (hl & 1)) { plain = ""; return true; }
  size_t n = hl / 2 - 16;
  uint8_t iv[16];
  uint8_t *ct = (uint8_t *)malloc(n + 1), *pt = (uint8_t *)malloc(n + 1);
  if (!ct || !pt) { free(ct); free(pt); plain = ""; return true; }
  const char *s = stored.c_str() + 3;
  bool ok = true;
  for (size_t i = 0; i < hl / 2; i++) {
    int a = hexv(s[2 * i]), b = hexv(s[2 * i + 1]);
    if (a < 0 || b < 0) { ok = false; break; }
    uint8_t v = (uint8_t)(a * 16 + b);
    if (i < 16) iv[i] = v; else ct[i - 16] = v;
  }
  if (ok) { secret_ctr(iv, ct, pt, n); pt[n] = 0; plain = String((const char *)pt); } else plain = "";
  free(ct);
  free(pt);
  return true;
}

// Reconnect info survives deep sleep: association takes ~0.3 s instead of a full scan.
RTC_DATA_ATTR static uint8_t rtc_bssid[6];
RTC_DATA_ATTR static int32_t rtc_channel = 0;

void begin() {
  nvs.begin("superos", false);
  g_ssid = nvs.getString("ssid", "");
  String sp = nvs.getString("pass", ""), sk = nvs.getString("dskey", "");
  if (!secret_open(sp, g_pass) && !g_pass.isEmpty()) nvs.putString("pass", secret_seal(g_pass));       // migrate old plain values
  if (!secret_open(sk, g_key) && !g_key.isEmpty()) nvs.putString("dskey", secret_seal(g_key));
  g_tz = nvs.getString("tz", g_tz);
}

bool wifi_is_on() { return WiFi.status() == WL_CONNECTED; }

uint8_t rssi_abs() { return wifi_is_on() ? (uint8_t)(-WiFi.RSSI()) : 0; }

bool wifi_up(uint32_t timeout_ms) {
  if (wifi_is_on()) return true;
  if (g_ssid.isEmpty()) return false;
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(WIFI_PS_MIN_MODEM);                  // modem sleep between beacons while connected
  if (rtc_channel > 0) WiFi.begin(g_ssid.c_str(), g_pass.c_str(), rtc_channel, rtc_bssid, true);
  else WiFi.begin(g_ssid.c_str(), g_pass.c_str());
  uint32_t t0 = millis();
  while (!wifi_is_on() && millis() - t0 < timeout_ms) delay(20);
  if (!wifi_is_on()) { rtc_channel = 0; return false; }
  memcpy(rtc_bssid, WiFi.BSSID(), 6);
  rtc_channel = WiFi.channel();
  return true;
}

void wifi_off() {
  WiFi.disconnect(true, false);
  WiFi.mode(WIFI_OFF);
}

String wifi_scan() {
  WiFi.mode(WIFI_STA);
  int n = WiFi.scanNetworks(false, false);
  String out;
  for (int i = 0; i < n && i < 9; i++) out += ascii_fold(WiFi.SSID(i)) + "|" + String(WiFi.RSSI(i)) + "\n";
  WiFi.scanDelete();
  return out.length() ? out : String("(no networks)");
}

void wifi_set(const String &ssid, const String &pass) {
  g_ssid = ssid;
  g_pass = pass;
  nvs.putString("ssid", ssid);
  nvs.putString("pass", secret_seal(pass));
  rtc_channel = 0;
  wifi_off();
}

void api_set(const String &key) {
  g_key = key;
  nvs.putString("dskey", secret_seal(key));          // sealed with a chip-bound key (see secret_seal); not real flash encryption
}

bool has_api_key() { return !g_key.isEmpty(); }

String ascii_fold(const String &s) {
  String out;
  out.reserve(s.length());
  static const char *map = "AAAAAAACEEEEIIIIDNOOOOO*OUUUUYTsaaaaaaaceeeeiiiidnooooo/ouuuuyty";
  for (size_t i = 0; i < s.length();) {
    uint8_t c = (uint8_t)s[i];
    if (c < 0x80) {
      out += (c == '\r') ? ' ' : (char)c;
      i++;
    } else if (c == 0xC3 && i + 1 < s.length()) {                 // Latin-1 supplement (accents, n with tilde)
      uint8_t d = (uint8_t)s[i + 1];
      out += (d >= 0x80 && d < 0xC0) ? map[d - 0x80] : '?';
      i += 2;
    } else if (c == 0xE2 && i + 2 < s.length() && (uint8_t)s[i + 1] == 0x80) {   // typographic punctuation
      uint8_t d = (uint8_t)s[i + 2];
      out += (d >= 0x98 && d <= 0x99) ? '\'' : (d >= 0x9C && d <= 0x9D) ? '"' : (d == 0x93 || d == 0x94) ? '-' : '?';
      i += 3;
    } else {
      out += '?';
      i += (c >= 0xF0) ? 4 : (c >= 0xE0) ? 3 : 2;
    }
  }
  return out;
}

static const char *SYSTEM_PROMPT =
    "You answer on a 96x64 monochrome calculator screen (24x10 characters). Plain ASCII only, no markdown, no LaTeX: "
    "powers as x^2, roots as sqrt(x), fractions as a/b. Be brief (under 500 characters). "
    "For a plottable function add a final line [PLOT: expr, xmin, xmax].";

static esp_err_t http_event(esp_http_client_event_t *e) {
  if (e->event_id == HTTP_EVENT_ON_DATA && e->user_data) ((String *)e->user_data)->concat((const char *)e->data, e->data_len);
  return ESP_OK;
}


// ---- plain HTTPS GET (certificate bundle) + Wikipedia / Open-Meteo ------------------------------------------------------------------
static esp_err_t http_event_capped(esp_http_client_event_t *e) {
  if (e->event_id == HTTP_EVENT_ON_DATA && e->user_data) {
    String *s = (String *)e->user_data;
    if (s->length() + e->data_len < 24000) s->concat((const char *)e->data, e->data_len);
  }
  return ESP_OK;
}
static bool http_get(const String &url, String &out) {
  out = "";
  esp_http_client_config_t cfg = {};
  cfg.url = url.c_str();
  cfg.method = HTTP_METHOD_GET;
  cfg.event_handler = http_event_capped;
  cfg.user_data = &out;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.timeout_ms = 15000;
  cfg.buffer_size = 2048;
  esp_http_client_handle_t cli = esp_http_client_init(&cfg);
  if (!cli) return false;
  esp_http_client_set_header(cli, "User-Agent", "Super-OS/1.0 (TI-83 Plus SE co-processor)");
  esp_err_t err = esp_http_client_perform(cli);
  int code = esp_http_client_get_status_code(cli);
  esp_http_client_cleanup(cli);
  return err == ESP_OK && code >= 200 && code < 300;
}
static String url_encode(const String &s) {
  static const char *hex = "0123456789ABCDEF";
  String o;
  for (size_t i = 0; i < s.length(); i++) {
    uint8_t c = (uint8_t)s[i];
    if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~')
      o += (char)c;
    else {
      o += '%';
      o += hex[c >> 4];
      o += hex[c & 15];
    }
  }
  return o;
}

String wiki(uint8_t lang, const String &query) {
  if (query.isEmpty()) return "?";
  if (!wifi_up(10000)) return "No WiFi: set it in WIFI+API.";
  const char *lc = lang ? "en" : "es";
  String res;
  if (!http_get(String("https://") + lc + ".wikipedia.org/w/rest.php/v1/search/title?q=" + url_encode(query) + "&limit=1", res)) return "Wikipedia: no answer";
  JsonDocument d;
  if (deserializeJson(d, res)) return "Wikipedia: bad reply";
  const char *title = d["pages"][0]["title"];
  if (!title) return String("NOT FOUND: ") + query;
  String t(title);
  String path = t;
  path.replace(" ", "_");
  if (!http_get(String("https://") + lc + ".wikipedia.org/api/rest_v1/page/summary/" + url_encode(path), res)) return "Wikipedia: no summary";
  JsonDocument s;
  if (deserializeJson(s, res)) return "Wikipedia: bad summary";
  String out = t + "\n" + String((const char *)(s["extract"] | ""));
  if (out.length() > 3500) out = out.substring(0, 3500);
  return out;
}

static const char *wmo_text(int code, bool en) {
  struct W {
    int c;
    const char *es, *en;
  };
  static const W t[] = {{0, "CIELO DESPEJADO", "CLEAR SKY"}, {1, "MAYORMENTE DESPEJADO", "MAINLY CLEAR"}, {2, "PARCIALMENTE NUBLADO", "PARTLY CLOUDY"},
                        {3, "NUBLADO", "OVERCAST"}, {45, "NIEBLA", "FOG"}, {48, "NIEBLA ESCARCHA", "RIME FOG"}, {51, "LLOVIZNA LEVE", "LIGHT DRIZZLE"},
                        {53, "LLOVIZNA", "DRIZZLE"}, {55, "LLOVIZNA FUERTE", "HEAVY DRIZZLE"}, {61, "LLUVIA LEVE", "LIGHT RAIN"}, {63, "LLUVIA", "RAIN"},
                        {65, "LLUVIA FUERTE", "HEAVY RAIN"}, {71, "NIEVE LEVE", "LIGHT SNOW"}, {73, "NIEVE", "SNOW"}, {75, "NIEVE FUERTE", "HEAVY SNOW"},
                        {80, "CHUBASCOS", "SHOWERS"}, {81, "CHUBASCOS FUERTES", "HEAVY SHOWERS"}, {82, "CHUBASCOS VIOLENTOS", "VIOLENT SHOWERS"},
                        {95, "TORMENTA", "THUNDERSTORM"}, {96, "TORMENTA GRANIZO", "THUNDERSTORM HAIL"}, {99, "TORMENTA GRANIZO FUERTE", "SEVERE HAIL STORM"}};
  for (const W &w : t)
    if (w.c == code) return en ? w.en : w.es;
  return "?";
}

String weather(uint8_t lang, const String &city) {
  if (city.isEmpty()) return "?";
  if (!wifi_up(10000)) return "No WiFi: set it in WIFI+API.";
  bool en = lang != 0;
  String res;
  if (!http_get("https://geocoding-api.open-meteo.com/v1/search?name=" + url_encode(city) + "&count=1&language=" + (en ? "en" : "es"), res)) return "Weather: no answer";
  JsonDocument g;
  if (deserializeJson(g, res)) return "Weather: bad reply";
  JsonObject c = g["results"][0];
  if (c.isNull()) return String("CITY NOT FOUND: ") + city;
  String url = "https://api.open-meteo.com/v1/forecast?latitude=" + String((double)c["latitude"], 4) + "&longitude=" + String((double)c["longitude"], 4) +
               "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
               "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto&forecast_days=3";
  if (!http_get(url, res)) return "Weather: no forecast";
  JsonDocument f;
  if (deserializeJson(f, res)) return "Weather: bad forecast";
  char b[96];
  String out = String((const char *)(c["name"] | "?")) + ", " + String((const char *)(c["country"] | "")) + "\n";
  JsonObject cur = f["current"];
  snprintf(b, sizeof b, "%s %.1fC (%s %.1fC)\n", en ? "NOW" : "AHORA", (double)cur["temperature_2m"], en ? "FEELS" : "SENS", (double)cur["apparent_temperature"]);
  out += b;
  out += String(wmo_text(cur["weather_code"] | -1, en)) + "\n";
  snprintf(b, sizeof b, "HUM %d%%  %s %.0f KM/H\n", (int)(cur["relative_humidity_2m"] | 0), en ? "WIND" : "VIENTO", (double)cur["wind_speed_10m"]);
  out += b;
  static const char *dn_es[3] = {"HOY", "MAN", "PAS"}, *dn_en[3] = {"TODAY", "TOMORROW", "DAY 3"};
  JsonObject day = f["daily"];
  for (int i = 0; i < 3; i++) {
    snprintf(b, sizeof b, "%s %.0f/%.0fC %s %.1fMM %s\n", en ? dn_en[i] : dn_es[i], (double)day["temperature_2m_min"][i], (double)day["temperature_2m_max"][i],
             en ? "RAIN" : "LLUVIA", (double)day["precipitation_sum"][i], wmo_text(day["weather_code"][i] | -1, en));
    out += b;
  }
  return out;
}

String chat(uint8_t model, const String &text) {
  if (g_key.isEmpty()) return "[offline] No DeepSeek API key: set it in WIFI+API.";
  if (!wifi_up(10000)) return "No WiFi: set it in WIFI+API.";
  JsonDocument req;
  req["model"] = model ? "deepseek-reasoner" : "deepseek-chat";
  req["max_tokens"] = 600;
  JsonArray msgs = req["messages"].to<JsonArray>();
  JsonObject sys = msgs.add<JsonObject>();
  sys["role"] = "system";
  sys["content"] = SYSTEM_PROMPT;
  JsonObject usr = msgs.add<JsonObject>();
  usr["role"] = "user";
  usr["content"] = text;
  String body;
  serializeJson(req, body);

  String res;
  esp_http_client_config_t cfg = {};
  cfg.url = "https://api.deepseek.com/chat/completions";
  cfg.method = HTTP_METHOD_POST;
  cfg.event_handler = http_event;
  cfg.user_data = &res;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;    // verify api.deepseek.com against the built-in CA bundle
  cfg.timeout_ms = 120000;                           // R1 may reason for a long time
  cfg.buffer_size = 2048;
  esp_http_client_handle_t cli = esp_http_client_init(&cfg);
  if (!cli) return "http init failed";
  esp_http_client_set_header(cli, "Content-Type", "application/json");
  String auth = "Bearer " + g_key;
  esp_http_client_set_header(cli, "Authorization", auth.c_str());
  esp_http_client_set_post_field(cli, body.c_str(), body.length());
  esp_err_t err = esp_http_client_perform(cli);
  esp_http_client_cleanup(cli);
  if (err != ESP_OK) return String("http error ") + esp_err_to_name(err);
  JsonDocument doc;
  if (deserializeJson(doc, res)) return "DeepSeek: bad reply";
  const char *content = doc["choices"][0]["message"]["content"];
  if (content) return String(content);
  return String("DeepSeek error: ") + String(doc["error"]["message"] | "unknown");
}

bool time_hm(uint8_t &hour, uint8_t &minute) {
  if (!wifi_up(10000)) return false;
  configTzTime(g_tz.c_str(), "pool.ntp.org", "time.google.com");
  struct tm tm;
  if (!getLocalTime(&tm, 8000)) return false;
  hour = (uint8_t)tm.tm_hour;
  minute = (uint8_t)tm.tm_min;
  return true;
}
}  // namespace services
