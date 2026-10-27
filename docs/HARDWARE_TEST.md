# Hardware test plan: Super-OS on the calculator, without the ESP32

Goal: install `SuperOS.8xu` on a TI-83 Plus Silver Edition and check the base system (everything that does not need the ESP32). Install steps and the way back: `docs/INSTALL.md`.
Only the boot and the first screen have been seen on a real unit (2026-10-26); every "expected" below is what the **emulator** shows. Items marked **[ESP32]** need the co-processor.

## 0. Before flashing (do not skip)

1. **Back up the calculator.** An OS change erases RAM; archived variables may or may not survive (see 8), so treat everything as lost. Use TiLP to save your programs and variables to the PC.
2. **Get the original OS file** so you can go back: download the TI-83 Plus OS (the Silver Edition uses the same OS file as the TI-83 Plus, version 1.19) from TI's website and keep it next to the PC. Without it you cannot recover from a failed install.
3. **Have at hand:** a working link cable (USB SilverLink / TI-Graph Link USB or serial) and **TiLP** (it sends `.8xu` OS files as they are). TI Connect CE was not checked with a TI-83 Plus SE or with a non-TI OS: use TiLP. **Fresh batteries** (a flash write cannot be interrupted), this folder.
4. **Read section 9 first** and make sure you know how to get the `Waiting... Please install operating system now` screen (DEL while reinserting a battery), ideally by rehearsing it once while the TI OS is still installed (then just resend the TI OS). That is your way back; Super-OS itself cannot receive an OS.
5. Optional but recommended: run the same image in the PC simulator first: `.\scripts\3_run_simulator_or_flash.ps1`.
6. Check the package: `python tools\verify_8xu.py` must end with `all checks passed` (file structure + the RSA signature math with key 04; acceptance by your boot code is still untested).
7. Note your unit: on the TI OS press **2ND + MEM > 1 About** and write down the OS version. Boot code revision is not shown there; if the upgrade is rejected, write down that fact (see 9).
8. **Archived TI variables may stay in flash** after an OS change. Super-OS never writes pages `$07-$1F`; it uses `$20-$7B` for its package store, settings journal and the
   DIAGNOSTICS scratch sector. Old data there is handled (tested in the emulator with random data): the settings journal restarts on a clean sector, and an
   install over a foreign package directory is refused. If OTA > INSTALLED lists names you never installed, use **OTA > 3 ERASE ALL** once.

## 1. Install

1. Connect the cable, calculator ON, nothing running.
2. TiLP: select the cable, detect the calculator, **Send file** `dist/SuperOS.8xu` (it is recognised as an OS upgrade).
3. The calculator shows a progress bar and restarts into the new OS. **Do not unplug or remove batteries.** Typical duration: 1-2 minutes.

Expected: after the restart the Super-OS home screen appears (status bar, tab row `INIC MATE IA JUEG SIST`, icons list).
If the install is refused, the unit shows `Waiting... Please install operating system now`, or the screen stays blank / frozen for more than ~10 s after the transfer: go to section 9.

## 2. First boot (about 1 minute)

| Check | Expected |
|---|---|
| Home screen | status bar `100%/15MHZ` area + clock, tab row, numbered list |
| Idle | no flicker, stable image, no beeps/garbage |
| Keys F1-F5 | tabs change (INIC / MATE / IA / JUEG / SIST) |
| Wait 2 minutes untouched | the screen turns off (deep sleep); ON wakes it to the same screen |
| 2ND + ON | immediate sleep; ON wakes it |

## 3. DIAGNOSTICS (F5 tab, item 7): hardware self-checks

| Test | Expected |
|---|---|
| `2 LCD` | RIGHT cycles black / white / checker / stripes / gray. UP/DOWN change contrast live. Write down the contrast value where it is readable. Gray bands show 4 levels (a little flicker is normal). |
| `3 KEYS` | every key changes exactly one bit of R0..R6; ON shows `ON:1` while held; hold CLEAR 2 s to leave |
| `4 RAM` | 7 lines PASS; page 1 shows LIVE (the OS runs there) |
| `5 FLASH` | GUARD, ERASE, PROGRAM, ERASE AGAIN all PASS. Only pages `$74-$77` are touched. If ERASE/PROGRAM fail the unit's flash geometry or unlock differs: write down which line. |
| `1 ESP32 LINK` **[ESP32]** | without the ESP32: `TIP:1 RING:1` idle levels, the test ends with FAIL after a few seconds: expected. |

## 4. Calculator and grapher (F2 tab)

* `F2, 1` Calculator: `2+3*4` ENTER = 14; `sqrt(16)` = 4; `sin(30)` in DEG = 0.5; `5 STO A` then `A*2` = 10; `1/0` = error message; `2nd+MODE` leaves.
* `F2, 2` Grapher: `Y=` type `X^2` ENTER, `GRAPH` draws the parabola in about 1-2 s; `TRACE` shows X/Y; `ZOOM` entries work; `2nd+GRAPH` table.
* `F2, 5` periodic table, `F2, 6` converter (5 mm = 0.5 cm, 100 C = 212 F), `F2, 7` constants, CLOCK (set the time), SETTINGS (language ES/EN, battery profile, contrast trim: these persist after pulling a battery for 10 s, then reinsert).

## 4b. Timing and keyboard (the two things the emulator could not tell)

* `F5`, `7 DIAGNOSTICS`, `7 TIMING`: **TICKS/S about 108**, **CPU MHZ about 15.0**, RTC OK. A tick rate far from 108 or a CPU near 6 MHz would explain slow games.
* `3 KEYBOARD`: press every key once; each must flip exactly one bit and nothing else (the settle time was lengthened to 48 T).
* If the calculator ever restarts by itself, the next boot shows `REINICIO PC=.... SP=....`: write both numbers down.

## 5. Games (F4 tab): no ESP32 needed

Native games, `1` to `8` (Tetris, Snake, Breakout, Pong, 2048, Invaders, Minesweeper, Sokoban) and, on the second page (`9` or `F4` again), Reversi: each must start, answer the arrows / `2ND` / `ALPHA`, pause with `MODE` and leave with `CLEAR` `CLEAR`. Look for: flicker, missing pixels (the LCD is updated tile by tile), keys that need two presses, speeds that feel wrong, anything that restarts the calculator. Best scores are kept in the settings (flash journal): beat one, pull a battery for 10 s, reinsert, and the record must still be there.

## 5c. Lock, exam mode, notes, contrast shortcut

* `+` / `-` on the launcher change the contrast at once; after the next other key the value survives a battery pull.
* `F5`, `8 LOCK`: `1` set a PIN twice, then `2ND+ON` (sleep) and wake: the PIN screen must come before anything else, a wrong PIN is refused. `2` exam mode: games, AI and network entries answer `MODO EXAMEN: CERRADO`. `3` turns it off. Test the way out **before** relying on it: there is no back door (a forgotten PIN = reinstall the OS).
* `F2`, `8 NOTES`: write a note, leave, reopen it (the text must be there), sleep and wake, erase it with `DEL` then its number.

## 5b. CHIP-8 classics (F4 `8`): no ESP32 needed

`1 ARCADE` (PONG, BREAKOUT, SNAKE), `2 ACTION` (INVADERS, DODGE, SIMON). Number pad = CHIP-8 keypad (arrows = 2 4 6 8, ENTER = 5), CLEAR quits.
Expected: smooth, no flicker, CLEAR returns to the pack menu. If a key does nothing, check `3 KEYS` first. `3 STREAM 3D` **[ESP32]**: shows `SIN RESPUESTA ESP32` (or similar) after ~6 s; CLEAR cancels at once.

## 6. Behaviour without the ESP32 (this is what you will see today)

Open `F3 > 1 CHAT IA`, type anything with the number keys, press ENTER: `ESPERANDO...` then `SIN RESPUESTA ESP32` after ~6 s; pressing CLEAR during the wait cancels immediately. Same for Wikipedia, weather, Step by step, CAS, WiFi+API, OTA, STREAM 3D. **[ESP32]** The actual AI/CAS/Wikipedia/weather/OTA/streaming functions cannot be tested today.

## 7. Battery and contrast

1. SETTINGS: choose the profile that matches your cells (alkaline / NiMH / Li-ion). Do not select Li-ion with alkaline cells.
2. Fresh batteries: note the contrast at which text is readable; leave the calculator on the launcher with auto-sleep set to the longest value and note the time until it dies or the low-battery message appears. The emulator cannot tell you the real duration. **Real consumption: not measured by me.**
3. With the batteries half empty the status bar level drops and the contrast boosts automatically (low-battery profile).

## 8. What to write down if something fails

* Which step, the **exact text** on the screen (or a photo), and *when* it happened (during install, at the first screen, after N seconds, on a key press).
* Unit: OS version before the install, cable type, software (TiLP version), batteries.
* Whether the calculator still responds to ON, and whether the TI OS can be reinstalled.

## 9. Back to the factory OS (read this BEFORE installing)

**Super-OS cannot receive an OS through the cable** (it does not implement TI's link protocol), so TiLP / TI Connect cannot talk to it while it runs.
The way back always goes through the **boot code's receive mode**, which lives on page `$7F` and is never written by `SuperOS.8xu`:

1. Take out **one** AAA battery (leave the small backup cell in place).
2. Press and **hold DEL**, put the AAA battery back while holding DEL, release DEL after a second or two.
3. The screen must show `Waiting... Please install operating system now` (this is the boot code, not Super-OS). If the screen stays blank, press ON once.
4. Connect the cable and send the original TI-83 Plus OS `.8xu` with TiLP (Send file). The boot code accepts TI's own signed OS.
5. Restore your backup (section 0).

The same procedure is the answer to every failure after the install: blank screen, garbage, a freeze, a reset loop, or a Super-OS that runs but you want gone.
It is the documented way the TI-83 Plus family forces the boot code to wait for an OS; it was **not** tried on this project's unit.
If step 3 never shows the message: stop, do not try other key combinations or tools, keep the unit powered off and write down what you see (section 8).

What could still go wrong and is out of reach of the procedure above (assessed as unlikely, not tested): the boot code itself refusing to start, which
would need page `$7F` or `$7E` damaged. `SuperOS.8xu` does not contain those pages and Super-OS refuses to program or erase them (and every page below `$20`).

## Not testable today (needs the ESP32 or instruments)
Link, turbo, Wi-Fi, DeepSeek, Super-CAS, 3D plot, Wikipedia, weather, OTA over Wi-Fi, streamed games, real current draw and battery life.
