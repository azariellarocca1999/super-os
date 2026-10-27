#!/usr/bin/env python3
"""Checks added by the supervision review (docs/REVIEW.md, second pass).  Each one reproduced a defect before its fix.
Called from selftest.py; `python tools/selftest_review.py` runs only this part."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
import uidrive  # noqa: E402
from uidrive import Session, pbm_text, KEYS, kc, out, root  # noqa: E402

check = S.check
PS = 16384
ESP = {"HZ_BRIDGE": "python " + os.path.join(root, "bridge_pc", "virtual_esp.py"), "HZ_LINKMODE": "line", "HZ_OFFLINE": "1",
       "HZ_BRIDGE_LOG": os.path.join(out, "esp_review.log")}


def lit(tag, name, y0=0, y1=64):
    p = pbm_text(tag, name)
    return sum(sum(p[y]) for y in range(y0, y1))


def hold(s, name, ms):
    code = KEYS[name]
    s.ev += ["%d:down:%s" % (s.t, kc(code)), "%d:up:%s" % (s.t + ms, kc(code))]
    s.t += ms + 100


def with_rom(data, fn):
    path = os.path.join(out, "review_variant.rom")
    open(path, "wb").write(data)
    saved = uidrive.rom
    uidrive.rom = path
    try:
        return fn()
    finally:
        uidrive.rom = saved


def run(check_fn=None):
    global check
    if check_fn:
        check = check_fn
    print("== 25. Review pass 2: boot hand-off, CLEAR held while an app sends its exit request, leftover TI-OS archive data")
    base = open(uidrive.rom, "rb").read()

    # 25a. The factory boot code hands control to the OS at $0053 (community documentation: KnightOS header, WikiTI), not only at $0000.
    page0 = base[:PS]
    check("page 0 has a jump at $0053 (boot code hand-off) and $0056 is left $FF for the boot code's valid mark",
          page0[0x53] == 0xC3 and page0[0x56] == 0xFF, "(bytes $0053..$0057 = %s)" % page0[0x53:0x58].hex())
    rom = bytearray(base)
    stub = 0x7F * PS
    jp = rom.find(b"\xC3", stub, stub + 32)
    rom[jp + 1:jp + 3] = b"\x53\x00"                    # stand-in boot page jumps to $0053 instead of $0000
    s = Session("rv_boot53", start=1500)
    s.snap("home", wait=1500)
    o = with_rom(bytes(rom), lambda: s.run(extra_ms=300))
    check("boot through $0053 reaches the launcher (no RST $38 loop on $FF bytes)", "stuck_at_reset_vec=0" in o and lit("rv_boot53", "home", 56, 64) > 0,
          "(footer lit=%d)" % lit("rv_boot53", "home", 56, 64))

    # 25b. Leaving a streamed game: c8_scankeys sees CLEAR held and the app sends CMD_GAME stop + CMD_TURBO 0 while CLEAR is still down.
    # The CLEAR-cancel of link_request must not abort those exit requests; with a chip that needs 30 ms before replying it did.
    if os.path.exists(ESP["HZ_BRIDGE_LOG"]):
        os.remove(ESP["HZ_BRIDGE_LOG"])
    s = Session("rv_stopclear", start=1500)
    s.press("TRACE", "K9", "K3")                                   # GAMES tab, STREAM 3D
    s.snap("list", wait=3200)
    s.press("ENTER")
    s.snap("g1", wait=2500)
    hold(s, "CLEAR", 700)
    s.snap("back", wait=4000)
    s.run(extra_ms=300, env=dict(ESP, HZ_ESP_REPLY_DELAY_MS="30"))
    lg = open(ESP["HZ_BRIDGE_LOG"]).read() if os.path.exists(ESP["HZ_BRIDGE_LOG"]) else ""
    tail = lg[lg.rfind("cmd=$32 len=1"):] if "cmd=$32 len=1" in lg else ""
    check("CLEAR held while leaving a stream: stop + turbo-off complete (no abort, no 3 s turbo timeout on the ESP32)",
          "byte layer is now safe" in tail and "turbo timeout" not in lg and lit("rv_stopclear", "back", 14, 30) > 60,
          "(stop seen=%s, safe=%s, timeout=%s)" % (bool(tail), "byte layer is now safe" in tail, "turbo timeout" in lg))

    # 25c. A TI-OS upgrade keeps the archive: pages Super-OS uses ($20-$7B) can hold old TI data on a real unit.  Fill them with
    # pseudo-random bytes and check that the OS boots, the settings work and OTA > INSTALLED does not run or list garbage.
    rnd = random.Random(83)
    rom = bytearray(base)
    for pg in range(0x07, 0x7C):
        rom[pg * PS:(pg + 1) * PS] = bytes(rnd.getrandbits(8) for _ in range(PS))
    s = Session("rv_tiarch", start=1500)
    s.snap("home", wait=1500)
    s.press("ZOOM", "K5", "K2")                          # OTA > INSTALLED
    s.snap("inst", wait=900)
    s.press("CLEAR", "CLEAR", "CLEAR")
    s.snap("end", wait=600)
    o = with_rom(bytes(rom), lambda: s.run(extra_ms=300))
    check("leftover TI archive data in $07-$7B: boots to the launcher and comes back from OTA > INSTALLED (no reset)",
          "stuck_at_reset_vec=0" in o and lit("rv_tiarch", "end", 56, 64) == lit("rv_tiarch", "home", 56, 64) and lit("rv_tiarch", "home", 56, 64) > 0)

    # 25d. Same foreign data in the settings journal sector: a changed setting must still be journalled and restored after a RAM loss
    # (before the fix the first journal write hung forever in the DQ7 poll with the screen off).
    path = os.path.join(out, "review_variant.rom")
    open(path, "wb").write(bytes(rom))
    saved = S.rom
    S.rom = path
    try:
        ev = S.tap(1000, kc(19)) + S.tap(1500, kc(1)) + S.tap(1700, kc(1)) + S.tap(1900, kc(3))   # ONE change (trim 8 -> 9) = one journal write
        ev += ["3000:snap:before", "4000:reset", "7000:snap:after"]
        d = S.run("rv_journal", 7500, ev, env={"HZ_ROM": "70:0", "HZ_ROMLEN": "16"})
    finally:
        S.rom = saved
    c = {k: v.get("contrast") for k, v in d["snaps"].items()}
    check("foreign data in the journal sector: the sector is reclaimed and a single contrast change survives a RAM wipe", c.get("before") == 49 and c.get("after") == 49,
          "(%s)" % c)

    # 25f. Foreign data in the package directory (page $20) can point the next install anywhere.  The flash guard still allowed pages
    # $03-$1F, but the OS now occupies $00-$06: an OTA install over such a directory programmed the package into the OS itself.
    rom = bytearray(base)
    rom[0x20 * PS:0x20 * PS + 16] = b"JUNK    " + bytes([0x05, 0x00, 0x40, 0x00, 0x01, 0x01, 0xFF, 0xFF])   # page $05, off $4000, len $100
    store = os.path.join(out, "store_review")
    os.makedirs(store, exist_ok=True)
    for f in os.listdir(store):
        os.remove(os.path.join(store, f))
    open(os.path.join(store, "HELLO.bin"), "wb").write(open(os.path.join(root, "build", "demo.bin"), "rb").read())
    path = os.path.join(out, "review_variant.rom")
    open(path, "wb").write(bytes(rom))
    saved = S.rom
    S.rom = path
    try:
        ev = S.tap(1000, S.GRAPH) + S.tap(1400, kc(19)) + S.tap(2200, kc(34)) + S.tap(6200, kc(34)) + S.tap(7200, S.ENTER) + ["9000:snap:after"]
        d = S.run("rv_pkgguard", 9500, ev, dict(ESP, HZ_STORE_DIR=store, HZ_ROM="05:100", HZ_ROMLEN="128"))
    finally:
        S.rom = saved
    lines = [l for l in d["raw"].splitlines() if l.startswith("ROMDUMP")]
    after = bytes(int(x, 16) for x in lines[0].split(":")[2].split()) if lines else b""
    check("a corrupt package directory cannot make an install program the OS pages ($05 unchanged)",
          after == bytes(rom[0x05 * PS + 0x100:0x05 * PS + 0x180]) and d.get("stuck0", 1) == 0, "(page $05 changed: %s)" % (after != bytes(rom[0x05 * PS + 0x100:0x05 * PS + 0x180])))

    # 25g. Blank directory, foreign data in the package DATA pages: programming the package can never verify.  Before the review the DQ7
    # poll spun forever with interrupts off; now the install must fail, write no directory entry and leave the UI alive.
    rom = bytearray(base)
    rnd = random.Random(84)
    for pg in range(0x24, 0x28):
        rom[pg * PS:(pg + 1) * PS] = bytes(rnd.getrandbits(8) | 0x01 for _ in range(PS))   # bit 0 set: a package byte with bit 0 = 0 fails
    open(path, "wb").write(bytes(rom))
    S.rom = path
    try:
        ev = S.tap(1000, S.GRAPH) + S.tap(1400, kc(19)) + S.tap(2200, kc(34)) + S.tap(6200, kc(34)) + S.tap(7200, S.ENTER) + ["10000:snap:after"]
        ev += S.tap(10300, S.CLEAR) + S.tap(10800, S.CLEAR) + ["12000:snap:back"]
        d = S.run("rv_pkgdata", 12500, ev, dict(ESP, HZ_STORE_DIR=store, HZ_ROM="20:0", HZ_ROMLEN="16"))
    finally:
        S.rom = saved
    lines = [l for l in d["raw"].splitlines() if l.startswith("ROMDUMP")]
    entry = bytes(int(x, 16) for x in lines[0].split(":")[2].split()) if lines else b""
    snaps = d["snaps"]
    check("foreign data in the package data pages: the install fails cleanly (no directory entry, no hang, UI answers)",
          entry == b"\xff" * 16 and snaps["back"]["halt"] > 80 and d.get("stuck0", 1) == 0,
          "(entry %s, idle %.0f %% halted at the end)" % (entry[:5], snaps["back"]["halt"]))

    # 25e. The ESP32 deep-sleeps on its OWN idle timer (was a fixed 180 s in the firmware, now a 900 s safety net) while the calculator's timer is a setting (30-600 s).
    # If the chip sleeps first the calculator still believes it is awake: no wake pulse, and the SYNC byte's first bit pulls RING (not TIP),
    # so the chip is never woken and every request fails until the calculator's own timer runs out.  Chip timer shortened to 12 s here.
    if os.path.exists(ESP["HZ_BRIDGE_LOG"]):
        os.remove(ESP["HZ_BRIDGE_LOG"])
    s = Session("rv_selfsleep", start=1500)
    s.press("ZOOM", "K1", "K2", "ENTER")                 # first chat: wakes the chip
    s.snap("r1", wait=4000)
    s.press("CLEAR", "CLEAR")
    s.t += 16000                                         # the chip falls asleep on its own (12 s idle)
    s.press("ZOOM", "K1", "K2", "ENTER")                 # same chat again, from the launcher
    s.snap("r2", wait=8000)
    s.run(extra_ms=300, env=dict(ESP, HZ_ESP_IDLE_S="12"))
    lg = open(ESP["HZ_BRIDGE_LOG"]).read() if os.path.exists(ESP["HZ_BRIDGE_LOG"]) else ""
    check("the ESP32 slept on its own idle timer: the next request wakes it again and gets its answer",
          "idle 12 s -> deep sleep" in lg and lg.count("request cmd=$02") == 2 and pbm_text("rv_selfsleep", "r2") == pbm_text("rv_selfsleep", "r1"),
          "(chat requests seen by the chip: %d, boots: %d)" % (lg.count("request cmd=$02"), lg.count("ESP_READY sent")))


if __name__ == "__main__":
    run()
    print("RESULT: %d/%d" % (sum(S.results), len(S.results)))
    sys.exit(0 if all(S.results) else 1)
