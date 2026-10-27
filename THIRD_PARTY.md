# Third-party code and data

The repository contains the following third-party material; each keeps its own license.

| Component | Where | License |
|---|---|---|
| **Peanut-GB** (Game Boy emulator core, Mahyar Koshkouei; contains code from SameBoy) | `esp32-firmware/lib/superplay/peanut_gb.h` | MIT |
| **dmg-acid2** (Game Boy test ROM, Matt Currie) | `esp32-firmware/lib/superplay/dmg_acid2.h`, `games/roms/dmg-acid2.gb` | MIT |
| **ZX0** compressor (Einar Saukas) | `esp32-firmware/lib/zx0/` (license file inside) | BSD-3-Clause |
| **ZX0 Z80 decoder** (Einar Saukas, Urusergi) | `z80-os/drivers/dzx0_standard.asm` | BSD-3-Clause |
| Periodic table data | `tools/ptable_data.txt` (generated from the `mendeleev` Python package's data) | the package is MIT; the facts are not copyrightable |
| CODATA constants | `tools/fxlib.py` / generated tables | physical constants (public) |

Fetched by `scripts/1_install_toolchains.ps1` into `tools/` (**not** redistributed in this repository): spasm-ng (assembler), Tilem's emulator core (used for the emulator tests), rabbitsign and mktiupgrade (signing), the OS signing key files (`tools/keys/`, taken from the rabbitsign and KnightOS sources; **never commit them**), PlatformIO and its Arduino-ESP32 / ArduinoJson packages. Check the license of each before redistributing them.

This project is not affiliated with Texas Instruments. No TI software, firmware or ROM is included. The structure of OS upgrade files was learned by comparing the public files of the official OS and of KnightOS; no code was copied from either.
