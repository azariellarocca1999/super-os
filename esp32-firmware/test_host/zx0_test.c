/* Host test of the firmware's ZX0 packer (esp32-firmware/lib/zx0), which runs once per reply on the ESP32 for as long as it is on:
   - an EMPTY input (store::list() with no packages is ""): the reference optimizer read optimal[-1] for 0 bytes;
   - repeated calls must not leak (the reference tool is a one-shot program that never frees its tables or block pool);
   - an allocation failure must make zx0_pack return NULL, not exit() (exit = a reboot on the ESP32), and leak nothing.
   Each case runs in a child process so that a crash or an exit() is reported instead of ending the test.
   Build + run: sh esp32-firmware/test_host/build_zx0_test.sh */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "zx0_pack.h"

/* counting allocator used by the ZX0 sources (zx0_count.h is forced into them) */
static long live_bytes = 0, allocs = 0, fail_at = 0;
void *cnt_malloc(size_t n) {
  if (fail_at && ++allocs == fail_at) return NULL;
  size_t *p = (size_t *)malloc(n + sizeof(size_t));
  if (!p) return NULL;
  *p = n;
  live_bytes += (long)n;
  return p + 1;
}
void *cnt_calloc(size_t k, size_t n) {
  void *p = cnt_malloc(k * n);
  if (p) memset(p, 0, k * n);
  return p;
}
void cnt_free(void *q) {
  if (!q) return;
  size_t *p = (size_t *)q - 1;
  live_bytes -= (long)*p;
  free(p);
}

static unsigned char sample[3000];

static int one(const char *name, const unsigned char *data, size_t n) {
  size_t clen = 0;
  unsigned char *c = zx0_pack(data, n, &clen);
  if (!c || clen == 0) { printf("  [FAIL] %s: no compressed stream (the reply would never be sent)\n", name); return 1; }
  cnt_free(c);
  printf("  [PASS] %s: %u bytes -> %u compressed\n", name, (unsigned)n, (unsigned)clen);
  return 0;
}

static int leak(void) {
  long after_first = 0;
  for (int i = 0; i < 40; i++) {
    size_t clen = 0;
    unsigned char *c = zx0_pack(sample, sizeof sample, &clen);
    if (!c) { printf("  [FAIL] repeated replies: zx0_pack failed at call %d\n", i); return 1; }
    cnt_free(c);
    if (i == 0) after_first = live_bytes;
  }
  int ok = live_bytes == 0;
  printf("  [%s] 40 replies of 3000 bytes leave no heap behind (live bytes after 1 call: %ld, after 40: %ld)\n", ok ? "PASS" : "FAIL",
         after_first, live_bytes);
  return !ok;
}

static int oom(void) {
  int bad = 0;
  for (long k = 1; k <= 12; k++) {          /* make the 1st, 2nd, ... allocation fail */
    allocs = 0;
    fail_at = k;
    size_t clen = 0;
    unsigned char *c = zx0_pack(sample, sizeof sample, &clen);
    fail_at = 0;
    if (c) cnt_free(c);                     /* past the last allocation the call simply succeeds */
    if (live_bytes != 0) { printf("  [FAIL] allocation %ld failing leaves %ld bytes behind\n", k, live_bytes); bad = 1; live_bytes = 0; }
  }
  printf("  [%s] an allocation failure returns NULL (no exit(), i.e. no reboot on the ESP32) and frees everything\n", bad ? "FAIL" : "PASS");
  return bad;
}

int main(int argc, char **argv) {
  static const unsigned char text[] = "HELLO|82\nGAME|300|8\n";
  for (size_t i = 0; i < sizeof sample; i++) sample[i] = (unsigned char)("SUPER-OS ZX0 TEST "[i % 18] ^ (i / 97));
  if (argc > 1) {                     /* child mode: run one case */
    int k = atoi(argv[1]);
    if (k == 0) return one("empty reply (store list with no packages)", text, 0);
    if (k == 1) return one("one byte", text, 1);
    if (k == 2) return one("a package list", text, sizeof text - 1);
    if (k == 3) return leak();
    return oom();
  }
  int fails = 0;
  for (int k = 0; k < 5; k++) {
    char cmd[512];
    snprintf(cmd, sizeof cmd, "\"%s\" %d", argv[0], k);
    fflush(stdout);
    int rc = system(cmd);
    if (rc != 0) {
      fails++;
      if (rc != 1 && rc != 256) printf("  [FAIL] case %d crashed or exited (exit status %d)\n", k, rc);
    }
  }
  printf("RESULT: %s\n", fails ? "FAIL" : "all ZX0 packer checks passed");
  return fails ? 1 : 0;
}
