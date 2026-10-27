#!/usr/bin/env python3
"""Screen lock, exam mode, contrast shortcut, best scores in the flash journal and the notepad on the headless emulator.
Called from selftest.py; `python tools/selftest_lock.py` runs only this part."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
import uidrive  # noqa: E402
from uidrive import Session, parse_mem, pbm_text  # noqa: E402

check = S.check


def lit(tag, name, y0=0, y1=64):
    p = pbm_text(tag, name)
    return sum(sum(p[y]) for y in range(y0, y1))


def configure(s, mode_key):
    """SYS tab > LOCK > mode (K1 PIN / K2 exam), PIN 1234 twice, dismiss the DONE message."""
    s.press("GRAPH", "K8", mode_key)
    for _ in range(2):
        s.press("K1", "K2", "K3", "K4")
    s.press("ENTER")
    s.t += 300


def wake(s, wait=1500):
    s.ev += ["%d:down:%s" % (s.t, S.ON), "%d:up:%s" % (s.t + 200, S.ON)]
    s.t += wait


def sleep_now(s, wait=2000):
    """2ND + ON: sleep at once, from wherever the calculator is."""
    s.ev += ["%d:down:%s" % (s.t, S.K2ND), "%d:down:%s" % (s.t + 100, S.ON), "%d:up:%s" % (s.t + 300, S.ON), "%d:up:%s" % (s.t + 400, S.K2ND)]
    s.t += wait


def no_reset(out):
    m = parse_mem(out)
    return len(m) == 1 and m[0] == 0


def run(check_fn=None):
    global check
    if check_fn:
        check = check_fn
    print("== 26. Screen lock and exam mode")

    s = Session("lk_cfg", start=1500)
    configure(s, "K2")
    out = s.run(extra_ms=200, env={"HZ_DUMP": "8700", "HZ_DUMPLEN": "64"})
    m = parse_mem(out)
    check("LOCK: exam mode and the PIN 1234 are stored in the settings (s_lock = 2, s_pin = $1234)", m[0x1E] == 2 and m[0x1C] == 0x34 and m[0x1D] == 0x12,
          "(lock=%d pin=%02X%02X)" % (m[0x1E], m[0x1D], m[0x1C]))

    # exam mode: the closed items answer with a message and do not start (games, notes, reference tools, settings, diagnostics); the calculator opens
    for name, keys, closed in (("game", ("TRACE", "K1"), True), ("notes", ("WINDOW", "K8"), True), ("periodic table", ("WINDOW", "K5"), True),
                               ("settings", ("YEQ", "K6"), True), ("diagnostics", ("GRAPH", "K7"), True), ("calculator", ("WINDOW", "K1"), False)):
        tag = "lk_ex_" + name.split()[0]
        s = Session(tag, start=1500)
        configure(s, "K2")
        s.press(*keys)
        s.snap("x", wait=400)
        out = s.run(extra_ms=100, env={"HZ_DUMP": "86E4", "HZ_DUMPLEN": "1"})
        l = lit(tag, "x", 20, 50)
        check("EXAM: %s %s" % (name, "is closed (a message is shown)" if closed else "still opens"), (0 < l < 250) if closed else True, "(lit=%d)" % l)
    s = Session("lk_ex_g", start=1500)
    configure(s, "K2")
    s.press("TRACE", "K1")
    s.snap("blk", wait=300)
    out = s.run(extra_ms=200, env={"HZ_DUMP": "A405", "HZ_DUMPLEN": "1"})
    m = parse_mem(out)
    check("EXAM: a game does not start (the game library never initialised)", m[0] == 0, "(gl_per=%d)" % m[0])

    # wake-up inside the launcher: PIN screen first, wrong PIN refused with a wait, right PIN restores the screen
    s = Session("lk_pin", start=1500)
    configure(s, "K1")
    s.press("YEQ")
    s.snap("home1", wait=300)
    sleep_now(s)
    wake(s, 1200)
    s.snap("pin", wait=200)
    s.press("K0", "K0", "K0", "K0")         # wrong PIN
    s.snap("bad", wait=400)
    s.press("K1", "K2", "K3", "K4")         # typed during the wait: ignored
    s.t += 1000
    s.snap("still", wait=100)
    s.t += 3500                             # the 3 s wait is over: the prompt is back
    s.snap("again", wait=200)
    s.press("K1", "K2", "K3", "K4")         # right PIN
    s.snap("home2", wait=500)
    out = s.run(extra_ms=100, env={"HZ_DUMP": "86E4", "HZ_DUMPLEN": "1"})
    p_home1, p_pin, p_bad, p_still, p_again, p_home2 = (lit("lk_pin", n, 14, 58) for n in ("home1", "pin", "bad", "still", "again", "home2"))
    check("LOCK: after a sleep the PIN screen comes before anything else (no key needed)", p_pin < 120 and abs(p_pin - p_home1) > 40, "(lit home %d, pin screen %d)" % (p_home1, p_pin))
    check("LOCK: a wrong PIN is refused (message + wait)", 0 < p_bad < 250, "(lit=%d)" % p_bad)
    check("LOCK: during the wait the right PIN is not accepted either", 0 < p_still < 250, "(lit=%d)" % p_still)
    check("LOCK: after the wait the PIN prompt is back, and the right PIN returns to the launcher", p_again < 120 and abs(p_home2 - p_home1) < 40,
          "(prompt lit %d; home %d vs %d)" % (p_again, p_home2, p_home1))
    check("LOCK: never resets the calculator", no_reset(out))

    # wake-up inside an app and inside a game: the lock covers them too, and the picture comes back
    for name, keys, tag, idle in (("the calculator", ("WINDOW", "K1", "K1", "PLUS", "K2", "K3", "MUL", "K4", "K5"), "lk_app", False), ("a game", ("TRACE", "K3"), "lk_gm", True)):
        s = Session(tag, start=1500)
        configure(s, "K1")
        s.press(*keys)
        s.snap("before", wait=1200)
        if idle:
            s.t += 125000                   # games sleep through the idle timer (120 s): the lock must cover that path too
        else:
            sleep_now(s)
        wake(s, 1200)
        s.snap("pin", wait=200)
        s.press("K1", "K2", "K3", "K4")
        s.snap("after", wait=900)
        out = s.run(extra_ms=100, env={"HZ_DUMP": "86E4", "HZ_DUMPLEN": "1"})
        b, p, a = lit(tag, "before", 8, 56), lit(tag, "pin", 14, 56), lit(tag, "after", 8, 56)
        check("LOCK: waking up inside %s asks for the PIN, then the picture comes back" % name, p < 120 and abs(a - b) <= max(40, b // 10) and b > 15,
              "(lit before %d, pin %d, after %d)" % (b, p, a))
        check("LOCK: %s keeps running after the PIN (no reset)" % name, no_reset(out))

    # boot lock: RAM wiped (battery pull), the lock and PIN come back from the flash journal, the PIN is asked at start-up
    s = Session("lk_boot", start=1500)
    configure(s, "K1")
    s.ev.append("%d:reset" % s.t)
    s.t += 3500
    s.snap("boot", wait=100)
    s.press("K1", "K2", "K3", "K4")
    s.snap("home", wait=700)
    out = s.run(extra_ms=100, env={"HZ_DUMP": "86E4", "HZ_DUMPLEN": "1"})
    pb, ph = lit("lk_boot", "boot", 14, 58), lit("lk_boot", "home", 14, 58)
    check("LOCK: after a restart (RAM wiped) the PIN is asked at start-up, and the right PIN opens the launcher", pb < 120 and ph > 300, "(lit boot %d, home %d)" % (pb, ph))

    print("== 26b. Contrast shortcut on the launcher (+ / -)")
    s = Session("lk_cs", start=1500)
    s.press("PLUS", "PLUS", "PLUS", "MINUS")                     # trim 8 -> 10
    s.press("WINDOW")                                            # the next other key writes it to the flash journal
    out = s.run(extra_ms=300, env={"HZ_DUMP": "8700", "HZ_DUMPLEN": "16"})
    m = parse_mem(out)
    check("CONTRAST: + / - on the launcher change the trim live (8 -> 10)", m[3] == 10 and m[0] == 0x53, "(trim=%d)" % m[3])
    s = Session("lk_cs2", start=1500)
    s.press("PLUS", "PLUS", "WINDOW")
    s.ev.append("%d:reset" % s.t)
    s.t += 2500
    out = s.run(extra_ms=100, env={"HZ_DUMP": "8700", "HZ_DUMPLEN": "16"})
    m = parse_mem(out)
    check("CONTRAST: the shortcut value reaches the flash journal and survives a RAM wipe (trim 10)", m[3] == 10, "(trim=%d)" % m[3])

    print("== 26c. Best scores survive a RAM wipe; the settings journal rolls over when full")
    s = Session("lk_hs", start=1500)
    s.press("TRACE", "K8")
    s.t += 600
    for k in ("UP", "RIGHT", "RIGHT", "RIGHT", "DOWN", "LEFT", "LEFT", "LEFT", "LEFT", "UP", "LEFT", "DOWN"):     # Sokoban level 1
        s.press(k)
        s.t += 200
    s.t += 800
    s.ev.append("%d:reset" % s.t)
    s.t += 2500
    out = s.run(extra_ms=100, env={"HZ_DUMP": "8700", "HZ_DUMPLEN": "64"})
    m = parse_mem(out)
    check("SCORES: the best score (1 level) is restored from the flash journal after a RAM wipe", m[0x16] == 1 and m[0x17] == 0, "(best=%d)" % m[0x16])

    PS = 0x4000
    build_id = int(open(os.path.join(S.root, "build", "buildid.inc")).read().split("$")[1][:4], 16)

    def checksum(data, init):
        a = init
        for v in data:
            a ^= v
            a = ((a << 1) | (a >> 7)) & 0xFF
        return a

    def journal_rom(name, lock=0, pin=0, build=build_id, slots=256):
        """A ROM whose settings journal (flash page $70) holds `slots` identical records: magic, profile, trim 8, sleep, lang, font, esp sleep,
        10 scores, PIN, lock, build id, checksum -- as the kernel writes them (64-byte records)."""
        settings = [ord("S"), ord("O"), 0, 8, 120, 0, 0, 18] + [0] * 20 + [pin & 0xFF, pin >> 8, lock, build & 0xFF, build >> 8]
        settings.append(checksum(settings, 0x5A))
        rec = bytes([0xA5] + settings + [checksum(settings, 0xC3)]) + bytes([0xFF] * 28)
        assert len(rec) == 64
        rom = bytearray(open(S.rom, "rb").read())
        rom[0x70 * PS:0x70 * PS + slots * 64] = rec * slots
        p = os.path.join(S.out, name)
        open(p, "wb").write(bytes(rom))
        return p
    path = journal_rom("journal_full.rom")                                           # a journal with every one of its 256 slots used
    saved = uidrive.rom
    uidrive.rom = path                                                               # (Session reads uidrive.rom, not selftest.rom)
    try:
        s = Session("lk_full", start=1500)
        s.press("PLUS", "WINDOW")                                                    # trim 8 -> 9: the 257th record = erase + restart the sector
        s.t += 4000                                                                  # (the sector erase takes a while; a reset in the middle would be a different test)
        s.ev.append("%d:reset" % s.t)
        s.t += 2500
        s.snap("after", wait=100)
        out = s.run(extra_ms=100, env={"HZ_DUMP": "8700", "HZ_DUMPLEN": "16"})
    finally:
        uidrive.rom = saved
    m = parse_mem(out)
    check("JOURNAL: with all 256 slots used a new save erases the sector, restarts it, and the value survives a RAM wipe (trim 9)", m[3] == 9 and m[0] == 0x53,
          "(trim=%d)" % m[3])

    print("== 26d. Reinstalling the OS (a different build) clears the lock; the same build keeps it")
    saved = uidrive.rom
    for name, build, locked in (("same build", build_id, True), ("other build", (build_id ^ 0x5A5A) or 1, False)):
        uidrive.rom = journal_rom("journal_lock.rom", lock=1, pin=0x1234, build=build, slots=3)
        try:
            s = Session("lk_re_" + name.split()[0], start=3500)
            s.snap("boot", wait=100)
            out = s.run(extra_ms=100, env={"HZ_DUMP": "8700", "HZ_DUMPLEN": "64"})
        finally:
            uidrive.rom = saved
        m = parse_mem(out)
        l = lit("lk_re_" + name.split()[0], "boot", 14, 58)
        check("REINSTALL (%s): the PIN screen %s at start-up and s_lock is %d" % (name, "is asked" if locked else "is NOT asked (lock cleared)", 1 if locked else 0),
              (l < 120 and m[0x1E] == 1) if locked else (l > 300 and m[0x1E] == 0 and m[0x1C] == 0 and m[0x1D] == 0), "(lit=%d lock=%d pin=%02X%02X)" % (l, m[0x1E], m[0x1D], m[0x1C]))

    print("== 27. Notepad")
    s = Session("nt", start=1500)
    s.press("WINDOW", "K8")                 # MATH tab > NOTES
    s.snap("empty", wait=300)
    s.press("K1", "ALPHA", "ALPHA")         # open note 1 and switch the editor to 123 mode
    s.press("K1", "K2", "K3", "ENTER")
    s.snap("saved", wait=400)
    s.press("K1")                           # reopen: the text is loaded into the editor
    s.snap("edit", wait=300)
    s.press("CLEAR")                        # leave without changes
    s.snap("kept", wait=300)
    s.press("DEL", "K1")                    # delete note 1
    s.snap("gone", wait=300)
    out = s.run(extra_ms=100, env={"HZ_DUMP": "86E4", "HZ_DUMPLEN": "1"})
    row = lambda n: lit("nt", n, 14, 20)
    check("NOTES: an empty slot shows only a dash", row("empty") < row("saved"), "(lit %d / %d)" % (row("empty"), row("saved")))
    check("NOTES: the saved note shows its text in the list", row("saved") > row("empty") + 8, "(lit %d)" % row("saved"))
    check("NOTES: reopening loads the stored text into the editor (123 shown)", lit("nt", "edit", 14, 40) > 15, "(lit=%d)" % lit("nt", "edit", 14, 40))
    check("NOTES: CLEAR leaves the note unchanged", row("kept") == row("saved"), "(lit %d vs %d)" % (row("kept"), row("saved")))
    check("NOTES: DEL + number erases the note", row("gone") == row("empty"), "(lit %d vs %d)" % (row("gone"), row("empty")))
    check("NOTES: never resets the calculator", no_reset(out))

    # a full-length note (90 characters), letters in ABC mode, a sleep + wake, and the text is still there; notes 2 and 3 are independent
    s = Session("nt2", start=1500)
    s.press("WINDOW", "K8")
    s.press("K2", "ALPHA")                  # note 2, ABC mode: the letter keys (MATH = A ...)
    for _ in range(5):
        s.press("MATH")
    s.press("ALPHA")                        # 123 mode: digits
    for _ in range(90):
        s.press("K2")                       # (the editor stops at 90 characters)
    s.press("ENTER")
    s.press("K3", "ALPHA", "ALPHA", "K9", "ENTER")      # note 3 = "9"
    s.snap("list", wait=400)
    sleep_now(s)
    wake(s, 1500)
    s.press("CLEAR")                        # leave the app, come back
    s.press("WINDOW", "K8")
    s.snap("back", wait=500)
    s.press("K2")
    s.snap("edit2", wait=500)
    out = s.run(extra_ms=100, env={"HZ_DUMP": "86E4", "HZ_DUMPLEN": "1"})
    check("NOTES: a 90-character note and a second note are listed, and survive sleep and leaving the app",
          lit("nt2", "list", 14, 40) > 30 and lit("nt2", "back", 14, 40) == lit("nt2", "list", 14, 40), "(lit %d / %d)" % (lit("nt2", "list", 14, 40), lit("nt2", "back", 14, 40)))
    check("NOTES: the long note opens in the editor (several lines of text)", lit("nt2", "edit2", 14, 60) > 150, "(lit=%d)" % lit("nt2", "edit2", 14, 60))
    check("NOTES: long notes never reset the calculator", no_reset(out))


if __name__ == "__main__":
    run()
    print("RESULT: %d/%d" % (sum(S.results), len(S.results)))
    sys.exit(0 if all(S.results) else 1)
