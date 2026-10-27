# Installing Super-OS on a TI-83 Plus Silver Edition

> **Read this whole page first.** Installing an operating system replaces the calculator's OS. The factory boot code (flash page `$7F`) is never touched by `SuperOS.8xu`, so you can always get back to the official OS, *but only if you prepare for it*. Nobody has tested this on any unit except one TI-83+ SE with **boot code 1.00 and OS 1.19**. Other boot code revisions are unknown.

## What you need

* A **TI-83 Plus Silver Edition** (the plain TI-83 Plus has a different flash layout and is **not** supported; the TI-84 Plus family is not supported either).
* A link cable that your PC can talk to (USB SilverLink / TI-Graph Link USB, or a serial cable) and TI's free **TI Connect** (its "OS downloader" sends `.8xu` files; **TiLP** works too).
* **Fresh batteries.** A flash write must not be interrupted.
* The **official TI-83 Plus OS** file (`TI83Plus_OS*.8Xu`, same file for the Silver Edition) from TI's website. This is your way back. It is not included here (copyright).
* `SuperOS.8xu` from the [releases](../../../releases) (or `python tools/build.py` and take `dist/SuperOS.8xu`).

## Before you flash

1. **Back up** the calculator with TI Connect (programs, variables). An OS change erases RAM and you should treat the archive as lost.
2. Note the OS version: `2ND` `MEM` `1 About`. TI Connect's device information also shows the boot code ("BIOS") version.
3. **Rehearse the way back** while the TI OS is still installed:
   * take out **one** AAA battery (leave the small backup cell alone);
   * press and **hold DEL**, put the battery back, release DEL after a second or two;
   * the screen must say `Waiting... Please install operating system now`. If it stays blank press ON once;
   * send the official OS with the OS downloader and make sure the calculator comes back as a TI-83 Plus.
   If this does not work on your unit, **stop**.
4. Run `python tools/verify_8xu.py dist/SuperOS.8xu`: it must end with `all checks passed` (file structure, the RSA signature with the OS key, the signature record layout, untouched factory pages). It cannot tell you whether *your* boot code accepts the file.

## Flash

1. Link cable connected, calculator ON, nothing running.
2. Put the calculator in OS-receive mode as in the rehearsal (`Waiting...`), or just have it on the home screen.
3. Send `SuperOS.8xu` with the OS downloader (TI Connect: `TIOSDownloader.exe` in its folder). A progress bar runs for 1-2 minutes. **Do not unplug the cable or remove batteries.** The bar stops at about 50 % because the calculator measures against a full TI OS; that is normal.
4. The calculator turns itself off. Press **ON**. You should see the Super-OS home screen (`INIC MATE IA JUEG SIST`).

If the contrast looks wrong on your unit, `SuperOS_bringup.8xu` sweeps the contrast during the first seconds of boot and draws a progress bar (1-9 blocks) that tells how far the boot got; it is the variant that was used to bring up the first real unit.

## First checks (5 minutes)

`SYS` tab (F5) `7 DIAGNOSTICS`: `3 KEYBOARD` (every key flips exactly one bit), `2 LCD` (patterns, contrast), `4 RAM`, `5 FLASH` (only touches pages `$74-$77`), `7 TIMING` (should read about 108 ticks/s and 15 MHz). Then the calculator (`F2 1`), the grapher, and the games (`F4`). Apps that need the ESP32 say `SIN RESPUESTA ESP32` after about 6 seconds and `CLEAR` cancels the wait.

If the OS restarts by itself it shows `REINICIO` with the program counter and stack pointer of the last tick on the next boot: please include them in your report.

## The way back

Super-OS cannot receive an OS over the cable (it does not implement TI's link protocol), so recovery always goes through the boot code's receive mode: **remove one AAA battery, hold DEL, put it back**, wait for `Waiting... Please install operating system now`, send the official OS. This works because the boot page is never written. If it does not show the message: stop, do not try other key combinations, keep the unit powered off and ask for help with a description of what you see.

## Reporting a problem

Open an issue with: the step, the **exact text** on the screen (or a photo), when it happened, your model, boot code and OS version before the install, the cable and software you used. Real-hardware reports are the most valuable contribution this project can get.
