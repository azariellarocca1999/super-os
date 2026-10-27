#!/usr/bin/env python3
"""Virtual ESP32-S3: line-level model of the SuperLink 'safe' physical layer for the PC simulator.

hz80_sim.exe (HZ_BRIDGE=... HZ_LINKMODE=line) runs this process in lockstep with the emulated calculator:
  harness -> "T <microseconds> <calc_pulls>"      (bit0 = tip pulled low by the calculator, bit1 = ring)
  bridge  -> "P <peer_pulls>"                     (what this ESP32 pulls low)
The model reproduces the real firmware's behaviour: deep sleep, wake on a 50 ms TIP pulse, boot delay,
ESP_READY ($A5 $5A), SuperLink frames with ACK/NACK, services, CMD_SLEEP and the idle deep-sleep timer.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import services as sv  # noqa: E402

BOOT_US = 300_000          # ESP32-S3 deep-sleep boot
WAKE_PULSE_US = 20_000     # a TIP pull longer than this wakes the chip (real hardware: ext0 wakes on any low level)
FAULT_RX = int(os.environ.get("HZ_ESP_FAULT_RX", "0"))   # every N-th received frame is NACKed
FAULT_TX = int(os.environ.get("HZ_ESP_FAULT_TX", "0"))   # every N-th reply frame goes out with a bad CRC the first time
IDLE_SLEEP_US = int(float(os.environ.get("HZ_ESP_IDLE_S", "900")) * 1_000_000)
REPLY_DELAY_US = int(float(os.environ.get("HZ_ESP_REPLY_DELAY_MS", "0")) * 1000)   # extra think time before the first reply frame (a busy chip)


class VirtualEsp:
    def __init__(self):
        self.t = 0
        self.calc = 0
        self.peer = 0
        self.state = sv.State()
        self.asleep = True
        self.turbo = False
        self.last_activity = 0
        self.boot_t = 0
        self.gen = self.run()
        next(self.gen)

    # ---- driver ------------------------------------------------------------------------------
    def feed(self, t, calc):
        self.t, self.calc = t, calc
        try:
            next(self.gen)
        except StopIteration:
            pass
        return self.peer

    def wait(self, cond):
        while not cond():
            yield

    # ---- byte layer (mirror image of the Z80 code) --------------------------------------------
    def recv_byte(self):
        if self.turbo:
            value = 0
            for i in range(8):                                  # calculator-clocked: sample TIP while RING is pulled low
                yield from self.wait(lambda: self.calc & 2)
                if not self.calc & 1:
                    value |= 1 << i
                yield from self.wait(lambda: not self.calc & 2)
            self.rx = value
            self.last_activity = self.t
            return
        value = 0
        for i in range(8):
            yield from self.wait(lambda: self.calc != 0)
            if self.calc & 1 and not self.calc & 2:     # tip low -> bit 0
                self.peer = 2                           # ack: pull ring
                yield from self.wait(lambda: not self.calc & 1)
            elif self.calc & 2 and not self.calc & 1:   # ring low -> bit 1
                value |= 1 << i
                self.peer = 1                           # ack: pull tip
                yield from self.wait(lambda: not self.calc & 2)
            else:
                yield
                continue
            self.peer = 0
            yield from self.wait(lambda: self.calc == 0)
        self.rx = value
        self.last_activity = self.t
        if os.environ.get("HZ_ESP_DEBUG"):
            sv.log("rx %02X @%d" % (value, self.t))

    def turnaround(self, us=250):
        t0 = self.t
        yield from self.wait(lambda: self.t - t0 >= us)

    def send_byte(self, byte):
        if self.turbo:
            self.peer = 1                                       # start bit: TIP low = byte ready
            for i in range(8):
                yield from self.wait(lambda: self.calc & 2)     # the calculator pulls the clock low: present the next bit
                self.peer = 0 if (byte >> i) & 1 else 1
                yield from self.wait(lambda: not self.calc & 2)
            yield from self.wait(lambda: self.calc & 2)         # stop bit (released)
            self.peer = 0
            yield from self.wait(lambda: not self.calc & 2)
            self.last_activity = self.t
            return
        yield from self.turnaround()       # stay released long enough for the calculator to see idle-high
        if os.environ.get("HZ_ESP_DEBUG"):
            sv.log("tx %02X @%d calc=%d" % (byte, self.t, self.calc))
        for i in range(8):
            bit = (byte >> i) & 1
            self.peer = 2 if bit else 1                 # 0 -> tip, 1 -> ring
            other = 1 if bit else 2
            yield from self.wait(lambda: self.calc & other)   # calc pulls the other line = ack
            self.peer = 0
            yield from self.wait(lambda: self.calc == 0)
        self.last_activity = self.t

    # ---- frame layer --------------------------------------------------------------------------
    def recv_frame(self):
        crc = 0
        while True:                                     # resync on SYNC
            yield from self.recv_byte()
            if self.rx == sv.SL_SYNC:
                break
        hdr = []
        for _ in range(3):
            yield from self.recv_byte()
            hdr.append(self.rx)
        cmd, ln = hdr[0], hdr[1] | hdr[2] << 8
        payload = bytearray()
        for _ in range(ln):
            yield from self.recv_byte()
            payload.append(self.rx)
        yield from self.recv_byte()
        ok = self.rx == sv.crc8(bytes(hdr) + bytes(payload))
        self.rx_attempts = getattr(self, "rx_attempts", 0) + 1
        injected = getattr(self, "fault_injected", False)
        self.fault_injected = False
        if FAULT_RX and ok and not injected and self.rx_attempts % FAULT_RX == 0:
            ok = False                                  # fault injection: pretend this frame arrived corrupted (the calculator must retry once)
            self.fault_injected = True
            sv.log("FAULT injected: rx frame #%d rejected (NACK)" % self.rx_attempts)
        if os.environ.get("HZ_ESP_DEBUG"):
            sv.log("crc rx=%02X calc=%02X ok=%s" % (self.rx, sv.crc8(bytes(hdr) + bytes(payload)), ok))
        yield from self.send_byte(sv.ACK if ok else sv.NACK)
        self.state.rx_frames += 1 if ok else 0
        self.state.crc_errors += 0 if ok else 1
        self.frame = (cmd, bytes(payload)) if ok else None

    def send_frame(self, cmd, payload):
        self.state.tx_frames += 1
        raw = sv.frame(cmd, payload)
        self.tx_frames_n = getattr(self, "tx_frames_n", 0) + 1
        for attempt in range(3):
            out = raw
            if FAULT_TX and attempt == 0 and self.tx_frames_n % FAULT_TX == 0:
                out = raw[:-1] + bytes([raw[-1] ^ 0x55])  # fault injection: corrupt the CRC of the first transmission only
                sv.log("FAULT injected: tx frame #%d sent with a bad CRC" % self.tx_frames_n)
            for b in out:
                yield from self.send_byte(b)
            yield from self.recv_byte()                 # ACK / NACK
            if self.rx == sv.ACK:
                return

    # ---- main behaviour -----------------------------------------------------------------------
    def run(self):
        while True:
            if self.asleep:
                yield from self.sleep_until_wake()
            # awake: wait for traffic or the idle timeout
            idle_t0 = self.t
            while True:
                yield
                self.state.uptime_us = self.t - self.boot_t
                if self.calc != 0:
                    break
                if self.turbo and self.t - self.last_activity > 3_000_000:
                    self.turbo = False                           # the calculator vanished: back to the safe layer
                    sv.log("turbo timeout -> safe")
                if self.t - self.last_activity > IDLE_SLEEP_US:
                    sv.log("idle %d s -> deep sleep" % (IDLE_SLEEP_US // 1_000_000))
                    self.asleep = True
                    break
            if self.asleep:
                continue
            yield from self.recv_frame()
            if self.frame is None:
                continue
            cmd, payload = self.frame
            sv.log("request cmd=$%02X len=%d %r @%dms" % (cmd, len(payload), payload[:40], self.t // 1000))
            if cmd == sv.CMD_SLEEP:
                sv.log("CMD_SLEEP -> deep sleep")
                self.asleep = True
                continue
            self.state.now_us = self.t
            if REPLY_DELAY_US:
                t0 = self.t
                yield from self.wait(lambda: self.t - t0 >= REPLY_DELAY_US)
            for rcmd, rpl in sv.handle(self.state, cmd, payload):
                yield from self.wait_idle_gap()
                yield from self.send_frame(rcmd, rpl)
            self.last_activity = self.t
            if self.state.turbo_req is not None:                # CMD_TURBO: the calculator has acked the last frame
                self.turbo = self.state.turbo_req
                self.state.turbo_req = None
                sv.log("byte layer is now %s" % ("TURBO" if self.turbo else "safe"))

    def wait_idle_gap(self):
        t0 = self.t
        yield from self.wait(lambda: self.t - t0 >= (150 if self.turbo else 1500))   # the calculator re-arms its receiver

    def sleep_until_wake(self):
        """Deep sleep: ignore everything except a TIP pull longer than WAKE_PULSE_US, then boot and say READY."""
        sv.log("deep sleep")
        self.peer = 0
        while True:
            yield from self.wait(lambda: self.calc == 1)
            t0 = self.t
            yield from self.wait(lambda: self.calc != 1)
            if self.t - t0 >= WAKE_PULSE_US:
                break
            sv.log("ignored a short TIP pulse (%d us)" % (self.t - t0))
        sv.log("woken by TIP pulse (%d ms) -> booting" % ((self.t - t0) // 1000))
        t1 = self.t
        yield from self.wait(lambda: self.t - t1 >= BOOT_US)
        self.asleep = False
        self.boot_t = self.t
        self.state.boots += 1
        self.last_activity = self.t
        for b in (0xA5, 0x5A):                           # ESP_READY
            yield from self.send_byte(b)
        sv.log("ESP_READY sent")


def main():
    esp = VirtualEsp()
    for line in sys.stdin:
        parts = line.split()
        if len(parts) == 3 and parts[0] == "T":
            peer = esp.feed(int(parts[1]), int(parts[2]))
            if os.environ.get("HZ_ESP_TRACE") and int(parts[1]) > 3059000 and int(parts[1]) < 3075000:
                sv.log("T %s calc=%s -> peer=%d" % (parts[1], parts[2], peer))
            sys.stdout.write("P %d\n" % peer)
            sys.stdout.flush()


if __name__ == "__main__":
    main()
