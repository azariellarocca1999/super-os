#pragma once
#include <stddef.h>
#include <stdint.h>

// SuperLink, ESP32 side.  Frame: [SYNC=$53][CMD][LEN_L][LEN_H][PAYLOAD...][CRC8], each frame acked with
// $06 / $15.  Physical layer "safe" = TI handshake (mirror image of z80-os/net/superlink.z80).
namespace superlink {
uint8_t crc8(const uint8_t *d, size_t n, uint8_t crc = 0);

struct Stats {
  uint32_t rx_frames, tx_frames, crc_errors, nacks_sent, tx_retries, byte_timeouts;
};
extern Stats stats;
uint8_t levels();                                   // bit0 TIP, bit1 RING (1 = high), as seen now

void begin();
bool attention();                                   // the calculator holds a line low
bool recv_byte(uint8_t &b, uint32_t first_timeout_us);
bool send_byte(uint8_t b);
bool recv_frame(uint8_t &cmd, uint8_t *payload, uint16_t &len, uint32_t first_timeout_us);   // acks the frame
bool send_frame(uint8_t cmd, const uint8_t *payload, uint16_t len);                          // retries x3
bool send_ready();                                  // $A5 $5A after waking from deep sleep
bool send_stream(const uint8_t *data, size_t n);    // ZX0-compress and stream as RSP_MORE .. RSP_LAST
bool send_raw(const uint8_t *data, size_t n);       // same chunking, NOT compressed (game frames)
void set_turbo(bool on);                            // calculator-clocked byte layer (see z80-os/net/superlink.z80)
bool turbo();
}  // namespace superlink
