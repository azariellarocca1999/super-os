#!/usr/bin/env python3
"""Super-OS PC simulator: TI-83 Plus SE (Tilem core, 15 MHz) + virtual ESP32-S3 on the SuperLink line.

  python pc-simulator/simulator.py [--rom build/superos.rom] [--no-esp] [--online]

* The LCD is shown at 6x; the keypad can be clicked or typed (arrows, Enter = ENTER, Esc = CLEAR,
  Backspace = DEL, F1..F5 = Y= WINDOW ZOOM TRACE GRAPH, F6 = MODE, Shift = 2ND, Tab = ALPHA, O = ON).
* The virtual ESP32 runs the same SuperLink protocol (wake pulse, ESP_READY, frames, CMD_SLEEP).
  --online lets it call the real DeepSeek API (DEEPSEEK_API_KEY or the key typed in WIFI+API).
* Everything needs only Python's standard library (tkinter).
"""
import argparse
import os
import subprocess
import sys
import threading
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM = os.path.join(ROOT, "tools", "bin", "hz80_sim.exe")
SCALE = 6
BG, FG = "#b0bea0", "#1c2418"

# key code (row*8+bit+1) layout in TI-83 Plus arrangement
K = dict(YEQ=53, WINDOW=52, ZOOM=51, TRACE=50, GRAPH=49, SND=54, MODE=55, DEL=56, ALPHA=48, X=40, STAT=32,
         MATH=47, APPS=39, PRGM=31, VARS=23, CLEAR=15, INV=46, SIN=38, COS=30, TAN=22, POW=14, SQ=45, COMMA=37,
         LPAR=29, RPAR=21, DIV=13, LOG=44, N7=36, N8=28, N9=20, MUL=12, LN=43, N4=35, N5=27, N6=19, SUB=11,
         STO=42, N1=34, N2=26, N3=18, ADD=10, ON=0, N0=33, DOT=25, NEG=17, ENTER=9, DOWN=1, LEFT=2, RIGHT=3, UP=4)
LAYOUT = [
    [("Y=", "YEQ"), ("WINDOW", "WINDOW"), ("ZOOM", "ZOOM"), ("TRACE", "TRACE"), ("GRAPH", "GRAPH")],
    [("2ND", "SND"), ("MODE", "MODE"), ("DEL", "DEL"), ("<", "LEFT"), ("^", "UP"), ("v", "DOWN"), (">", "RIGHT")],
    [("ALPHA", "ALPHA"), ("X", "X"), ("STAT", "STAT")],
    [("MATH", "MATH"), ("APPS", "APPS"), ("PRGM", "PRGM"), ("VARS", "VARS"), ("CLEAR", "CLEAR")],
    [("x^-1", "INV"), ("SIN", "SIN"), ("COS", "COS"), ("TAN", "TAN"), ("^", "POW")],
    [("x2", "SQ"), (",", "COMMA"), ("(", "LPAR"), (")", "RPAR"), ("/", "DIV")],
    [("LOG", "LOG"), ("7", "N7"), ("8", "N8"), ("9", "N9"), ("*", "MUL")],
    [("LN", "LN"), ("4", "N4"), ("5", "N5"), ("6", "N6"), ("-", "SUB")],
    [("STO", "STO"), ("1", "N1"), ("2", "N2"), ("3", "N3"), ("+", "ADD")],
    [("ON", "ON"), ("0", "N0"), (".", "DOT"), ("(-)", "NEG"), ("ENTER", "ENTER")],
]
PCKEYS = {"Up": "UP", "Down": "DOWN", "Left": "LEFT", "Right": "RIGHT", "Return": "ENTER", "Escape": "CLEAR",
          "BackSpace": "DEL", "F1": "YEQ", "F2": "WINDOW", "F3": "ZOOM", "F4": "TRACE", "F5": "GRAPH", "F6": "MODE",
          "Shift_L": "SND", "Shift_R": "SND", "Tab": "ALPHA", "o": "ON", "plus": "ADD", "minus": "SUB", "asterisk": "MUL",
          "slash": "DIV", "asciicircum": "POW", "parenleft": "LPAR", "parenright": "RPAR", "period": "DOT", "comma": "COMMA",
          "m": "MATH", "a": "MATH", "s": "SIN", "c": "COS", "t": "TAN", "l": "LN", "g": "LOG", "x": "X"}
for d in range(10):
    PCKEYS[str(d)] = "N%d" % d


def rowbit(name):
    c = K[name]
    return "-1.0" if name == "ON" else "%d.%d" % ((c - 1) // 8, (c - 1) % 8)


class App:
    def __init__(self, root, args):
        self.root = root
        root.title("Super-OS simulator - TI-83 Plus SE")
        root.configure(bg="#2b2b2b")
        env = dict(os.environ)
        if not args.no_esp:
            env["HZ_BRIDGE"] = "%s %s" % (sys.executable, os.path.join(ROOT, "bridge_pc", "virtual_esp.py"))
            env["HZ_LINKMODE"] = "line"
            if not args.online:
                env["HZ_OFFLINE"] = "1"
        self.proc = subprocess.Popen([SIM, "--live", args.rom], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env, bufsize=0)
        self.img = tk.PhotoImage(width=96, height=64)
        self.lcd = tk.Label(root, image=self.img, bd=8, relief="sunken", bg=BG)
        self.lcd.pack(padx=10, pady=10)
        self.stat = tk.Label(root, text="booting...", fg="#9fe", bg="#2b2b2b", font=("Consolas", 9))
        self.stat.pack()
        self.log = tk.Text(root, height=5, width=64, bg="#1b1b1b", fg="#9c9", font=("Consolas", 8))
        self.log.pack(padx=8, pady=4)
        pad = tk.Frame(root, bg="#2b2b2b")
        pad.pack(pady=6)
        for r, row in enumerate(LAYOUT):
            for c, (label, key) in enumerate(row):
                b = tk.Button(pad, text=label, width=6, height=1, bg="#444", fg="white", activebackground="#666")
                b.grid(row=r, column=c, padx=1, pady=1)
                b.bind("<ButtonPress-1>", lambda e, k=key: self.send("D", k))
                b.bind("<ButtonRelease-1>", lambda e, k=key: self.send("U", k))
        self.down = {}
        root.bind("<KeyPress>", self.kd)
        root.bind("<KeyRelease>", self.ku)
        root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.reader, daemon=True).start()
        threading.Thread(target=self.err_reader, daemon=True).start()
        self.frame = None
        self.nframes = 0
        self.poll()

    def send(self, d, key):
        try:
            self.proc.stdin.write(("%s %s\n" % (d, rowbit(key))).encode())
        except OSError:
            pass

    def kd(self, e):
        k = PCKEYS.get(e.keysym)
        if not k:
            return
        if k in self.down:                      # auto-repeat: cancel the pending release
            self.root.after_cancel(self.down[k])
            self.down[k] = None
            self.down.pop(k)
            self.down[k] = self.root.after(60, lambda: self.release(k))
            return
        self.send("D", k)
        self.down[k] = self.root.after(10 ** 7, lambda: None)

    def ku(self, e):
        k = PCKEYS.get(e.keysym)
        if k in self.down:
            self.root.after_cancel(self.down[k])
            self.down[k] = self.root.after(30, lambda: self.release(k))

    def release(self, k):
        self.down.pop(k, None)
        self.send("U", k)

    def reader(self):
        for line in iter(self.proc.stdout.readline, b""):
            s = line.decode(errors="replace").strip()
            if s.startswith("F "):
                self.frame = s[2:]
            elif s.startswith("S "):
                p = s.split()
                self.status = "t=%.1fs  halted %s%%  CPU %s kHz" % (int(p[1]) / 1000, p[2], p[3])

    def err_reader(self):
        for line in iter(self.proc.stderr.readline, b""):
            self.root.after(0, lambda t=line.decode(errors="replace"): (self.log.insert("end", t), self.log.see("end")))

    def poll(self):
        if self.frame:
            raw = bytes.fromhex(self.frame)
            self.frame = None
            self.nframes += 1
            rows = []
            for y in range(64):
                row = []
                for x in range(96):
                    on = (raw[y * 12 + x // 8] >> (7 - x % 8)) & 1
                    row.append(FG if on else BG)
                rows.append("{" + " ".join(row) + "}")
            small = tk.PhotoImage(width=96, height=64)
            small.put(" ".join(rows))
            self.img = small.zoom(SCALE, SCALE)
            self.lcd.configure(image=self.img)
        if hasattr(self, "status"):
            self.stat.configure(text=self.status)
        self.root.after(30, self.poll)

    def close(self):
        try:
            self.proc.stdin.write(b"Q\n")
        except OSError:
            pass
        self.proc.kill()
        self.root.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(ROOT, "build", "superos.rom"))
    ap.add_argument("--no-esp", action="store_true", help="do not attach the virtual ESP32")
    ap.add_argument("--exit-after", type=float, default=0, help="smoke test: exit after N seconds")
    ap.add_argument("--online", action="store_true", help="virtual ESP calls the real DeepSeek API")
    a = ap.parse_args()
    if not os.path.exists(SIM):
        sys.exit("hz80_sim.exe missing: run scripts\\1_install_toolchains.ps1")
    r = tk.Tk()
    app = App(r, a)
    if a.exit_after:
        def done():
            print("frames=%d status=%s" % (app.nframes, getattr(app, "status", "?")))
            app.close()
        r.after(int(a.exit_after * 1000), done)
    r.mainloop()


if __name__ == "__main__":
    main()
