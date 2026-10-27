#!/bin/sh
# Host build + run of the worker-job ownership test: sh esp32-firmware/test_host/build_jobs_test.sh
cd "$(dirname "$0")/../.."
if ! command -v g++ >/dev/null 2>&1; then
  for d in "$LOCALAPPDATA"/Microsoft/WinGet/Packages/BrechtSanders.WinLibs*/mingw64/bin /c/Users/*/AppData/Local/Microsoft/WinGet/Packages/BrechtSanders.WinLibs*/mingw64/bin; do
    [ -d "$d" ] && PATH="$d:$PATH"
  done
fi
g++ -std=c++17 -O2 -Wall -pthread -o tools/bin/jobs_test.exe esp32-firmware/test_host/jobs_test.cpp && tools/bin/jobs_test.exe
