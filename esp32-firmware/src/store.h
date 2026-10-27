#pragma once
#include <Arduino.h>

// OTA package store on the ESP32 (LittleFS /store/NAME.bin) + the HTTP upload window.
namespace store {
void begin();
String list();                                   // "NAME|bytes\n" lines
bool get(const String &name, uint8_t **data, size_t *len);   // malloc'ed, free() it
String start_upload_window(uint32_t seconds);    // brings Wi-Fi up, opens port 80; returns a text for the calculator
bool upload_window_open();
void poll();                                     // call from loop(): serves at most one pending upload
}  // namespace store
