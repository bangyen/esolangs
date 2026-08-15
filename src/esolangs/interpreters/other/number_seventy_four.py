"""Interpreter for Number Seventy-Four.

A one-bit tape language.  ``0`` and ``1`` push their bit onto the front of
the output string, and ``H`` writes an ``H`` only if the output already
starts with ``0`` (the first character written, which the last push
determines).  The program is scanned in repeated passes: once the output
starts with ``H`` the program prints it and halts, otherwise it restarts
from the beginning of the program.  Any other character is ignored, and
there is no input command.

Semantics match the Rust cross-check (``extra/rust/number_seventy_four.rs``):
- the halting check is made only at a pass boundary, so a program that
  makes the output start with ``H`` mid-pass and then pushes a ``0``/``1``
  afterwards never halts;
- a program whose output never starts with ``H`` restarts forever and never
  returns (an ``H`` on an empty output does nothing); a program with no
  ``0``/``1``/``H`` commands at all halts with no output instead of looping;
- there are no invalid operations or malformed programs, so ``run`` never
  raises :class:`HaltError` or :class:`ValueError`.
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run a Number Seventy-Four program."""
    # a program with no 0/1/H commands can never make the output start with
    # H, so the reference would restart forever; halt instead (like the other
    # no-op interpreters)
    if not any(c in "01H" for c in code):
        return
    data = ""
    while not data.startswith("H"):
        for c in code:
            if c == "0":
                data = "0" + data
            elif c == "1":
                data = "1" + data
            elif c == "H" and data.startswith("0"):
                data = "H" + data
    io.print_str(data)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
