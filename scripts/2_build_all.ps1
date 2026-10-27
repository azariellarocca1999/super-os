# Super-OS  --  2_build_all.ps1
# Builds everything: assets (ZX0), Z80 OS pages, 2 MB dev ROM, signed .8xu upgrade, ESP32-S3 firmware (.bin).
#   .\scripts\2_build_all.ps1                 build all
#   .\scripts\2_build_all.ps1 -Test           ... and run the float-library tests, the Super-CAS tests and the emulator self-test
#   .\scripts\2_build_all.ps1 -NoFirmware     skip the (slow) ESP32 build
# Run from PowerShell (not Git-Bash).  Needs scripts\1_install_toolchains.ps1 to have run once.
param([switch]$Test, [switch]$NoFirmware)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Remove-Item Env:MSYSTEM -ErrorAction SilentlyContinue

Write-Host "== Z80 OS: assets + pages + ROM + signed .8xu" -ForegroundColor Cyan
python tools\build.py
if ($LASTEXITCODE) { throw "OS build failed" }
python tools\verify_8xu.py
if ($LASTEXITCODE) { throw "the signed .8xu failed its structure checks" }

if (-not $NoFirmware) {
    Write-Host "== ESP32-S3 firmware (PlatformIO)" -ForegroundColor Cyan
    cmd /c "python -m platformio run -d esp32-firmware -e esp32s3zero > build\pio_build.log 2>&1"
    if ($LASTEXITCODE) { Get-Content build\pio_build.log -Tail 30; throw "firmware build failed (see build\pio_build.log)" }
    New-Item -ItemType Directory -Force dist | Out-Null
    Copy-Item esp32-firmware\.pio\build\esp32s3zero\firmware.bin dist\esp32s3zero_firmware.bin -Force
    Select-String -Path build\pio_build.log -Pattern "RAM:|Flash:" | ForEach-Object { $_.Line }
}

if ($Test) {
    Write-Host "== Streamed-games engine (host build) + CHIP-8 tests" -ForegroundColor Cyan
    # `sh` is not on the PowerShell PATH (and `bash` there is WSL's): use Git's POSIX shell explicitly
    $sh = @("C:\Program Files\Git\bin\sh.exe", "C:\Program Files\Git\usr\bin\sh.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $sh) { $sh = (Get-Command sh -ErrorAction SilentlyContinue).Source }
    if (-not $sh) { throw "no POSIX sh found (install Git for Windows)" }
    & $sh games/host/build_play.sh
    if ($LASTEXITCODE) { throw "games engine host build failed" }
    python games\host\play_tests.py
    if ($LASTEXITCODE) { throw "games engine tests failed" }
    & $sh esp32-firmware/test_host/build_jobs_test.sh
    if ($LASTEXITCODE) { throw "ESP32 job ownership host test failed" }
    python tools\c8test.py
    if ($LASTEXITCODE) { throw "CHIP-8 interpreter tests failed" }
    python tools\c8games_test.py
    if ($LASTEXITCODE) { throw "CHIP-8 game tests failed" }
    Write-Host "== Z80 float library vs Python (mathtest)" -ForegroundColor Cyan
    python tools\mathtest.py
    if ($LASTEXITCODE) { throw "math library tests failed" }
    Write-Host "== Super-CAS host tests" -ForegroundColor Cyan
    python cas\cas_tests.py
    if ($LASTEXITCODE) { throw "CAS tests failed" }
    Write-Host "== emulator self-test" -ForegroundColor Cyan
    python tools\selftest.py
    if ($LASTEXITCODE) { throw "self-test failed" }
}
Write-Host "done. dist\: superos.rom (emulator), SuperOS.8xu (signed OS upgrade), esp32s3zero_firmware.bin, see docs\INSTALL.md for the install steps. Test plan: docs\HARDWARE_TEST.md" -ForegroundColor Green
