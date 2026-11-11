"""Interpreter for Alight, a two-dimensional language of word commands.

Spec: https://esolangs.org/wiki/Alight; where prose and examples disagree this follows
the examples (infix left to right, in-place three-argument ``at``, seen through every
variable naming that list; ``docs/limitations.md``).  ``inp`` at EOF reads ``eof``.

Errors:
    ProgramError: unparsable command or expression; empty program; no ``begin``.
    HaltError: any invalid runtime operation (bad type, unknown name, zero divisor).
"""

from collections.abc import Mapping
from typing import Any

from esolangs.languages.alight.interpreter._machine import (
    _Image,
    _Machine,
    _prepare_source,
)
from esolangs.languages.alight.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime.io import IO


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the padded grid and entry for fresh walkers."""
    if not isinstance(source, (str, list)):
        raise TypeError("alight machines require text or split text source")
    if options.keys() - {"expression_syntax", "list_update"}:
        raise TypeError("alight machines accept only expression_syntax and list_update")
    image = _prepare_source(
        source,
        options.get("expression_syntax", "infix"),
        options.get("list_update", "in_place"),
    )
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(
    code: list[str] | str | _Image,
    io: IO,
    *,
    expression_syntax: str = "infix",
    list_update: str = "in_place",
) -> CompletionReport:
    """Run an Alight program to its ``end``."""
    machine = _Machine(
        code, io, expression_syntax=expression_syntax, list_update=list_update
    )
    return drive(machine, policy=CAPABILITIES.completion)


def run(
    code: list[str] | str,
    io: IO,
    *,
    expression_syntax: str = "infix",
    list_update: str = "in_place",
) -> None:
    """Run an Alight program to its ``end``."""
    _execute(code, io, expression_syntax=expression_syntax, list_update=list_update)
