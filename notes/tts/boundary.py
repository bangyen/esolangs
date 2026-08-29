"""Locate the reset boundary exactly and confirm the emitter fires after it.

``staged.py`` reaches only non-inverted tables, which says the emitter is not
running on the surviving rows as intended.  ``comm`` increments at the end of
every ``parse`` call and the reset fires on ``comm % 15 == 0``, so the exact
word index matters.  Rather than assume it, this measures it.
"""

from emitafter import stack_after

GATE = "o v98 @ v0 v99"


def main():
    """Find the pad length that leaves a clean stack for the next word."""
    print("--- stack size after N pad words (row 00, a survivor) ---")
    for n in range(0, 14):
        src = GATE + (" " + " ".join(["#"] * n) if n else "")
        stk, out, outcome = stack_after(src, "00")
        print(f"  pad {n:2}: len(stack)={len(stk):2} out={out!r} {outcome}")

    print("\n--- and for the dying row 11 ---")
    for n in range(0, 14):
        src = GATE + (" " + " ".join(["#"] * n) if n else "")
        stk, out, outcome = stack_after(src, "11")
        print(f"  pad {n:2}: len(stack)={len(stk):2} out={out!r} {outcome}")


if __name__ == "__main__":
    main()
