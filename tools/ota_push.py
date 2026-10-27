#!/usr/bin/env python3
"""Push a Z80 program to the ESP32's OTA store (real firmware or the PC simulator's virtual ESP32).

  python tools/ota_push.py build/mygame.bin --name MYGAME --host 192.168.1.50 [--port 80]
  python tools/ota_push.py build/demo.bin --name HELLO --host 127.0.0.1 --port 8266     (simulator)

  --kind bin    (default) Z80 program, <= 5200 bytes, runs on the calculator
  --kind game   CHIP-8 game run by the calculator's own interpreter (<= 3584 bytes); a .c8 assembly source (tools/chip8.py syntax)
                or a binary .ch8 ROM.  Appears in OTA > PC PACKAGES / INSTALLED; ENTER plays it.
  --kind gb     Game Boy ROM kept on the ESP32 (<= 1.5 MB), listed under GAMES > STREAM 3D and played through Peanut-GB
  --kind ch8    CHIP-8 ROM kept on the ESP32, streamed

On the calculator: SYS tab > OTA > "4 RECEIVE FROM PC" opens the upload window (120 s), then
"1 PC PACKAGES" lists, downloads and installs the package into the flash store; "2 INSTALLED" runs it.
Programs are raw images loaded at userMem ($9D95) -- same format as the demo (Ion-style header optional).
"""
import argparse
import os
import sys
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--name", help="package name, <= 8 chars A-Z 0-9 _ (default: file name)")
    ap.add_argument("--host", default="superos-esp.local")
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--kind", choices=("bin", "game", "gb", "ch8"), default="bin")
    a = ap.parse_args()
    name = (a.name or os.path.splitext(os.path.basename(a.file))[0]).upper()
    if not (1 <= len(name) <= 8 and all(c.isalnum() or c == "_" for c in name)):
        sys.exit("package name must be 1-8 chars of A-Z, 0-9, _")
    data = open(a.file, "rb").read()
    if a.file.lower().endswith(".c8") and a.kind in ("game", "ch8"):           # CHIP-8 assembly source
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import chip8
        data = chip8.assemble(data.decode(), a.file)
    limit = {"bin": 5200, "game": 3584, "ch8": 3584, "gb": 1_500_000}[a.kind]
    if len(data) > limit:
        sys.exit("%s package is %d bytes: the limit is %d" % (a.kind, len(data), limit))
    req = urllib.request.Request("http://%s:%d/upload?name=%s&kind=%s" % (a.host, a.port, name, a.kind), data, {"Content-Type": "application/octet-stream"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        print(r.read().decode().strip(), "->", name, len(data), "bytes")


if __name__ == "__main__":
    main()
