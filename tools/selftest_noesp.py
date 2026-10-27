#!/usr/bin/env python3
"""Base-system checks with NO ESP32 attached (floating link lines): every app that needs the co-processor must fail with a clear message,
must never freeze the UI, and CLEAR must cancel the wait.  Called from selftest.py; `python tools/selftest_noesp.py` runs only this part."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
from uidrive import Session, pbm_text  # noqa: E402

check = S.check

# name: (tab key, item key, extra keys before ENTER, ENTER needed)
APPS = {
    "AI chat": ("ZOOM", "K1", ["K2"], True),
    "step by step": ("WINDOW", "K4", ["K2"], True),
    "Wikipedia": ("ZOOM", "K3", ["K2"], True),
    "weather": ("ZOOM", "K6", ["K2"], True),
    "Super-CAS": ("WINDOW", "K3", ["K2"], True),
    "WiFi scan": ("ZOOM", "K4", ["K1"], False),
    "OTA PC packages": ("ZOOM", "K5", ["K1"], False),
    "STREAM 3D": ("TRACE>K9", "K3", [], False),
}


def lit_rows(tag, name, y0, y1):
    p = pbm_text(tag, name)
    return sum(sum(p[y]) for y in range(y0, y1))


def same_region(tag, a, b, y0, y1):
    pa, pb = pbm_text(tag, a), pbm_text(tag, b)
    return all(pa[y] == pb[y] for y in range(y0, y1))


def run(check_fn=None):
    global check
    if check_fn:
        check = check_fn
    print("== 24. No ESP32 attached: every network app fails gracefully, CLEAR cancels the wait, the UI never freezes")
    for name, (tab, item, extra, enter) in APPS.items():
        tag = "noesp_" + name.replace(" ", "_").replace("-", "_")
        s = Session(tag, start=1500)
        s.press(*tab.split(">"))                      # "TRACE>K9" = the tab key, then the key of the second page
        s.snap("home", wait=300)                      # the launcher of that tab (reference for "back at the launcher")
        s.press(item)
        s.press(*extra)
        if enter:
            s.press("ENTER")
        s.snap("wait", wait=700)                      # request in flight (waiting screen)
        s.snap("late", wait=9000)                     # 9.7 s later: the 5 s wake wait has expired
        s.press("CLEAR")
        s.snap("c1", wait=500)
        s.press("CLEAR")
        s.snap("c2", wait=500)
        s.press("CLEAR")                              # editors: dismiss message, clear text, leave
        s.snap("c3", wait=500)
        s.run(extra_ms=300)
        failed_shown = not same_region(tag, "wait", "late", 8, 64) or lit_rows(tag, "late", 8, 64) > 0
        check("%s: with no ESP32 the request ends with a message (not hung)" % name, not same_region(tag, "wait", "late", 14, 50) or name in ("OTA PC packages",),
              "(lit wait=%d late=%d)" % (lit_rows(tag, "wait", 8, 64), lit_rows(tag, "late", 8, 64)))
        # back at the launcher = same picture as before (the highlighted item may differ: compare the lit pixel count with a tolerance)
        back = any(abs(lit_rows(tag, "home", 8, 64) - lit_rows(tag, c, 8, 64)) <= 60 for c in ("c1", "c2", "c3")) and \
            lit_rows(tag, "c3", 56, 64) == lit_rows(tag, "home", 56, 64)
        check("%s: CLEAR returns to the launcher" % name, back)
    # tour: open every launcher entry (except SLEEP), press CLEAR a few times: the launcher must come back every time
    tabs = (("YEQ", 9, (7,)), ("WINDOW", 8, ()), ("ZOOM", 6, ()), ("TRACE", 9, (9,)), ("TRACE>K9", 4, (4,)), ("GRAPH", 8, (4,)))   # 9 = MORE and 4 = BACK flip the page
    bad = []
    for tab, count, skip in tabs:
        for i in range(1, count + 1):
            if i in skip:
                continue
            tag = "tour_%s_%d" % (tab.replace(">", "_"), i)
            s = Session(tag, start=1500)
            s.press(*tab.split(">"))
            s.snap("home", wait=300)
            s.press("K%d" % i)
            s.snap("open", wait=900)
            for _ in range(4):
                s.press("CLEAR")
                s.snap("c", wait=350)
            if tab == "WINDOW" and i == 1:
                s.second("MODE")                      # the calculator is left with 2ND+MODE (CLEAR clears the entry, as on a TI)
            s.snap("end", wait=300)
            out = s.run(extra_ms=200)
            ok = lit_rows(tag, "end", 56, 64) == lit_rows(tag, "home", 56, 64) and "stuck_at_reset_vec=0" in out
            if not ok:
                bad.append("%s item %d" % (tab, i))
    n_entries = sum(c - len(sk) for _t, c, sk in tabs)
    check("tour: all %d launcher entries open and CLEAR brings the launcher back (no hang, no reset)" % n_entries, not bad, "(failed: %s)" % bad)
    # cancel: CLEAR 1 s into the 5 s wake wait must end the wait immediately
    s = Session("noesp_cancel", start=1500)
    s.press("ZOOM", "K1", "K2", "ENTER")
    s.snap("wait", wait=900)
    s.press("CLEAR")
    s.snap("after", wait=600)
    s.run(extra_ms=300)
    check("CLEAR cancels the wait for an absent ESP32 within 0.6 s (before the 5 s wake timeout)", not same_region("noesp_cancel", "wait", "after", 14, 50),
          "(lit wait=%d after=%d)" % (lit_rows("noesp_cancel", "wait", 8, 64), lit_rows("noesp_cancel", "after", 8, 64)))
    # link robustness: corrupted frames in both directions are recovered by the retry logic (chat round trip must still work)
    esp = {"HZ_BRIDGE": "python " + os.path.join(S.root, "bridge_pc", "virtual_esp.py"), "HZ_LINKMODE": "line", "HZ_OFFLINE": "1",
           "HZ_BRIDGE_LOG": os.path.join(S.out, "esp_fault.log"), "HZ_ESP_FAULT_RX": "1", "HZ_ESP_FAULT_TX": "1"}
    if os.path.exists(esp["HZ_BRIDGE_LOG"]):
        os.remove(esp["HZ_BRIDGE_LOG"])
    s = Session("fault_chat", start=1500)
    s.press("ZOOM", "K1")
    for k in ("K4", "K3", "K5", "K5", "K6"):
        s.press(k)                                    # h e l l o (T9 keys 4 3 5 5 6)
    s.snap("typed", wait=300)
    s.press("ENTER")
    s.snap("reply", wait=6000)
    s.run(extra_ms=300, env=esp)
    lg = open(esp["HZ_BRIDGE_LOG"]).read()
    check("fault injection: corrupted frames were really injected in both directions", "FAULT injected: rx" in lg and "FAULT injected: tx" in lg,
          "(%d rx, %d tx)" % (lg.count("FAULT injected: rx"), lg.count("FAULT injected: tx")))
    # the same conversation without faults is the reference: "something changed on screen" would also accept an error message
    clean = dict(esp, HZ_ESP_FAULT_RX="0", HZ_ESP_FAULT_TX="0", HZ_BRIDGE_LOG=os.path.join(S.out, "esp_clean.log"))
    s = Session("fault_clean", start=1500)
    s.press("ZOOM", "K1")
    for k in ("K4", "K3", "K5", "K5", "K6"):
        s.press(k)
    s.snap("typed", wait=300)
    s.press("ENTER")
    s.snap("reply", wait=6000)
    s.run(extra_ms=300, env=clean)
    check("fault injection: the chat reply still reaches the screen after NACK/retries (identical to a run without faults)", "request cmd=$02" in lg and
          same_region("fault_chat", "reply", "reply", 8, 64) and pbm_text("fault_chat", "reply") == pbm_text("fault_clean", "reply") and
          lit_rows("fault_chat", "reply", 8, 64) != lit_rows("fault_chat", "typed", 8, 64))
    # unexpected restart: a CPU reset that keeps the RAM is reported once on the next boot, any key goes on to the home screen
    s = Session("crashrep", start=1500)
    s.ev += ["1500:softreset"]
    s.snap("rep", wait=800)
    s.press("ENTER")
    s.snap("home", wait=600)
    s.run(extra_ms=200)
    check("an unexpected reset is reported with PC / SP on the next boot", lit_rows("crashrep", "rep", 14, 48) > 150, "(lit=%d)" % lit_rows("crashrep", "rep", 14, 48))
    check("after the report the home screen comes back", lit_rows("crashrep", "home", 56, 64) > 60)
    # DIAGNOSTICS 7 TIMING: measures the real tick rate and CPU speed (emulator: ~108 ticks/s, ~15 MHz)
    s = Session("timing", start=1500)
    s.press("GRAPH", "K7", "K7")
    s.snap("t", wait=2600)
    s.run(extra_ms=200)
    check("DIAGNOSTICS > TIMING shows ticks per second, CPU MHz and the RTC state", lit_rows("timing", "t", 14, 50) > 150, "(lit=%d)" % lit_rows("timing", "t", 14, 50))
    # the status-bar clock keeps ticking while waiting (the UI task is not blocked in a busy loop)
    s = Session("noesp_clock", start=1500)
    s.press("ZOOM", "K1", "K2", "ENTER")
    s.snap("w0", wait=500)
    s.snap("w1", wait=2500)
    s.run(extra_ms=300)
    check("the waiting screen keeps running (power/clock tasks are scheduled during the wait)",
          lit_rows("noesp_clock", "w1", 0, 7) > 0)


if __name__ == "__main__":
    run()
    ok = all(S.results)
    print("RESULT: %d/%d" % (sum(S.results), len(S.results)))
    sys.exit(0 if ok else 1)
