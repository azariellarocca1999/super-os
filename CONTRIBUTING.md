# Contributing

Thanks for looking! The most useful contribution is **a report from a real calculator**; the second is a game, an app or a fix with a test.

## Reports from hardware

Open an issue with the model, boot code (TI Connect shows it as "BIOS"), OS version before the install, how you installed it, what you saw (exact text or a photo) and, if the OS restarted by itself, the `PC=` and `SP=` it printed on the next boot. See `docs/INSTALL.md`.

## Building and testing

Windows + PowerShell (the toolchain scripts download everything into `tools/`):

```
.\scripts\1_install_toolchains.ps1
.\scripts\2_build_all.ps1 -Test        # everything must pass
python tools\build.py && python tools\selftest.py      # quick loop for Z80 changes
python tools\audit_text.py             # no UI string may exceed the 24-column screen
python tools\check_labels.py           # duplicated assembler names (spasm silently accepts them)
```

## Rules of the house

* **Code, comments and docs in English** (the UI is bilingual ES / EN; strings go through `tools/gen_strings.py`).
* **No change without a test** that fails before it. Games get a bot in `tools/selftest_games.py`; anything that touches the link goes through the virtual ESP32 (it can inject faults: `HZ_ESP_FAULT_RX / TX`).
* **Do not say it works on hardware unless somebody tried it.** `docs/STATUS.md` separates "verified in the emulator" from "verified on a unit".
* spasm-ng quirks: labels are global and case-insensitive (a label and an `.equ` with the same name silently collide), expressions evaluate left to right (use parentheses), `.org` does not pad, `.db` data lives in flash: **never write to a label that sits in code**, use an `.equ` into RAM.
* Never commit secrets (the DeepSeek key lives in the ESP32's NVS), the OS signing keys, ROMs you do not own, or TI software.

## Layout

See the repository map in `README.md`. A new native game is a file in `z80-os/games/` using `glib.z80`; `docs/GAMES.md` lists the five places to wire it in.

By contributing you agree that your work is released under the MIT license of this repository.
