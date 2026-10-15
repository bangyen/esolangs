"""Interpreter for Alight, a two-dimensional language of word commands.

The language spec is the wiki page, https://esolangs.org/wiki/Alight; where
its prose and its examples disagree this interpreter follows the examples
(infix operators evaluated left to right, in-place three-argument ``at``),
as recorded in ``docs/limitations.md`` under "Interpreter conventions".
An in-place ``at`` is seen through every variable naming that list.
``inp`` at EOF reads ``eof``; invalid runtime operations raise
:class:`~esolangs.exceptions.HaltError`.
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
