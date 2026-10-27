#include "superlink.h"
#include <Arduino.h>
#include "config.h"
#include "soc/gpio_struct.h"
#include "zx0_pack.h"

namespace superlink {
Stats stats = {};
static const uint32_t MASK_TIP = 1u << PIN_TIP, MASK_RING = 1u << PIN_RING;

uint8_t crc8(const uint8_t *d, size_t n, uint8_t crc) {
  while (n--) {
    crc ^= *d++;
    for (int i = 0; i < 8; i++) crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x07) : (uint8_t)(crc << 1);
  }
  return crc;
}

// Open-drain emulation: output latch = 0, direction toggles drive-low / Hi-Z.
static inline void pull(uint8_t m) {  // bit0 = tip, bit1 = ring
  uint32_t drive = ((m & 1) ? MASK_TIP : 0) | ((m & 2) ? MASK_RING : 0);
  GPIO.enable_w1tc = (MASK_TIP | MASK_RING) & ~drive;
  GPIO.enable_w1ts = drive;
}
static inline uint8_t lines() {  // bit0 tip level, bit1 ring level (1 = high)
  uint32_t in = GPIO.in;
  return (uint8_t)(((in >> PIN_TIP) & 1) | (((in >> PIN_RING) & 1) << 1));
}

void begin() {
  for (int p : {PIN_TIP, PIN_RING}) {
    pinMode(p, INPUT_PULLUP);
    digitalWrite(p, LOW);  // latch low; the direction stays input until pull()
  }
  GPIO.enable_w1tc = MASK_TIP | MASK_RING;
}

bool attention() { return lines() != 3; }
uint8_t levels() { return lines(); }

static bool wait_for(uint8_t mask, uint8_t val, uint32_t timeout_us) {
  uint32_t t0 = micros();
  while ((lines() & mask) != val) {
    if ((uint32_t)(micros() - t0) > timeout_us) return false;
  }
  return true;
}

// ---- turbo byte layer ------------------------------------------------------------------------------------------------
// The calculator owns the clock (RING).  calc->ESP: sample TIP while RING is low.  ESP->calc: TIP low = byte ready, then on every
// falling clock edge present the next bit (8 data bits LSB first, then a released stop bit).  Each byte runs with interrupts off
// (~100 us): the calculator clocks at ~100 kbit/s, so edges are only ~5 us apart.
static bool g_turbo = false;
void set_turbo(bool on) { g_turbo = on; }
bool turbo() { return g_turbo; }

static inline uint32_t cyc() { return ESP.getCycleCount(); }
static inline bool ring_low() { return !((GPIO.in >> PIN_RING) & 1); }
static bool wait_ring(bool low, uint32_t timeout_us) {          // true when RING reached the wanted level
  uint32_t t0 = cyc(), lim = timeout_us * (getCpuFrequencyMhz());
  while (ring_low() != low) {
    if ((uint32_t)(cyc() - t0) > lim) return false;
  }
  return true;
}

static bool turbo_send_byte(uint8_t b) {
  pull(1);                                                      // start bit: TIP low = byte ready
  if (!wait_ring(true, 200000)) { pull(0); stats.byte_timeouts++; return false; }   // the calculator starts clocking
  noInterrupts();
  bool ok = true;
  for (int i = 0; i < 8 && ok; i++) {
    if (i > 0) ok = wait_ring(true, 3000);
    if (!ok) break;
    pull(((b >> i) & 1) ? 0 : 1);                               // data 0 = pull TIP, 1 = release
    ok = wait_ring(false, 3000);
  }
  if (ok) ok = wait_ring(true, 3000);                           // 9th clock: stop bit
  pull(0);
  if (ok) ok = wait_ring(false, 3000);
  interrupts();
  if (!ok) stats.byte_timeouts++;
  return ok;
}

static bool turbo_recv_byte(uint8_t &out, uint32_t first_timeout_us) {
  if (!wait_ring(true, first_timeout_us)) return false;         // first clock pulse of the byte
  noInterrupts();
  uint8_t v = 0;
  bool ok = true;
  for (int i = 0; i < 8 && ok; i++) {
    if (i > 0) ok = wait_ring(true, 3000);
    if (!ok) break;
    if ((GPIO.in >> PIN_TIP) & 1) v |= (uint8_t)(1u << i);      // TIP released = 1, pulled low by the calculator = 0
    ok = wait_ring(false, 3000);
  }
  interrupts();
  if (!ok) return false;
  out = v;
  return true;
}

bool send_byte(uint8_t b) {
  if (g_turbo) return turbo_send_byte(b);
  delayMicroseconds(LINK_TURNAROUND_US);
  for (int i = 0; i < 8; i++) {
    pull(((b >> i) & 1) ? 2 : 1);                      // 0 -> tip, 1 -> ring
    if (!wait_for(3, 0, LINK_STEP_TIMEOUT_US)) { pull(0); stats.byte_timeouts++; return false; }   // both low = acknowledged
    pull(0);
    if (!wait_for(3, 3, LINK_STEP_TIMEOUT_US)) return false;
  }
  return true;
}

bool recv_byte(uint8_t &out, uint32_t first_timeout_us) {
  if (g_turbo) return turbo_recv_byte(out, first_timeout_us);
  uint8_t v = 0;
  uint32_t tmo = first_timeout_us;
  for (int i = 0; i < 8; i++) {
    uint32_t t0 = micros();
    uint8_t l;
    while ((l = lines()) == 3) {
      if ((uint32_t)(micros() - t0) > tmo) return false;
    }
    tmo = LINK_STEP_TIMEOUT_US;
    if (l == 2) {                                      // tip low -> bit 0
      pull(2);
      if (!wait_for(1, 1, LINK_STEP_TIMEOUT_US)) { pull(0); return false; }
    } else if (l == 1) {                               // ring low -> bit 1
      v |= (uint8_t)(1u << i);
      pull(1);
      if (!wait_for(2, 2, LINK_STEP_TIMEOUT_US)) { pull(0); return false; }
    } else {
      return false;                                    // both low: collision
    }
    pull(0);
    if (!wait_for(3, 3, LINK_STEP_TIMEOUT_US)) return false;
  }
  out = v;
  return true;
}

bool recv_frame(uint8_t &cmd, uint8_t *payload, uint16_t &len, uint32_t first_timeout_us) {
  for (int attempt = 0; attempt < 3; attempt++) {
    uint8_t b;
    uint32_t tmo = first_timeout_us;
    do {                                               // resync on SYNC; wake pulse remnants are ignored here
      if (!recv_byte(b, tmo)) return false;
      tmo = LINK_STEP_TIMEOUT_US;
    } while (b != SL_SYNC);
    uint8_t hdr[3];
    for (int i = 0; i < 3; i++)
      if (!recv_byte(hdr[i], LINK_STEP_TIMEOUT_US)) return false;
    cmd = hdr[0];
    len = hdr[1] | (hdr[2] << 8);
    bool fits = len <= MAX_PAYLOAD;
    for (uint16_t i = 0; i < len; i++) {
      uint8_t x;
      if (!recv_byte(x, LINK_STEP_TIMEOUT_US)) return false;
      if (fits) payload[i] = x;
    }
    uint8_t c;
    if (!recv_byte(c, LINK_STEP_TIMEOUT_US)) return false;
    bool ok = fits && c == crc8(payload, len, crc8(hdr, 3));
    send_byte(ok ? SL_ACK : SL_NACK);
    if (ok) { stats.rx_frames++; return true; }
    stats.crc_errors++;
    stats.nacks_sent++;
    first_timeout_us = 400000;                         // wait for the retransmission
  }
  return false;
}

bool send_frame(uint8_t cmd, const uint8_t *payload, uint16_t len) {
  uint8_t hdr[3] = {cmd, (uint8_t)(len & 0xFF), (uint8_t)(len >> 8)};
  uint8_t crc = crc8(payload, len, crc8(hdr, 3));
  for (int attempt = 0; attempt < 3; attempt++) {
    bool ok = send_byte(SL_SYNC);
    for (int i = 0; ok && i < 3; i++) ok = send_byte(hdr[i]);
    for (uint16_t i = 0; ok && i < len; i++) ok = send_byte(payload[i]);
    ok = ok && send_byte(crc);
    uint8_t ack;
    if (ok && recv_byte(ack, 400000) && ack == SL_ACK) { stats.tx_frames++; return true; }
    stats.tx_retries++;
  }
  return false;
}

bool send_ready() { return send_byte(0xA5) && send_byte(0x5A); }

bool send_raw(const uint8_t *data, size_t n) {
  bool ok = true;
  for (size_t off = 0; ok && (off < n || off == 0); off += CHUNK_MAX) {
    size_t part = n - off < CHUNK_MAX ? n - off : CHUNK_MAX;
    bool last = off + part >= n;
    delayMicroseconds(g_turbo ? 150 : 2000);           // the calculator re-arms its receiver between frames
    ok = send_frame(last ? RSP_LAST : RSP_MORE, data + off, (uint16_t)part);
    if (n == 0) break;
  }
  return ok;
}

bool send_stream(const uint8_t *data, size_t n) {
  size_t clen = 0;
  uint8_t *comp = zx0_pack(data, n, &clen);
  if (!comp) return false;
  bool ok = true;
  for (size_t off = 0; ok && (off < clen || off == 0); off += CHUNK_MAX) {
    size_t part = clen - off < CHUNK_MAX ? clen - off : CHUNK_MAX;
    bool last = off + part >= clen;
    delay(2);                                          // the calculator re-arms its receiver between frames
    ok = send_frame(last ? RSP_LAST : RSP_MORE, comp + off, (uint16_t)part);
    if (clen == 0) break;
  }
  free(comp);
  return ok;
}
}  // namespace superlink
