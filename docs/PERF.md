# Performance and battery: measurements and decisions

All numbers come from the headless emulator (`python tools\perf_measure.py`, 8 s of emulated time per scenario, the emulator's own HALT counter).
**HALT % is a proxy** for power use: the Z80 clock stops in HALT, but how much current that saves on a real SE was not measured (no instruments, no hardware).
No claim below is a battery-life number.

## Baseline (taken after the CLEAR-cancel change of `link_request`, before any optimisation attempt)

| Scenario | HALT % | Busy % |
|---|---|---|
| launcher idle | 96.7 | 3.3 |
| calculator editor idle | 96.2 | 3.8 |
| calculator editor, typing | 90.2 | 9.8 |
| grapher (plot included in the 8 s window) | 76.1 | 23.9 |
| periodic table idle | 95.2 | 4.8 |
| CHIP-8 PONG running | 74.4 | 25.6 |
| CHIP-8 SNAKE running | 68.8 | 31.2 |
| waiting for an absent ESP32 (5 s wake wait) | 93.5 | 6.5 |

Grapher: the plot itself costs ~2 s of CPU once; measured over 40 s the same scenario reaches 92.9 % HALT, and after the plot the idle cost equals the launcher's (~3 %).
(Same scenario at 8 / 20 / 40 s: 76.1 / 88.8 / 92.9 %.)

## What was tried

| Change | Result | Decision |
|---|---|---|
| `wait_key` poll interval 28 ms -> 37 ms (fewer idle context switches) | launcher idle 96.7 -> 97.0 % (-9 % of the busy time), CHIP-8 PONG 74.4 -> 75.2 %, SNAKE 68.8 -> 69.0 %. **But** the INVADERS menu check of `selftest_m4` failed (taps of 50 ms are missed with a 37 ms poll) | **Reverted.** The saving is not worth losing key taps. |
| Poll for completion in `link_request` (new, needed for CLEAR-cancel) | While waiting the busy share is 6.5 % versus ~3 % idle (a 2-tick poll + key scan; the cost of the old blocking wait was not measured separately), only during a request (5-6 s without an ESP32) | Kept: functional gain (cancel). |

## What the kernel already does (verified by reading + the numbers above)
* The scheduler returns straight from the ISR when the idle task is current and no sleeper is due (`v_nextwake`): an idle tick costs an ISR and nothing else.
* Every wait is a HALT through the idle task; the legacy timer already runs at its slowest rate (107.8 Hz); deep sleep turns the LCD and the timers off and only arms ON + link activity.
* CHIP-8: renders and blits only when the display changed (`c8_dirty`), runs at most 150 opcodes per tick and yields on `Fx07`.
* ESP32 firmware: 80 MHz by default (240 MHz only while a streamed game runs), Wi-Fi modem sleep `WIFI_PS_MIN_MODEM`, Wi-Fi off before deep sleep, BSSID/channel cached in RTC memory, deep sleep after the idle timeout.

## Not done, with the reason
* **6 MHz while idle**: the link layer (safe handshake polling and the turbo byte layer, tuned with cycle counts `TL_TX/TL_RXLOW/TL_RXHIGH`) and `sl_wait_start` are speed dependent; dropping the clock while the link task can run would silently break the turbo link, and the gain is unmeasurable here (HALT already stops the clock). Needs a real current measurement first.
* Float library, expression evaluator, grapher and CHIP-8 opcode timing were **not** re-optimised in this pass: no before/after numbers exist, so nothing is claimed. Existing figures: grapher full-width plot ~1.3 s, mathtest 324 cases pass.
* LCD contrast/refresh, per-task background cost and ESP32 buffer sizes: reviewed, no change justified by a measurement.
* Real battery duration, deep-sleep current of the calculator and of the ESP32 board: **not measured** (hardware).

## Games and the tile flush (round 2)
Same method (`python tools\perf_measure.py`, 8 s of emulated time, HALT % from the emulator's slice counters). Before the CHIP-8 frame fix and the tile flush, then after:

| Scenario | HALT % before | HALT % after |
|---|---|---|
| CHIP-8 PONG / SNAKE running | 74.4 / 68.8 | **92.4 / 92.1** (frames shown only when complete) |
| native Tetris / Snake | 92.0 / 92.8 | 92.5 / 93.6 (event driven: a few redraws per second) |
| native Breakout, ball waiting on the paddle | 49.4 | **94.0** (no redraw when nothing moved) |
| native Pong playing | 66.3 | **87.6** (tile flush + no redraw during the serve wait) |
| native Invaders playing | 48.5 | 60.6 (the formation covers most of the screen) |
| native 2048 / Minesweeper waiting | 94.3 / 94.1 | 94.3 / 94.1 |

How: `gl_flush` compares the frame buffer with a copy of what the LCD shows and sends only the changed 8x8 tiles (a full screen is 768 x 156 T = 8 ms; a moving ball is a few tiles); `gl_changed` skips the whole redraw when the game state hash did not change. Not measured: real current draw (no instrument), so none of this is a battery-life claim.
