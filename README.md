# Super-OS

**A free, from-scratch operating system for the TI-83 Plus Silver Edition** (Z80 at 15 MHz, 128 KB RAM, 2 MB flash), with an optional ESP32-S3 on the link port that adds Wi-Fi, an AI chat, a computer-algebra system and streamed games.

[Español](README.es.md) · [Install it](docs/INSTALL.md) · [Games](docs/GAMES.md) · [Manual](docs/MANUAL.md) · [Status and honesty](docs/STATUS.md)

![The native games](docs/screens/games.png)

> **Honest status.** **1.0 means feature-complete and fully tested in the emulator, not hardware-proven.** Super-OS was written and tested in an emulator, and on 2026-10-26 it booted on a real TI-83+ SE (boot code 1.00, OS 1.19) for the first time. Everything past "it boots and shows the home screen" was verified in the emulator only (the 1.0 test battery plays whole Reversi games against a reference implementation, solves every Sokoban level and checks the lock in every context), but **it has not been re-tested on a real unit**, and the ESP32 firmware has never run on a chip. Hardware reports are what the next version is made of. Installing an OS can leave a calculator unusable until you reinstall the official one: read [docs/INSTALL.md](docs/INSTALL.md) first, including "the way back".

## What is in it

* **A real operating system**: preemptive kernel (idle, UI, power and link tasks), 96x64 UI with two fonts, ES / EN, three battery profiles, deep sleep, a real-time clock, flash-journaled settings, a package store with over-the-air installs, hardware diagnostics (LCD, keyboard, RAM, flash, timing, link).
* **Nine native games**, full screen, with pause, sleep handling and **best scores kept in flash**: **Tetris, Snake, Breakout, Pong, 2048, Space Invaders, Minesweeper, Sokoban (8 proven-solvable levels), Reversi (against the calculator)** ([guide](docs/GAMES.md)), plus six CHIP-8 classics running in a CHIP-8 interpreter.
* **Everyday extras**: PIN lock (asked at start-up and after every sleep, wherever you were) and **exam mode** (calculator and grapher only), a four-note **notepad**, live contrast shortcut (`+` / `-` on the launcher). How it compares with KnightOS and Doors CS: [docs/FEATURES.md](docs/FEATURES.md).
* **Scientific tools**: a 32-bit-mantissa floating-point library, a TI-style calculator with a MATH menu, a 2D grapher (trace, table, zoom), unit converter (84 units), periodic table (118 elements), 49 physical constants.
* **With the ESP32-S3** (optional): DeepSeek chat and step-by-step R1 explanations, **Super-CAS** (symbolic algebra: derivatives, integrals, limits, equations, matrices, 3D plots), Wikipedia, weather, and games streamed from the ESP32 (a ray-casting maze, Game Boy through [Peanut-GB](https://github.com/deltabeard/Peanut-GB)) over a calculator-clocked "turbo" link. Everything works without it; the apps that need it say so and CLEAR cancels the wait.
* **Careful engineering**: 130+ automated emulator checks, a Z80-vs-Python reference for the float library (324 cases) and the CHIP-8 interpreter, 212 CAS checks, fault injection on the link, a verifier for the signed `.8xu`, a duplicate-label check, a text-overflow audit.

## Try it in five minutes (emulator, nothing to flash)

```
git clone https://github.com/azariellarocca1999/super-os && cd super-os
.\scripts\1_install_toolchains.ps1      # once: downloads the assembler, emulator core, signing tools (Windows + PowerShell)
.\scripts\2_build_all.ps1 -Test         # builds everything and runs the whole test battery
.\scripts\3_run_simulator_or_flash.ps1  # a window with the calculator and a virtual ESP32
```

Keys in the simulator: arrows, Enter = ENTER, Esc = CLEAR, Backspace = DEL, F1-F5 = tabs, Shift = 2ND, Tab = ALPHA, O = ON. Games tab = F4.

## On a real calculator

Download `SuperOS.8xu` from the [releases](../../releases) and follow [docs/INSTALL.md](docs/INSTALL.md): back up, have the official OS ready, rehearse the recovery (battery out, hold DEL, battery in) and send the file with TI Connect's OS downloader. Hard-won facts from the first real flash (they are the reason a plain-looking `.8xu` was rejected until they were right):

* the OS must be signed with the **OS key (04)**, not the app key (0104), and the signature records must be laid out like TI's own files;
* the LCD needs the full start-up sequence (`05 01 03 17 0B`, then contrast `C0 + 24 + n`);
* the keyboard matrix needs ~40 T-states of settling at 15 MHz.

## Repository map

```
z80-os/           the OS: kernel, drivers, UI, power, SuperLink, math, apps, games (flash pages 0-6)
esp32-firmware/   PlatformIO firmware (SuperLink, Wi-Fi, DeepSeek, NTP, Wikipedia, weather, OTA) + lib/supercas + lib/superplay
bridge_pc/        a virtual ESP32 for the simulator (same protocol, same services)
pc-simulator/     headless + live emulator harness on Tilem's core
games/            CHIP-8 sources and the redistributable test ROMs
cas/ tools/       host tools, generators, the test suite (selftest*.py, mathtest.py, c8test.py, ...), the Z80 disassembler/tracer
docs/             STATUS, INSTALL, MANUAL, GAMES, BRINGUP (first contact with the ESP32), WIRING, PERF, REVIEW, PENDING
scripts/          install toolchains, build + test, run
```

## Documentation

| | |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | flashing, the way back, what to check first |
| [docs/GAMES.md](docs/GAMES.md) | the games, controls, scoring |
| [docs/FEATURES.md](docs/FEATURES.md) | what Super-OS has next to KnightOS / Doors CS, and what is missing |
| [docs/MANUAL.md](docs/MANUAL.md) | short user manual (EN / ES) |
| [docs/STATUS.md](docs/STATUS.md) | what is verified, what is not |
| [docs/REVIEW.md](docs/REVIEW.md) | the critical review, including every bug found on real hardware |
| [docs/PERF.md](docs/PERF.md) | measured power / performance numbers |
| [docs/BRINGUP.md](docs/BRINGUP.md), [docs/WIRING.md](docs/WIRING.md) | connecting the ESP32 (level shifters, first contact) |
| [docs/PENDING.md](docs/PENDING.md) | roadmap |

## Contributing

Issues and pull requests are welcome, especially **reports from real calculators** (model, boot code, OS version, what you saw). See [CONTRIBUTING.md](CONTRIBUTING.md). Dependencies and licenses of third-party code: [THIRD_PARTY.md](THIRD_PARTY.md).

## License

[MIT](LICENSE). Super-OS is an independent project: it is not affiliated with or endorsed by Texas Instruments. "TI-83 Plus" and "TI-83 Plus Silver Edition" are trademarks of Texas Instruments. No TI software or commercial ROMs are included; you need your own official OS to go back.
