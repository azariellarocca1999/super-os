// Super-OS co-processor: Waveshare ESP32-S3-Zero.
//
// Power architecture ("Zero-Drain Deep Sleep"):
//  * default state = deep sleep (~tens of uA on the chip; the board regulator/LED dominate -- measure it)
//  * ext0 wake on GPIO1 (TIP) LOW: the calculator pulls TIP low for 50 ms, releases it, and waits for ESP_READY
//    ($A5 $5A).  Deep-sleep boot takes ~250 ms, so the pulse is already over when we are up: that is why the
//    calculator waits for READY instead of starting to talk.  (ESP32-S3 deep sleep CANNOT wake from UART;
//    esp_sleep_enable_uart_wakeup is light-sleep only, and the link is a 2-wire handshake anyway.)
//  * CMD_SLEEP from the calculator, or DEFAULT_IDLE_SLEEP_S seconds without traffic -> back to deep sleep.
#include <Arduino.h>
#include "config.h"
#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_sleep.h"
#include "services.h"
#include "store.h"
#include "superlink.h"
#include "cas.h"
#include "games.h"

static uint8_t payload[MAX_PAYLOAD + 8];
RTC_DATA_ATTR static uint32_t boots = 0;
static const char *wake_name = "POWER-ON";
static uint32_t last_activity;
static uint32_t idle_limit_ms = DEFAULT_IDLE_SLEEP_S * 1000UL;

static void enter_deep_sleep() {
  services::wifi_off();
  for (int p : {PIN_TIP, PIN_RING}) {              // keep the lines pulled up while the core is off
    rtc_gpio_init((gpio_num_t)p);
    rtc_gpio_set_direction((gpio_num_t)p, RTC_GPIO_MODE_INPUT_ONLY);
    rtc_gpio_pullup_en((gpio_num_t)p);
    rtc_gpio_pulldown_dis((gpio_num_t)p);
  }
  esp_sleep_enable_ext0_wakeup((gpio_num_t)PIN_TIP, 0);   // wake when the calculator pulls TIP low
  esp_deep_sleep_start();                                  // never returns
}

static void reply_text(const String &s) {
  String a = services::ascii_fold(s);
  superlink::send_stream((const uint8_t *)a.c_str(), a.length());
}

#include "jobs.h"   // two-owner job protocol (host-tested: esp32-firmware/test_host/jobs_test.cpp)
// A task that cannot be created (no heap: e.g. an abandoned HTTPS task still holds its TLS buffers) would leave the job with no owner
// and the calculator waiting for the whole timeout: the caller must answer at once and free the job itself.
static bool job_spawn(TaskFunction_t fn, const char *name, uint32_t stack, Job *j) { return xTaskCreate(fn, name, stack, j, 1, nullptr) == pdPASS; }

// While the (possibly long) HTTPS call runs, keep the calculator's reply timeout alive with CMD_STATUS frames.
struct ChatJob : Job {
  uint8_t model;
  String text;
  String result;
};
static void chat_task(void *arg) {
  ChatJob *j = (ChatJob *)arg;
  j->result = services::chat(j->model, j->text);
  job_finish(j);
  vTaskDelete(nullptr);
}


// Super-CAS runs in its own task: the recursive symbolic code needs far more stack than the Arduino loop task has
struct CasJob : Job {
  uint8_t kind = 0;           // 0 text command, 1 plot3d
  String text;
  String result;
  uint8_t bitmap[768];
  bool ok = false;
};
static std::atomic<bool> cas_running{false};    // the engine has global state: only one job at a time, even after a timeout
static void cas_task(void *arg) {
  CasJob *j = (CasJob *)arg;
  std::string in(j->text.c_str(), j->text.length());
  if (j->kind == 0) {
    j->result = String(cas::runCommand(in).c_str());
    j->ok = true;
  } else {
    std::string err;
    j->ok = cas::runPlot3d(in, j->bitmap, err);
    if (!j->ok) j->result = String(err.c_str());
  }
  cas::reset();
  cas_running = false;
  job_finish(j);
  vTaskDelete(nullptr);
}
// Waits for the job; keeps the calculator's reply timeout alive. Returns true when the job finished (result usable, handler frees it).
template <typename J> static bool wait_job(J *job, uint32_t timeout_ms, uint32_t poll_ms) {
  uint32_t t0 = millis(), beat = millis();
  while (job->st.load() == 0 && millis() - t0 < timeout_ms) {
    delay(poll_ms);
    if (millis() - beat > 8000) {                         // keepalive: [state][rssi]
      uint8_t st[2] = {services::wifi_is_on() ? (uint8_t)2 : (uint8_t)1, services::rssi_abs()};
      superlink::send_frame(CMD_STATUS, st, 2);
      beat = millis();
    }
  }
  return job_claim(job);
}
static bool run_cas_job(CasJob *job, bool &busy, bool &nomem) {
  nomem = false;
  busy = cas_running.exchange(true);
  if (busy) return false;
  if (!job_spawn(cas_task, "cas", 32768, job)) { cas_running = false; nomem = true; return false; }
  return wait_job(job, 60000, 20);
}


// Wikipedia / weather: HTTPS + JSON parsing in a task with a comfortable stack
struct NetJob : Job {
  uint8_t kind = 0;           // 0 wiki, 1 weather
  uint8_t lang = 0;
  String text;
  String result;
};
static void net_task(void *arg) {
  NetJob *j = (NetJob *)arg;
  j->result = j->kind == 0 ? services::wiki(j->lang, j->text) : services::weather(j->lang, j->text);
  job_finish(j);
  vTaskDelete(nullptr);
}
static void run_net_job(uint8_t kind, uint8_t *payload, uint16_t len) {
  NetJob *job = new NetJob();
  job->kind = kind;
  job->lang = len ? payload[0] : 0;
  job->text = String((const char *)payload + 1, len > 0 ? len - 1 : 0);
  if (!job_spawn(net_task, "net", 16384, job)) { reply_text("ERROR: out of memory"); delete job; return; }
  bool done = wait_job(job, 60000, 50);
  reply_text(done ? job->result : String("timeout"));
  job_release(job, done);
}

static String diag_report() {
  char b[320];
  uint8_t l = superlink::levels();
  snprintf(b, sizeof b,
           "SUPER-OS ESP32 REPORT\nFW %s\nBOARD ESP32-S3-ZERO\nUPTIME %lu S\nBOOTS %lu  WAKE %s\nWIFI %s RSSI -%u\nAPI KEY %s\n"
           "LINES T:%d R:%d (IDLE HIGH)\nRX %lu TX %lu CRC ERR %lu\nRETRY %lu TMO %lu\nHEAP %u PSRAM %u",
           FW_VERSION, (unsigned long)(millis() / 1000), (unsigned long)boots, wake_name,
           services::wifi_is_on() ? "ON" : "OFF", services::rssi_abs(), services::has_api_key() ? "SET" : "NOT SET", l & 1, (l >> 1) & 1,
           (unsigned long)superlink::stats.rx_frames, (unsigned long)superlink::stats.tx_frames, (unsigned long)superlink::stats.crc_errors,
           (unsigned long)superlink::stats.tx_retries, (unsigned long)superlink::stats.byte_timeouts, (unsigned)ESP.getFreeHeap(),
           (unsigned)ESP.getFreePsram());
  return String(b);
}

static void handle(uint8_t cmd, uint16_t len) {
  String arg;
  switch (cmd) {
    case CMD_PING:
      reply_text("PONG " + String((const char *)payload, len));
      break;
    case CMD_CHAT: {
      ChatJob *job = new ChatJob();
      job->model = len ? payload[0] : (uint8_t)0;
      job->text = String((const char *)payload + 1, len > 0 ? len - 1 : 0);
      if (!job_spawn(chat_task, "chat", 16384, job)) { reply_text("ERROR: out of memory"); delete job; break; }
      bool done = wait_job(job, 150000, 50);
      reply_text(done ? job->result : String("DeepSeek timeout"));
      job_release(job, done);
      break;
    }
    case CMD_STORE: {
      uint8_t op = len ? payload[0] : 0;
      if (op == 0) {
        reply_text(store::list());
      } else {
        uint8_t *data = nullptr;
        size_t n = 0;
        String name((const char *)payload + 1, len - 1);
        if (store::get(name, &data, &n)) {
          superlink::send_stream(data, n);              // binary program: ZX0-compressed as is
          free(data);
        } else {
          superlink::send_frame(RSP_ERR, (const uint8_t *)"no such package", 15);
        }
      }
      break;
    }
    case CMD_OTA:
      reply_text(store::start_upload_window(len ? payload[0] : 120));
      break;
    case CMD_DIAG:
      reply_text(diag_report());
      break;
    case CMD_WIKI:
      run_net_job(0, payload, len);
      break;
    case CMD_WEATHER:
      run_net_job(1, payload, len);
      break;
    case CMD_CAS: {
      CasJob *job = new CasJob();
      job->kind = 0;
      job->text = String((const char *)payload, len);
      bool busy = false, nomem = false;
      bool done = run_cas_job(job, busy, nomem);
      if (busy || nomem) { reply_text(busy ? "ERROR: CAS busy (previous job still running)" : "ERROR: out of memory"); delete job; }
      else { reply_text(done ? job->result : String("ERROR: timeout")); job_release(job, done); }
      break;
    }
    case CMD_PLOT3D: {
      CasJob *job = new CasJob();
      job->kind = 1;
      job->text = String((const char *)payload, len);
      bool busy = false, nomem = false;
      bool done = run_cas_job(job, busy, nomem);
      if (done && job->ok) {
        superlink::send_stream(job->bitmap, 768);
      } else {
        String m = busy ? String("CAS busy") : nomem ? String("out of memory") : done ? job->result : String("timeout");
        superlink::send_frame(RSP_ERR, (const uint8_t *)m.c_str(), m.length());
      }
      if (busy || nomem) delete job; else job_release(job, done);
      break;
    }
    case CMD_GAME: {                                    // streamed games: [op] 0 list, 1 start [i], 2 frame [keys][flags], 3 stop
      static uint8_t fbuf[800];
      uint8_t op = len ? payload[0] : 0;
      if (op == 0) {
        String l = games::list();
        superlink::send_raw((const uint8_t *)l.c_str(), l.length());
      } else if (op == 1) {
        bool ok = games::start(len > 1 ? payload[1] : 0);
        if (ok) setCpuFrequencyMhz(240);                // Game Boy emulation needs the speed; back to 80 MHz on stop
        superlink::send_raw((const uint8_t *)(ok ? "OK" : "ERR"), ok ? 2 : 3);
      } else if (op == 2) {
        uint16_t keys = len >= 3 ? (uint16_t)(payload[1] | payload[2] << 8) : 0;
        bool full = len >= 4 && (payload[3] & 1);
        size_t n = games::running() ? games::frame(keys, full, fbuf) : 0;
        superlink::send_raw(fbuf, n);
      } else if (op == 3) {
        games::stop();
        setCpuFrequencyMhz(80);
        superlink::send_raw((const uint8_t *)"OK", 2);
      } else {
        superlink::send_frame(RSP_ERR, (const uint8_t *)"bad game op", 11);
      }
      break;
    }
    case CMD_TURBO: {                                   // reply in the current byte layer, then switch
      superlink::send_frame(RSP_LAST, nullptr, 0);
      superlink::set_turbo(len && payload[0]);
      break;
    }
    case CMD_BENCH: {                                   // N pseudo-random bytes (same LCG as the PC simulator)
      uint16_t n = len >= 2 ? (payload[0] | (payload[1] << 8)) : 256;
      if (n > 4000) n = 4000;
      uint8_t *buf = (uint8_t *)malloc(n ? n : 1);
      uint32_t x = 12345;
      for (uint16_t i = 0; i < n; i++) {
        x = (x * 1103515245u + 12345u) & 0x7FFFFFFFu;
        buf[i] = (x >> 16) & 0xFF;
      }
      superlink::send_stream(buf, n);
      free(buf);
      break;
    }
    case CMD_WIFI_SCAN:
      reply_text(services::wifi_scan());
      break;
    case CMD_WIFI_SET: {
      uint16_t z = 0;
      while (z < len && payload[z]) z++;                      // SSID \0 password
      services::wifi_set(String((const char *)payload, z), z < len ? String((const char *)payload + z + 1, len - z - 1) : String(""));
      reply_text("OK");
      break;
    }
    case CMD_API_SET:
      services::api_set(String((const char *)payload, len));
      reply_text("OK");
      break;
    case CMD_STATUS: {
      uint8_t st[2] = {services::wifi_is_on() ? (uint8_t)2 : (uint8_t)1, services::rssi_abs()};
      superlink::send_frame(CMD_STATUS, st, 2);
      superlink::send_frame(RSP_LAST, nullptr, 0);
      break;
    }
    case CMD_TIME: {
      uint8_t hm[2];
      if (services::time_hm(hm[0], hm[1])) superlink::send_frame(CMD_TIME, hm, 2);
      superlink::send_frame(RSP_LAST, nullptr, 0);
      break;
    }
    case CMD_SLEEP:
      enter_deep_sleep();
      break;
    default:
      superlink::send_frame(RSP_ERR, (const uint8_t *)"bad command", 11);
  }
}

void setup() {
  setCpuFrequencyMhz(80);                           // bit-banging and ZX0 of a few KB need nothing more
  superlink::begin();
  services::begin();
  store::begin();
  boots++;
  last_activity = millis();
  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  wake_name = cause == ESP_SLEEP_WAKEUP_EXT0 ? "EXT0(TIP)" : cause == ESP_SLEEP_WAKEUP_UNDEFINED ? "POWER-ON" : "OTHER";
  if (cause == ESP_SLEEP_WAKEUP_EXT0 || cause == ESP_SLEEP_WAKEUP_UNDEFINED) {
    while (superlink::attention()) delay(1);        // let the calculator release the 50 ms pulse
    superlink::send_ready();                        // ESP_READY: $A5 $5A
  }
}

void loop() {
  store::poll();                                    // OTA upload window (port 80), only while open
  if (store::upload_window_open()) last_activity = millis();
  uint8_t cmd;
  uint16_t len;
  if (superlink::recv_frame(cmd, payload, len, 250000)) {
    last_activity = millis();
    handle(cmd, len);
    last_activity = millis();
  } else if (superlink::turbo() && millis() - last_activity > 3000) {
    superlink::set_turbo(false);                    // the calculator vanished mid-game: back to the safe byte layer
    games::stop();
    setCpuFrequencyMhz(80);
  } else if (millis() - last_activity > idle_limit_ms) {
    enter_deep_sleep();
  }
}
