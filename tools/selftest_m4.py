#!/usr/bin/env python3
"""Milestone 4 checks on the headless emulator: CHIP-8 game packs on the Z80, streamed games over the SuperLink turbo byte layer.
Called from selftest.py (shared results list); `python tools/selftest_m4.py` runs only this part."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest as S  # noqa: E402
from uidrive import Session, pbm_text, KEYS, kc, out, root  # noqa: E402

check = S.check
ESP = {"HZ_BRIDGE": "python " + os.path.join(root, "bridge_pc", "virtual_esp.py"), "HZ_LINKMODE": "line", "HZ_OFFLINE": "1",
       "HZ_BRIDGE_LOG": os.path.join(out, "esp_m4.log")}


def lit(tag, name, x0=0, x1=96, y0=0, y1=64):
    p = pbm_text(tag, name)
    return sum(p[y][x] for y in range(y0, y1) for x in range(x0, x1))


def top_y(tag, name, x0, x1, y_min=8):
    p = pbm_text(tag, name)
    ys = [y for y in range(y_min, 64) for x in range(x0, x1) if p[y][x]]
    return min(ys) if ys else -1


def left_x(tag, name, y0, y1):
    p = pbm_text(tag, name)
    xs = [x for y in range(y0, y1) for x in range(96) if p[y][x]]
    return min(xs) if xs else -1


def hold(s, name, ms):
    code = KEYS[name]
    s.ev += ["%d:down:%s" % (s.t, kc(code)), "%d:up:%s" % (s.t + ms, kc(code))]
    s.t += ms + 100


def esp_log():
    return open(ESP["HZ_BRIDGE_LOG"]).read() if os.path.exists(ESP["HZ_BRIDGE_LOG"]) else ""


def fresh_log():
    if os.path.exists(ESP["HZ_BRIDGE_LOG"]):
        os.remove(ESP["HZ_BRIDGE_LOG"])


def frame_rate(log, keys_repr):
    ts = [int(x) for x in re.findall(r"cmd=\$32 len=4 b'%s' @(\d+)ms" % keys_repr, log)]
    return ((len(ts) - 1) * 1000.0 / (ts[-1] - ts[0]) if len(ts) > 2 else 0.0), len(ts)


def run(check_fn=None):
    global check
    if check_fn:
        check = check_fn
    print("== 21. Milestone 4: CHIP-8 game packs on the Z80 (ARCADE / ACTION tabs of the GAMES launcher)")
    s = Session("m4pong", start=1500)
    s.press("TRACE", "K9", "K2")
    s.snap("menu", wait=400)
    s.press("ENTER")
    s.snap("p1", wait=1500)
    hold(s, "K8", 900)                                       # calculator 8 = CHIP-8 key 2 = up
    s.snap("p2", wait=200)
    s.press("CLEAR")
    s.snap("after", wait=600)
    s.run(extra_ms=300)
    check("ARCADE menu lists the pack (PONG / BREAKOUT / SNAKE)", lit("m4pong", "menu", y0=14, y1=40) > 120, "(lit=%d)" % lit("m4pong", "menu", y0=14, y1=40))
    check("PONG runs: paddles and score drawn in the 64x32 field", lit("m4pong", "p1", 16, 80) > 40, "(lit=%d)" % lit("m4pong", "p1", 16, 80))
    check("the 16-pixel margins stay empty", lit("m4pong", "p1", 0, 16) == 0 and lit("m4pong", "p1", 80, 96) == 0)
    t1, t2 = top_y("m4pong", "p1", 18, 20), top_y("m4pong", "p2", 18, 20)
    check("key 8 moves the left paddle up (matrix keypad -> CHIP-8 keypad)", 0 <= t2 < t1, "(top row %d -> %d)" % (t1, t2))
    check("CLEAR leaves the game back to the pack menu", abs(lit("m4pong", "after", y0=14, y1=40) - lit("m4pong", "menu", y0=14, y1=40)) < 40)
    s.png("p1", 4)

    s = Session("m4inv", start=1500)
    s.press("TRACE", "K9", "K2")                                   # CLASSIC menu: PONG BREAKOUT SNAKE INVADERS DODGE SIMON
    s.press("DOWN", "DOWN", "DOWN", "ENTER")                 # INVADERS
    s.snap("i1", wait=1500)
    hold(s, "K6", 1200)                                      # chip 6 = right
    s.snap("i2", wait=200)
    s.press("CLEAR")
    s.run(extra_ms=300)
    a, b = left_x("m4inv", "i1", 56, 64), left_x("m4inv", "i2", 56, 64)
    check("INVADERS: aliens drawn and the ship follows the right key", lit("m4inv", "i1", 16, 80) > 80 and 0 <= a < b, "(ship x %d -> %d)" % (a, b))
    s.png("i1", 4)

    print("== 22. Milestone 4: streamed games - turbo byte layer, delta frames, maze 3D and Game Boy (Peanut-GB) rendered on the ESP32")
    fresh_log()
    s = Session("m4maze", start=1500)
    s.press("TRACE", "K9", "K3")
    s.snap("list", wait=3200)                                # wake the ESP32, list the titles
    s.press("ENTER")
    s.snap("g1", wait=2500)
    t0 = s.t
    hold(s, "K6", 4000)                                      # chip 6 = turn right: worst case, the whole picture changes
    s.snap("g2", wait=0)
    s.press("CLEAR")
    s.snap("back", wait=1500)
    s.run(extra_ms=300, env=ESP)
    lg = esp_log()
    check("STREAM menu lists the titles sent by the ESP32 (MAZE 3D, DMG-ACID2)", lit("m4maze", "list", y0=14, y1=30) > 60, "(lit=%d)" % lit("m4maze", "list", y0=14, y1=30))
    check("CMD_TURBO switched both ends to the calculator-clocked byte layer", "turbo ON requested" in lg and "byte layer is now TURBO" in lg)
    check("maze 3D picture streamed to the calculator", lit("m4maze", "g1") > 1200, "(lit=%d)" % lit("m4maze", "g1"))
    check("turning changes the picture (delta frames applied)", open(os.path.join(out, "m4maze_g1.pbm")).read() != open(os.path.join(out, "m4maze_g2.pbm")).read())
    fps_turn, n = frame_rate(lg, r".x02@.x00.x00")
    fps_idle, n2 = frame_rate(lg, r".x02.x00.x00.x00")
    check("worst case (whole picture changing) streams at >= 10 frames/s", fps_turn >= 10.0, "(%.1f frames/s over %d requests; idle %.0f frames/s)" % (fps_turn, n, fps_idle))
    check("leaving the game stops it and returns to the safe byte layer", "cmd=$32 len=1 b'\\x03'" in lg and "byte layer is now safe" in lg
          and lit("m4maze", "back", y0=14, y1=30) > 60)
    s.png("g1", 4)

    fresh_log()
    s = Session("m4gb", start=1500)
    s.press("TRACE", "K9", "K3")
    s.t += 3200
    s.press("DOWN", "ENTER")                                 # DMG-ACID2 through Peanut-GB on the ESP32
    s.snap("gb", wait=5000)
    s.press("CLEAR")
    s.run(extra_ms=300, env=ESP)
    n_gb = lit("m4gb", "gb")
    check("Game Boy: dmg-acid2 (Peanut-GB on the ESP32) is shown on the calculator", 500 < n_gb < 3500, "(lit=%d)" % n_gb)
    s.png("gb", 4)

    print("== 23. Milestone 4: OTA games - a CHIP-8 game pushed to the ESP32, installed into the calculator's flash store and played")
    import chip8
    store = os.path.join(out, "store_m4")
    os.makedirs(store, exist_ok=True)
    for f in os.listdir(store):
        os.remove(os.path.join(store, f))
    rom = chip8.assemble(open(os.path.join(root, "games", "chip8", "snake.c8")).read(), "snake")
    open(os.path.join(store, "SNKOTA.c8"), "wb").write(rom)
    fresh_log()
    GRAPH, ENTER, CLEAR = S.GRAPH, S.ENTER, S.CLEAR
    tap = S.tap
    ev = tap(1000, GRAPH) + tap(1400, kc(19)) + tap(2200, kc(34)) + ["6000:snap:list"] + tap(6200, kc(34)) + tap(7200, ENTER)
    ev += tap(7800, GRAPH) + tap(8200, kc(19)) + tap(8800, kc(26)) + tap(9600, kc(34)) + tap(10400, ENTER) + ["12000:snap:run"] + tap(12200, CLEAR)
    d = S.run("m4ota", 13000, ev, dict(ESP, HZ_STORE_DIR=store, HZ_ROM="20:0", HZ_ROMLEN="16"))
    lg = esp_log()
    entry = [int(x, 16) for x in [l for l in d["raw"].splitlines() if l.startswith("ROMDUMP")][0].split(":")[2].split()]
    check("the ESP32 lists the CHIP-8 game with its type marker and serves it", "request cmd=$04 len=1" in lg and "request cmd=$04 len=7" in lg)
    check("installed as package type 2 (CHIP-8) in the flash directory: SNKOTA, length %d" % len(rom),
          bytes(entry[:6]) == b"SNKOTA" and entry[11] | entry[12] << 8 == len(rom) and entry[13] == 2, "(%s, type %d)" % (bytes(entry[:8]), entry[13]))
    lit_run = d["snaps"]["run"]["lit"]
    check("ENTER on the installed package runs it in the CHIP-8 interpreter (snake drawn)", 20 < lit_run < 400, "(lit=%d)" % lit_run)
    S.png("m4ota_run", 4)


if __name__ == "__main__":
    run()
    n = sum(S.results)
    print("RESULT: %d/%d milestone 4 checks passed" % (n, len(S.results)))
    sys.exit(0 if n == len(S.results) else 1)
