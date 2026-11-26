"""Interpreter for Brainfuck.

8-bit wrapping tape growing in both directions, matching-bracket loops.

Input/output:
    ``,`` reads one byte and ``.`` writes one.  ``,`` at EOF raises (the
    spec leaves EOF undefined), so ``,[.,]`` ends with an error.

Errors:
    ProgramError: Unbalanced brackets.
    InputExhaustedError: ``,`` at EOF.

Decisions:
    * ``<`` at the leftmost cell adds a fresh zero cell to its left: the
      wiki allows cells left of the start ("an interpreter may provide
      some"), and its primo and KSab Hello Worlds need four and five.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cached_property, partial
from typing import Any

from esolangs.languages.brainfuck._native import (
    _advance_compiled,
    _compile,
    _compile_ops,
    _CompiledState,
    _Op,
)
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import HALTED_REPORT, CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._validate import require_text_source
from esolangs.runtime.brackets import BracketProgram
from esolangs.runtime.brackets import match_brackets as matches
from esolangs.runtime.io import IO, _BufferedOutput

#: ``(ind, ptr, tape)``: an immutable value, rebound per step.  ``tape[ptr]``
#: is always the true cell: ``+``/``-`` write through, so one logical state
#: has one spelling and the cycle detector's hash sees a repeat as a repeat.
#: A buffered cell (an ``acc``/``dirty`` pair, one rebuild per run of
#: ``+``/``-`` instead of one per command) earned 17.5% run-to-halt but
#: cost 9.4% on the traced workload, whose ``snapshot()`` every step
#: commits the cell anyway; the traced workload is the one this repo's
#: verification drivers impose, so the buffer was removed (interpreter
#: candidate I-1).
#: A plain tuple: ``NamedTuple.__new__`` is Python-level, 2.7x slower to
#: build, and this is built once per step.  Code and bracket map are
#: parameters, not fields, so the cycle detector stores no constants.
#: Order starts ``ind, ptr, tape`` because ``snapshot`` returns those three.
type _State = tuple[int, int, tuple[int, ...]]
# Keep the proof's grouping even if state storage or cycle snapshots change.
_WORKSPACE_MODEL = WorkspaceModel(
    "brainfuck-v1", ("instruction", "pointer", "tape", "input_cursor")
)


def _written(tape: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    """Return ``tape`` with cell ``ptr`` set to ``value``.

    One rebuild per write; a tape is the handful of cells touched (nine
    to eighteen), so the rebuild stays small.
    """
    return (*tape[:ptr], value, *tape[ptr + 1 :])


# :func:`_advance` is pure over an immutable ``_State`` and ``snapshot`` returns it
# directly; the shell does ``.`` and ``,``. ``factor.py`` drives a decoded program
# through it.
def _advance(state: _State, code: str, brackets: Mapping[int, int]) -> _State:
    """Return the state after executing the command at the code position.

    Pure; ``,``'s value arrives already written.  Fields are unpacked and one
    state built at the end: per-branch rebuilds made this ~5.6x slower than
    the mutable original, against ~2x.
    """
    ind, ptr, tape = state
    char = code[ind]
    if char == "+":
        tape = _written(tape, ptr, (tape[ptr] + 1) % 256)
    elif char == "-":
        tape = _written(tape, ptr, (tape[ptr] - 1) % 256)
    elif char == ">":
        # Past the right end grows by one.
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
    elif char == "<":
        # Past the left end grows by one, and the pointer stays at index 0,
        # now the new cell.
        if ptr:
            ptr -= 1
        else:
            tape = (0, *tape)
    elif (char == "[" and tape[ptr] == 0) or (char == "]" and tape[ptr] != 0):
        # Lands on the partner; +1 steps past it.
        ind = brackets[ind]
    return (ind + 1, ptr, tape)


class _Program(BracketProgram):
    """The source-step view plus a native view compiled only when requested."""

    @cached_property
    def compiled(self) -> tuple[_Op, ...]:
        """Lower source once without rebuilding its validated loop map."""
        return _compile_ops(self.source, self.brackets)


class _Machine:
    """A Brainfuck run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str | BracketProgram, io: IO) -> None:
        if isinstance(code, BracketProgram):
            self.code, self.brackets = code.source, code.brackets
        else:
            self.code, self.brackets = code, matches(code)
        self.io = io
        self._writer = _BufferedOutput()
        # ``halted`` is read twice per command; take the length once.
        self.size = len(self.code)
        self.state: _State = (0, 0, (0,))

    # Views for ``factor.py``.

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def ind(self) -> int:
        return self.state[0]

    def input_position(self) -> int:
        """Report the input cursor for the growth detector."""
        return self.io.progress()

    @property
    def halted(self) -> bool:
        return self.state[0] >= self.size

    # VM view.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Tape plus input cursor (a repeat that ignores consumed input is
        # not a cycle).
        ind, ptr = self.state[0], self.state[1]
        boundary = (ind, ptr, self.state[2], self.io.progress())
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def step(self) -> None:
        """Execute one command, advancing the code position.

        The shell does ``.`` and ``,``; ``,``'s value is written through
        before :func:`_advance` steps past it.
        """
        state = self.state
        if state[0] >= self.size:
            return
        ind, ptr, tape = state
        char = self.code[ind]
        if char == ".":
            byte = chr(tape[ptr])
            self._writer.write(self.io, byte, first=partial(self.io.print_char, byte))
        elif char == ",":
            # ``input_char`` is a whole code point.  Unreduced, ``,.`` echoed
            # an emoji while ``,+.`` printed ``\x01``.  CVNC does the same.
            state = (ind, ptr, _written(tape, ptr, self.io.input_char() % 256))
        self.state = _advance(state, self.code, self.brackets)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Project control, the whole allocated tape and consumed input for proofs."""
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            instruction=(
                WorkspaceVariant("pending_output", (self.ind, accepted))
                if accepted
                else self.ind
            ),
            pointer=self.ptr,
            tape=self.tape,
            input_cursor=self.io.progress(),
        )


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the loop map and lazily share native compilation across runs."""
    source = require_text_source(source, options, "Brainfuck")
    program = _Program.parse(source)

    def build(io: IO) -> _Machine:
        return _Machine(program, io)

    def execute(io: IO) -> CompletionReport:
        return _execute(program.compiled, io)

    return RuntimePlan(build, execute)


def _execute(code: str | tuple[_Op, ...], io: IO) -> CompletionReport:
    """Run source or retained native operations with a fresh mutable tape."""
    ops = _compile(code) if isinstance(code, str) else code
    tape = bytearray(1)
    state: _CompiledState = (0, 0)
    while state[0] < len(ops):
        state = _advance_compiled(state, ops, tape, io)
    return HALTED_REPORT


def run(code: str, io: IO) -> None:
    """Run compact operations on a fresh tape."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
