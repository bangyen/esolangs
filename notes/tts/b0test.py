r"""Test whether b0 alone is reachable with one bit per input line.

The committed claim was that b0's weight is pinned at 1 because ``+``
duplicates the top and b1 always lands above b0.  That holds only when both
bits arrive from a single ``@``.  The original tests drive the interpreter
with ``side_effect=[...]``, one line per ``input()`` call, and under that
convention ``@ + + @`` duplicates b0 *while it is still the top*, freeing
its weight.

``v97 @ + + @`` should leave ``[97, b0, b0, b0, b1]`` and gate on
``(3*b0 + b1) / 2 > 97``: the row sums are 192, 193, 195, 196, so it fires
exactly when b0 is 49 -- the table ``(0, 0, 1, 1)``, i.e. b0.
"""

from invert import table


def main():
    """Check the predicted b0 witness under the per-line convention."""
    src = "v97 @ + + @"
    print(f"  {src!r} with one bit per line:")
    print(f"    table = {table(src, sep=chr(10))}")
    print("    predicted (0, 0, 1, 1) = b0")

    print("\n  and the same program on a single line (old convention):")
    print(f"    table = {table(src, sep='')}")


if __name__ == "__main__":
    main()
