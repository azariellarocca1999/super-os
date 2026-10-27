#!/usr/bin/env python3
"""Checks added by the third review (docs/REVIEW.md, "Pass 3").  Each one reproduced a defect before its fix.
Called from selftest.py; `python tools/selftest_review2.py` runs only this part."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
import selftest_lock as L  # noqa: E402
from uidrive import Session, parse_mem, pbm_text  # noqa: E402

check = S.check


def note_session(tag, sleep):
    """Lock on (PIN 1234), notepad, note 1, type a word; optionally sleep + wake + PIN while the editor is open; ENTER saves."""
    s = Session(tag, start=1500)
    L.configure(s, "K1")
    s.press("WINDOW", "K8", "K1")                     # notepad, edit note 1
    s.t += 400
    s.press("K4", "K3", "K5", "K5", "K6")             # T9: h e l l o
    s.t += 300
    if sleep:
        L.sleep_now(s)
        L.wake(s, 1200)
        s.press("K1", "K2", "K3", "K4")
        s.t += 900
    s.press("ENTER")                                  # accept the word
    s.t += 300
    s.press("ENTER")                                  # save the note
    s.snap("list", wait=800)
    out = s.run(extra_ms=100, env={"HZ_DUMP": "86E4", "HZ_DUMPLEN": "1"})
    return pbm_text(tag, "list"), out


def run(check_fn=None):
    global check
    if check_fn:
        check = check_fn
    print("== 30. Review pass 3: the PIN screen must not disturb the app it interrupts")
    ref, _ = note_session("rv3_note_ref", False)
    got, out = note_session("rv3_note_lock", True)
    check("LOCK: a note being edited when the calculator sleeps is saved into its own slot after the PIN (app scratch preserved)",
          got[14:50] == ref[14:50] and sum(map(sum, ref[14:22])) > 20 and L.no_reset(out),
          "(lit note lines: reference %d, after the lock %d)" % (sum(map(sum, ref[14:50])), sum(map(sum, got[14:50]))))

    # T9SEQ (up to 12 key digits) was declared at VARS+$60 on top of v_blast, v_bjmp, v_wcols, v_model, v_edmode and v_edcase:
    # a long T9 word rewrote the AI model and switched the editor mode in the middle of the word.
    s = Session("rv3_t9", start=1500)
    s.press("ZOOM", "K1")                             # AI chat editor (T9)
    s.t += 300
    for _ in range(12):
        s.press("K2")
    s.t += 300
    out = s.run(extra_ms=100, env={"HZ_DUMP": "8669", "HZ_DUMPLEN": "3"})
    m = parse_mem(out)
    check("T9: a 12-key word leaves the AI model, the editor mode and the case untouched (T9SEQ has its own 12 bytes)",
          list(m) == [0, 0, 0], "(v_model, v_edmode, v_edcase = %s)" % list(m))

    # The calculator keeps its variables, history and Y= functions in RAM between launches (m_magic).  Other apps reuse that RAM:
    # the information apps of page 4 ($9E00-$9F5F) and the CHIP-8 interpreter / pack menus ($A000-$A2FF).
    from uidrive import cstr, C_HIST, GR_BASE
    for name, keys in (("periodic table", ("WINDOW", "K5")), ("a CHIP-8 game", ("TRACE", "K9", "K2", "ENTER"))):
        tag = "rv3_keep_" + name.split()[-1]
        s = Session(tag, start=1500)
        s.press("WINDOW", "K1")
        s.t += 700
        s.type("5"); s.press("STO", "ALPHA", "MATH"); s.press("ENTER")          # 5 -> A
        s.type("7"); s.press("ENTER")
        s.second("MODE")                                                        # leave the calculator
        s.t += 600
        s.press(*keys)
        s.t += 2500
        for _ in range(4):
            s.press("CLEAR")
            s.t += 400
        s.second("MODE")
        s.t += 300
        s.press("WINDOW", "K1")
        s.t += 700
        s.press("ALPHA", "MATH"); s.type("*2"); s.press("ENTER")               # A*2
        out = s.run(extra_ms=400, env={"HZ_DUMP": "%X" % C_HIST, "HZ_DUMPLEN": "150"})
        h = parse_mem(out)
        hist = [(cstr(h, 50 * i), cstr(h, 50 * i + 25)) for i in range(3)]
        check("CALCULATOR: variables and history survive opening %s (A*2 = 10, earlier lines kept)" % name,
              hist[2][1] == "10" and hist[1][1] == "7" and hist[0][1] == "5", "(%s)" % hist)

    # The Y= functions of the grapher live at GR_BASE ($A104..): the CHIP-8 display buffer ($A100, 256 B) covered them.
    s = Session("rv3_keep_y1", start=1500)
    s.press("WINDOW", "K2", "YEQ")
    s.t += 600
    s.press("X")
    s.press("ENTER")
    s.t += 300
    s.second("MODE"); s.t += 300
    s.second("MODE"); s.t += 600
    s.press("TRACE", "K9", "K2", "ENTER")                                       # a CHIP-8 game
    s.t += 2500
    for _ in range(4):
        s.press("CLEAR")
        s.t += 400
    out = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % GR_BASE, "HZ_DUMPLEN": "4"})
    m = parse_mem(out)
    check("GRAPHER: the Y1 function survives a CHIP-8 game (Y1 = X as before: 80 58 29 00)", m == bytes([0x80, 0x58, 0x29, 0x00]),
          "(Y1 bytes %s)" % m.hex())

    # OTA packages may be 5200 bytes, but they are loaded at userMem ($9D95) and the task stacks start at $B000: only 4715 bytes fit.
    import shutil
    store = os.path.join(S.out, "store_rv3")
    shutil.rmtree(store, ignore_errors=True)
    os.makedirs(store)
    demo = open(os.path.join(S.root, "build", "demo.bin"), "rb").read()
    open(os.path.join(store, "BIGPKG.bin"), "wb").write(demo + bytes(4800 - len(demo)))
    esp = {"HZ_BRIDGE": "python " + os.path.join(S.root, "bridge_pc", "virtual_esp.py"), "HZ_LINKMODE": "line", "HZ_OFFLINE": "1",
           "HZ_BRIDGE_LOG": os.path.join(S.out, "esp_rv3.log"), "HZ_STORE_DIR": store}
    if os.path.exists(esp["HZ_BRIDGE_LOG"]):
        os.remove(esp["HZ_BRIDGE_LOG"])
    tap, kc = S.tap, S.kc
    ev = tap(1000, S.GRAPH) + tap(1400, kc(19)) + tap(2200, kc(34)) + tap(6200, kc(34)) + tap(7200, S.ENTER)
    ev += tap(9800, S.GRAPH) + tap(10200, kc(19)) + tap(10800, kc(26)) + tap(11600, kc(34)) + tap(12400, S.ENTER) + ["14500:snap:run"]
    ev += tap(15000, S.CLEAR) + tap(15600, S.CLEAR) + tap(16200, S.CLEAR) + ["17500:snap:back"]
    d = S.run("rv3_bigpkg", 18000, ev, dict(esp, HZ_ROM="20:0", HZ_ROMLEN="16"))
    snaps = d["snaps"]
    lg = open(esp["HZ_BRIDGE_LOG"]).read()
    rd = [l for l in d["raw"].splitlines() if l.startswith("ROMDUMP")]
    entry = bytes(int(x, 16) for x in rd[0].split(":")[2].split()) if rd else b""
    check("OTA: a 4800-byte package (more than fits between userMem and $B000) is refused, never installed or loaded over the task stack",
          "request cmd=$04 len=7" in lg and entry == bytes([255]) * 16 and d.get("stuck0", 1) == 0 and snaps["back"]["halt"] > 50,
          "(directory entry %s, halted %.0f %%)" % (entry[:6], snaps["back"]["halt"]))

    # A user program at userMem ($9D95) of more than ~107 bytes covers the calculator's variables ($9EA0..) but not always its
    # validity mark ($9F68): the calculator then showed garbage.  After a user program the mark is dropped, so it starts clean.
    for f in os.listdir(store):
        os.remove(os.path.join(store, f))
    open(os.path.join(store, "MIDPKG.bin"), "wb").write(demo + bytes([0x55]) * (300 - len(demo)))
    if os.path.exists(esp["HZ_BRIDGE_LOG"]):
        os.remove(esp["HZ_BRIDGE_LOG"])
    s = Session("rv3_userprog", start=1500)
    s.press("WINDOW", "K1")
    s.t += 700
    s.type("5"); s.press("STO", "ALPHA", "MATH"); s.press("ENTER")              # 5 -> A
    s.second("MODE"); s.t += 600
    s.press("GRAPH", "K6", "K1"); s.t += 4000                                   # OTA > PC packages: list
    s.press("K1"); s.t += 1000; s.press("ENTER"); s.t += 2600                    # download + install MIDPKG
    s.press("GRAPH", "K6", "K2"); s.t += 800; s.press("K1"); s.t += 800; s.press("ENTER"); s.t += 2000   # INSTALLED > run it
    for _ in range(4):
        s.press("CLEAR"); s.t += 400
    s.second("MODE"); s.t += 300
    s.press("WINDOW", "K1"); s.t += 700
    s.press("ALPHA", "MATH"); s.type("*2"); s.press("ENTER")
    out = s.run(extra_ms=400, env=dict(esp, HZ_DUMP="%X" % C_HIST, HZ_DUMPLEN="150"))
    h = parse_mem(out)
    hist = [(cstr(h, 50 * i), cstr(h, 50 * i + 25)) for i in range(3)]
    lg = open(esp["HZ_BRIDGE_LOG"]).read() if os.path.exists(esp["HZ_BRIDGE_LOG"]) else ""
    last = [r for e, r in hist if e == "A*2"]
    check("USER PROGRAM: after a 300-byte program the calculator starts clean (A*2 = 0), never with garbage variables",
          "request cmd=$04 len=7" in lg and last == ["0"], "(downloaded %s, history %s)" % ("request cmd=$04 len=7" in lg, hist))

    # An empty package store on the ESP32 (its factory state): the list reply is empty, and the ZX0 packer read optimal[-1] for 0 bytes
    # (the firmware crashed; the Python model raised).  An empty reply now goes out as one NUL = an empty text.
    shutil.rmtree(store, ignore_errors=True)
    os.makedirs(store)
    s = Session("rv3_emptystore", start=1500)
    s.press("GRAPH", "K6", "K1")
    s.snap("list", wait=5000)
    s.press("CLEAR", "CLEAR", "CLEAR")
    o = s.run(extra_ms=300, env=dict(esp, HZ_STORE_DIR=store))
    l = pbm_text("rv3_emptystore", "list")
    check("OTA: an empty package store on the ESP32 answers with an empty list (no crash, no endless wait)",
          any(l[y][x] for y in range(18, 30) for x in range(0, 3)) and "stuck_at_reset_vec=0" in o,
          "(the list line starts at column 0: %s)" % any(l[y][x] for y in range(18, 30) for x in range(0, 3)))

    # fix_8xu_tail.py (and verify_8xu.py) stripped trailing FF bytes to find the signature: a signature whose RSA value ends in FF
    # (1 build in 256) lost a byte and the build failed.  Same file, last signature byte forced to FF: it must survive a rewrite.
    import fix_8xu_tail as F
    CRLF = bytes([13, 10])
    b = open(os.path.join(S.root, "dist", "SuperOS.8xu"), "rb").read()
    lines = b[78:].split(CRLF)
    t = [i for i, ln in enumerate(lines) if ln.startswith(b":00000001FF")][-1]
    rec = bytearray(bytes.fromhex(lines[t - 1][1:].decode()))
    rec[4 + rec[0] - 1] = 0xFF
    rec[-1] = (-sum(rec[:-1])) & 0xFF
    lines[t - 1] = b":" + rec.hex().upper().encode()
    path = os.path.join(S.out, "sigff.8xu")
    open(path, "wb").write(b[:78] + CRLF.join(lines))
    try:
        F.fix(path)
        ok = open(path, "rb").read().count(b":" + rec.hex().upper().encode()) == 1
    except SystemExit:
        ok = False
    check("SIGNING: a signature whose last byte is FF keeps all 67 bytes through fix_8xu_tail", ok)

if __name__ == "__main__":
    run()
    print("RESULT: %d/%d" % (sum(S.results), len(S.results)))
    sys.exit(0 if all(S.results) else 1)
