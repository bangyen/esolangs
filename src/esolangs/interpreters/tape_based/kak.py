"""Interpreter for Kak.

A one-bit-tape language: ``!`` advances the pointer and flips the current
bit, ``<`` moves the pointer left (a no-op at cell 0), and ``?`` is a
conditional skip: when the current bit is zero it consumes characters until
it has consumed one of ``!``/``?``/``<``, skipping them all without
executing them.  Every other character is a no-op.  The tape starts as a
single zero cell with the pointer on it (which can never be flipped, since
``!`` always advances before flipping), and there is no input command.

After the program text has been read once, the whole tape is printed as a
bit string on its own line and execution restarts from the beginning while
the current bit is nonzero; the program therefore always runs at least once,
and the empty program prints ``0``.  These semantics are ported exactly from
the Rust cross-check at ``extra/rust/kak.rs`` (itself a port of the original
C++ reference).

The ``?`` skip is read on the fly exactly as the reference does it.  When
the current bit is zero the ``?`` consumes the character right after it; if
the program ends immediately there, the skip stops without error (the
reference's failed ``get`` leaves the ``?`` itself in the buffer, which is
one of the stopping characters).  Otherwise the ``?`` keeps consuming
characters while they are not ``!``/``?``/``<``.  The character that finally
stops the skip (a ``!``/``?``/``<``) is consumed but not executed, so a skip
effectively jumps to just past the next command, and any ``!``/``?``/``<``
characters encountered along the way are skipped as well.

Documented divergence from the reference:

- a ``?`` that runs off the end of the program *while searching for a
  stopping character* (after already consuming at least one non-``!``/``?``/
  ``<`` character) is an invalid operation and halts with
  :class:`~esolangs.exceptions.HaltError` (the reference exits with
  EXIT_FAILURE, and the repository's other interpreters raise ``HaltError``
  for runtime invalid operations);
- the ``__main__`` entry point silently does nothing without an argument,
  following the other in-package interpreters, instead of exiting with
  EXIT_FAILURE like the reference.
"""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_SKIP = "!?<"


def run(code: str, io: IO) -> None:
    """Run a Kak program."""
    tape = [0]
    ptr = 0
    n = len(code)

    while True:
        i = 0
        while i < n:
            char = code[i]
            i += 1
            if char == "!":
                ptr += 1
                if ptr == len(tape):
                    tape.append(0)
                tape[ptr] = 1 - tape[ptr]
            elif char == "?" and not tape[ptr]:
                if i < n:
                    char = code[i]
                    i += 1
                    while char not in _SKIP:
                        if i >= n:
                            raise HaltError("`?` skipped off the end of the program")
                        char = code[i]
                        i += 1
            elif char == "<" and ptr:
                ptr -= 1

        io.print_line("".join(str(bit) for bit in tape))
        if not tape[ptr]:
            return


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
