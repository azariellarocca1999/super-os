#pragma once
#include <Arduino.h>

namespace services {
void begin();                                   // load Wi-Fi credentials / API key / timezone from NVS
bool wifi_up(uint32_t timeout_ms);              // fast reconnect (BSSID/channel cached in RTC memory)
void wifi_off();
bool wifi_is_on();
uint8_t rssi_abs();                             // |RSSI| in dB, 0 when offline

String wifi_scan();                             // "SSID|-62\n..."  strongest first, max 9
void wifi_set(const String &ssid, const String &pass);
void api_set(const String &key);
bool has_api_key();

String wiki(uint8_t lang, const String &query);     // Wikipedia summary (lang 0 = es, 1 = en)
String weather(uint8_t lang, const String &city);   // Open-Meteo: now + 3 days
String chat(uint8_t model, const String &text); // DeepSeek: model 0 = deepseek-chat (V3), 1 = deepseek-reasoner (R1)
bool time_hm(uint8_t &hour, uint8_t &minute);   // NTP -> local time
String ascii_fold(const String &utf8);          // the calculator font is ASCII only
}  // namespace services
