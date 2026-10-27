# Pending (state after the first hardware contact and the native games)

## A. Needs the real calculator (the very next step)
- Re-test on the unit everything fixed after the first boot: keyboard settle time, the tile-flushed games, the CHIP-8 frame fix, DIAGNOSTICS `7 TIMING` (ticks/s, MHz), the crash trail. `docs/HARDWARE_TEST.md`.
- The things only a unit can tell: contrast defaults on real cells (bases 48 / 50 / 58 are KnightOS-like guesses), flash settings journal and the flash diagnostics (the unlock stub in page `$7C` never ran on hardware), deep sleep and wake, RAM test, battery life and current draw.
- Other boot code revisions: only boot code 1.00 / OS 1.19 has been seen.

## B. Needs the ESP32
- First contact: wiring with BSS138, line levels, wake by TIP, ESP_READY (`docs/BRINGUP.md`). Turbo link on a real cable (`TL_TX / TL_RXLOW / TL_RXHIGH`, the ESP32 bit-banging that never ran on a chip), interrupts with Wi-Fi active.
- Peanut-GB speed at 240 MHz, PSRAM with big ROMs, Super-CAS timings, Wikipedia / weather on the chip, OTA over real Wi-Fi.
- Everything in the ESP32 firmware that was only compiled: sealed NVS secrets, the worker-job ownership protocol (`jobs.h`, host-tested), the upload-server deadlines.

## C. Ideas, in rough order of value (see also [FEATURES.md](FEATURES.md))
1. A programming language on the calculator (TI-BASIC-like): interpreter + token editor + storage. The biggest missing feature next to KnightOS / Doors CS; needs its own flash page (the math page is 97 % full).
2. Statistics / lists / matrices app (one-variable stats, regression) and complex numbers; better `sin` / `cos` for |x| > ~3e4; more CAS coverage. All need a new flash page for the math code.
3. SCHIP (128x64) for the CHIP-8 interpreter, pause and speed selection there; more native games (Connect 4, a small Pac-Man-like, Lunar Lander). Page 5 is 91 % full: the next game needs a second games page.
4. Sound is impossible (no speaker), but a `beep` through the link-port line could drive a piezo on the ESP32 side.
5. Notes that survive a battery change (a flash journal for them), longer notes, a viewer for text packages; RTC that keeps running in deep sleep; packages over 5200 bytes; rename packages from the UI; folders in the package store.
6. Adaptive turbo (drop speed after CRC errors) and calibration in DIAGNOSTICS; a protocol-level cancel so the ESP32 stops waiting for DeepSeek after CLEAR.
7. ESP32 flash encryption (irreversible eFuses): decision pending; the current secret sealing is only chip-bound obfuscation.
8. NES: **recommended to leave out** (Nofrendo is GPL, no redistributable test ROM).

## D. Done (history in `docs/REVIEW.md`, `docs/PERF.md`, `docs/STATUS.md`)
Milestones 1-4; critical review and a second supervision pass; the signed `.8xu` boots on a TI-83+ SE; keyboard / LCD / key / label fixes found on the unit; nine native games with a tile flush; crash trail and timing diagnostics; GitHub-ready docs; contrast shortcut; best scores in the flash journal (this also fixed a bug that stored the wrong value as a record); PIN lock and exam mode; notepad.
