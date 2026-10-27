# What Super-OS has, next to the other custom calculator OSes and shells

Researched on 2026-10-26 from the public descriptions of **KnightOS** and the **Doors CS / MirageOS / Ion** shells for the TI-83 Plus family ([KnightOS kernel notes](https://www.omnimaga.org/news/some-news-about-knightos), [Cemetech shell archive](https://www.cemetech.net/downloads/browse/83plus/asm/shells), [Doors CS 7 announcement](https://www.cemetech.net/forum/viewtopic.php?p=107789)). The aim was to see which headline features users of such projects expect and which of them fit Super-OS. This is a feature comparison from the projects' own descriptions, not a benchmark.

| Feature people expect | KnightOS | Doors CS / Mirage / Ion | Super-OS |
|---|---|---|---|
| Replaces the TI OS, signed `.8xu` | yes | no (runs on top of TI-OS) | **yes** (boots on a real TI-83+ SE) |
| Preemptive multitasking, own kernel | yes (up to 10-32 processes, depending on version) | no | yes (idle / UI / power / link tasks; apps run one at a time) |
| Launcher with several ways to reach apps | yes ("castle") | yes (GUI + shortcuts) | yes (5 tabs, numbered entries, second page of games) |
| File manager, folders, copy / rename / hide | yes (tree filesystem) | yes (nested folders, lock, rename, archive) | **partial**: a package store (list, run, delete, erase all); no folders |
| Runs third-party programs | KnightOS programs | TI-BASIC and assembly (Ion, Mirage, Doors) | CHIP-8 games, packages over the air, a small TI-OS `B_CALL` shim for simple Ion-style programs; **no TI-BASIC** |
| Programming on the calculator | text editor + tools | via TI-OS | **no** (a notepad only) |
| Calculator + grapher | yes (basic) | the TI-OS one | **yes** (own float library, grapher, table, trace, zoom; Super-CAS with the ESP32) |
| Games | a few | the main reason these shells exist | **9 native + 6 CHIP-8 + streamed** |
| Screen lock / PIN, exam mode | no | no | **yes** (PIN after sleep, exam mode closes games and network apps) |
| Notes | text editor | no | **yes** (4 notes, battery-backed RAM) |
| Link between calculators | yes | CALCnet (Doors CS) | no (the link port is used for the ESP32) |
| Wi-Fi, AI chat, Wikipedia, weather | no | no | **yes, with the ESP32** |
| Power management | basic | n/a | **yes** (3 battery profiles, deep sleep, contrast compensation) |
| Hardware diagnostics | no | no | **yes** (LCD, keys, RAM, flash, timing, link) |

## Added after the comparison

PIN lock + exam mode (in the kernel, so it covers apps and games), a four-note notepad, persistent best scores, a live contrast shortcut, Sokoban and Reversi.

## Looked at and not done (and why)

* **TI-BASIC / a programming language.** The most requested feature of all, and the biggest piece of work: an interpreter, an editor with tokens, storage. The math page is 97 % full, so it needs its own flash page and a design of its own. Listed first in [PENDING.md](PENDING.md).
* **Folders and a real file manager.** The package store is append-only flash (deleting only marks entries); folders need a different on-flash layout.
* **Running unmodified TI programs.** Needs most of the TI-OS `B_CALL` surface and the TI-OS memory layout; the shim covers the simple Ion-style cases only. Almost all programs on ticalc.org carry no clear redistribution licence, so none are bundled; install your own through OTA.
* **Calculator-to-calculator link.** The only link port is taken by the ESP32 bridge.