# Bring-up guide: first contact with real hardware

Everything in `docs/STATUS.md` was verified in the emulator. The steps below turn that into evidence on your units. Stop at the first failing step.

## 0. Before connecting anything

1. Measure the idle voltage of the calculator's link lines (tip and ring to sleeve) with the calculator ON: expect roughly its logic supply (4.5-6 V).
   This decides the level shifter: **BSS138 per line** (docs/WIRING.md). Never wire 5 V to an ESP32-S3 pin.
2. Power the ESP32 from USB-C for all bench work. Connect **GND first**, then the two lines.
3. Keep a TI OS file and TiLP / TI Connect CE ready. The factory boot page is never touched by `SuperOS.8xu`, so a failed OS is recoverable by sending an OS again **from the boot code's receive mode** (remove one AAA battery, hold DEL while reinserting it -> `Waiting... Please install operating system now`; Super-OS itself cannot receive an OS, see `docs/HARDWARE_TEST.md` section 9).

## 1. ESP32-S3-Zero firmware

```
.\scripts\3_run_simulator_or_flash.ps1 -Mode FlashEsp      (hold BOOT while plugging USB-C if it is not detected)
```
Open a serial monitor at 115200 (`python -m platformio device monitor`). Expected: the firmware boots, no crash loop. In deep sleep the
USB serial port disappears (normal): the chip is asleep until the calculator pulls TIP low.

## 2. Calculator: hardware self-checks (SYS tab F5 -> 7 DIAGNOSTICS) - do these BEFORE the link

| Test | Pass looks like | If it fails |
|---|---|---|
| **2 LCD** | RIGHT cycles black / white / checker / stripes / gray; UP/DOWN change contrast live; gray bands show 4 distinct levels (some flicker is normal) | wrong contrast range -> adjust the profile base in `power/power.z80`; garbled image -> LCD pacing (`lcd_cmd` delay) is too short for your panel revision |
| **3 KEYS** | every key changes exactly one bit of R0..R6; ON shows `ON:1` while held; hold CLEAR 2 s to leave | a key with no bit -> matrix/contact issue |
| **4 RAM** | 7 lines PASS (page 1 shows LIVE because the OS runs in it) | any FAIL = that 16 KB RAM page is bad or not mapped (128 KB claim) |
| **5 FLASH** | GUARD, ERASE, PROGRAM, ERASE AGAIN all PASS | ERASE/PROGRAM FAIL = flash unlock or sector geometry differs on your unit; the guard line must always be PASS. This test erases only pages $74-$77 |

## 3. Calculator <-> ESP32 link (DIAGNOSTICS -> 1 ESP32 LINK)

Idle screen shows live line levels `TIP:1 RING:1` (1 = high). **Both must read 1 with the ESP32 connected and idle.** `TIP:0` or `RING:0`
at idle means a short, a wrong divider/shifter, or a missing pull-up. Counters `RTY / CRC / TMO` should stay 0.
Press ENTER to run the test sequence:

| Line | Meaning | Emulator reference | What to check if worse |
|---|---|---|---|
| WAKE+STATUS | pulse TIP 50 ms, ESP boots, `ESP_READY`, status frame | ~380 ms | > 4 s or FAIL: `ext0` wake pin (GPIO1) wiring/pull-up; ESP in a crash loop |
| PING 64B x10 | 64-byte frames both ways | 10/10, ~56 ms each | < 10/10 with TMO counting: handshake timing (cable capacitance / slow pull-up) |
| BENCH 512B | ESP sends 512 pseudo-random bytes | ~17 kbit/s (ideal wires) | much lower is expected on real wires; CRC>0 = noise |

DIAGNOSTICS -> 6 ESP32 REPORT shows the chip's own view: firmware, uptime, boot count, wake cause (`EXT0(TIP)` after a calculator wake), Wi-Fi/RSSI,
the line levels as the ESP sees them, and its own RX/TX/CRC/retry/timeout counters. Compare with the calculator's counters: asymmetric errors point to one side's timing.

## 4. Wi-Fi, AI, clock

SYS/AI tab -> WIFI+API: scan, pick a network (1-9), type the password (ALPHA switches T9 / ABC / 123, 2ND = upper case), then API key. Then AI CHAT.
CLOCK -> ENTER syncs the time through NTP. The first request after the ESP32 slept includes its boot (~0.3-0.5 s) plus Wi-Fi reconnect.

## 5. OTA packages

1. Build a Z80 program image (raw, origin $9D95, <= 5200 bytes; Ion-style header optional).
2. Calculator: SYS tab -> OTA -> `4 RECEIVE FROM PC` (opens a 120 s upload window and shows the ESP32 IP).
3. PC: `python tools\ota_push.py game.bin --name GAME --host <ip>` (or `superos-esp.local`).
4. Calculator: OTA -> `1 PC PACKAGES` -> pick -> installed into flash; OTA -> `2 INSTALLED` -> ENTER runs it, DEL deletes.
   Settings are journalled in flash page $70 and survive battery removal.

## 6. Milestone 3 apps that depend on the ESP32

1. **Super-CAS** (MATH tab, 3): `diff(x^2,x)` must answer `2*x`; the first request after a deep sleep takes ~0.4 s (wake) plus the calculation. If it says
   `NO ESP32`, run DIAGNOSTICS -> 1 first. A heavy integral may take several seconds: the ESP32 keeps the link alive with status frames for up to 60 s.
2. **3D plot**: `plot3d(sin(x)*cos(y),-3,3,-3,3)` returns a 768-byte bitmap (about 1-2 s on the ESP32-S3).
3. **Wikipedia / weather**: configure Wi-Fi first (SYS/AI tab -> WIFI+API). A not-found page or city answers with `NOT FOUND`.
4. **Step by step**: needs the DeepSeek API key; R1 can think for up to ~2 minutes (the calculator waits 20 s per reply step and the ESP32 sends keep-alives).
5. The 32-bit ESP32 uses a software 128-bit integer inside the CAS; if a symbolic result looks wrong, compare with the host tool:
   `echo "int(x*exp(x),x)" | tools\bin\cas_cli.exe` (same sources).

## 7. Milestone 4: games and the turbo link (hardware tuning)

1. **CHIP-8 games on the calculator** (GAMES tab F4: ARCADE / ACTION) need nothing but the calculator. Key map: the number pad is the CHIP-8 keypad
   (`7 8 9 / 4 5 6 / 1 2 3 / 0 . (-)` = CHIP-8 `1 2 3 / 4 5 6 / 7 8 9 / A 0 B`), arrows = 2 4 6 8, ENTER / 2ND = 5, CLEAR quits. If a key does nothing check
   DIAGNOSTICS -> 3 KEYS first (the games read the matrix directly).
2. **Turbo link** (DIAGNOSTICS -> 1 ESP32 LINK, ENTER): the last line `TURBO 512B xx KBIT/S` repeats the 512-byte benchmark over the calculator-clocked byte layer.
   Emulator reference: ~64 kbit/s effective (3 frames of overhead included) versus 17 for the safe layer. Real wires will be slower or fail:
   * `FAIL` or CRC/TMO counters growing: the ESP32 cannot follow the clock. In `z80-os/net/superlink.z80` raise `TL_TX` to 2 and `TL_RXLOW` / `TL_RXHIGH` to 4 / 2
     (about 84 kbit/s) or 3 / 6 / 3 (about 60 kbit/s), rebuild, retry. The ESP32 side polls GPIO with interrupts off for ~100 us per byte; if the Wi-Fi stack stalls it,
     pin the link code to core 1.
   * The rise time of the open-drain lines (weak calculator pull-ups + cable + BSS138 shifter) is the usual limit: look at TIP/RING with a scope while a benchmark runs;
     each clock phase needs >= 3 us of clean level.
   * If the turbo request itself fails the games still work through the safe layer (slow: about 1-2 frames/s).
3. **STREAM 3D** (GAMES tab -> 3rd entry): `MAZE 3D` and `DMG-ACID2` (Game Boy test ROM, MIT) are built in. The number at the bottom right is the frame rate.
   Maze keys: 2 forward, 8 back, 4 / 6 turn, 1 / 3 strafe, 5 map. Game Boy keys: 2 4 6 8 d-pad, 5 = A, 7 = B, 9 = START, 1 = SELECT.
   The ESP32 switches to 240 MHz during a game (Peanut-GB); not measured on the chip - if frames are slow check `CMD_DIAG` heap/PSRAM.
4. **Your own ROMs**: open the OTA window (SYS -> OTA -> 4), then from the PC
   `python tools\ota_push.py zelda.gb --name ZELDA --kind gb --host <ip>` (Game Boy, <= 1.5 MB, stays on the ESP32, appears in STREAM 3D),
   `python tools\ota_push.py game.c8 --name MYGAME --kind game --host <ip>` (CHIP-8 assembly or a .ch8 ROM, <= 3584 bytes; OTA -> 1 PC PACKAGES installs it into the calculator's
   flash, OTA -> 2 INSTALLED plays it). No commercial ROMs are shipped; supply your own legally.
