#!/bin/sh
# Host build + run of the firmware ZX0 packer test: sh esp32-firmware/test_host/build_zx0_test.sh
cd "$(dirname "$0")/../.."
if ! command -v gcc >/dev/null 2>&1; then
  for d in "$LOCALAPPDATA"/Microsoft/WinGet/Packages/BrechtSanders.WinLibs*/mingw64/bin /c/Users/*/AppData/Local/Microsoft/WinGet/Packages/BrechtSanders.WinLibs*/mingw64/bin; do
    [ -d "$d" ] && PATH="$d:$PATH"
  done
fi
Z=esp32-firmware/lib/zx0
gcc -O1 -Wall -I$Z -o tools/bin/zx0_test.exe esp32-firmware/test_host/zx0_test.c $Z/zx0_pack.c $Z/optimize.c $Z/compress.c $Z/memory.c && tools/bin/zx0_test.exe
