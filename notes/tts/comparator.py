r"""Test the drain threshold as an input-dependent branch, contra walls.md.

The walls entry concludes "there is no input-dependent branch either",
having considered only the loops (``\\`` while nonempty, ``:`` while the
stack is unchanged) and the fixed 15-command reset.  It does not consider
the drain condition itself:

    while stk and sum(stk[1:]) / 2 > stk[0]:

That comparison is evaluated against stack *values*, so if the input byte
sits in the tail it decides whether the drain fires at all.  With a front of
49 and a trailing 50, ``(input + 50) / 2 > 49`` holds for input byte 49
(``'1'``) and fails for 48 (``'0'``) -- emission vs silence, gated on the
input, under the standard ``'0'``/``'1'`` encoding.

That shape is exactly the termination-based convention documented later in
walls.md (Point Break, ArrowQueue): the answer carried by whether the
program emits, rather than by what it prints.
"""

from probe import go


def main():
    """Test input-gated emission under the standard bit encoding."""
    print("--- the comparator as a branch (inputs '0'/'1') ---")
    for src in ("o v49 @ v50", "v49 @ v50", "o v49 @ v51", "v48 @ v50"):
        outs = [go(src, ch) for ch in ("0", "1")]
        gated = outs[0][0] != outs[1][0]
        print(f"  {src!r:14} -> {outs}  input-gated={gated}")

    print("--- can the gate be inverted (a NOT)? ---")
    for src in ("o v50 @ v50", "o v49 @ v49", "v50 @ v51"):
        outs = [go(src, ch) for ch in ("0", "1")]
        print(f"  {src!r:14} -> {outs}")


if __name__ == "__main__":
    main()
