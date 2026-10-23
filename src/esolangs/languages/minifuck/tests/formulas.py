"""Minifuck's emitted characters: the positional strip."""


def _chars(n: int, _: str) -> int:
    """81T/2 + 59 - n, n >= 3: the positional mux on its longest controls.

    The mux is built on every table and is the longest candidate, so every other
    form is at most it.  Past the table it is fixed: walk to the field 27, the
    field's init (4 a one after the first zero, 4 the first zero, 2 the end zero:
    4T + 6 at most), a 11-character crossing, a 3.5T - 24 walk, the setters
    9T - 10 - n (weights 6k - 1, pads 1.5k - 1 twice), the relay 24T + 33 + 16.
    The most init is a 0 control row then ones, so ones everywhere but the last
    row (the witness).  Ignoring an input swaps the strip for half its size.
    """
    return 81 * 2**n // 2 + 59 - n


FORMULAS = {"scaling": (_chars, True, tuple(range(3, 13)))}
