#!/usr/bin/env python3
"""Super-OS automated self-verification on the headless Tilem core (TI-83 Plus Silver Edition).

Exit code 0 = every check passed.  Run: python tools\\selftest.py
"""
import os
import re
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sim = os.path.join(root, "tools", "bin", "hz80_sim.exe")
rom = os.path.join(root, "build", "superos.rom")
out = os.path.join(root, "build", "test")
os.makedirs(out, exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# key matrix (row.bit)
RIGHT, LEFT, DOWN, UP = "0.2", "0.1", "0.0", "0.3"
ENTER, CLEAR = "1.0", "1.6"
K2ND, ON = "6.5", "-1.0"
YEQ, WINDOW, ZOOM, TRACE, GRAPH = "6.4", "6.3", "6.2", "6.1", "6.0"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print("  [%s] %s %s" % ("PASS" if ok else "FAIL", name, detail))


def kc(code):
    """firmware key code (row*8+bit+1) -> 'row.bit' for the harness"""
    return "%d.%d" % ((code - 1) // 8, (code - 1) % 8)


def tap(t, key, hold=60):
    return ["%d:down:%s" % (t, key), "%d:up:%s" % (t + hold, key)]


def type_keys(t, codes, step=150):
    ev = []
    for c in codes:
        ev += tap(t, kc(c), 60)
        t += step
    return ev, t


def run(tag, ms, events=(), env=None):
    cmd = [sim, rom, os.path.join(out, tag), str(ms)] + list(events)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=dict(os.environ, **(env or {})))
    d = {"raw": r.stdout, "snaps": {}, "err": r.stderr}
    for line in r.stdout.splitlines():
        m = re.match(r"PC=(\w+) SP=(\w+) halted=(\d) lcd_active=(\d) contrast=(\d+) speed_khz=(\d+)", line)
        if m:
            d.update(pc=int(m[1], 16), sp=int(m[2], 16), halted=int(m[3]), lcd=int(m[4]), contrast=int(m[5]), khz=int(m[6]))
        m = re.match(r"slices=(\d+) halted_pct=([\d.]+) stuck_at_reset_vec=(\d+) stuck_at_0038=(\d+) same_pc=(\d+) bad_sp=(\d+)", line)
        if m:
            d.update(slices=int(m[1]), halt_pct=float(m[2]), stuck0=int(m[3]), stuck38=int(m[4]), samepc=int(m[5]), badsp=int(m[6]))
        m = re.match(r"sp_range=(\w+)\.\.(\w+) lit_pixels=(\d+) lcd_off_cmds=(\d+) lcd_on_cmds=(\d+) lowpower_p3_writes=(\d+) last_p4=(\w+) port20_writes=(\d+) last_p20=(\w+)", line)
        if m:
            d.update(lit=int(m[3]), off=int(m[4]), on=int(m[5]), lowp=int(m[6]), p4=int(m[7], 16), p20w=int(m[8]), p20=int(m[9], 16))
        m = re.match(r"MEM (\w+):((?: [0-9A-F]{2})+)", line)
        if m:
            d["mem"] = [int(x, 16) for x in m[2].split()]
        m = re.match(r"ROM (\w+):(\w+) = (\w+)", line)
        if m:
            d["rombyte"] = int(m[3], 16)
        m = re.match(r"SNAP (\S+)\s+t=(\d+)ms lit=(\d+) lcd_active=(\d) halted_pct=([\d.]+) pc=(\w+) contrast_cmd=(\d+)", line)
        if m:
            d["snaps"][m[1]] = dict(lit=int(m[3]), lcd=int(m[4]), halt=float(m[5]), contrast=int(m[7]))
    return d


def pbm(tag):
    toks = open(os.path.join(out, tag + ".pbm")).read().split()
    return [[int(toks[3 + y * 96 + x]) for x in range(96)] for y in range(64)]


def region_lit(tag, y0, y1):
    p = pbm(tag)
    return sum(sum(r) for r in p[y0:y1])


def png(tag, scale=5):
    subprocess.run([sys.executable, os.path.join(root, "tools", "pbm2png.py"), os.path.join(out, tag + ".pbm"), os.path.join(out, tag + ".png"), str(scale)])


def main():
    if not os.path.exists(rom):
        sys.exit("ROM missing: run scripts\\2_build_all.ps1 first")

    esp_env = {"HZ_BRIDGE": "python " + os.path.join(root, "bridge_pc", "virtual_esp.py"), "HZ_LINKMODE": "line", "HZ_OFFLINE": "1",
               "HZ_BRIDGE_LOG": os.path.join(out, "esp.log")}

    def fresh_log():
        if os.path.exists(esp_env["HZ_BRIDGE_LOG"]):
            os.remove(esp_env["HZ_BRIDGE_LOG"])

    def esp_log():
        return open(esp_env["HZ_BRIDGE_LOG"]).read() if os.path.exists(esp_env["HZ_BRIDGE_LOG"]) else ""

    only_m3 = "--m3" in sys.argv
    if not only_m3:
        print("== 1. boot on the Silver Edition: 15 MHz, no bootloop, HALT idle")
        d = run("boot", 3000, ["2500:snap:a"])
        check("CPU switched to 15 MHz (port $20 = 1)", d["khz"] == 15000 and d["p20"] == 1, "(%d kHz)" % d["khz"])
        check("PC not stuck at the reset vector", d["stuck0"] == 0)
        check("PC not stuck in the RST $38 handler", d["stuck38"] < d["slices"] * 0.02)
        check("stack lives in RAM (>= $8000)", d["badsp"] == 0)
        check("CPU idles in HALT >= 90%% of the time", d["halt_pct"] >= 90.0, "(%.1f%%)" % d["halt_pct"])
        check("LCD renders the home screen", 600 <= d["lit"] <= 3000, "(%d lit)" % d["lit"])
        check("contrast command sent (alkaline profile = 48, readable on a real panel)", d["contrast"] == 48)
        check("legacy timer at the slowest rate (107.8 Hz)", d["p4"] == 0x06)
        check("status bar (6 px) drawn", region_lit("boot_a", 0, 6) > 40, "(%d px)" % region_lit("boot_a", 0, 6))
        check("tabs row drawn", region_lit("boot_a", 7, 13) > 30)
        png("boot_a")

        print("== 2. preemptive tasks + real-time clock (crystal timer 1)")
        d = run("tasks", 5200, [], env={"HZ_DUMP": "8621", "HZ_DUMPLEN": "60"})
        check("RTC advances once per second from crystal timer 1 (v_clks >= 4 after 5.2 s)", 4 <= d["mem"][59] <= 6, "(%d s)" % d["mem"][59])
        check("power task runs in the background (v_pcount >= 4)", d["mem"][0] >= 4, "(%d s)" % d["mem"][0])

        print("== 3. launcher: F-key tabs and numbered shortcuts")
        ev = tap(1000, TRACE) + ["1500:snap:games"] + tap(1600, YEQ) + ["2100:snap:home"] + tap(2200, kc(26)) + ["2800:snap:app"]
        d = run("home", 3000, ev)
        s = d["snaps"]
        check("F4 switches to the GAMES tab", s["games"]["lit"] != s["home"]["lit"] or
              open(os.path.join(out, "home_games.pbm")).read() != open(os.path.join(out, "home_home.pbm")).read())
        check("key 2 opens the 2nd item (INTERNET, pending app screen)", open(os.path.join(out, "home_app.pbm")).read() != open(os.path.join(out, "home_home.pbm")).read())
        png("home_home")
        png("home_app")

        print("== 4. settings: language ES/EN and battery profile -> contrast")
        ev = tap(1000, kc(34 + 0)) * 0                     # placeholder to keep the list explicit
        ev = tap(1000, DOWN) * 0
        # open SETTINGS = item 6 of tab INIC (key 6)
        ev = tap(1000, kc(19)) + ["1500:snap:es"] + tap(1600, RIGHT) + ["2100:snap:en"]
        d = run("settings", 2200, ev)
        check("LEFT/RIGHT toggles the language (screen text changed)",
              open(os.path.join(out, "settings_es.pbm")).read() != open(os.path.join(out, "settings_en.pbm")).read())
        ev = tap(1000, kc(19)) + tap(1500, DOWN) + tap(1700, RIGHT) + ["2200:snap:p1"] + tap(2300, RIGHT) + ["2800:snap:p2"] + tap(2900, RIGHT) + ["3400:snap:p0"]
        d = run("profile", 3500, ev)
        c = {k: v["contrast"] for k, v in d["snaps"].items()}
        check("profile 1 alkaline contrast 48", c["p0"] == 48, "(%s)" % c)
        check("profile 2 NiMH contrast 50", c["p1"] == 50)
        check("profile 3 Li-ion/LiPo boosted contrast 58", c["p2"] == 58)
        png("profile_p2")

        print("== 5. low battery: probe thresholds on port $04 + contrast boost")
        d = run("lowbat", 12000, ["3000:bat:0"])
        check("low-battery boost applied (48 -> 52)", d["contrast"] == 52, "(%d)" % d["contrast"])

        print("== 6. deep sleep after 120 s idle, wake on ON key; 2ND+ON immediate")
        ev = ["126000:snap:asleep", "128000:down:%s" % ON, "128200:up:%s" % ON, "130000:snap:awake"]
        d = run("sleep", 131000, ev)
        check("LCD off (cmd $02) and low-power HALT (port $03 bit3 = 0)", d["off"] >= 1 and d["lowp"] >= 1)
        check("LCD blanked while asleep", d["snaps"]["asleep"]["lcd"] == 0)
        check("LCD re-enabled after ON, screen restored", d["on"] >= 2 and d["snaps"]["awake"]["lcd"] == 1 and d["snaps"]["awake"]["lit"] > 300)
        check("CPU asleep >= 96%% of a 131 s run", d["halt_pct"] >= 96.0, "(%.2f%%)" % d["halt_pct"])
        ev = ["1000:down:%s" % K2ND, "1100:down:%s" % ON, "1300:up:%s" % ON, "1400:up:%s" % K2ND, "3000:snap:s"]
        d = run("sleep2", 3100, ev)
        check("2ND+ON sleeps now", d["snaps"]["s"]["lcd"] == 0 and d["off"] >= 1)

        print("== 7. AI chat over SuperLink: wake pulse -> ESP boot -> READY -> frame -> ZX0 reply -> viewer")
        fresh_log()
        K4, K3, K5, K6 = 35, 18, 27, 19
        ev = tap(1000, kc(34))                                  # key 1 = CHAT
        e2, t = type_keys(1500, [K4, K3, K5, K5, K6])           # h e l l o  (T9)
        ev += e2 + ["%d:snap:typed" % (t + 200)] + tap(t + 400, ENTER) + ["%d:snap:reply" % (t + 5000)]
        d = run("chat", t + 5500, ev, env=esp_env)
        lg = esp_log()
        check("ESP32 deep sleep woken by the 50 ms TIP pulse", "woken by TIP pulse (4" in lg or "woken by TIP pulse (5" in lg, "(%s)" % [l for l in lg.splitlines() if "TIP" in l])
        check("ESP_READY ($A5 $5A) received by the calculator", "ESP_READY sent" in lg)
        check("SuperLink frame decoded by the ESP (CMD_CHAT, 6 bytes: model 0 + hello; CRC8 ok)", "request cmd=$02 len=6" in lg and "hello" in lg)
        check("reply streamed back as ZX0 chunks and shown", "-> zx0" in lg and d["snaps"]["reply"]["lit"] != d["snaps"]["typed"]["lit"])
        png("chat_typed")
        png("chat_reply")

        print("== 8. WiFi & API setup: ABC (TI alpha layout) entry -> CMD_API_SET")
        fresh_log()
        ev = tap(1000, kc(27)) + tap(1600, kc(26)) + ["2100:snap:abc"]       # 5 = WIFI, 2 = API key
        e3, t = type_keys(2300, [47, 39, 31], step=200)          # MATH=a  APPS=b  PRGM=c
        ev += e3 + tap(t + 200, ENTER) + ["%d:snap:done" % (t + 5000)]
        d = run("wifi", t + 5500, ev, env=esp_env)
        check("API key typed with the alpha layout and stored by the ESP (3 chars)", "api key stored (3 chars)" in esp_log(), "(%s)" % esp_log().splitlines()[-1:])
        png("wifi_abc")

        print("== 9. ESP32 idle supervision: CMD_SLEEP after the idle timeout")
        fresh_log()
        ev = tap(1000, kc(34))
        e2, t = type_keys(1500, [K4, K3, K5, K5, K6])
        ev += e2 + tap(t + 400, ENTER)
        d = run("espsleep", t + 200000, ev, env=esp_env)
        check("calculator sends CMD_SLEEP after 180 s without traffic", "CMD_SLEEP" in esp_log())
        check("whole run stayed in HALT >= 95%% of the time", d["halt_pct"] >= 95.0, "(%.1f%%)" % d["halt_pct"])

        print("== 10. TI-OS/Ion style program through the B_CALL shim (BOOKS -> 3)")
        ev = tap(1000, kc(20)) + tap(1600, kc(18)) + ["3000:snap:demo1", "4300:snap:demo2"] + tap(4500, CLEAR) + ["5600:snap:back"]
        d = run("demo", 5700, ev)
        sn = d["snaps"]
        pa = open(os.path.join(out, "demo_demo1.pbm")).read()
        pb = open(os.path.join(out, "demo_demo2.pbm")).read()
        pc = open(os.path.join(out, "demo_back.pbm")).read()
        check("demo renders through RST $28 (ClrLCDFull / PutS / GrBufCpy)", sn["demo1"]["lit"] >= 96, "(%d lit)" % sn["demo1"]["lit"])
        check("demo animates (plotSScreen + fast copy)", pa != pb)
        check("legacy GetCSC polling loop HALTs (no busy wait)", sn["demo2"]["halt"] > 55, "(%.1f%% halted)" % sn["demo2"]["halt"])
        check("CLEAR returns to the OS", pc != pb)

        print("== 11. settings journal in flash survives a power cycle (RAM wiped)")
        ev = tap(1000, kc(19)) + tap(1500, DOWN) + tap(1700, DOWN) + tap(1900, RIGHT) + tap(2100, RIGHT) + tap(2300, RIGHT)   # SETTINGS: contrast trim 8 -> 11
        ev += ["3000:snap:before", "4000:reset", "7000:snap:after"]
        d = run("persist", 7500, ev, env={"HZ_ROM": "70:0", "HZ_ROMLEN": "64"})
        lines = [l for l in d["raw"].splitlines() if l.startswith("ROMDUMP")]
        recs = [int(x, 16) for x in lines[0].split(":")[2].split()] if lines else []
        check("journal records in flash page $70 (marker $A5 + 'SO' magic)", len(recs) >= 32 and recs[0] == 0xA5 and recs[1:3] == [0x53, 0x4F])
        check("contrast trim restored from flash after RAM was wiped (cmd 51)", d["snaps"]["before"]["contrast"] == 51 and d["snaps"]["after"]["contrast"] == 51,
              "(%s)" % {k: v["contrast"] for k, v in d["snaps"].items()})

        store = os.path.join(out, "store")
        os.makedirs(store, exist_ok=True)
        demo_bin = open(os.path.join(root, "build", "demo.bin"), "rb").read()
        open(os.path.join(store, "HELLO.bin"), "wb").write(demo_bin)
        ota_env = dict(esp_env, HZ_STORE_DIR=store)

        print("== 12. OTA: list on the ESP32 -> download (ZX0) -> install into the flash package store -> run")
        fresh_log()
        # F5 (SYS tab) -> 6 OTA -> 1 remote list -> 1 pick -> key; then OTA -> 2 installed -> 1 pick -> ENTER runs it
        ev = tap(1000, GRAPH) + tap(1400, kc(19)) + tap(2200, kc(34)) + ["6000:snap:list"] + tap(6200, kc(34)) + tap(7200, ENTER)
        ev += tap(7800, GRAPH) + tap(8200, kc(19)) + tap(8800, kc(26)) + tap(9600, kc(34)) + tap(10400, ENTER) + ["11600:snap:run1", "12600:snap:run2"]
        d = run("ota", 13000, ev, dict(ota_env, HZ_ROM="20:0", HZ_ROMLEN="16"))
        lg = esp_log()
        entry = [int(x, 16) for x in [l for l in d["raw"].splitlines() if l.startswith("ROMDUMP")][0].split(":")[2].split()]
        check("ESP lists packages and serves the download", "request cmd=$04 len=1" in lg and "request cmd=$04 len=6" in lg)
        check("directory entry programmed in flash: HELLO, page $24, length 82, type 1",
              bytes(entry[:5]) == b"HELLO" and entry[8] == 0x24 and entry[11] | entry[12] << 8 == len(demo_bin) and entry[13] == 1, "(%s)" % bytes(entry[:8]))
        d2 = run("ota_data", 7600, ev[:ev.index("7800:down:%s" % GRAPH)], dict(ota_env, HZ_ROM="24:0", HZ_ROMLEN=str(len(demo_bin))))
        data = bytes(int(x, 16) for x in [l for l in d2["raw"].splitlines() if l.startswith("ROMDUMP")][0].split(":")[2].split())
        check("package bytes in flash page $24 identical to the pushed file (ZX0 round trip + flash programming)", data == demo_bin, "(%d bytes)" % len(data))
        check("installed program runs from the package store and animates",
              open(os.path.join(out, "ota_run1.pbm")).read() != open(os.path.join(out, "ota_run2.pbm")).read())

        print("== 13. diagnostics: link test (wake+status, 10 pings, 512 B benchmark)")
        fresh_log()
        ev = tap(1000, GRAPH) + tap(1400, kc(36)) + tap(2200, kc(34)) + tap(3400, ENTER) + ["9000:snap:t"]
        d = run("diag", 9500, ev, dict(esp_env, HZ_DUMP="86D8", HZ_DUMPLEN="4"))
        lg = esp_log()
        check("10 pings of 64 bytes and one 512-byte benchmark reached the ESP", lg.count("request cmd=$01 len=64") == 10 and "request cmd=$16" in lg)
        check("calculator counted 10/10 successful pings (v_dgok)", d["mem"][2] == 10, "(%s)" % d["mem"][:4])
        check("the 512-byte benchmark is repeated over the turbo byte layer and the safe layer is restored",
              "turbo ON requested" in lg and "byte layer is now TURBO" in lg and "byte layer is now safe" in lg and lg.count("request cmd=$16") == 2)
        png("diag_t")

        print("== 14. diagnostics: RAM test of all 8 pages")
        ev = tap(1000, GRAPH) + tap(1400, kc(36)) + tap(2200, kc(35)) + ["8000:snap:r"]
        d = run("diagram", 8500, ev, env={"HZ_DUMP": "86DF", "HZ_DUMPLEN": "1"})
        check("128 KB RAM: pages 0,2..7 pass the write/verify test (page 1 is the live one)", d["mem"][0] == 0xFD, "(mask %02X)" % d["mem"][0])
        png("diagram_r")

        print("== 15. diagnostics: flash guard + erase/program/verify in the scratch sector")
        ev = tap(1000, GRAPH) + tap(1400, kc(36)) + tap(2200, kc(27)) + tap(3000, ENTER) + ["9000:snap:f"]
        d = run("diagfl", 9500, ev, env={"HZ_DUMP": "86E0", "HZ_DUMPLEN": "1", "HZ_ROM": "74:0", "HZ_ROMLEN": "8"})
        check("guard refuses pages $7F $7E $7C $06 $03 $02 $00 $1F; scratch sector erased, programmed, verified, erased again", d["mem"][0] == 0x0F, "(mask %02X)" % d["mem"][0])
        png("diagfl_f")

        print("== 16. diagnostics: LCD patterns and 4-level gray, keyboard matrix, ESP32 report")
        ev = tap(1000, GRAPH) + tap(1400, kc(36)) + tap(2200, kc(26)) + ["2800:snap:black"] + tap(2900, RIGHT) + tap(3300, RIGHT) + ["3800:snap:check"]
        ev += tap(3900, RIGHT) + tap(4300, RIGHT) + tap(4700, RIGHT) + ["5400:snap:gray"]
        d = run("diaglcd", 6000, ev)
        s = d["snaps"]
        check("all-black pattern lights the whole panel", s["black"]["lit"] == 6144, "(%d px)" % s["black"]["lit"])
        check("checkerboard lights half the pixels", abs(s["check"]["lit"] - 3072) < 40, "(%d px)" % s["check"]["lit"])
        check("gray test shows a mid-phase frame (partial coverage)", 500 < s["gray"]["lit"] < 5800, "(%d px)" % s["gray"]["lit"])
        ev = tap(1000, GRAPH) + tap(1400, kc(36)) + tap(2200, kc(27 - 24)) * 0
        ev = tap(1000, GRAPH) + tap(1400, kc(36)) + tap(2200, kc(18)) + ["3000:snap:idle", "3100:down:%s" % kc(34), "3600:snap:held", "3700:up:%s" % kc(34)]
        d = run("diagkeys", 4000, ev)
        check("keyboard matrix screen reacts to a held key", open(os.path.join(out, "diagkeys_idle.pbm")).read() != open(os.path.join(out, "diagkeys_held.pbm")).read())
        png("diagkeys_held")
        fresh_log()
        ev = tap(1000, GRAPH) + tap(1400, kc(36)) + tap(2200, kc(19)) + ["8000:snap:rep"]
        d = run("diagesp", 8500, ev, esp_env)
        check("ESP32 report requested (CMD_DIAG) and shown", "request cmd=$15" in esp_log() and d["snaps"]["rep"]["lit"] > 100)
        png("diagesp_rep")

        print("== 17. OTA from the PC: calculator opens the upload window, tools/ota_push.py uploads through HTTP")
        import time
        fresh_log()
        port = 18266
        pushdir = os.path.join(out, "store_push")
        os.makedirs(pushdir, exist_ok=True)
        for f in os.listdir(pushdir):
            os.remove(os.path.join(pushdir, f))
        pkg = os.path.join(out, "newpkg.bin")
        open(pkg, "wb").write(bytes([0xC9]) + b"push-test-image")
        env = dict(os.environ, **dict(esp_env, HZ_STORE_DIR=pushdir, HZ_OTA_PORT=str(port)))
        ev = tap(1000, GRAPH) + tap(1400, kc(19)) + tap(2200, kc(35)) + ["4000:snap:win"]       # SYS -> OTA -> 4 receive
        proc = subprocess.Popen([sim, rom, os.path.join(out, "otapush"), "60000"] + ev, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        pushed = ""
        t0 = time.time()
        while time.time() - t0 < 60 and proc.poll() is None:
            if "OTA window open" in esp_log():
                time.sleep(0.5)
                for attempt in range(12):                        # the listener needs a moment after the window opens
                    r = subprocess.run([sys.executable, os.path.join(root, "tools", "ota_push.py"), pkg, "--name", "NEWPKG", "--host", "127.0.0.1", "--port", str(port)],
                                       capture_output=True, text=True)
                    pushed = r.stdout + r.stderr
                    if r.returncode == 0:
                        break
                    time.sleep(1.0)
                break
            time.sleep(0.1)
        proc.wait(timeout=120)
        check("calculator asked the ESP32 for an upload window (CMD_OTA)", "OTA window open" in esp_log())
        check("ota_push.py uploaded NEWPKG and the ESP stored it", os.path.exists(os.path.join(pushdir, "NEWPKG.bin")) and "OTA upload received: NEWPKG" in esp_log(), "(%s)" % pushed.strip())


    print("== 18. Milestone 3: scientific calculator, grapher, table (headless key-driven checks)")
    from uidrive import Session, parse_mem, cstr, C_HIST, GR_BASE, M_BASE as M_BASE_ADDR
    import fxlib

    def calc_hist(tag, builder):
        s = Session(tag, start=1500)
        s.press("WINDOW", "K1")                              # MATH tab -> 1 CALCULATOR
        s.t += 700
        builder(s)
        r = s.run(extra_ms=400, env={"HZ_DUMP": "%X" % C_HIST, "HZ_DUMPLEN": "150"})
        h = parse_mem(r)
        return [(cstr(h, 50 * i), cstr(h, 50 * i + 25)) for i in range(3)]

    def b1(s):
        s.type("2+3*4"); s.press("ENTER")
        s.second("SQ"); s.type("16)"); s.press("ENTER")
        s.second("POW"); s.press("ENTER")
    h = calc_hist("m3calc1", b1)
    check("calculator: 2+3*4 = 14", h[0][1] == "14", "(%s)" % (h[0],))
    check("calculator: sqrt(16) = 4 (2ND+x2)", h[1][1] == "4", "(%s)" % (h[1],))
    check("calculator: 2ND+^ is pi = 3.14159265", h[2][1] == "3.14159265", "(%s)" % (h[2],))

    def b2(s):
        s.press("MODE")                                      # DEG
        s.press("SIN"); s.type("30)"); s.press("ENTER")
        s.type("5"); s.press("STO", "ALPHA", "MATH"); s.press("ENTER")   # 5 -> A
        s.press("ALPHA", "MATH"); s.type("*2"); s.press("ENTER")
    h = calc_hist("m3calc2", b2)
    check("calculator: sin(30) in degree mode = 0.5", h[0][1] == "0.5", "(%s)" % (h[0],))
    check("calculator: 5 STO A stores a variable", h[1][1] == "5", "(%s)" % (h[1],))
    check("calculator: A*2 = 10 uses the variable", h[2][1] == "10", "(%s)" % (h[2],))

    def b3(s):
        s.type("1/0"); s.press("ENTER")
        s.type("2+"); s.press("ENTER")
        s.press("MATH", "ENTER"); s.type("-3)"); s.press("ENTER")   # MATH menu: first item ABS(
    h = calc_hist("m3calc3", b3)
    check("calculator: 1/0 reports a division error", h[0][1] in ("DIV POR 0", "DIV BY 0"), "(%s)" % (h[0],))
    check("calculator: 2+ reports a syntax error", h[1][1] in ("SINTAXIS", "SYNTAX"), "(%s)" % (h[1],))
    check("calculator: MATH menu inserts ABS( and abs(-3) = 3", h[2][1] == "3", "(%s)" % (h[2],))

    s = Session("m3graph", start=1500)
    s.press("WINDOW", "K2")                                  # MATH tab -> 2 GRAPH (Y1 = sin(x))
    s.snap("plot", wait=3500)
    s.press("RIGHT", "RIGHT", "RIGHT")
    s.snap("trace", wait=500)
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % (GR_BASE + 217), "HZ_DUMPLEN": "40"})
    lit = {n: int(m) for n, m in re.findall(r"SNAP (\S+)\s+t=\d+ms lit=(\d+)", r)}
    check("grapher: sin(x) plotted with axes (lit pixels)", 120 < lit.get("plot", 0) < 900, "(lit=%s)" % lit.get("plot"))
    check("grapher: trace readout is exact", cstr(parse_mem(r)).startswith("Y1 X=0.73684 Y=0.67195"), "(%r)" % cstr(parse_mem(r)))
    png("m3graph_trace") if False else None

    s = Session("m3tab", start=1500)
    s.press("WINDOW", "K2")
    s.t += 3500
    s.second("GRAPH")
    s.t += 1500
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % (GR_BASE + 217), "HZ_DUMPLEN": "16"})
    check("table: last row dy/dx of sin at x=6 is cos(6) = 0.9602", cstr(parse_mem(r)) == "0.9602", "(%r)" % cstr(parse_mem(r)))

    s = Session("m3fit", start=1500)
    s.press("WINDOW", "K2")
    s.t += 3500
    s.press("ZOOM", "K6")
    s.t += 4000
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % (GR_BASE + 156), "HZ_DUMPLEN": "12"})
    b = parse_mem(r)
    ymin, ymax = fxlib.unpack(b[0:6]), fxlib.unpack(b[6:12])
    check("zoom fit: y range of sin(x) becomes about -1.1 .. 1.1", abs(ymin + 1.1) < 0.02 and abs(ymax - 1.1) < 0.02, "(%.3f .. %.3f)" % (ymin, ymax))

    s = Session("m3win", start=1500)
    s.press("WINDOW", "K2")
    s.t += 3500
    s.press("WINDOW")
    s.press("DEL", "DEL", "DEL"); s.type("-5"); s.press("ENTER")    # XMIN = -5
    s.press("DEL", "DEL"); s.type("5"); s.press("ENTER")            # XMAX = 5
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % (GR_BASE + 144), "HZ_DUMPLEN": "12"})
    b = parse_mem(r)
    check("window editor: XMIN/XMAX typed as -5 and 5", fxlib.unpack(b[0:6]) == -5.0 and fxlib.unpack(b[6:12]) == 5.0,
          "(%s .. %s)" % (fxlib.unpack(b[0:6]), fxlib.unpack(b[6:12])))

    print("== 19. Milestone 3: Super-CAS client, 3D plot, step by step (R1), converter, [PLOT:] from the AI")
    cas_env = dict(esp_env, HZ_OFFLINE="1")

    def cas_run(tag, builder, wait=7000, dump=("D000", 160), extra_env=None):
        fresh_log()
        s = Session(tag, start=1500)
        s.press("WINDOW", "K3")                              # MATH tab -> 3 SUPER-CAS
        s.t += 800
        builder(s)
        s.t += wait
        r = s.run(extra_ms=300, env=dict(cas_env, HZ_DUMP=dump[0], HZ_DUMPLEN=str(dump[1]), **(extra_env or {})))
        return cstr(parse_mem(r)), r, s

    def b_diff(s):
        s.press("MATH", "ENTER")                             # diff(
        s.press("SIN"); s.type("X)*X,X)"); s.press("ENTER")
    txt, r, s = cas_run("m3cas1", b_diff)
    check("CAS: diff(sin(x)*x,x) computed by the ESP32 engine", txt.startswith("x*cos(x) + sin(x)"), "(%r)" % txt)
    check("CAS: the formula travelled as CMD_CAS text", "CAS command: 'diff(SIN(X)*X,X)'" in esp_log(), "(%s)" % [l for l in esp_log().splitlines() if "CAS" in l])

    def b_solve(s):
        s.press("MATH", "DOWN", "DOWN", "DOWN", "ENTER")     # solve(
        s.type("X^2-2"); s.press("ALPHA", "PLUS"); s.type("0,X)"); s.press("ENTER")
    txt, r, s = cas_run("m3cas2", b_solve)
    check("CAS: solve(x^2-2=0,x) = {-sqrt(2), sqrt(2)}", txt.startswith("{x = -sqrt(2), x = sqrt(2)}"), "(%r)" % txt)

    def b_int(s):
        s.press("MATH", "DOWN", "ENTER")                     # int(
        s.type("X"); s.press("MUL"); s.second("LN"); s.type("X^2)"); s.type(",X)"); s.press("ENTER")   # int(x*exp(x^2),x)
    txt, r, s = cas_run("m3cas3", b_int)
    check("CAS: int(x*exp(x^2),x) = exp(x^2)/2 + C", txt.startswith("exp(x^2)/2 + C"), "(%r)" % txt)

    def b_3d(s):
        s.press("MATH")
        for _ in range(20):
            s.press("DOWN")
        s.press("ENTER")                                     # plot3d(
        s.press("SIN"); s.type("X)"); s.press("MUL"); s.press("COS"); s.press("ALPHA", "K1"); s.type(")")
        s.press("COMMA"); s.press("NEG"); s.type("3,3"); s.press("COMMA"); s.press("NEG"); s.type("3,3)")
        s.press("ENTER")
    fresh_log()
    s = Session("m3plot3d", start=1500)
    s.press("WINDOW", "K3")
    s.t += 800
    b_3d(s)
    s.snap("surface", wait=7000)
    r = s.run(extra_ms=300, env=cas_env)
    lit = {n: int(m) for n, m in re.findall(r"SNAP (\S+)\s+t=\d+ms lit=(\d+)", r)}
    check("3D surface: the ESP32 renders plot3d(sin(x)*cos(y),-3,3,-3,3) and the calculator shows it", 300 < lit.get("surface", 0) < 3500 and "CAS" not in "", "(lit=%s)" % lit.get("surface"))
    s.png("surface", 4)

    fresh_log()
    s = Session("m3step", start=1500)
    s.press("WINDOW", "K4")                                  # STEP BY STEP
    s.t += 800
    s.type("X^2"); s.press("ENTER")
    s.t += 7000
    r = s.run(extra_ms=300, env=dict(cas_env, HZ_DUMP="D000", HZ_DUMPLEN="120"))
    check("step by step: R1 is asked to explain the problem", "request cmd=$02" in esp_log() and "Explain step by step" in esp_log(), "(%s)" % [l for l in esp_log().splitlines() if "request" in l])
    check("step by step: the explanation is shown", "R1" in cstr(parse_mem(r)), "(%r)" % cstr(parse_mem(r)))

    from uidrive import ED_BASE
    CS = GR_BASE + 330
    s = Session("m3conv", start=1500)
    s.press("WINDOW", "K6", "ENTER")                         # CONVERTER -> LENGTH
    s.t += 400
    s.press("K3", "DEL"); s.type("5"); s.press("ENTER")      # value = 5 (mm -> cm)
    s.t += 300
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % (CS + 170), "HZ_DUMPLEN": "6"})
    check("converter: 5 mm = 0.5 cm", abs(fxlib.unpack(parse_mem(r)) - 0.5) < 1e-8, "(%s)" % fxlib.unpack(parse_mem(r)))
    s = Session("m3conv2", start=1500)
    s.press("WINDOW", "K6", "DOWN", "DOWN", "DOWN", "ENTER")  # TEMPERATURE: C -> F by default
    s.t += 400
    s.press("K3", "DEL"); s.type("100"); s.press("ENTER")
    s.t += 300
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % (CS + 170), "HZ_DUMPLEN": "6"})
    check("converter: 100 C = 212 F", abs(fxlib.unpack(parse_mem(r)) - 212.0) < 1e-6, "(%s)" % fxlib.unpack(parse_mem(r)))

    fresh_log()
    run_s = Session("m3aiplot", start=1500)
    run_s.press("K1")                                        # HOME tab: key 1 = AI CHAT
    run_s.t += 700
    for code in (35, 18, 27, 27, 19):
        run_s.key(code)
    run_s.press("ENTER")
    run_s.t += 7000
    run_s.press("CLEAR")                                     # leave the viewer
    run_s.t += 500
    run_s.snap("ask", wait=300)
    run_s.press("ENTER")                                     # plot it
    run_s.snap("graph", wait=5000)
    reply = "Here is the curve. [PLOT: x^2, -3, 3]"
    r = run_s.run(extra_ms=300, env=dict(cas_env, HZ_CHAT_REPLY=reply, HZ_DUMP="%X" % GR_BASE, HZ_DUMPLEN="3"))
    lit = {n: int(m) for n, m in re.findall(r"SNAP (\S+)\s+t=\d+ms lit=(\d+)", r)}
    check("[PLOT:] block of an AI answer: formula tokenised into Y1 (X^2)", parse_mem(r)[:3] == b"X^2", "(%r)" % parse_mem(r)[:3])
    check("[PLOT:] block: the grapher shows the parabola", lit.get("graph", 0) > 150, "(lit=%s)" % lit.get("graph"))

    print("== 20. Milestone 3: periodic table, constants (-> ANS), Wikipedia and weather through the ESP32")
    P_Z = 0x9E00 + 245
    s = Session("m3pt", start=1500)
    s.press("WINDOW", "K5")                                  # MATH tab -> 5 PERIODIC TABLE
    s.t += 900
    s.snap("grid", wait=100)
    s.press("DOWN", "DOWN", "ENTER")                         # H -> Li -> Na, detail page
    s.t += 300
    s.press("RIGHT")                                         # next element = Mg
    s.t += 300
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % P_Z, "HZ_DUMPLEN": "1"})
    lit = {n: int(m) for n, m in re.findall(r"SNAP (\S+)\s+t=\d+ms lit=(\d+)", r)}
    check("periodic table: grid of 118 elements drawn", lit.get("grid", 0) > 150, "(lit=%s)" % lit.get("grid"))
    check("periodic table: H -> down -> down = Na (11), RIGHT in the detail page = Mg (12)", parse_mem(r)[:1] == bytes([12]), "(Z=%s)" % list(parse_mem(r)[:1]))
    s.png("grid", 4)

    ANS = M_BASE_ADDR + 160 + 26 * 6
    s = Session("m3const", start=1500)
    s.press("WINDOW", "K7")                                  # MATH tab -> 7 CONSTANTS
    s.t += 900
    s.press("ENTER")                                         # detail of c
    s.t += 300
    s.press("ENTER")                                         # store in ANS
    s.t += 500
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % ANS, "HZ_DUMPLEN": "6"})
    v = fxlib.unpack(parse_mem(r))
    check("constants: ENTER on the speed of light stores 299792458 in ANS", abs(v - 299792458.0) < 1, "(%s)" % v)
    s = Session("m3const2", start=1500)
    s.press("WINDOW", "K7")
    s.t += 900
    s.press("DOWN", "ENTER")                                 # G
    s.t += 300
    s.press("ENTER")
    s.t += 500
    r = s.run(extra_ms=300, env={"HZ_DUMP": "%X" % ANS, "HZ_DUMPLEN": "6"})
    v = fxlib.unpack(parse_mem(r))
    check("constants: gravitational constant 6.6743E-11 (scientific notation parsed)", abs(v - 6.6743e-11) < 1e-17, "(%s)" % v)

    def net_app(tag, keys, reply_prefix, cmd):
        fresh_log()
        s = Session(tag, start=1500)
        s.press(*keys)
        s.t += 800
        for code in (35, 18, 27, 27, 19):                    # h e l l o
            s.key(code)
        s.press("ENTER")
        s.t += 7000
        r = s.run(extra_ms=300, env=dict(cas_env, HZ_DUMP="D000", HZ_DUMPLEN="60"))
        return cstr(parse_mem(r)), esp_log()

    txt, lg = net_app("m3wiki", ("K2",), "", 3)                # HOME tab -> 2 INTERNET (Wikipedia)
    check("Wikipedia: the query reaches the ESP32 (CMD_WIKI) and the answer is shown", "request cmd=$03" in lg and txt.startswith("[offline wiki es] hello"), "(%r)" % txt)
    txt, lg = net_app("m3weather", ("ZOOM", "K6"), "", 6)      # AI tab -> 6 WEATHER
    check("Weather: the city reaches the ESP32 (CMD_WEATHER) and the answer is shown", "request cmd=$06" in lg and txt.startswith("[offline weather es] hello"), "(%r)" % txt)
    if "--m3" not in sys.argv:
        import selftest_m4
        selftest_m4.run(check)
        import selftest_noesp
        selftest_noesp.run(check)
        import selftest_games
        selftest_games.run(check)
        import selftest_lock
        selftest_lock.run(check)
        import selftest_review
        selftest_review.run(check)
    print()
    n = sum(results)
    print("RESULT: %d/%d checks passed" % (n, len(results)))
    sys.exit(0 if n == len(results) else 1)


if __name__ == "__main__":
    main()
