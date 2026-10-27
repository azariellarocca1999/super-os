# Super-OS  --  1_install_toolchains.ps1
# Downloads and builds every tool the project needs into tools\bin (portable, nothing is installed
# system-wide except the optional GCC and the Python packages):
#   spasm-ng (Z80 assembler), zx0 / dzx0 (compressor), rabbitsign + mktiupgrade (signed .8xu),
#   hz80_sim (headless TI-83+SE emulator based on Tilem's core), PlatformIO (ESP32-S3 firmware).
# Run from PowerShell (NOT from Git-Bash/MSYS: PlatformIO refuses MSYS):   .\scripts\1_install_toolchains.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$src = Join-Path $root "tools\src"
$bin = Join-Path $root "tools\bin"
New-Item -ItemType Directory -Force $src, $bin | Out-Null

function Step($m) { Write-Host "== $m" -ForegroundColor Cyan }

# ---- 1. C compiler (WinLibs GCC through winget when there is none) --------------------------------------
Step "C compiler"
function Find-Gcc {
    $p = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter "BrechtSanders*" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p) { return (Join-Path $p.FullName "mingw64\bin") }
    $g = Get-Command gcc.exe -ErrorAction SilentlyContinue
    if ($g) { return (Split-Path $g.Source) }
    return $null
}
$gccdir = Find-Gcc
if (-not $gccdir) {
    winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT --accept-package-agreements --accept-source-agreements --silent
    $gccdir = Find-Gcc
}
if (-not $gccdir) { throw "GCC not found; install WinLibs manually" }
$env:Path = "$gccdir;$env:Path"
Write-Host "gcc: $gccdir"

# ---- 2. Sources --------------------------------------------------------------------------------------------
Step "clone sources (shallow)"
$repos = @{
    "spasm-ng"   = "https://github.com/alberthdev/spasm-ng";
    "ZX0"        = "https://github.com/einar-saukas/ZX0";
    "tilem"      = "https://github.com/debrouxl/tilem";
    "rabbitsign" = "https://github.com/abbrev/rabbitsign";
    "mktiupgrade" = "https://github.com/KnightOS/mktiupgrade";
    "kernel"     = "https://github.com/KnightOS/kernel";
    "Peanut-GB"  = "https://github.com/deltabeard/Peanut-GB";
}
foreach ($k in $repos.Keys) {
    $d = Join-Path $src $k
    if (-not (Test-Path $d)) { git clone --depth 1 -q $repos[$k] $d }
}
python "$root\tools\patch_sources.py"

# ---- 3. Build ----------------------------------------------------------------------------------------------
Step "zx0 / dzx0"
$z = Join-Path $src "ZX0\src"
gcc -O2 -w -o "$bin\zx0.exe" "$z\zx0.c" "$z\optimize.c" "$z\compress.c" "$z\memory.c"
gcc -O2 -w -o "$bin\dzx0.exe" "$z\dzx0.c" "$z\memory.c"

Step "spasm-ng (assembler, app signing disabled)"
Push-Location (Join-Path $src "spasm-ng")
$env:FORCE_NO_GIT = "1"
cmd /c "mingw32-make -j8 NO_APPSIGN=1 >nul 2>&1"
if ($LASTEXITCODE) { throw "spasm-ng build failed" }
Copy-Item spasm.exe $bin -Force
Pop-Location

Step "rabbitsign"
$r = Join-Path $src "rabbitsign"
$rs = "app8x app9x apps autokey cmdline error graphlink header input keys mem os8x output output8x output9x program rabin rsa typestr md5 mpz rabbitsign" -split " " | ForEach-Object { "$r\src\$_.c" }
gcc -O2 -w -DHAVE_CONFIG_H -DPROTOTYPES "-I$r" "-I$r\src" @rs -o "$bin\rabbitsign.exe"

# periodic table data needs the `mendeleev` package once (the result is cached in tools\ptable_data.txt)
Step "mendeleev (periodic table data, one time)"
if (-not (Test-Path "$root\tools\ptable_data.txt")) { cmd /c "python -m pip install --quiet --disable-pip-version-check --target build\pydeps mendeleev >nul 2>&1" }

Step "mktiupgrade"
$m = Join-Path $src "mktiupgrade"
$ms = @("$m\main.c") + (Get-ChildItem "$m\upgrade\*.c").FullName + (Get-ChildItem "$m\crypto\*.c").FullName + (Get-ChildItem "$m\crypto\libtom\*.c").FullName
gcc -O2 -w "-I$m\upgrade" "-I$m\crypto" "-I$m\crypto\libtom" @ms -o "$bin\mktiupgrade.exe"
New-Item -ItemType Directory -Force "$root\tools\keys" | Out-Null
Copy-Item "$src\kernel\keys\04.key" "$root\tools\keys\" -Force
Copy-Item "$src\rabbitsign\keys\0104.key" "$root\tools\keys\" -Force

Step "hz80_sim (headless TI-83+SE emulator, Tilem core)"
$t = Join-Path $src "tilem"
$cs = (Get-ChildItem "$t\emu\*.c" | Where-Object { $_.Name -ne "audio.c" }).FullName + (Get-ChildItem "$t\emu\x*\*.c").FullName + "$root\pc-simulator\hz80_sim.c"
gcc -O2 -w -DHAVE_CONFIG_H "-I$t" "-I$t\emu" @cs -o "$bin\hz80_sim.exe"

Step "cas_cli (Super-CAS host build: tests and virtual ESP32)"
$cas = Join-Path $root "esp32-firmware\lib\supercas"
g++ -std=c++17 -O2 -w -o "$bin\cas_cli.exe" "$root\cas\cas_cli.cpp" @((Get-ChildItem "$cas\cas_*.cpp").FullName)

# ---- 4. ESP32 toolchain ----------------------------------------------------------------------------------------
Step "PlatformIO + pyserial"
cmd /c "python -m pip install --quiet --disable-pip-version-check platformio pyserial >nul 2>&1"

Step "done"
Get-ChildItem $bin | Select-Object Name, Length | Format-Table -AutoSize
