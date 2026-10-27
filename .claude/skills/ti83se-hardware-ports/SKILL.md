---
name: ti83se-hardware-ports
description: TI-83 Plus Silver Edition hardware reference for Super-OS - I/O ports, memory map, RAM execution limits, flash protection, LCD timing at 15 MHz, crystal timers, battery probing. Use before touching any port, bank or flash code.
---

# TI-83 Plus Silver Edition - hardware facts used by Super-OS

Sources: WikiTI port pages (`docs/wikiti/`), the Tilem2 core (`tools/src/tilem`, ground truth of the emulator) and the KnightOS kernel layout
(`tools/src/kernel`: PRIVILEGED 0x1F0000, BOOT 0x1FC000 on SE). Anything marked **(emu)** is what Tilem does and is not confirmed on silicon.

## CPU / clock
* `out ($20),a`: 0 = 6 MHz, 1 = 15 MHz (values 2-3 give ~15 MHz as well). SE/84+ only; on the plain 83+ the port aliases port 0.
* SE detection: `in a,($02)` bit 7 = 1 on everything except the plain 83+ / 73.

## Memory map (mode 0, `out ($04)` bit0 = 0)
| window | content | port |
|---|---|---|
| $0000-$3FFF | flash page 0 | - |
| $4000-$7FFF | bank A: flash page $00-$7F or RAM page $80-$87 (bit 7 = RAM) | $06 |
| $8000-$BFFF | bank B: same | $07 |
| $C000-$FFFF | RAM page $80-$87 only | $05 (0-7) |

Reset: PC=$8000 with boot page $7F mapped there; certificate page $7E at $4000 (reads return $FF unless flash is unlocked **(emu)**).
Flash pages $00-$7F (2 MB). Boot ($7F) and certificate ($7E) must never be written. Privileged pages are $7C-$7F.

## RAM execution limits
Ports $25/$26 (units of 1 KB) and $21 define where code may execute in RAM; the defaults make only **odd** RAM pages
($81,$83,$85,$87) executable. Super-OS keeps code in flash, data/stacks/buffers in page $81 at $8000 (executable, so TI-OS style
programs at userMem $9D95 run) and uses the $C000 window (port 5) as bulk data RAM. Writing ports $21-$23/$25/$26 requires flash unlocked.

## Flash unlock
`out ($14),1` is honoured only if the byte sequence `00 00 ED 56 F3 D3 14` was *fetched* from a privileged page ($7C-$7F).
Super-OS ships the 8-byte routine `nop nop im 1 di out ($14),a ret` at page $7C offset $3FF0 (tools/flashunlock.z80).
Programming sequence (JEDEC): `$AA->$4AAA, $55->$4555, $A0->$4AAA, byte->target`, poll DQ7; the loop runs from RAM.
Only pages $20-$7B can be programmed (`flash_check_page`); the OS ($00-$06, $7C) and $7C-$7F are refused.

## Interrupts (port $03 mask, $04 source, $02 ack on SE)
$03: bit0 ON key, bit1 timer 1, bit2 timer 2, bit3 = 0 -> low-power on HALT, bit4 link activity.
$04 read: bit0 ON, 1 T1, 2 T2, bit3 = ON held (0), bit4 link, bits 5-7 crystal timers 1-3 expired.
$02 write (SE): write 0 to a bit to acknowledge (ON, T1, T2, link). Legacy timer rate: `out ($04)` bits 1-2; 11 = slowest = 32768/304 = 107.8 Hz.

## Crystal timers ($30-$38, SE only)
Per timer: $30 on/off + divisor, $31 loop/interrupt control, $32 counter (counts DOWN from the written value; 0 = free loop, no flag).
Divisor $46 = 128 Hz, $47 = 8 Hz, $44 = 32768 Hz. Super-OS RTC: `$46`, loop+irq = 3, counter 128 = 1 s. Acknowledge by writing $31.
With port $03 bits 1-2 clear, timer interrupts are suppressed during HALT **(emu)**, so the RTC pauses in deep sleep.

## LCD (T6A04) at 15 MHz
$10 commands: $01 8-bit, $02 off, $03 on, $05 Y-down auto-increment, $20+n column, $80+n row, $C0+n contrast.
At least 10 us = 150 T-states between ANY two accesses at 15 MHz; Super-OS pads to ~156 T per byte (counted, no polling).
Port $02 bit1 = 0 while the SE LCD delay hardware is busy; ports $29-$2C/$2F configure it (boot code sets them).

## Battery
`in a,($02)` bit 0 = battery good against a threshold selected by `out ($04)` bits 6-7 (SE: only bit 7; 84+: both). Probe thresholds
high -> low to get levels 0..3. Always restore the timer bits afterwards.

## Keyboard
`out ($01),mask` (0 = selected row) then `in a,($01)` active low. `out ($01),0` selects every row: one read tells whether any key is down.
Key code = row*8 + bit + 1 (identical to TI GetCSC). ON is not in the matrix: `in a,($04)` bit 3.
