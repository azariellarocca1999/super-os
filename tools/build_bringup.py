"""Build dist/SuperOS_bringup.8xu: the normal OS plus a contrast sweep right at boot (BRINGUP_SWEEP=1), for a unit that installs fine but shows nothing.
Every build already draws the boot progress bar (stages 1-9, see crumb_ns in z80-os/kernel/page0.z80); the sweep additionally cycles the LCD contrast
for a few seconds so that "blank screen" can be told apart from "contrast out of range".  The normal build is rebuilt afterwards."""
import os
import shutil
import subprocess
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)


def build(sweep):
    open("build/bringup.inc", "w").write("#define BRINGUP_SWEEP %d\n" % sweep)
    r = subprocess.run([sys.executable, "tools/build.py"], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        sys.exit("build failed")


build(1)
shutil.copy("build/SuperOS.8xu", "dist/SuperOS_bringup.8xu")
print("dist/SuperOS_bringup.8xu written (contrast sweep at boot)")
build(0)
print("normal build restored")
