#!/bin/sh
# Host build of the streamed-games engine: sh games/host/build_play.sh   -> tools/bin/play_cli.exe
cd "$(dirname "$0")/../.."
if ! command -v g++ >/dev/null 2>&1; then
  for d in "$LOCALAPPDATA"/Microsoft/WinGet/Packages/BrechtSanders.WinLibs*/mingw64/bin /c/Users/*/AppData/Local/Microsoft/WinGet/Packages/BrechtSanders.WinLibs*/mingw64/bin; do
    [ -d "$d" ] && PATH="$d:$PATH"
  done
fi
L=esp32-firmware/lib/superplay
g++ -std=c++17 -O2 -Wall -Wno-unused-function -I$L -o tools/bin/play_cli.exe games/host/play_cli.cpp $L/frame.cpp $L/raycast.cpp $L/chip8.cpp $L/gbcore.cpp
