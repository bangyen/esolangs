r"""Test whether an input-gated silent halt exists.

Every table reached so far is monotone: the drain can only turn emission
*on* as the input sum rises.  Inverting needs a way for the firing rows to
produce nothing, which the byte-mode range check supplies:

    n = self.stk.pop(0) - 1
    if not self.num and not 0 <= n <= 0x10FFFF:
        raise HaltError

So in byte mode a pop whose value falls outside the Unicode range halts the
program with no output at all.  If the drain condition is input-gated and
the popped value is out of range, the rows that fire die silently and the
rows that do not fire fall through to whatever follows -- an inversion.
"""

from probe import go

BIG = 0x10FFFF + 2  # popping this yields n > 0x10FFFF -> HaltError


def rows(source, sep=""):
    """Return (output, status) for each of the four two-bit inputs."""
    out = []
    for b0 in "01":
        for b1 in "01":
            out.append(go(source, f"{b0}{sep}{b1}", limit=600))
    return out


def main():
    """Check that an out-of-range pop halts silently, and that it gates."""
    print("--- an out-of-range pop halts with no output ---")
    for src in (f"o v{BIG} v999999", f"O v{BIG} v999999"):
        print(f"  {src!r:22} -> {go(src, '')}")

    print("\n--- gated on the input sum? ---")
    for src in (f"o v{BIG} @ v99", f"o v{BIG} @ v999", f"o v{BIG} @ v9999"):
        print(f"  {src!r:22} -> {[r[0] for r in rows(src)]}"
              f"  statuses {[r[1] for r in rows(src)]}")


if __name__ == "__main__":
    main()
