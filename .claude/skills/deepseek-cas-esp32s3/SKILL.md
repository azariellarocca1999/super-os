---
name: deepseek-cas-esp32s3
description: ESP32-S3 side of Super-OS - DeepSeek chat/reasoner over HTTPS (esp_http_client + CA bundle), NVS credentials, NTP, deep sleep with ext0 wake, ZX0 reply compression, and the plan for the symbolic CAS and 96x64 plot bitmaps.
---

# ESP32-S3-Zero firmware notes

* Board: Waveshare ESP32-S3-Zero (ESP32-S3FH4R2, 4 MB flash, 2 MB PSRAM). Build with PlatformIO + pioarduino (Arduino-ESP32 3.x) from PowerShell, never from MSYS/Git-bash.
* Link pins GPIO1 (TIP, RTC) / GPIO2 (RING). Level shifting with one BSS138 per line (see docs/WIRING.md).
* DeepSeek: `POST https://api.deepseek.com/chat/completions`, header `Authorization: Bearer <key>`, body
  `{"model":"deepseek-chat"|"deepseek-reasoner","max_tokens":600,"messages":[{"role":"system",...},{"role":"user",...}]}`;
  the answer is `choices[0].message.content`. R1 may take more than 60 s: send `CMD_STATUS` keepalives every 8 s from the main loop while a FreeRTOS task blocks in HTTP.
* TLS: `esp_http_client_config_t.crt_bundle_attach = esp_crt_bundle_attach`.
* Credentials live in NVS namespace `superos` (ssid, pass, dskey, tz). NVS is not encrypted: use flash encryption for production.
* Deep sleep: `esp_sleep_enable_ext0_wakeup(GPIO_NUM_1, 0)` plus RTC pull-ups. UART wake exists only for light sleep. Boot ~250 ms; Wi-Fi reconnect uses the
  BSSID/channel cached in `RTC_DATA_ATTR`.
* Replies: ASCII-fold, ZX0-compress with `lib/zx0` (byte-identical to the build's zx0.exe), stream as frames of at most 240 bytes.
* Plot blocks `[PLOT: expr, xmin, xmax]` (system prompt): the *calculator* tokenises the formula (`txt_tok` in `z80-os/math/cas.z80`) and plots it locally in
  the grapher after the answer was read (`aiplot_main`); nothing extra is needed on the ESP32.
* Super-CAS (milestone 3, built): `esp32-firmware/lib/supercas` is a custom C++17 engine (no exceptions / RTTI, arena of nodes, canonical auto-simplifying
  constructors, exact rationals on int64 with a software 128-bit integer on the 32-bit chip -> `cas_i128.h`).  Entry points: `cas::runCommand(text)` -> text and
  `cas::runPlot3d(text, bitmap768, err)`.  Commands are parsed as ordinary expressions and evaluated while parsing, so they nest (`diff(int(f,x),x)`).
  SuperLink: `CMD_CAS` $30 (text -> ZX0 text) and `CMD_PLOT3D` $31 (text -> 768-byte bitmap, `RSP_ERR` on failure).  Run it in a task with >= 32 KB stack
  (recursive code) and send `CMD_STATUS` keepalives while it works.  Host build + tests: `sh cas/build_cas.sh`, `python cas/cas_tests.py`; every answer is
  checked numerically with an independent Python evaluator.  Also build with `-DCAS_SOFT128` to exercise the software 128-bit path on the host.
* Wikipedia: `GET https://{es|en}.wikipedia.org/w/rest.php/v1/search/title?q=..&limit=1` then `/api/rest_v1/page/summary/<Title_with_underscores>` -> `extract`.
  Weather: Open-Meteo geocoding (`geocoding-api.open-meteo.com/v1/search`) then `api.open-meteo.com/v1/forecast?current=..&daily=..&timezone=auto`.
  Payload of both commands: `[language 0 = ES, 1 = EN][text]`; replies are plain ASCII text.
