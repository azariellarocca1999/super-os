# Status

**Alpha. First contact with real hardware happened on 2026-10-26**: the signed `.8xu` installs on a TI-83 Plus Silver Edition (boot code 1.00, OS 1.19) and the OS boots and shows an image. Everything else
below is verified **in the emulator only** unless it says otherwise. The ESP32 firmware has never run on a chip.

## What the real unit taught us (all fixed, none re-tested on the unit yet; details in `docs/REVIEW.md`)
1. The OS must be signed with the **OS key `04`** (we used the app key `0104`) and the signature records must be laid out like TI's files (`tools/fix_8xu_tail.py`).
2. The LCD needs `05 01 03 17 0B` and the contrast command is `C0 + 24 + n` (bases 48 / 50 / 58); the boot code leaves the panel unpowered otherwise.
3. The keyboard matrix needs ~40 T-states to settle at 15 MHz (scans waited 16-24).
4. The CHIP-8 interpreter showed half-drawn frames (burst limit in the middle of a frame); the CHIP-8 Pong AI could not reach the ball; a label and an `.equ` with the same name sent a jump into RAM.

## What is new since the first hardware contact
* **Nine native games** (`z80-os/games/`: Tetris, Snake, Breakout, Pong, 2048, Space Invaders, Minesweeper, Sokoban, Reversi) on a shared library with a tile-based LCD flush and best scores in the flash journal; the six CHIP-8 classics stay in a second-page menu. `docs/GAMES.md`.
* **Added in 0.6**: PIN lock + exam mode, notepad, live contrast shortcut, persistent scores (fixing an old bug that stored `id*2` instead of the score), journal records 64 B (the first boot of this version starts from default settings), Invaders skips redraws when nothing moved (CPU idle 61 % -> 86 %). All of it is emulator-only: **not tested on the unit**. Comparison with other custom OSes: `docs/FEATURES.md`.
* **Tools that catch what the emulator cannot**: crash trail (`REINICIO PC= SP=` after an unexpected restart), DIAGNOSTICS `7 TIMING`, `tools/check_labels.py`, `tools/audit_text.py`, `tools/z80dis.py` (disassembler + boot tracer), the bring-up build with a progress bar and contrast sweep.
* A GitHub-ready repository: MIT license, `docs/INSTALL.md`, `docs/GAMES.md`, `CONTRIBUTING.md`, issue template for hardware reports.

## Not verified on hardware
Everything after the boot screen (keyboard fix, games, diagnostics, calculator, grapher, settings in flash, deep sleep, battery life), the ESP32 firmware, the turbo link, Wi-Fi services, power draw.

| Check | Count | How to run |
|---|---|---|
| Emulator self-test (TI-83 Plus SE core + virtual ESP32) | **191 checks** (UI, link, OTA, calculator, CAS client, games, lock / notes, no-ESP32 behaviour, fault injection, 46 for the native games and 13 for lock / notes / contrast) | `python tools\selftest.py` (`--m3` = only the milestone 3 UI part, `python tools\selftest_m4.py` = only milestone 4, `python tools\selftest_noesp.py` = only the no-ESP32 part) |
| Signed `.8xu`: structure, pages, checksums, untouched factory pages, **RSA signature math (key 04)**, boot entry bytes | 22 checks | `python tools\verify_8xu.py` (also run by `2_build_all.ps1`) |
| Z80 floating point library vs Python | **324 cases** | `python tools\mathtest.py` |
| Super-CAS (same C++ as the firmware, host build) | **212 checks** | `python cas\cas_tests.py` |
| CHIP-8 interpreter: Z80 (flash page 5) vs Python reference, same programs | **20 comparisons** (opcode ROM + 6 games x 3 input patterns; V, I, PC, SP, timers, display, 4 KB of memory) | `python tools\c8test.py` |
| CHIP-8 games played by a bot on the reference | **9 checks** | `python tools\c8games_test.py` |
| Streamed-games engine (the ESP32 C++, host build) | **13 checks** (codec, raycaster, CHIP-8 vs reference, Peanut-GB dmg-acid2) | `python games\host\play_tests.py` |
| ESP32 worker-job ownership protocol (`src/jobs.h`, real threads, host build) | **5 checks** (20 000 jobs) | `sh esp32-firmware/test_host/build_jobs_test.sh` |
| Peanut-GB upstream tests on this toolchain (blargg cpu_instrs, instr_timing, dmg-acid2 hash) | pass | `tools/src/Peanut-GB/test` |
| ESP32-S3 firmware | builds: RAM 16.7 %, flash 42.5 % | `.\scripts\2_build_all.ps1` |

Screenshots: `docs/screens/games.png`, `docs/screens/milestone3.png`, `docs/screens/milestone4.png` (regenerate with `python tools\screens_games.py` / `screens_m3.py` / `screens_m4.py`).

## Milestone 4: games

### CHIP-8 on the calculator (ESP32 not needed) - GAMES tab (F4)
* **Interpreter** (`z80-os/games/chip8.z80`, flash page 5): the 35 CHIP-8 opcodes (no SCHIP), CHIP-8 RAM in RAM page 2 at $C000, 64x32 display doubled vertically into the
  96x64 frame buffer with 16-pixel margins, 60 Hz timers from the 108 Hz tick, direct key-matrix scan. `Fx07` ends the instruction burst of the tick (the game is waiting for
  its timer = end of its frame), which removes the erase/redraw flicker. There is no speaker: the left margin lights while the sound timer runs.
* **Reference and tools** (`tools/chip8.py`): assembler + reference interpreter with identical semantics (shifts use Vy, Fx55/65 advance I, clipping sprites, 16-bit LFSR for RND).
  `c8test.py` runs the same programs on both and compares every register, the display and all 4 KB of memory.
* **Six original games** (`games/chip8/*.c8`, 170-360 bytes each, flash page 6): ARCADE = PONG (vs a cpu paddle), BREAKOUT, SNAKE; ACTION = INVADERS, DODGE, SIMON.
  No third-party code or ROMs. Bots verify they are playable (the tracking paddle scores in PONG, breaks 23/24 bricks in BREAKOUT, the snake eats 17 apples, ...).
  While writing the tests a real bug showed up: three games kept data at $300 on top of their own code - found because the Z80 and the reference diverged.
* **Keys**: the number pad is the CHIP-8 keypad (`7 8 9 / 4 5 6 / 1 2 3 / 0 . (-)` = `1 2 3 / 4 5 6 / 7 8 9 / A 0 B`), `/ x - +` = C D E F, arrows = 2 4 6 8, ENTER / 2ND = 5, CLEAR quits.

### SuperLink turbo byte layer (calculator-clocked)
`CMD_TURBO [1]` switches both ends from the TI handshake to a synchronous layer: RING = clock (calculator only), TIP = data. The frame layer (SYNC/CMD/LEN/CRC8, ACK/NACK, retries) is unchanged.
CRC8 is now table driven (`crc8tab.inc`), `sl_wait_start` polls ~1 ms before halting, and a new syscall `link_direct` ($019C) runs a request in the caller's context (no round trip
through the link task: two scheduler ticks saved per frame). Emulator numbers: the diagnostics screen shows `TURBO 512B` next to the safe `BENCH 512B` (17 kbit/s effective
with protocol overhead and 3 frames; turbo 64 kbit/s, 3.7x); raw rate on the wire ~100-115 kbit/s (Z80 knobs `TL_TX / TL_RXLOW / TL_RXHIGH`, slower settings documented in `docs/BRINGUP.md`).

### Streamed games - GAMES tab -> STREAM 3D
* The ESP32 runs the game, the calculator sends its key mask and receives frames (`CMD_GAME`, raw chunks, not ZX0). The game advances by the real time since the previous request (pull model).
* **Delta frames**: `[0]` unchanged, `[1][12-byte bitmap][8 bytes per changed 8x8 tile]`, `[2]` full (first frame / resync after an error / flag bit 0).
* **Cores** (`esp32-firmware/lib/superplay`): **MAZE 3D** (an original DDA raycaster, ordered-dither shading, brick walls, minimap on key 5); **CHIP-8** for ROMs uploaded to the ESP32;
  **Game Boy through Peanut-GB** (MIT; 160x144 -> 96x64 box filter + Bayer dither) with the **dmg-acid2** test ROM (MIT) bundled as the demo - upstream cpu_instrs, instr_timing and the
  acid2 hash pass on this toolchain.
* **Frame rate in the emulator** (lockstep virtual ESP32, whole chain through the real Z80 code): idle ~70 frames/s, the worst case (turning in the maze: nearly every tile changes,
  ~780 bytes per frame) **16 frames/s**; the FPS counter is drawn bottom right.
* Game Boy keys: 2 4 6 8 d-pad, 5 = A, 7 = B, 9 = START, 1 = SELECT. Maze keys: 2 forward, 8 back, 4 / 6 turn, 1 / 3 strafe, 5 map.

### OTA games
`python tools\ota_push.py game.c8 --name MYGAME --kind game` (CHIP-8 assembly or a .ch8 ROM, <= 3584 bytes) -> `/store/MYGAME.c8` on the ESP32 -> OTA > PC PACKAGES installs it as flash package
**type 2** -> OTA > INSTALLED > ENTER plays it in the calculator's interpreter. `--kind gb` / `--kind ch8` upload ROMs that stay on the ESP32 (`/roms`) and show up in STREAM 3D.

## Not done / not verified (milestone 4)
* **Hardware**: nothing flashed or wired. The turbo layer was verified against the Python model of the ESP32 only: the C++ bit-banging (GPIO polling with interrupts off, ~100 us per byte) is compiled but
  never ran on a chip, and the real cable (weak pull-ups, BSS138 shifter, capacitance) decides whether 100 kbit/s works. Fallbacks are in `docs/BRINGUP.md` section 7; the games work in the safe layer too (1-2 frames/s).
* **NES is not included** (Nofrendo is GPL and there is no ROM to test with). Peanut-GB speed on the real ESP32-S3 (240 MHz), PSRAM use for big ROMs and cartridge-RAM saves (not persisted) are unmeasured.
* **No sound** (the link-port calculator has no speaker; a marker lights while the CHIP-8 sound timer runs). No SCHIP (128x64) opcodes.
* The "real time" of the streamed games is the time between requests, so on a slow link a game runs at wall-clock speed but shows fewer frames.

## Milestone 1 and 2 (unchanged, still passing)
Preemptive kernel at 15 MHz, status bar / tabs / launcher / ES-EN / two fonts, battery profiles, deep sleep, RTC, SuperLink safe layer with wake pulse,
DeepSeek chat (T9 / ABC / 123), WiFi + API setup, TI-OS B_CALL shim, flash settings journal, package store + OTA, link diagnostics, signed `.8xu`.

## Milestone 3: calculator, grapher, Super-CAS, information apps

| App (MATH / AI tab) | What it does | Evidence |
|---|---|---|
| **Z80 float library** (flash page 3) | 32-bit mantissa (~9.6 digits), range 1e-38..1e38; + - * / compare, sqrt, exp, ln, log, pow, sin/cos/tan, asin/acos/atan, sinh..atanh, factorial, mod, text <-> number | 324 cases against Python's `math` (tolerances 2e-9 .. 3e-8), all pass |
| **Calculator** | TI-style entry (2ND / ALPHA, MATH menu of 22 functions, STO `5>A`, variables A..Z, ANS), recursive-descent evaluator with precedence, implicit multiplication, `^` right-associative, `!`, `%`, `EE`, RAD/DEG, last-entry recall, 3-line history, 9 significant digits | sqrt(16), pi, sin(30) in DEG, variables, division and syntax errors, MATH menu: checked through the key matrix in the emulator |
| **2D grapher** | Y1..Y3 editor, window editor, ZOOM (standard / trig / in / out / square / fit-Y), TRACE with exact X/Y readout, TABLE with X, Y1 and numeric Y1', hidden curve breaks at asymptotes, full-width plot in ~1.3 s | plot lit pixels, trace text `Y1 X=0.73684 Y=0.67195`, table value cos(6)=0.9602, zoom-fit -1.1..1.1, window typed as -5..5 |
| **Super-CAS** (engine on the ESP32, `esp32-firmware/lib/supercas`) | exact rationals; `diff`, `int` (substitution, parts, partial fractions, trig powers, exp*trig, sqrt of quadratics; definite with numeric fallback), `taylor`, `limit`, `solve` (polynomials with exact roots incl. complex, rational roots, biquadratic, isolation of one occurrence, numeric scan, linear/2x2 non-linear systems), `factor`, `expand`, `simplify`, `together`, matrices (`det inv transpose rank rref eig`, products and powers), `approx`, `sum`, `ncr`, `gcd`... | 212 host checks verify every answer numerically (derivatives by finite differences, antiderivatives by differentiating them, roots by substitution) |
| **CAS app** | same editor as the calculator; MATH opens a menu of 21 commands; ENTER sends the text over SuperLink (`CMD_CAS`) and shows the answer in the scroll viewer; UP recalls the last command | `diff(sin(x)*x,x)`, `solve(x^2-2=0,x)`, `int(x*exp(x^2),x)` through the virtual ESP32 |
| **3D surface** | `plot3d(f(x,y),x0,x1,y0,y1)`: the ESP32 renders a hidden-line wireframe into the 768-byte frame buffer (`CMD_PLOT3D`) | lit pixels of `sin(x)*cos(y)` on the calculator screen |
| **Step by step** (STEP) | sends the typed problem to **DeepSeek-R1** (`CMD_CHAT`, model 1) | request seen by the ESP32, answer shown |
| **[PLOT:] hook** | an AI answer containing `[PLOT: expr, xmin, xmax]` offers to plot it: the ASCII formula is tokenised into Y1, the window is set and the Y range fitted | tokens `X^2` in Y1 and the parabola on screen |
| **Converter** | 12 categories, 84 units (temperature with offsets), value entry with the expression editor | 5 mm = 0.5 cm, 100 C = 212 F |
| **Periodic table** (flash page 4) | 118 elements (ZX0 data from the `mendeleev` package: mass, group, period, category, configuration, melting / boiling point, electronegativity, density), grid with cursor, Spanish / English names | Na / Mg navigation and detail page |
| **Constants** | 49 physical / astronomical constants (CODATA 2022); ENTER stores the value in the calculator's ANS | c = 299792458 and G = 6.6743E-11 land in ANS |
| **Wikipedia / weather** | prompt -> ESP32 (`CMD_WIKI` / `CMD_WEATHER`) -> text in the viewer. Wikipedia REST summary (language follows the OS setting), Open-Meteo geocoding + now / 3 days | request reaches the ESP32 and the reply is shown (offline echo in tests); the Python bridge was also run against the live services |

Changes under the hood: the generic UI helpers, the text editor and the viewer moved to page 0 (syscalls, `call_pagex`); the math apps run on a private stack
at `$BE00`; flash page 3 = math + calculator + grapher + CAS client + converter (97 % full), page 4 = information apps; two new protocol commands `CMD_CAS` ($30) and
`CMD_PLOT3D` ($31); on the 32-bit ESP32 the CAS uses a software 128-bit integer (`cas_i128.h`, validated on the host with `-DCAS_SOFT128`).

## Not done / not verified (milestones 1-3)
* **Hardware:** nothing flashed or wired (see `docs/BRINGUP.md`). The firmware C++ for Wikipedia / weather compiles but has not run on a chip (the same logic in Python was run against the real services).
* **Super-CAS on the chip:** the engine runs in a 32 KB FreeRTOS task; symbolic work on the real ESP32-S3 has not been timed. Hard integrals may take seconds.
* **CAS coverage:** no closed form -> `ERROR: no elementary antiderivative found`; trig equations return principal solutions (no `+2k*pi`); `solve` scans [-60, 60] for non-polynomial equations; no differential equations, no series sums to infinity.
* **Calculator numbers:** no complex numbers in the calculator itself (the CAS has `i`); `sin`/`cos` lose precision beyond |x| ~ 3e4; results above 1.7e38 report an overflow.
* **RTC pauses in deep sleep**; **SuperLink turbo** (60-115 kbit/s) not implemented; packages are raw Z80 images (<= 5200 bytes).
* **API key / Wi-Fi password** are now sealed in the ESP32's NVS with a chip-bound AES key (obfuscation, not flash encryption; compiled only, see `docs/REVIEW.md`).

## First contact with real hardware (2026-10-26)
Unit: TI-83 Plus Silver Edition, boot code (BIOS) 1.00, OS 1.19. `dist/SuperOS_bringup.8xu` installed with TI Connect's `TIOSDownloader` and **the OS boots and shows an image** (user report; nothing else on the unit was tested yet). Four things the emulator could not tell, found by comparing with the official TI OS and KnightOS (`tools/z80dis.py`, `docs/REVIEW.md` C-HW1..3): the OS must be signed with key `04` (not `0104`), the signature records must be laid out as TI's files (`tools/fix_8xu_tail.py`), the LCD init needs `17 0B` and the contrast scale starts at 24, and the execution-protection ports must be set. Everything else in this file is still verified in the emulator only.
