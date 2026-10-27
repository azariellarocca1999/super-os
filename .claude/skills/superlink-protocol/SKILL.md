---
name: superlink-protocol
description: SuperLink serial protocol between Super-OS (Z80) and the ESP32-S3 over the 2.5 mm link port - frame format, bit-level handshake, wake pulse, ACK/NACK, ESP_READY, sleep command, throughput math and the turbo plan.
---

# SuperLink

## Frame
`[SYNC=$53][CMD][LEN_L][LEN_H][PAYLOAD...][CRC8]` - CRC8 poly $07, init 0, over CMD, LEN_L, LEN_H and the payload.
Every frame is answered by ONE byte: ACK $06 / NACK $15 (the sender retries up to 3 times).
Replies to a request are a stream of frames `RSP_MORE ($80) ... RSP_LAST ($81)`; the concatenated payloads are one ZX0 stream.
Frames may be interleaved with `CMD_STATUS` ([state][rssi]), `CMD_TIME` ([h][m]) and `RSP_NOTIFY`; each restarts the calculator's reply
timeout (used as keepalive while an LLM thinks). `RSP_ERR ($82)` aborts.

Commands: PING 1, CHAT 2 ([model 0=V3 1=R1][text]), WIKI 3, STORE 4, BOOK 5, WEATHER 6, WIFI_SCAN $10, WIFI_SET $11 (ssid 0 password),
STATUS $12, TIME $13, API_SET $14, DIAG $15, BENCH $16, OTA $20, CAS $30, PLOT3D $31, GAME $32, TURBO $33, SLEEP $FF.

## Bit/byte layer ("safe": TI-compatible handshake, speed independent)
Lines: tip = D0 (port bit 0), ring = D1 (bit 1); open drain: a line is low if ANY end pulls it. Bytes go LSB first.
The sender pulls TIP low for a 0 and RING low for a 1; the receiver acknowledges by pulling the OTHER line; the sender releases; the receiver releases.
The sender waits for both lines high before the next bit. A responder must stay released ~250 us before pulling (turnaround), otherwise the
peer never sees idle-high (this bug was found in the lockstep simulator).

## Wake / sleep
* ESP32 asleep (calculator's `v_esp = 0`): the calculator pulls TIP low for 50 ms, releases, and waits up to 5 s for the raw bytes `$A5 $5A` (ESP_READY).
  ESP32-S3 deep-sleep wake = `esp_sleep_enable_ext0_wakeup(GPIO_NUM_1, 0)`; boot takes ~250 ms, the pulse is over by then, hence the READY handshake.
* Idle: after `s_espsleep` x 10 s (default 180 s, max 600 s) without traffic the calculator sends `CMD_SLEEP`; the ESP32 acks and deep-sleeps. The ESP32's own idle timer (900 s) is only a safety net and must stay above the calculator's maximum.
* Calculator side: the link-activity interrupt (port $03 bit 4) wakes the link task and the calculator's own deep sleep.

## Turbo byte layer (implemented, emulator-verified; hardware timing pending)
`CMD_TURBO [1]` is answered in the safe layer; after the calculator ACKs the last reply frame both ends switch (`[0]` switches back, a failed exchange makes the
calculator fall back and the ESP32 reverts after 3 s of silence). Frames, ACK/NACK, retries, CRC8 are unchanged - only the byte layer differs.
* RING (D1) = clock, driven by the calculator only; TIP (D0) = data. Idle: both released (high).
* calc -> ESP: the calculator sets TIP (0 = pulled low, 1 = released), pulls RING low, releases RING; the ESP samples TIP at the clock edge. 8 bits, LSB first.
* ESP -> calc: TIP low = "byte ready" (start bit). The calculator then clocks 9 pulses; on every falling edge the ESP puts the next bit on TIP (8 data bits, then a released stop bit);
  the calculator reads TIP while the clock is low. After the stop bit TIP is high, so the next start bit is unambiguous.
* Z80 timing knobs `TL_TX / TL_RXLOW / TL_RXHIGH` in `z80-os/net/superlink.z80` (1/3/1 = ~100-115 kbit/s; 2/4/2 = ~84 kbit/s - use it if the cable is slow). ESP32 side: tight GPIO polling with interrupts off per byte (`superlink.cpp`).
* `link_direct` (syscall $019C) runs an exchange in the caller's context (no link-task round trip) - streaming loops use it.
* `CMD_GAME [op]`: 0 titles (text lines), 1 start `[index]`, 2 frame `[keys lo][keys hi][flags]`, 3 stop. Replies are RAW (not ZX0) RSP_MORE/RSP_LAST chunks.

## Throughput
Safe mode costs ~4 line transitions per bit plus polling latency: ~1.6 ms per byte in the lockstep simulator (~5 kbit/s). It is meant for text
(chat, lists). Streaming (games, plots) needs the **turbo** physical layer: calculator-clocked synchronous transfer (D1 = clock, D0 = data, no per-bit
handshake, 60-115 kbit/s target). A 768-byte frame is 6144 bits: 115 kbit/s -> 18.7 FPS maximum, 60 kbit/s -> 9.7 FPS.
The turbo layer above implements this; cable capacitance and pull-up strength set the real ceiling and must be validated on hardware.
