"""Interpreter for AlbaBet.

A tiny two-register language: an accumulator ``x`` and a secondary register
``y`` both start at 0.  ``a``/``b`` move ``x`` by +1/-1 (``b`` clamps at 0,
as a natural number), ``c``/``d`` set ``x`` to 0 and move the old ``x`` into
0 or ``y``, ``e``/``f`` copy ``x`` into ``y`` or clear ``y``, ``j`` adds
``x`` into ``y``, ``g``/``h`` multiply ``x`` by ``y`` or square ``x``, and
``i`` prints ``x`` as the Unicode character whose code point it is.  Any
other character is ignored.

``i`` prints ``Char.ofNat x``: when ``x`` is not a valid Unicode scalar
value (the surrogate range 0xD800-0xDFFF, or 0x110000 and above) it prints
NUL instead.  The values are unbounded natural numbers and the output is
that character's UTF-8 encoding.  Every character is a defined operation or
a no-op, so there is no malformed program (no :class:`ValueError`) and no
invalid runtime operation (no :class:`~esolangs.exceptions.HaltError`).
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run an AlbaBet program, printing each ``i`` as a character."""
    x = 0
    y = 0
    for c in code:
        if c == "a":
            x += 1
        elif c == "b":
            if x:
                x -= 1  # natural-number subtraction clamps at 0
        elif c == "c":
            x = 0
        elif c == "d":
            x, y = 0, x
        elif c == "e":
            y = x
        elif c == "f":
            y = 0
        elif c == "j":
            y += x
        elif c == "g":
            x *= y
        elif c == "h":
            x *= x
        elif c == "i":
            if not (x < 0xD800 or 0xDFFF < x < 0x110000):
                x = 0  # invalid scalar -> Char.ofNat yields NUL
            io.print_char(chr(x))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
