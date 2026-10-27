"""Super-OS bridge services: AI (DeepSeek), WiFi bookkeeping, time, store/books.

Used by the PC simulator of the ESP32-S3 (virtual_esp.py) and by bridge_server.py (USB adapter mode).
The real ESP32-S3 firmware (esp32-firmware/) implements the same commands in C++.
"""
import datetime
import http.server
import threading
import urllib.parse
import json
import os
import subprocess
import tempfile
import unicodedata
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZX0 = os.path.join(ROOT, "tools", "bin", "zx0.exe")

SL_SYNC = 0x53
CMD_PING, CMD_CHAT, CMD_WIKI, CMD_STORE, CMD_BOOK, CMD_WEATHER = 1, 2, 3, 4, 5, 6
CMD_WIFI_SCAN, CMD_WIFI_SET, CMD_STATUS, CMD_TIME, CMD_API_SET = 0x10, 0x11, 0x12, 0x13, 0x14
CMD_DIAG, CMD_BENCH, CMD_OTA = 0x15, 0x16, 0x20
CMD_CAS, CMD_PLOT3D, CMD_GAME, CMD_TURBO = 0x30, 0x31, 0x32, 0x33
CMD_SLEEP = 0xFF
RSP_MORE, RSP_LAST, RSP_ERR, RSP_NOTIFY = 0x80, 0x81, 0x82, 0x90
ACK, NACK = 0x06, 0x15
CHUNK = 240

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODELS = {0: "deepseek-chat", 1: "deepseek-reasoner"}
SYSTEM_PROMPT = ("You answer on a 96x64 monochrome calculator screen (24x10 characters). Plain ASCII only, no markdown, "
                 "no LaTeX: write powers as x^2, roots as sqrt(x), fractions as a/b. Be brief (under 500 characters). "
                 "For a plottable function add a final line [PLOT: expr, xmin, xmax].")


def crc8(data, crc=0):
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def frame(cmd, payload=b""):
    body = bytes([cmd, len(payload) & 0xFF, len(payload) >> 8]) + payload
    return bytes([SL_SYNC]) + body + bytes([crc8(body)])


def log(*a):
    print("[esp-sim]", *a, file=os.sys.stderr, flush=True)
    path = os.environ.get("HZ_BRIDGE_LOG")
    if path:
        with open(path, "a") as f:
            f.write(" ".join(str(x) for x in a) + "\n")


def zx0(data: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "i"), os.path.join(d, "o")
        open(src, "wb").write(data)
        subprocess.run([ZX0, "-f", src, dst], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return open(dst, "rb").read()


def ascii_clean(text: str) -> bytes:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.encode("ascii", "replace")


ROMS_DIR = os.environ.get("HZ_ROMS_DIR", os.path.join(ROOT, "games", "roms"))
STORE_DIR = os.environ.get("HZ_STORE_DIR", os.path.join(ROOT, "bridge_pc", "store"))
OTA_PORT = int(os.environ.get("HZ_OTA_PORT", "8266"))


def store_list():
    """OTA store: Z80 programs (NAME.bin, "NAME|bytes") and calculator-side CHIP-8 games (NAME.c8, "NAME|bytes|8")."""
    os.makedirs(STORE_DIR, exist_ok=True)
    lines = []
    for f in sorted(os.listdir(STORE_DIR)):
        stem, ext = os.path.splitext(f)
        size = os.path.getsize(os.path.join(STORE_DIR, f))
        if ext.lower() == ".bin":
            lines.append("%s|%d" % (stem.upper()[:8], size))
        elif ext.lower() == ".c8":
            lines.append("%s|%d|8" % (stem.upper()[:8], size))
    return "\n".join(lines) + ("\n" if lines else "")


def store_get(name):
    for ext in (".bin", ".c8"):
        path = os.path.join(STORE_DIR, os.path.basename(name) + ext)
        if os.path.exists(path):
            return open(path, "rb").read()
    return None


class _Upload(http.server.BaseHTTPRequestHandler):
    """PUT/POST /upload?name=NAME[&kind=bin|game|gb|ch8]  (raw body) -- same endpoint as the ESP32 firmware.
    bin = Z80 program, game = CHIP-8 game run by the calculator, gb / ch8 = ROM streamed by the ESP32 (games/roms)."""

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        name = (q.get("name") or [""])[0].upper()
        kind = (q.get("kind") or ["bin"])[0].lower()
        limits = {"bin": 5200, "game": 3584, "ch8": 3584, "gb": 1_500_000}
        n = int(self.headers.get("Content-Length", 0))
        if u.path != "/upload" or not name.isalnum() and "_" not in name or len(name) > 8 or kind not in limits or n == 0 or n > limits[kind]:
            self.send_response(400)
            self.end_headers()
            return
        data = self.rfile.read(n)
        if kind in ("bin", "game"):
            os.makedirs(STORE_DIR, exist_ok=True)
            path = os.path.join(STORE_DIR, name + (".bin" if kind == "bin" else ".c8"))
        else:
            os.makedirs(ROMS_DIR, exist_ok=True)
            path = os.path.join(ROMS_DIR, name + "." + kind)
        open(path, "wb").write(data)
        log("OTA upload received: %s (%d bytes) kind=%s" % (name, len(data), kind))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK\n")

    do_PUT = do_POST

    def log_message(self, *a):
        pass


_ota_server = None


def ota_start(seconds):
    global _ota_server
    if _ota_server is None:
        _ota_server = http.server.ThreadingHTTPServer(("127.0.0.1", OTA_PORT), _Upload)
        threading.Thread(target=_ota_server.serve_forever, daemon=True).start()
    log("OTA window open for %d s on port %d" % (seconds, OTA_PORT))
    return "UPLOAD WINDOW %d S\nHTTP://127.0.0.1:%d\nPOST /UPLOAD?NAME=XXXX\nTOOLS/OTA_PUSH.PY" % (seconds, OTA_PORT)


class State:
    """What the (virtual) ESP32 remembers: Wi-Fi credentials and the DeepSeek key (NVS on the real chip)."""

    def __init__(self):
        self.ssid = ""
        self.password = ""
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.rssi = 62
        self.rx_frames = 0
        self.tx_frames = 0
        self.crc_errors = 0
        self.boots = 0
        self.uptime_us = 0
        self.now_us = 0                  # emulated time of the request (set by the virtual ESP)
        self.turbo_req = None            # CMD_TURBO: applied by the link layer after the reply is acknowledged
        self.play = None                 # streamed-games engine (tools/bin/play_cli.exe), started on demand
        self.play_last_us = None
        self.frames_served = 0


def svc_chat(state: State, payload: bytes) -> str:
    model = MODELS.get(payload[0], "deepseek-chat") if payload else "deepseek-chat"
    text = payload[1:].decode("ascii", "replace")
    if os.environ.get("HZ_CHAT_REPLY"):                      # tests: fixed answer
        return os.environ["HZ_CHAT_REPLY"]
    if os.environ.get("HZ_OFFLINE") or not state.api_key:
        return "[offline %s] You said: %s" % ("R1" if model.endswith("reasoner") else "V3", text)
    body = json.dumps({"model": model, "max_tokens": 600, "messages": [
        {"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(DEEPSEEK_URL, body, {"Authorization": "Bearer " + state.api_key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001
        return "DeepSeek error: %s" % e


def svc_wifi_scan(state: State) -> str:
    return "HomeNet|-48\nCafe Libre|-67\nVecino 5G|-74\nOficina|-81"


def diag_report(state: State) -> str:
    return ("SUPER-OS ESP32 REPORT\nFW 0.2 (PC SIM)\nBOARD ESP32-S3-ZERO\nUPTIME %d S\nBOOTS %d  WAKE EXT0\n"
            "WIFI %s RSSI -%d\nAPI KEY %s\nLINES T:1 R:1 (IDLE HIGH)\nRX %d TX %d CRC ERR %d\nHEAP 212000 PSRAM 2.0M") % (
        state.uptime_us // 1_000_000, state.boots, state.ssid or "NOT SET", state.rssi, "SET" if state.api_key else "NOT SET",
        state.rx_frames, state.tx_frames, state.crc_errors)



WMO_ES = {0: "CIELO DESPEJADO", 1: "MAYORMENTE DESPEJADO", 2: "PARCIALMENTE NUBLADO", 3: "NUBLADO", 45: "NIEBLA", 48: "NIEBLA ESCARCHA",
          51: "LLOVIZNA LEVE", 53: "LLOVIZNA", 55: "LLOVIZNA FUERTE", 61: "LLUVIA LEVE", 63: "LLUVIA", 65: "LLUVIA FUERTE", 71: "NIEVE LEVE",
          73: "NIEVE", 75: "NIEVE FUERTE", 80: "CHUBASCOS", 81: "CHUBASCOS FUERTES", 82: "CHUBASCOS VIOLENTOS", 95: "TORMENTA", 96: "TORMENTA GRANIZO",
          99: "TORMENTA GRANIZO FUERTE"}
WMO_EN = {0: "CLEAR SKY", 1: "MAINLY CLEAR", 2: "PARTLY CLOUDY", 3: "OVERCAST", 45: "FOG", 48: "RIME FOG", 51: "LIGHT DRIZZLE", 53: "DRIZZLE",
          55: "HEAVY DRIZZLE", 61: "LIGHT RAIN", 63: "RAIN", 65: "HEAVY RAIN", 71: "LIGHT SNOW", 73: "SNOW", 75: "HEAVY SNOW", 80: "SHOWERS",
          81: "HEAVY SHOWERS", 82: "VIOLENT SHOWERS", 95: "THUNDERSTORM", 96: "THUNDERSTORM HAIL", 99: "SEVERE THUNDERSTORM HAIL"}


def http_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Super-OS/0.3 (TI-83 Plus SE co-processor)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def svc_wiki(state, payload: bytes) -> str:
    lang = "en" if payload[:1] == bytes([1]) else "es"
    q = payload[1:].decode("ascii", "replace").strip()
    if os.environ.get("HZ_OFFLINE") or not q:
        return "[offline wiki %s] %s" % (lang, q)
    try:
        hits = http_json("https://%s.wikipedia.org/w/rest.php/v1/search/title?q=%s&limit=1" % (lang, urllib.parse.quote(q)))
        pages = hits.get("pages", [])
        if not pages:
            return "NOT FOUND: " + q
        title = pages[0]["title"]
        d = http_json("https://%s.wikipedia.org/api/rest_v1/page/summary/%s" % (lang, urllib.parse.quote(title.replace(" ", "_"))))
        return (title + "\n" + d.get("extract", ""))[:3500]
    except Exception as e:  # noqa: BLE001
        return "Wikipedia error: %s" % e


def svc_weather(state, payload: bytes) -> str:
    lang = "en" if payload[:1] == bytes([1]) else "es"
    q = payload[1:].decode("ascii", "replace").strip()
    if os.environ.get("HZ_OFFLINE") or not q:
        return "[offline weather %s] %s" % (lang, q)
    try:
        g = http_json("https://geocoding-api.open-meteo.com/v1/search?name=%s&count=1&language=%s" % (urllib.parse.quote(q), lang))
        res = g.get("results")
        if not res:
            return "CITY NOT FOUND: " + q
        c = res[0]
        f = http_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
                      "precipitation,weather_code,wind_speed_10m&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto&forecast_days=3"
                      % (c["latitude"], c["longitude"]))
        wmo = WMO_EN if lang == "en" else WMO_ES
        cur, day = f["current"], f["daily"]
        L = []
        L.append("%s, %s" % (c.get("name", q), c.get("country", "")))
        L.append(("NOW" if lang == "en" else "AHORA") + " %.1fC (%s %.1fC)" % (cur["temperature_2m"], "FEELS" if lang == "en" else "SENS", cur["apparent_temperature"]))
        L.append(wmo.get(cur["weather_code"], "CODE %d" % cur["weather_code"]))
        L.append("%s %d%%  %s %.0f KM/H" % ("HUM" if lang == "es" else "HUM", cur["relative_humidity_2m"], "VIENTO" if lang == "es" else "WIND", cur["wind_speed_10m"]))
        names = ["HOY", "MAN", "PAS"] if lang == "es" else ["TODAY", "TOMORROW", "DAY 3"]
        for i in range(3):
            L.append("%s %.0f/%.0fC %s %.1fMM %s" % (names[i], day["temperature_2m_min"][i], day["temperature_2m_max"][i],
                                                    "LLUVIA" if lang == "es" else "RAIN", day["precipitation_sum"][i], wmo.get(day["weather_code"][i], "")))
        return "\n".join(L)
    except Exception as e:  # noqa: BLE001
        return "Weather error: %s" % e

CAS_CLI = os.path.join(ROOT, "tools", "bin", "cas_cli.exe")


def run_cas(text: str) -> str:
    """Super-CAS: the same C++ the ESP32 firmware runs, built for the PC (cas/build_cas.sh)."""
    if not os.path.exists(CAS_CLI):
        return "ERROR: tools/bin/cas_cli.exe is missing (sh cas/build_cas.sh)"
    line = " ".join(text.split("\n"))
    r = subprocess.run([CAS_CLI], input=(line + "\n").encode("ascii", "replace"), capture_output=True, timeout=60)
    out = r.stdout.decode("ascii", "replace").split("\n")[0]
    return out.replace("\x02", "\n") or "ERROR: no output"


def run_plot3d(text: str):
    """-> 768-byte bitmap or an error text"""
    if not os.path.exists(CAS_CLI):
        return "tools/bin/cas_cli.exe is missing"
    r = subprocess.run([CAS_CLI, "--plot3d"], input=(text + "\n").encode("ascii", "replace"), capture_output=True, timeout=60)
    if len(r.stdout) == 768:
        return r.stdout
    return r.stdout.decode("ascii", "replace").replace("ERR:", "") or "plot3d failed"



PLAY_CLI = os.path.join(ROOT, "tools", "bin", "play_cli.exe")


def raw_stream(data: bytes):
    """Reply that is NOT ZX0 compressed (game frames): RSP_MORE chunks and a final RSP_LAST."""
    out = []
    for i in range(0, len(data), CHUNK):
        last = i + CHUNK >= len(data)
        out.append((RSP_LAST if last else RSP_MORE, data[i:i + CHUNK]))
    return out or [(RSP_LAST, b"")]


def play_engine(state: State):
    if state.play is None or state.play.poll() is not None:
        state.play = subprocess.Popen([PLAY_CLI, ROMS_DIR], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    return state.play


def play_cmd(state: State, line: str):
    p = play_engine(state)
    p.stdin.write((line + "\n").encode())
    p.stdin.flush()
    return p


def svc_game(state: State, payload: bytes):
    """CMD_GAME [op]: 0 list titles, 1 start [index], 2 frame [keys_lo][keys_hi][flags], 3 stop."""
    if not os.path.exists(PLAY_CLI):
        return [(RSP_ERR, b"tools/bin/play_cli.exe is missing (sh games/host/build_play.sh)")]
    op = payload[0] if payload else 0
    if op == 0:
        p = play_cmd(state, "L")
        n = int(p.stdout.readline())
        names = [p.stdout.readline().decode().strip() for _ in range(n)]
        return raw_stream("\n".join(names).encode("ascii", "replace"))
    if op == 1:
        p = play_cmd(state, "S %d" % (payload[1] if len(payload) > 1 else 0))
        ok = p.stdout.readline().strip() == b"OK"
        state.play_last_us = None
        log("game started" if ok else "game start failed")
        return raw_stream(b"OK" if ok else b"ERR")
    if op == 2:
        keys = (payload[1] | payload[2] << 8) if len(payload) >= 3 else 0
        full = payload[3] & 1 if len(payload) >= 4 else 0
        dt = 100000 if state.play_last_us is None else max(1000, min(state.now_us - state.play_last_us, 250000))
        state.play_last_us = state.now_us
        p = play_cmd(state, "F %d %d %d" % (keys, dt, full))
        n = int.from_bytes(p.stdout.read(2), "little")
        data = p.stdout.read(n)
        state.frames_served += 1
        return raw_stream(data)
    if op == 3:
        play_cmd(state, "S -1")
        play_engine(state).stdout.readline()
        return raw_stream(b"OK")
    return [(RSP_ERR, b"bad game op")]


def handle(state: State, cmd: int, payload: bytes):
    """-> list of (frame_cmd, payload) to send back; an empty list = nothing but the ACK."""
    if cmd == CMD_PING:
        return stream("PONG " + payload.decode("ascii", "replace"))
    if cmd == CMD_CHAT:
        return stream(svc_chat(state, payload))
    if cmd == CMD_WIFI_SCAN:
        return stream(svc_wifi_scan(state))
    if cmd == CMD_WIFI_SET:
        ssid, _, pw = payload.partition(b"\0")
        state.ssid, state.password = ssid.decode("ascii", "replace"), pw.decode("ascii", "replace")
        log("wifi credentials stored: ssid=%r (%d char password)" % (state.ssid, len(state.password)))
        return stream("OK")
    if cmd == CMD_API_SET:
        state.api_key = payload.decode("ascii", "replace")
        log("api key stored (%d chars)" % len(state.api_key))
        return stream("OK")
    if cmd == CMD_STORE:
        op = payload[0] if payload else 0
        if op == 0:
            return stream(store_list())
        data = store_get(payload[1:].decode("ascii", "replace"))
        return stream(data) if data is not None else [(RSP_ERR, b"no such package")]
    if cmd == CMD_OTA:
        return stream(ota_start(payload[0] if payload else 120))
    if cmd == CMD_BENCH:
        n = (payload[0] | payload[1] << 8) if len(payload) >= 2 else 256
        x, out = 12345, bytearray()
        for _ in range(min(n, 4000)):
            x = (x * 1103515245 + 12345) & 0x7FFFFFFF
            out.append((x >> 16) & 0xFF)
        return stream(bytes(out))
    if cmd == CMD_DIAG:
        return stream(diag_report(state))
    if cmd == CMD_WIKI:
        return stream(svc_wiki(state, payload))
    if cmd == CMD_WEATHER:
        return stream(svc_weather(state, payload))
    if cmd == CMD_CAS:
        text = payload.decode("ascii", "replace")
        log("CAS command: %r" % text)
        return stream(run_cas(text))
    if cmd == CMD_PLOT3D:
        res = run_plot3d(payload.decode("ascii", "replace"))
        if isinstance(res, bytes):
            return stream(res)
        return [(RSP_ERR, res.encode("ascii", "replace")[:200])]
    if cmd == CMD_GAME:
        return svc_game(state, payload)
    if cmd == CMD_TURBO:
        state.turbo_req = bool(payload and payload[0])
        log("turbo %s requested" % ("ON" if state.turbo_req else "OFF"))
        return [(RSP_LAST, b"")]
    if cmd == CMD_STATUS:
        return [(CMD_STATUS, bytes([2, state.rssi])), (RSP_LAST, b"")]
    if cmd == CMD_TIME:
        now = datetime.datetime.now()
        return [(CMD_TIME, bytes([now.hour, now.minute])), (RSP_LAST, b"")]
    return [(RSP_ERR, b"bad command")]


def stream(text_or_bytes):
    data = text_or_bytes if isinstance(text_or_bytes, bytes) else ascii_clean(text_or_bytes)
    comp = zx0(data)
    log("reply %d bytes -> zx0 %d bytes" % (len(data), len(comp)))
    out = []
    for i in range(0, len(comp), CHUNK):
        last = i + CHUNK >= len(comp)
        out.append((RSP_LAST if last else RSP_MORE, comp[i:i + CHUNK]))
    return out or [(RSP_LAST, b"")]
