#!/usr/bin/env python3
"""Download official BusyBox i386 static binary into third_party/."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "third_party" / "busybox-i386-static"
URL = "https://busybox.net/downloads/binaries/1.35.0-i686-linux-musl/busybox"
# Optional integrity check — update if URL version changes.
EXPECTED_SHA256 = None  # set to hex digest to enforce


def main() -> int:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL}")
    urllib.request.urlretrieve(URL, DEST)
    data = DEST.read_bytes()
    if data[:4] != b"\x7fELF":
        print("ERROR: downloaded file is not an ELF", file=sys.stderr)
        return 1
    digest = hashlib.sha256(data).hexdigest()
    print(f"Wrote {DEST} ({len(data)} bytes)")
    print(f"SHA256 {digest}")
    if EXPECTED_SHA256 and digest != EXPECTED_SHA256:
        print("ERROR: SHA256 mismatch", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
