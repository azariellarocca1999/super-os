"""Static verification of dist/SuperOS.8xu (structure, pages, checksums, untouched boot pages, RSA signature math, boot hand-off bytes).

Nothing here proves the file is accepted by a real calculator: it only catches build mistakes.
Usage: python tools/verify_8xu.py [file.8xu] [--rom dist/superos.rom]   (exit code 1 on any FAIL)
"""
import hashlib
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(ok, text):
    print("  [%s] %s" % ("PASS" if ok else "FAIL", text))
    if not ok:
        FAILS.append(text)


def parse_hex(lines):
    """Intel-hex records -> list of blocks; each block = list of (page, address, bytes). Returns (blocks, bad_checksums)."""
    blocks, cur, page, bad = [], [], 0, 0
    for ln in lines:
        ln = ln.strip()
        if not ln.startswith(":"):
            continue
        ln = ln.split()[0]              # TI's tools append a comment (":00000001FF   -- CONVERT 2.6 --")
        raw = bytes.fromhex(ln[1:])
        if sum(raw) & 0xFF:
            bad += 1
        n, addr, typ = raw[0], (raw[1] << 8) | raw[2], raw[3]
        data = raw[4:4 + n]
        if typ == 0:
            cur.append((page, addr, data))
        elif typ == 2:
            page = (data[0] << 8) | data[1]
        elif typ == 1:
            blocks.append(cur)
            cur, page = [], 0
    return blocks, bad


def main():
    path = os.path.join(root, "dist", "SuperOS.8xu")
    rom_path = os.path.join(root, "dist", "superos.rom")
    args = [a for a in sys.argv[1:]]
    if "--rom" in args:
        i = args.index("--rom")
        rom_path = args[i + 1]
        del args[i:i + 2]
    if args:
        path = args[0]
    b = open(path, "rb").read()
    print("file: %s (%d bytes, sha256 %s)" % (path, len(b), hashlib.sha256(b).hexdigest()[:16]))

    print("== TIFL header")
    check(b[:8] == b"**TIFL**", "magic **TIFL**")
    check(b[48] == 0x73, "device type $73 (TI-83 Plus family), got $%02X" % b[48])
    check(b[49] == 0x23, "data type $23 (OS upgrade), got $%02X" % b[49])
    length = int.from_bytes(b[74:78], "little")
    check(length == len(b) - 78, "payload length field %d == actual %d" % (length, len(b) - 78))
    text = b[78:].decode("ascii", "replace")
    lines = text.split("\n")
    blocks, bad = parse_hex(lines)
    check(bad == 0, "every Intel-hex record checksum is valid (%d bad)" % bad)
    check(len(blocks) == 3, "3 hex blocks: header, OS data, signature (found %d)" % len(blocks))
    if len(blocks) != 3:
        return finish()

    hdr, osdata, sig = blocks
    print("== OS header block")
    hbytes = b"".join(d for _, _, d in hdr)
    check(len(hbytes) == 0x1B, "header field block is 27 bytes (got %d)" % len(hbytes))
    print("     %s" % hbytes.hex())

    print("== pages")
    pages = {}
    for page, addr, data in osdata:
        buf = pages.setdefault(page, {})
        for i, v in enumerate(data):
            buf[addr + i] = v
    plist = sorted(pages)
    print("     pages in the upgrade: %s" % " ".join("%02X" % p for p in plist))
    for forbidden in (0x7D, 0x7E, 0x7F):
        check(forbidden not in pages, "factory page $%02X is NOT in the file (boot code / certificate untouched)" % forbidden)
    check(0 in pages, "page 00 present")
    allfit = True
    for p, buf in pages.items():
        lo, hi = min(buf), max(buf)
        base = 0x0000 if p == 0 else 0x4000
        if p == 0:
            ok = lo >= 0 and hi < 0x4000
        else:
            ok = lo >= 0 and hi < 0x8000  # mktiupgrade addresses a page as 0000-3FFF or 4000-7FFF, both accepted
        allfit = allfit and ok
        if not ok:
            print("     page %02X range %04X-%04X" % (p, lo, hi))
    check(allfit, "all addresses fit inside a 16 KB page window")
    payload = sum(len(d) for _, _, d in osdata)
    print("     OS data bytes: %d (%.1f KB)" % (payload, payload / 1024.0))

    print("== compare with the emulator ROM")
    if os.path.exists(rom_path):
        rom = open(rom_path, "rb").read()
        diffs = []
        for p, buf in pages.items():
            for a, v in buf.items():
                if rom[p * 0x4000 + (a & 0x3FFF)] != v:
                    diffs.append((p, a, v))
        # rabbitsign -r stamps the OS-valid byte $A5 at $0057 of page 0 (os8x.c); anything else is a build mismatch
        unexpected = [d for d in diffs if d != (0, 0x57, 0xA5)]
        print("     differences from the dev ROM: %s" % (", ".join("page %02X $%04X=%02X" % d for d in diffs) or "none"))
        check(not unexpected, "every byte of the .8xu equals the dev ROM except the OS-valid stamp $A5 at $0057 added by rabbitsign")
        check(len(rom) == 2 * 1024 * 1024, "dev ROM is 2 MB")
    else:
        print("     (dev ROM not found, skipped)")

    print("== signature record layout (as in TI's OS and KnightOS)")
    tail = b[-330:].replace(b"\r\n", b"\n").split(b"\n")
    sig_recs = [ln.split()[0] for ln in tail if ln.startswith(b":") and ln[1:3] in (b"20", b"03") and ln[3:9] == b"000000"]
    check(len(sig_recs) >= 3 and [r[1:3] for r in sig_recs[-3:]] == [b"20", b"20", b"03"],
          "signature = records of 32 + 32 + 3 bytes, all at address 0000 (rabbitsign's 3 x 32 padded layout is what a real boot code rejected?)")
    check(b.endswith(b"-- CONVERT 2.6 --\r\n"), "file ends with the TI terminator line ':00000001FF   -- CONVERT 2.6 --' + CRLF")
    print("== signature block")
    sbytes = b"".join(d for _, _, d in sig)                  # by the length byte below, never rstrip(FF): the RSA value may end in FF
    check(len(sbytes) >= 3 + (sbytes[2] if len(sbytes) > 2 else 255) and sbytes[:3] == bytes([0x02, 0x0D, 0x40]), "signature field header 02 0D 40 + 64-byte RSA value (got %s)" % sbytes[:3].hex())
    keyfile = os.path.join(root, "tools", "keys", "04.key")   # OS key: the official TI OS 1.19 and KnightOS verify against it (0104 = app key)
    tok = open(keyfile).read().split()[0]           # rabbitsign key format: [length byte][little-endian hex]
    modulus = int.from_bytes(bytes.fromhex(tok[2:2 + 2 * int(tok[:2], 16)]), "little")
    s = int.from_bytes(sbytes[3:67], "little") if len(sbytes) >= 67 else 0
    check(modulus.bit_length() == 512, "key 04 modulus is 512 bits")
    check(0 < s < modulus, "signature value is smaller than the key-04 modulus")
    # Independent re-implementation of rabbitsign's rs_validate_ti8x_os (tools/src/rabbitsign/src/os8x.c + rsa.c): the signed message is
    # MD5(header block || every page of the file as a full 16 KB image, in file order); valid when sig^17 mod n == that MD5 (little endian).
    image = bytearray()
    for p in plist:
        pg = bytearray(b"\xff" * 0x4000)
        for a, v in pages[p].items():
            pg[a & 0x3FFF] = v
        image += pg
    digest = hashlib.md5(hbytes + bytes(image)).digest()
    siglen = sbytes[2] if len(sbytes) >= 3 else 0
    s = int.from_bytes(sbytes[3:3 + siglen], "little")
    check(pow(s, 17, modulus) == int.from_bytes(digest, "little"),
          "RSA signature verifies: sig^17 mod n == MD5(header + pages)  (same math as rabbitsign's validator, recomputed here)")
    print("     What this proves: the file is correctly signed with the public key 04 (the TI-83 Plus family OS key: same key as TI's own OS 1.19 and KnightOS). What it does not prove:")
    print("     that your unit's boot code accepts it (revision differences), nor anything about the OS running on real hardware.")
    hdr_fields = hbytes.hex()
    check("801104" in hdr_fields, "header key ID field 8011 = 04")
    check(("8081%02x" % len(plist)) in hdr_fields, "header page count field 8081 = %d pages in the file" % len(plist))

    print("== boot hand-off bytes on page 0")
    p0 = pages.get(0, {})
    check(p0.get(0x53) == 0xC3, "$0053 holds a JP (the boot code enters a validated OS there): %s" % " ".join("%02X" % p0.get(a, 0xFF) for a in range(0x53, 0x58)))
    check(p0.get(0x56, 0xFF) == 0xFF and p0.get(0x57) == 0xA5, "$0056 = $FF (the boot code marks it $5A once the signature is accepted), $0057 = $A5")
    return finish()


def finish():
    print()
    if FAILS:
        print("verify_8xu: %d FAIL" % len(FAILS))
        return 1
    print("verify_8xu: all checks passed (file structure + signature math only - NOT a hardware test)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
