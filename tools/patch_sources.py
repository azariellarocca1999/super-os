#!/usr/bin/env python3
"""Idempotent source preparation for the third-party tools (Windows/MinGW builds)."""
import os
import re
import sys

src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")


def write_if_missing(path, text):
    if not os.path.exists(path):
        with open(path, "w", newline="\n") as f:
            f.write(text)


# Tilem core: a minimal config.h (no gettext, no audio)
write_if_missing(os.path.join(src, "tilem", "config.h"),
                 '#define HAVE_STDINT_H 1\n#define HAVE_LROUND 1\n#define PACKAGE_STRING "tilem"\n#define PACKAGE_VERSION "2.0"\n')

# RabbitSign: builds without GMP using its own mpz.c
write_if_missing(os.path.join(src, "rabbitsign", "config.h"),
                 '#define HAVE_ASSERT_H 1\n#define HAVE_INTTYPES_H 1\n#define HAVE_LIMITS_H 1\n#define HAVE_MEMCPY 1\n'
                 '#define HAVE_STDINT_H 1\n#define HAVE_STDLIB_H 1\n#define HAVE_STRING_H 1\n#define HAVE_RAND 1\n#define STDC_HEADERS 1\n'
                 '#define PACKAGE_VERSION "2.1"\n#define PACKAGE_NAME "rabbitsign"\n#define VERSION "2.1"\n#define KEYDIR "keys"\n'
                 '#define PACKAGE_BUGREPORT "none"\n#define PACKAGE_STRING "rabbitsign 2.1"\n')

# mktiupgrade: open binary files in binary mode (Windows text mode truncates at ^Z / rewrites CRLF)
p = os.path.join(src, "mktiupgrade", "main.c")
if os.path.exists(p):
    s = open(p, encoding="utf-8", errors="replace").read()
    s = re.sub(r'fopen\((context\.(?:infile|keyfile|sigfile)), "r"\)', r'fopen(\1, "rb")', s)
    s = s.replace('fopen(context.outfile, "w")', 'fopen(context.outfile, "wb")')
    open(p, "w", encoding="utf-8", newline="\n").write(s)

# key files must be LF-only for the key parser
for k in ("04.key", "0A.key"):
    kp = os.path.join(src, "kernel", "keys", k)
    if os.path.exists(kp):
        b = open(kp, "rb").read().replace(b"\r\n", b"\n")
        open(kp, "wb").write(b)
print("sources prepared")
