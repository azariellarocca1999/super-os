/* Host test of the firmware's ZX0 packer (esp32-firmware/lib/zx0) on the inputs the replies can produce, including an EMPTY one
   (store::list() with no packages is ""): the reference optimizer returns optimal[input_size - 1], i.e. optimal[-1] for 0 bytes.
   Each case runs in a child process so that a crash is reported instead of ending the test.
   Build + run: sh esp32-firmware/test_host/build_zx0_test.sh */
#include <stdio.h>
#include <stdlib.h>
#include "zx0_pack.h"

static int one(const char *name, const unsigned char *data, size_t n) {
  size_t clen = 0;
  unsigned char *c = zx0_pack(data, n, &clen);
  if (!c || clen == 0) { printf("  [FAIL] %s: no compressed stream (the reply would never be sent)\n", name); return 1; }
  free(c);
  printf("  [PASS] %s: %u bytes -> %u compressed\n", name, (unsigned)n, (unsigned)clen);
  return 0;
}

int main(int argc, char **argv) {
  static const unsigned char text[] = "HELLO|82\nGAME|300|8\n";
  if (argc > 1) {                     /* child mode: run one case */
    int k = atoi(argv[1]);
    fflush(stdout);
    if (k == 0) return one("empty reply (store list with no packages)", text, 0);
    if (k == 1) return one("one byte", text, 1);
    return one("a package list", text, sizeof text - 1);
  }
  int fails = 0;
  for (int k = 0; k < 3; k++) {
    char cmd[512];
    snprintf(cmd, sizeof cmd, "\"%s\" %d", argv[0], k);
    fflush(stdout);
    int rc = system(cmd);
    if (rc != 0) {
      fails++;
      if (rc != 1 && rc != 256) printf("  [FAIL] case %d crashed (exit status %d)\n", k, rc);
    }
  }
  printf("RESULT: %s\n", fails ? "FAIL" : "all ZX0 packer checks passed");
  return fails ? 1 : 0;
}
