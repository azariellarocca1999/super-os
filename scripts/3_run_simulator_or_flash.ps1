# Super-OS  --  3_run_simulator_or_flash.ps1
#   .\scripts\3_run_simulator_or_flash.ps1                    open the PC simulator (calculator + virtual ESP32)
#   .\scripts\3_run_simulator_or_flash.ps1 -Online            ... virtual ESP32 talks to the real DeepSeek API
#   .\scripts\3_run_simulator_or_flash.ps1 -Mode Test         run the automated self-test
#   .\scripts\3_run_simulator_or_flash.ps1 -Mode FlashEsp     upload the firmware to the ESP32-S3-Zero (USB-C)
#   .\scripts\3_run_simulator_or_flash.ps1 -Mode FlashCalc    send SuperOS.8xu with the TI-Graph Link USB (SilverLink) cable
param([ValidateSet("Sim", "Test", "FlashEsp", "FlashCalc")][string]$Mode = "Sim", [switch]$Online)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Remove-Item Env:MSYSTEM -ErrorAction SilentlyContinue

switch ($Mode) {
    "Sim" {
        if (-not (Test-Path build\superos.rom)) { & "$PSScriptRoot\2_build_all.ps1" -NoFirmware }
        $a = @("pc-simulator\simulator.py")
        if ($Online) { $a += "--online" }
        python @a
    }
    "Test" { python tools\selftest.py }
    "FlashEsp" {
        Write-Host "Connect the ESP32-S3-Zero by USB-C (hold BOOT while plugging if it is not detected)." -ForegroundColor Yellow
        cmd /c "python -m platformio run -d esp32-firmware -e esp32s3zero -t upload"
    }
    "FlashCalc" {
        Write-Host "REAL HARDWARE: this sends a new OS to the calculator. The factory boot code stays intact, but the" -ForegroundColor Yellow
        Write-Host "upgrade is UNTESTED on a physical unit. Read docs\STATUS.md first and keep a TI OS file at hand." -ForegroundColor Yellow
        $tilp = Get-Command tilp.exe -ErrorAction SilentlyContinue
        if ($tilp) {
            & $tilp.Source --calc=ti83p --cable=SilverLink dist\SuperOS.8xu
        } else {
            Write-Host "TiLP/TI Connect not found in PATH. Send dist\SuperOS.8xu manually with TI Connect CE or TiLP" -ForegroundColor Yellow
            Write-Host "(TI-83 Plus Silver Edition -> OS transfer)." -ForegroundColor Yellow
        }
    }
}
