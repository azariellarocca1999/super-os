---
name: dual-emulators-pack
description: Game architecture of Super-OS (milestone 4, implemented) - CHIP-8 interpreter on the Z80, streamed games (maze 3D raycaster, Game Boy via Peanut-GB, CHIP-8) from the ESP32, delta frames, turbo link, packs and OTA games. Use when working on games, the frame protocol or the emulator cores.
---

# Games: two engines, one calculator

## On the Z80 (works with the ESP32 asleep) - flash page 5 (`z80-os/games/`), ROMs in page 6
* `chip8.z80`: CHIP-8 interpreter (no SCHIP), CHIP-8 RAM = RAM page 2 at $C000, state at $A000 (V regs 256-aligned). Display 64x32 doubled vertically
  into the 96x64 buffer with 16 px margins (the left margin shows a marker while ST > 0 - there is no speaker).
  `Fx07` ends the burst of instructions of this tick (the game is waiting for its timer: that is the end of its frame, so the picture is shown whole - no flicker).
* Semantics = `tools/chip8.py` (the reference): shifts use Vy, Fx55/65 leave I = I+x+1, sprites clip, VF untouched by logic ops, 16-bit Galois LFSR for RND.
* Keys: the number pad mirrors the CHIP-8 keypad (7 8 9 / 4 5 6 / 1 2 3 / 0 . (-) = 1 2 3 / 4 5 6 / 7 8 9 / A 0 B; / x - + = C D E F), arrows = 2 4 6 8, ENTER and 2ND = 5. CLEAR quits.
* Packs: ARCADE = PONG, BREAKOUT, SNAKE; ACTION = INVADERS, DODGE, SIMON (original code, `games/chip8/*.c8`, built by `tools/gen_c8.py` into page 6).
  The CHIP-8 programs must keep their data above their code (data at $600 here; ROMs are < 400 bytes).
* OTA games: `tools/ota_push.py x.c8 --kind game` -> ESP32 `/store/X.c8` -> OTA menu installs it as package type 2 -> ENTER plays it (`c8_run_ram`).

## On the ESP32-S3 (streamed) - `esp32-firmware/lib/superplay`
* `Core::step(keys, dt_us, fb)` renders 96x64 1-bit frames (LCD layout). Cores: `raycast.cpp` (original DDA maze, dithered walls), `chip8.cpp`, `gbcore.cpp` (Peanut-GB, MIT,
  160x144 -> 96x64 box filter + Bayer dither; dmg-acid2 bundled as demo), user ROMs from LittleFS `/roms/*.gb|*.ch8` (uploaded with `ota_push.py --kind gb|ch8`).
* NES (Nofrendo, GPL) is NOT included. No commercial ROMs anywhere.
* The calculator paces the stream (pull model): `CMD_GAME [2][keys lo][keys hi][flags]` -> one frame; the game advances by the real time since the last request.
* Frame codec (`frame.cpp`): `[0]` unchanged | `[1][12-byte bitmap][8 bytes per changed 8x8 tile]` | `[2][768]`. Flags bit 0 = "send me a full frame".
* Host build for tests and the virtual ESP32: `sh games/host/build_play.sh` -> `tools/bin/play_cli.exe`; tests `python games/host/play_tests.py`.

## Budget (measured in the emulator, safe vs turbo)
Full 768-byte frame = 6144 bits.  Safe layer ~17 kbit/s effective; turbo ~100-115 kbit/s on the wire (calculator clocked) -> whole-picture-changing frames ~16 FPS, idle ~70 FPS,
typical games (few tiles change) well above 20 FPS.  The cable's real ceiling must be found on hardware (see docs/BRINGUP.md section 7).
