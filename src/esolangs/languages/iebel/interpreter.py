"""Interpreter for IEBEL.

A program is one instruction ``a b c`` per line, optionally prefixed by
its line number and a colon.  There are 256 registers of 0-255, all zero
at start.  An instruction compares register ``a`` with register ``b``:
equal loads the literal ``b`` into register ``a``; unequal jumps to line
``c`` when ``c >= 0``.  A ``c`` from -5 to -1 never jumps but then runs a
control, after the load.  Running past the last line halts.

Commands:
    ``-5``  increment register ``b`` (mod 256)
    ``-4``  decrement register ``b`` (mod 256)
    ``-3``  read one byte into register ``b``
    ``-2``  print register ``a`` as a character
    ``-1``  halt

Input/output:
    ``-3`` reads one byte and ``-2`` writes one character.

Errors:
    ProgramError: a line that is not three integers, a field out of range
    (``a``, ``b`` outside 0-255, ``c`` below -5), or a line-number prefix
    that is not the line's own number.
    InputExhaustedError: ``-3`` at EOF.

Decisions:
    * ``b`` is a register in the comparison and in the controls, and a
      literal in the load: the truth machine's ``0 48 5`` must compare the
      input with the 48 that ``48 48 0`` stored, and its ``0 0 -3`` must
      read into register 0, which ``0 1 -2`` then prints.
    * ``c >= 0`` jumps to the ``c``-th instruction, counted from 0; the
      examples' prefixes always equal that count, so a prefix that differs
      is rejected rather than read as a label.  A jump past the last line
      halts, as running off the end does.
    * Blank lines hold no instruction and are not counted.
    * Arithmetic wraps mod 256, the page's register range.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

from esolangs.languages.iebel.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


class _Op(NamedTuple):
    """One instruction and the source line it came from."""

    a: int
    b: int
    c: int
    line: int


type _State = tuple[int, tuple[int, ...]]


def _parse(code: str) -> tuple[_Op, ...]:
    """Read every non-blank line as ``[k:] a b c``, validating each field."""
    ops: list[_Op] = []
    for line, text in enumerate(code.split("\n")):
        if not text.strip():
            continue
        prefix, colon, body = text.partition(":")
        if not colon:
            body = prefix
        elif prefix.strip() != str(len(ops)):
            raise syntax_error(
                f"line {line} is numbered {prefix.strip()!r}, not {len(ops)}",
                "number lines from 0 in order, or drop the prefixes",
            )
        fields = body.split()
        try:
            a, b, c = (int(field) for field in fields)
        except ValueError:
            raise syntax_error(
                f"line {line} is not three integers: {body.strip()!r}",
                "write each instruction as a b c",
            ) from None
        if not (0 <= a <= 255 and 0 <= b <= 255 and c >= -5):
            raise syntax_error(
                f"line {line} has a field out of range: {a} {b} {c}",
                "keep a and b in 0-255 and c at -5 or above",
            )
        # Skip the Python constructor wrapper.
        # [interpreter_ablations.speedup_adoption_20261103]
        ops.append(tuple.__new__(_Op, (a, b, c, line)))
    return tuple(ops)


def _advance(
    state: _State, ops: tuple[_Op, ...], byte: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one instruction, and the character to print.

    Pure: ``-3``'s byte arrives as ``byte``; ``-1`` moves past the end.
    """
    ind, regs = state
    a, b, c, _ = ops[ind]
    out = None
    nxt = ind + 1
    if regs[a] == regs[b]:
        regs = (*regs[:a], b, *regs[a + 1 :])
    elif c >= 0:
        nxt = c
    if c == -5 or c == -4:
        step = 1 if c == -5 else -1
        regs = (*regs[:b], (regs[b] + step) % 256, *regs[b + 1 :])
    elif c == -3 and byte is not None:
        regs = (*regs[:b], byte % 256, *regs[b + 1 :])
    elif c == -2:
        out = chr(regs[a])
    elif c == -1:
        nxt = len(ops)
    return (min(nxt, len(ops)), regs), out


_WORKSPACE_MODEL = WorkspaceModel(
    "iebel-v1", ("instruction", "registers", "input_cursor")
)


class _Machine:
    """An IEBEL run: the instruction index and the 256 registers."""

    ip_shape = "line"

    def __init__(self, code: str | tuple[_Op, ...], io: IO) -> None:
        self.ops = _parse(code) if isinstance(code, str) else code
        self.io = io
        self.state: _State = (0, (0,) * 256)

    @property
    def ip(self) -> tuple[int]:
        """The next instruction's source line; one past the last once halted."""
        if self.halted:
            return (self.ops[-1].line + 1 if self.ops else 0,)
        return (self.ops[self.state[0]].line,)

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.ops)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of storage and cycle grouping."""
        return _WORKSPACE_MODEL.capture(
            instruction=self.state[0],
            registers=self.state[1],
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Run one instruction; the read and the write happen here."""
        if self.halted:
            return
        byte = self.io.input_char() if self.ops[self.state[0]].c == -3 else None
        self.state, out = _advance(self.state, self.ops, byte)
        if out is not None:
            self.io.print_char(out)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain immutable instructions; each invocation owns its runtime state."""
    if not isinstance(source, str):
        raise TypeError("iebel machines require text source")
    if options:
        raise TypeError("iebel machines accept no runtime options")

    program = _parse(source)

    def build(io: IO) -> _Machine:
        return _Machine(program, io)

    def execute(io: IO) -> CompletionReport:
        return drive(build(io), policy=CAPABILITIES.completion)

    return RuntimePlan(build, execute)


def _execute(code: str, io: IO) -> CompletionReport:
    """Run an IEBEL program until it halts or runs past its last line."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run an IEBEL program until it halts or runs past its last line."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
