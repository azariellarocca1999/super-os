# Super-OS  --  make_release.ps1
# Builds everything, runs the whole test battery, builds the bring-up variant and gathers the release files in release\.
#   .\scripts\make_release.ps1                 build + test + collect
#   .\scripts\make_release.ps1 -SkipTests      skip the test battery (not for a real release)
param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Remove-Item Env:MSYSTEM -ErrorAction SilentlyContinue

if ($SkipTests) { .\scripts\2_build_all.ps1 } else { .\scripts\2_build_all.ps1 -Test }
if ($LASTEXITCODE) { throw "build / tests failed: no release" }

python tools\build_bringup.py                     # dist\SuperOS_bringup.8xu (contrast sweep + boot progress bar), then the normal build again
if ($LASTEXITCODE) { throw "bring-up variant failed" }
python tools\verify_8xu.py dist\SuperOS.8xu
if ($LASTEXITCODE) { throw "dist\SuperOS.8xu failed its checks" }
python tools\verify_8xu.py dist\SuperOS_bringup.8xu --rom none        # every check except the byte compare with the (normal) dev ROM
if ($LASTEXITCODE) { throw "dist\SuperOS_bringup.8xu failed its checks (structure, signature, record layout)" }

New-Item -ItemType Directory -Force release | Out-Null
Copy-Item dist\SuperOS.8xu, dist\SuperOS_bringup.8xu, dist\esp32s3zero_firmware.bin release\ -Force
Copy-Item docs\INSTALL.md release\INSTALL.md -Force
Copy-Item dist\LEEME.txt release\LEEME.txt -Force
Get-ChildItem release | ForEach-Object { "{0}  {1,9:N0} bytes  sha256 {2}" -f $_.Name, $_.Length, (Get-FileHash $_.FullName -Algorithm SHA256).Hash.Substring(0, 16) }
Write-Host "release\ ready. Upload with: gh release create vX.Y.Z release\* --prerelease" -ForegroundColor Green
