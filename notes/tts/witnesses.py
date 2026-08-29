"""Every Temporary Stack witness cited in the walls.md entry, executed.

Each claim in the rewritten entry has a runnable check here, so the entry
rests on execution rather than on a reading of the interpreter -- the
discipline the 123 section had to be rewritten to meet.
"""

from probe import go


def main():
    """Run each cited witness and report it."""
    print("1. numeric mode prints the digit directly (no 49/50 constant):")
    for src, want in (("v1 v99", "0"), ("v2 v99", "1")):
        text, status = go(src, "")
        ok = "OK" if (text == want and status == "halt") else "MISMATCH"
        print(f"   {src!r:10} -> {text!r} status={status} [{ok}]")

    print("\n2. the drain comparator is an input-dependent branch")
    print("   (standard '0'/'1' encoding, emission vs silence):")
    outs = [go("o v49 @ v50", ch) for ch in ("0", "1")]
    ok = "OK" if (outs[0][0] == "" and outs[1][0] == "0") else "MISMATCH"
    print(f"   'o v49 @ v50' -> input '0': {outs[0][0]!r}, "
          f"input '1': {outs[1][0]!r} [{ok}]")

    print("\n3. a three-word identity in byte mode, bits read as '1'/'2':")
    outs = [go("o @ v999", ch) for ch in ("1", "2")]
    ok = "OK" if (outs[0][0] == "0" and outs[1][0] == "1") else "MISMATCH"
    print(f"   'o @ v999' -> bit 0: {outs[0][0]!r}, "
          f"bit 1: {outs[1][0]!r} [{ok}]")

    print("\n4. 'O' is numeric mode, 'o' is byte mode (easy to invert):")
    print(f"   'O @ v999' on '1' -> {go('O @ v999', '1')[0]!r} (a number)")
    print(f"   'o @ v999' on '1' -> {go('o @ v999', '1')[0]!r} (a character)")


if __name__ == "__main__":
    main()
