"""Interpreter for REFRACTRAN.

The first whitespace-delimited token is the positive initial integer; remaining
tokens are positive fractions. Forward search multiplies by the current
fraction, reverse search divides by it. An integral result replaces the value
and reverses the search; otherwise the search continues unchanged. Moving
past either end halts. For example, ``2 3/2`` halts at 3, printed as ``11``.

Input/output:
    No input is read. The final integer is dumped in binary without a prefix.

Errors:
    ProgramError: missing initial integer, malformed token, or nonpositive term.

Decisions:
    * The wiki supplies an initial integer but no file grammar: it precedes
      the fraction list. Products and nonnegative integer powers abbreviate
      that integer, as in ``2^3*3``. Fractions are decimal integer pairs.
    * Binary final-state output is an adapter convention, not an instruction;
      its last bit exposes parity without discarding the rest of the state.
    * Positive integers and fractions avoid zero division; comments start
      with ``#`` and end at newline, following the wiki's example convention.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any, NamedTuple

from esolangs.languages.refractran.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

_FRACTION = re.compile("([0-9]+)/([0-9]+)")


class _State(NamedTuple):
    cursor: int
    value: int
    direction: int


type _Image = tuple[int, tuple[tuple[int, int], ...], tuple[int, ...]]


def _parse(code: str) -> _Image:
    """Return the initial integer, reduced fractions and source offsets."""
    clean = re.sub(r"#[^\n]*", lambda m: " " * len(m[0]), code)
    tokens = list(re.finditer(r"\S+", clean))
    if not tokens:
        raise syntax_error("REFRACTRAN needs an initial integer", "start with 1")
    initial = 1
    for term in tokens[0][0].split("*"):
        match = re.fullmatch(r"([0-9]+)(?:\^([0-9]+))?", term)
        if match is None or int(match[1]) <= 0:
            raise syntax_error("invalid initial integer", "use positive factors")
        initial *= int(match[1]) ** int(match[2] or "1")
    fractions = []
    for token in tokens[1:]:
        match = _FRACTION.fullmatch(token[0])
        if match is None or int(match[1]) <= 0 or int(match[2]) <= 0:
            raise syntax_error("invalid fraction", "use positive numerator/denominator")
        a, b = int(match[1]), int(match[2])
        divisor = math.gcd(a, b)
        fractions.append((a // divisor, b // divisor))
    return initial, tuple(fractions), tuple(token.start() for token in tokens[1:])


def _advance(state: _State, fractions: tuple[tuple[int, int], ...]) -> _State:
    """Return one search step, multiplying forward and dividing backward."""
    index, value, direction = state
    a, b = fractions[index]
    if direction < 0:
        a, b = b, a
    if value % b == 0:
        value = value // b * a
        direction = -direction
    return _State(index + direction, value, direction)


_WORKSPACE_MODEL = WorkspaceModel(
    "refractran-v1", ("instruction", "integer", "direction", "printed", "input_cursor")
)


class _Machine:
    """The fraction cursor, direction and exact integer."""

    def __init__(self, code: str | _Image, io: IO) -> None:
        value, self.fractions, self.offsets = (
            _parse(code) if isinstance(code, str) else code
        )
        self.state = _State(0, value, 1)
        self.io = io
        self.printed = False

    @property
    def halted(self) -> bool:
        """Whether the search has exited and its final state was dumped."""
        return self.printed

    @property
    def ip(self) -> int | None:
        """The source offset of the fraction about to be inspected."""
        i = self.state.cursor
        return self.offsets[i] if 0 <= i < len(self.offsets) else None

    @property
    def memory(self) -> list[int]:
        """The exact integer and search direction."""
        return [self.state.value, self.state.direction]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        return _WORKSPACE_MODEL.capture(
            instruction=self.state.cursor,
            integer=self.state.value,
            direction=self.state.direction,
            printed=self.printed,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return all mutable execution state and the input cursor."""
        return (*self.state, self.printed, self.io.progress())

    def step(self) -> None:
        """Inspect a fraction, or dump the integer after exiting the list."""
        if self.halted:
            return
        if not 0 <= self.state.cursor < len(self.fractions):
            self.io.print_str(format(self.state.value, "b"))
            self.printed = True
        else:
            self.state = _advance(self.state, self.fractions)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain parsed instructions and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("REFRACTRAN machines require text source")
    if options:
        raise TypeError("REFRACTRAN machines accept no runtime options")

    image = _parse(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    """Run REFRACTRAN, dumping its final integer in binary."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run REFRACTRAN, dumping its final integer in binary."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
