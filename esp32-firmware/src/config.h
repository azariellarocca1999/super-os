#pragma once
// ---- wiring (Waveshare ESP32-S3-Zero) ----------------------------------------------------------
// TI-83 Plus SE 2.5 mm link jack: tip = D0 (red wire), ring = D1 (white wire), sleeve = GND.
// GPIO1 / GPIO2 are RTC-capable: required for deep-sleep wake (ext0 on GPIO1).
//
// ELECTRICAL (see docs/WIRING.md): the calculator lines idle near its supply (4.5-6 V) and the ESP32-S3
// is NOT 5 V tolerant -> one BSS138 level shifter per line (recommended).  The resistor divider from
// the original spec (1k series + 2k2 to GND) loads an open-drain line that the calculator only pulls
// up weakly: verify with a scope/multimeter before connecting.
#define PIN_TIP   1
#define PIN_RING  2

// ---- power ------------------------------------------------------------------------------------------
#define FW_VERSION "0.4"
#define DEFAULT_IDLE_SLEEP_S 900      // safety net only: the calculator sends CMD_SLEEP after its own setting (30-600 s); this must stay longer
                                      // than that maximum, or the chip sleeps while the calculator believes it is awake

// ---- link timing --------------------------------------------------------------------------------------
#define LINK_STEP_TIMEOUT_US  500000UL
#define LINK_TURNAROUND_US    250        // stay released this long before pulling a line (calculator needs to see idle-high)

// ---- protocol (must match z80-os/kernel/superos.inc) --------------------------------------------------
#define SL_SYNC       0x53
#define SL_ACK        0x06
#define SL_NACK       0x15
#define CMD_PING      0x01
#define CMD_CHAT      0x02
#define CMD_WIKI      0x03
#define CMD_STORE     0x04
#define CMD_BOOK      0x05
#define CMD_WEATHER   0x06
#define CMD_WIFI_SCAN 0x10
#define CMD_WIFI_SET  0x11
#define CMD_STATUS    0x12
#define CMD_TIME      0x13
#define CMD_API_SET   0x14
#define CMD_DIAG      0x15
#define CMD_BENCH     0x16
#define CMD_OTA       0x20
#define CMD_CAS       0x30      // Super-CAS: text command -> text result
#define CMD_PLOT3D    0x31      // plot3d(...) -> 96x64 bitmap (768 bytes)
#define CMD_GAME      0x32      // streamed games [op][...] -> raw frames (lib/superplay)
#define CMD_TURBO     0x33      // [1] / [0]: calculator-clocked byte layer on / off
#define CMD_SLEEP     0xFF
#define RSP_MORE      0x80
#define RSP_LAST      0x81
#define RSP_ERR       0x82
#define RSP_NOTIFY    0x90
#define CHUNK_MAX     240
#define MAX_PAYLOAD   512
