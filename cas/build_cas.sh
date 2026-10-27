#!/bin/sh
# Host build of the Super-CAS command line tool (needs g++, e.g. WinLibs from winget): sh cas/build_cas.sh
cd "$(dirname "$0")/.."
mkdir -p build
if ! command -v g++ >/dev/null 2>&1; then
  for d in "$LOCALAPPDATA"/Microsoft/WinGet/Packages/BrechtSanders.WinLibs*/mingw64/bin /c/Users/*/AppData/Local/Microsoft/WinGet/Packages/BrechtSanders.WinLibs*/mingw64/bin; do
    [ -d "$d" ] && PATH="$d:$PATH"
  done
fi
g++ -std=c++17 -O2 $CAS_FLAGS -Wall -Wno-unused-function -Wno-unused-variable -Wno-array-bounds -Wno-stringop-overflow -o tools/bin/cas_cli.exe cas/cas_cli.cpp esp32-firmware/lib/supercas/cas_*.cpp || exit 1
