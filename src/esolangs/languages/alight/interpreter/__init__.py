"""Interpreter for Alight, a two-dimensional language of word commands.

Spec: https://esolangs.org/wiki/Alight; where prose and examples disagree this follows
the examples (infix left to right, in-place three-argument ``at``, seen through every
variable naming that list; ``docs/limitations.md``).  ``inp`` at EOF reads ``eof``.

Errors:
    ProgramError: unparsable command or expression; empty program; no ``begin``.
    HaltError: any invalid runtime operation (bad type, unknown name, zero divisor).
"""

from esolangs.languages.alight.interpreter._machine import _Machine
from esolangs.runtime._drive import drive
from esolangs.runtime.io import IO


def run(
    code: list[str] | str,
    io: IO,
    *,
    expression_syntax: str = "infix",
    list_update: str = "in_place",
) -> None:
    """Run an Alight program to its ``end``."""
    machine = _Machine(
        code, io, expression_syntax=expression_syntax, list_update=list_update
    )
    drive(machine)
