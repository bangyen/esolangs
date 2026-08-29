r"""Build the affine two-input tables by construction, with no search.

``affine.py`` establishes the endgame: from location 7, ``111111111`` (nine
ones) walks to the write position flipping locations 7..0 and -1 on the way,
so a blank tape prints ``0xFF``.  Printing byte ``B`` therefore needs the
tape to hold ``B XOR 0xFF`` when the walk starts.

``'0'`` is 48 -> pre-pass 0xCF; ``'1'`` is 49 -> pre-pass 0xCE.  They differ
only in bit 0 of the byte, which is **location 7** (the byte is MSB-first,
so location ``i`` is bit ``7 - i``).  So:

* set locations 0-7 to 0xCF with a fixed prologue -- the constant part;
* embed each input at location 7 with the displacement-neutral setter, where
  ``12`` flips location 7 (toggling the answer) and ``21`` flips location 8
  (which ``byte()`` never reads, so a zero contributes nothing);
* walk home and print.

The answer is then ``'0'`` XOR (number of one-bits mod 2) -- which is XNOR
for two inputs.  Complementing the prologue's location 7 gives XOR, and
dropping or duplicating a setter gives the other affine tables.
"""

from affine import instantiate, run

# Location i holds bit 7 - i, so 0xCF = 1100 1111 sets locations 0,1,4,5,6,7.
PRE_ZERO = 0xCF   # prints '0' after the walk
PRE_ONE = 0xCE    # prints '1' after the walk


def prologue(value):
    """Emit code setting locations 0-7 to ``value``, ending at location 7.

    Walks right from location 0, flipping each cell that must be set.  A
    ``12`` flips the current cell and returns, so it is a set-in-place; a
    bare ``2`` steps right without flipping.
    """
    parts = []
    for i in range(8):
        if value & (1 << (7 - i)):
            parts.append("12")     # flip location i, stay
        if i < 7:
            parts.append("2")      # step right
    return "".join(parts)


def walk_and_print():
    """Walk from location 7 to the write position, print, and halt."""
    return "1" * 9 + "2" + "1"


def build(pre_value):
    """Assemble a full template embedding both inputs at location 7."""
    return prologue(pre_value) + "{X0}" + "{X1}" + walk_and_print()


def main():
    """Verify the prologue, then the two affine templates it yields."""
    print("--- prologue alone should print the target ---")
    for value, want in ((PRE_ZERO, "0"), (PRE_ONE, "1")):
        code = prologue(value) + walk_and_print()
        out, halted = run(code)
        ok = "OK" if out == want else "MISMATCH"
        print(f"  pre 0x{value:02X}: {out!r} (want {want!r}) "
              f"halted={halted} [{ok}]")

    print("\n--- with both inputs embedded at location 7 ---")
    for value in (PRE_ZERO, PRE_ONE):
        tpl = build(value)
        rows = []
        for r in range(4):
            bits = [(r >> 1) & 1, r & 1]
            out, halted = run(instantiate(tpl, bits))
            rows.append(out if halted else None)
        print(f"  pre 0x{value:02X}: rows {rows}")


if __name__ == "__main__":
    main()
