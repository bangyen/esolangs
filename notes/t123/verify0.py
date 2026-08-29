"""Verify the length-14 '0'-printer and show that it prints once, not swept.

``docs/walls.md`` claims every short program writing byte 48 or 49 does so
inside a loop enumerating all 256 bytes, "printing each -- the digits are
incidental to the sweep, not selected".  A program whose entire output is the
single character '0' is by definition not sweeping.
"""

from lib import run

CANDIDATES = [
    "12212221111121",
    "12222111211121",
    "21122221111121",
    "21222111121121",
    "22211112211121",
]


def main():
    """Print each candidate's full output and halt status."""
    for code in CANDIDATES:
        out, status = run(code, "", limit=20000)
        print(f"{code!r}: output={out!r} len={len(out)} status={status}")


if __name__ == "__main__":
    main()
