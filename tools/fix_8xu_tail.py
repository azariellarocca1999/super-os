"""Rewrite the signature block of a rabbitsign-produced .8xu the way TI's own OS files (and KnightOS, which boots on a real TI-83+SE) have it.

rabbitsign writes the 67-byte signature field (02 0D 40 + 64 bytes) as three 32-byte records at addresses 0000/0020/0040, padded with FF.
TI's files (and KnightOS) carry the same 67 bytes as records of 32 + 32 + 3 bytes, every one at address 0000, no padding, followed by the
terminator line ':00000001FF   -- CONVERT 2.6 --'.  The signature VALUE is identical (checked: re-signing KnightOS' data gives the same bytes);
only the record layout differs.  The calculator's boot code receives these records through TI's link protocol, so the layout is what it sees.

Usage: python tools/fix_8xu_tail.py file.8xu   (rewrites in place, also fixes the payload length in the TIFL header)
"""
import sys

TERMINATOR = b":00000001FF"


def hex_record(addr, data):
    raw = bytes([len(data), addr >> 8, addr & 0xFF, 0]) + data
    chk = (-sum(raw)) & 0xFF
    return b":" + (raw + bytes([chk])).hex().upper().encode() + b"\r\n"


def fix(path):
    b = open(path, "rb").read()
    head, text = b[:78], b[78:]
    lines = text.replace(b"\r\n", b"\n").split(b"\n")
    term = [i for i, ln in enumerate(lines) if ln.startswith(TERMINATOR)]
    if len(term) < 3:
        raise SystemExit("fix_8xu_tail: expected 3 hex blocks, found %d terminators" % len(term))
    sig_lines = lines[term[1] + 1:term[2]]
    sig = b""
    for ln in sig_lines:
        if ln.startswith(b":"):
            raw = bytes.fromhex(ln[1:].decode().split()[0])
            sig += raw[4:4 + raw[0]]
    # the field is 02 0D <len> + <len> bytes; take it by its length, never by stripping the FF padding: the RSA value itself may end in FF
    if len(sig) < 3 or sig[:3] != bytes([0x02, 0x0D, 0x40]) or len(sig) < 3 + sig[2]:
        raise SystemExit("fix_8xu_tail: unexpected signature field %s" % sig[:3].hex())
    sig = sig[:3 + sig[2]]
    body = b"\r\n".join(lines[:term[1] + 1]) + b"\r\n"
    body += hex_record(0, sig[:32]) + hex_record(0, sig[32:64]) + hex_record(0, sig[64:67])
    body += TERMINATOR + b"   -- CONVERT 2.6 --\r\n"
    head = head[:8] + bytes([0x02, 0x40]) + head[10:74] + len(body).to_bytes(4, "little")   # revision field as in KnightOS' working file
    open(path, "wb").write(head + body)
    return len(body)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print("%s: payload %d bytes" % (p, fix(p)))
