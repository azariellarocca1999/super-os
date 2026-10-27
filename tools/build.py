#!/usr/bin/env python3
"""Super-OS build: assets -> assemble every page -> ROM -> signed .8xu.  Used by scripts/2_build_all.ps1."""
import os
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)
bin_ = os.path.join(root, "tools", "bin")
spasm = os.path.join(bin_, "spasm.exe")
os.makedirs("build", exist_ok=True)
os.makedirs("dist", exist_ok=True)


def run(args, quiet=True):
    r = subprocess.run(args, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode or "error" in out.lower():
        print(out)
        sys.exit("FAILED: " + " ".join(args))
    return out


def asm(src, dst):
    # fix_jr turns any out-of-range JR into JP (editing the source) and re-assembles
    out = run([sys.executable, "tools/fix_jr.py", "-I", "z80-os", "-I", "build", src, dst])
    return out


def main():
    for name, default in (("autogame.inc", "#define AUTOGAME 0\n"), ("bringup.inc", "#define BRINGUP_SWEEP 0\n")):    # build switches: see build_bringup.py / tests
        if not os.path.exists(os.path.join("build", name)):
            open(os.path.join("build", name), "w").write(default)
    run([sys.executable, "tools/check_labels.py"])        # duplicated names are silent in spasm and send jumps to the wrong place
    run([sys.executable, "tools/gen_sys.py"])
    run([sys.executable, "tools/gen_strings.py"]) if os.path.exists("tools/gen_strings.py") else None
    for g in ("gen_mathjt", "gen_calckeys", "gen_mstrings"):
        run([sys.executable, "tools/%s.py" % g])
    run([sys.executable, "tools/fxlib.py", "build/consts.inc"])
    run([sys.executable, "tools/gen_units.py"])
    run([sys.executable, "tools/gen_ptable.py"])
    run([sys.executable, "tools/gen_pstrings.py"])
    run([sys.executable, "tools/gen_c8.py"])
    asm("z80-os/compat/demo_ti.z80", "build/demo.bin")
    print(run([sys.executable, "tools/mkpage2.py"]).rstrip())
    for src, dst in (("z80-os/kernel/page0.z80", "build/page0.bin"), ("z80-os/ui/page1.z80", "build/page1.bin"),
                     ("z80-os/math/page3.z80", "build/pagex03.bin"), ("z80-os/apps/page4.z80", "build/pagex04.bin"), ("z80-os/games/page5.z80", "build/pagex05.bin"),
                     ("tools/devboot.z80", "build/devboot.bin"), ("tools/flashunlock.z80", "build/flashunlock.bin")):
        out = asm(src, dst)
    print(run([sys.executable, "tools/mkrom.py"]).rstrip())
    # signed OS upgrade with key 04 (the OS key: the official TI OS and KnightOS verify against it; 0104 is the APP key and the
    # boot code of a real TI-83+SE rejects an OS signed with it).  mktiupgrade prints a harmless "not signed" warning for the
    # intermediate file; rabbitsign then signs it.
    subprocess.run([os.path.join(bin_, "mktiupgrade.exe"), "-d", "TI-83+SE", "-n", "04", "build/superos.rom",
                    "build/os_unsigned.8xu", "00", "01", "02", "03", "04", "05", "06", "7C"], capture_output=True)
    run([os.path.join(bin_, "rabbitsign.exe"), "-r", "-t", "8xu", "-k", os.path.join(root, "tools", "keys", "04.key"),
         "-o", "build/SuperOS.8xu", "build/os_unsigned.8xu"])
    run([sys.executable, "tools/fix_8xu_tail.py", "build/SuperOS.8xu"])      # signature records laid out like TI's / KnightOS' files
    import shutil
    shutil.copy("build/superos.rom", "dist/superos.rom")
    shutil.copy("build/SuperOS.8xu", "dist/SuperOS.8xu")
    print("build OK -> dist/superos.rom (emulator), dist/SuperOS.8xu (signed upgrade, UNTESTED on hardware)")


if __name__ == "__main__":
    main()
