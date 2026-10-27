// Host tool: reads commands (one per line) from stdin and prints the Super-CAS result.  Used by the tests and the virtual ESP32.
//   cas_cli            -> text commands, one result per command ("\x01" separates results, newline-escaped as "\n")
//   cas_cli --plot3d   -> reads one plot3d(...) line, writes 768 raw bytes (or ERR:text) to stdout
#include <cstdio>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
#include <cstring>
#include <iostream>
#include <string>

#include "../esp32-firmware/lib/supercas/cas.h"

int main(int argc, char **argv) {
#ifdef _WIN32
  _setmode(_fileno(stdout), _O_BINARY);
#endif
  std::string line;
  if (argc > 1 && !strcmp(argv[1], "--plot3d")) {
    std::getline(std::cin, line);
    uint8_t bm[768];
    std::string err;
    if (cas::runPlot3d(line, bm, err)) {
      fwrite(bm, 1, 768, stdout);
      return 0;
    }
    printf("ERR:%s", err.c_str());
    return 1;
  }
  while (std::getline(std::cin, line)) {
    std::string r = cas::runCommand(line);
    for (char &c : r)
      if (c == '\n') c = '\x02';
    fputs(r.c_str(), stdout);
    fputc('\n', stdout);
    fflush(stdout);
  }
  return 0;
}
