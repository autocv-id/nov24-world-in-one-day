#!/usr/bin/env python3
"""NI24 v2-mode1 entrypoint: stdlib-only copier.

Copies entry.png to $MAKEFUN_OUTPUT_DIR/entry.png (default /output).
Checks the PNG signature + size <= 1 MiB. Never imports draw.py.
"""
import os
import sys

MAX_BYTES = 1_048_576
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "entry.png")
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    dst = os.path.join(outdir, "entry.png")
    try:
        with open(src, "rb") as f:
            data = f.read()
    except OSError as e:
        print(f"main.py: cannot read entry.png: {e}", file=sys.stderr)
        return 1
    if len(data) > MAX_BYTES:
        print(f"main.py: entry.png too large: {len(data)} bytes", file=sys.stderr)
        return 1
    if not data.startswith(PNG_SIG):
        print("main.py: entry.png is not a PNG", file=sys.stderr)
        return 1
    os.makedirs(outdir, exist_ok=True)
    with open(dst, "wb") as f:
        f.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
