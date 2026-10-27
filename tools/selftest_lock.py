#!/usr/bin/env python3
"""Screen lock and exam mode on the headless emulator: the PIN is stored (twice, matching), exam mode closes games / network apps,
and after a sleep the PIN screen comes first (a wrong PIN is refused, the right one gets back to the launcher).
Called from selftest.py; `python tools/selftest_lock.py` runs only this part."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
from uidrive import Session, parse_mem, pbm_text  # noqa: E402

check = S.check
ON = 64


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

    s = Session("lk_blk", start=1500)
    configure(s, "K2")
    s.press("TRACE", "K1")                  # GAMES > TETRIS: closed in exam mode
    s.snap("blk", wait=300)
    out = s.run(extra_ms=200, env={"HZ_DUMP": "A405", "HZ_DUMPLEN": "1"})
    m = parse_mem(out)
    check("EXAM: a game does not start (the game library never initialised) and a message is shown", m[0] == 0 and 0 < lit("lk_blk", "blk", 20, 50) < 250,
          "(gl_per=%d lit=%d)" % (m[0], lit("lk_blk", "blk", 20, 50)))

    s = Session("lk_pin", start=1500)
    s.snap("home0", wait=100)
    configure(s, "K1")
    s.press("YEQ")
    s.snap("home1", wait=200)
    s.press("K7")                           # INIC > SLEEP
    s.t += 2500
    s.ev += ["%d:down:%s" % (s.t, S.ON), "%d:up:%s" % (s.t + 200, S.ON)]     # wake up (ON held 200 ms like selftest 6)
    s.t += 1500
    s.press("K1")                           # the key after waking: the PIN screen comes first
    s.snap("pin", wait=300)
    s.press("K0", "K0", "K0", "K0")         # wrong PIN
    s.snap("bad", wait=300)
    s.press("ENTER")
    s.press("K1", "K2", "K3", "K4")         # right PIN
    s.snap("home2", wait=400)
    s.press("K7")                           # and the launcher works again: item 7 = SLEEP goes to sleep, so use CLOCK (3) instead
    out = s.run(extra_ms=100, env={"HZ_DUMP": "86E4", "HZ_DUMPLEN": "1"})
    p_home1, p_pin, p_bad, p_home2 = (lit("lk_pin", n, 14, 58) for n in ("home1", "pin", "bad", "home2"))
    check("LOCK: after a sleep the first key shows the PIN screen instead of opening the app", p_pin < 120 and abs(p_pin - p_home1) > 40,
          "(lit home %d, pin screen %d)" % (p_home1, p_pin))
    check("LOCK: a wrong PIN is refused with a message", 0 < p_bad < 250, "(lit=%d)" % p_bad)
    check("LOCK: the right PIN returns to the launcher", abs(p_home2 - p_home1) < 40, "(lit %d vs %d)" % (p_home2, p_home1))
    check("LOCK: never resets the calculator", len(parse_mem(out)) == 1 and parse_mem(out)[0] == 0)

    print("== 26b. Contrast shortcut on the launcher (+ / -)")
    s = Session("lk_cs", start=1500)
    s.press("PLUS", "PLUS", "PLUS", "MINUS")                     # trim 8 -> 10
    s.press("WINDOW")                                            # the next other key writes it to the flash journal
    out = s.run(extra_ms=300, env={"HZ_DUMP": "8700", "HZ_DUMPLEN": "16"})
    m = parse_mem(out)
    check("CONTRAST: + / - on the launcher change the trim live (8 -> 10)",m[3] == 10 and m[0] == 0x53,
          "(trim=%d)" % m[3])

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
    check("NOTES: reopening loads the stored text into the editor (123 shown)", lit("nt", "edit", 14, 40) > 15,"(lit=%d)" % lit("nt", "edit", 14, 40))
    check("NOTES: CLEAR leaves the note unchanged", row("kept") == row("saved"), "(lit %d vs %d)" % (row("kept"), row("saved")))
    check("NOTES: DEL + number erases the note", row("gone") == row("empty"), "(lit %d vs %d)" % (row("gone"), row("empty")))
    check("NOTES: never resets the calculator", len(parse_mem(out)) == 1 and parse_mem(out)[0] == 0)


if __name__ == "__main__":
    run()
    print("RESULT: %d/%d" % (sum(S.results), len(S.results)))
    sys.exit(0 if all(S.results) else 1)
