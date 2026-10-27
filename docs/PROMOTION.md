# Promotion kit (drafts, not published)

Material for showing Super-OS to the people who would care about it. Nothing here is posted
automatically; each step is the maintainer's call.

## 1. GitHub repository settings

**Topics** (Settings → About → gear icon):

```
ti-83, ti-83-plus, z80, z80-assembly, operating-system, calculator, retrocomputing,
homebrew, esp32, ti-calculator
```

**Description** (one line, under 350 characters):

> A free, from-scratch operating system for the TI-83 Plus Silver Edition: native games, PIN lock, notepad, scientific tools, and an optional ESP32-S3 bridge for AI chat and computer algebra.

**Social preview** (Settings → Social preview): 1280×640 PNG. Suggested content: the games
montage (`docs/screens/games.png`) with the title "Super-OS" and the line "OS for the TI-83 Plus SE".

**Website**: leave empty, or link the release page `https://github.com/azariellarocca1999/super-os/releases/latest`.

## 2. A short GIF for the top of the README (to record)

Ten seconds, emulator only: home screen → Tetris (a few moves) → Sokoban (one undo) →
back to the launcher. Keep it under 3 MB. Save it as `docs/screens/demo.gif` and put it in
the README above the screenshot. This is the single change most likely to help.

## 3. Post drafts

### Cemetech / TI-Planet (forum post, English)

**Title:** Super-OS 1.0: a from-scratch OS for the TI-83 Plus SE (games, PIN lock, ESP32 bridge)

> Hi all. I have been writing an operating system for the TI-83 Plus Silver Edition in Z80 assembly. It has a preemptive kernel, a 96×64 UI in English and Spanish, deep sleep, flash-journaled settings, and nine native games (Tetris, Snake, Breakout, Pong, 2048, Invaders, Minesweeper, Sokoban, Reversi) with best scores kept in flash.
>
> There is also a calculator, grapher, unit converter, periodic table, a PIN lock with exam mode, and a notepad. An optional ESP32-S3 on the link port adds AI chat, a computer-algebra system and streamed games.
>
> Honest status: it has been verified in the emulator. It booted on one real TI-83+ SE (boot code 1.00, OS 1.19), but the rest has not been tested on hardware. Installing an OS can leave a calculator unusable until you reinstall the official one, so please read INSTALL.md first, including the way back.
>
> Source (MIT): https://github.com/azariellarocca1999/super-os
> Release: https://github.com/azariellarocca1999/super-os/releases/tag/v1.0.0
>
> Hardware reports are very welcome. `DIAGNOSTICS > 7 TIMING` is the most useful number.

### Reddit (r/TI_Calculators, r/retrocomputing, r/z80)

**Title:** I wrote a free OS for the TI-83 Plus SE in Z80 assembly (nine games, PIN lock, notepad)

Same body as the forum post, shortened, with the screenshot of the games menu attached.
Check each subreddit's self-promotion rules first; r/TI_Calculators allows project posts with
a clear status note.

### Hacker News (Show HN)

**Title:** Show HN: Super-OS, an operating system I wrote for a 2004 TI-83 Plus SE calculator

> Super-OS is a from-scratch OS for the TI-83 Plus Silver Edition (Z80 at 15 MHz, 128 KB RAM). It runs a preemptive kernel, a small UI, nine native games, a settings journal in flash and a scientific toolset. The optional ESP32-S3 bridge adds AI chat and streamed games over a custom link protocol. Everything past first boot is tested in an emulator; one real unit booted it. Repo and release notes are linked; I would value reports from anyone with the hardware.

Post it at a weekday morning (US time) and answer questions in the first hour.

### Mastodon / X / LinkedIn (short)

> Super-OS 1.0 is out: a free operating system I wrote in Z80 assembly for the TI-83 Plus Silver Edition. Nine native games, PIN lock, notepad, scientific tools. Emulator-tested; it booted on a real calculator. Hardware reports welcome.
> https://github.com/azariellarocca1999/super-os
> #retrocomputing #z80 #ti83 #homebrew

## 4. Things that help over time

* Tag issues `good first issue`: more Sokoban levels (`tools/gen_sokoban.py`), translations of `tools/gen_strings.py`, a new CHIP-8 ROM.
* Keep release notes short and factual; they are what people link to.
* A 3–5 minute video of the calculator (install, first boot, one game) is the most shareable thing you can add.
* Pin the repo on your GitHub profile.

## 5. Checklist before posting

- [ ] Release page and README links work
- [ ] The honest-status paragraph is visible in every post
- [ ] No ROMs or keys are attached (they are gitignored; keep it that way)
- [ ] Demo GIF added, if recorded
