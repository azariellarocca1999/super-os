#pragma once
#include <Arduino.h>

// Streamed games (lib/superplay): built-in MAZE 3D and DMG-ACID2, plus user ROMs (.gb, .ch8) uploaded to LittleFS /roms.
namespace games {
String list();                                       // titles, one per line
bool start(int index);                               // builds the core; false when the index / ROM is invalid
size_t frame(uint16_t keys, bool want_full, uint8_t *out);   // advance by the real time since the last frame, encode (>= 769 bytes)
void stop();
bool running();
}  // namespace games
