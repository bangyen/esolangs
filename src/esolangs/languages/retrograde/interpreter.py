r"""Interpreter for Retrograde.

A bidirectional bit tape and a source cursor start at zero, moving forward.
Each instruction executes, then the cursor advances in its current direction.
Leaving either source boundary halts.

Commands:
    ``*`` toggle the current bit in either direction
    ``>`` / ``<`` move right/left forward, left/right backward
    ``{`` / ``}`` on bit 1, jump to the paired brace and reverse direction
    ``/`` toggle only forward
    ``\`` toggle only backward

Input/output:
    No stdin is read. On halt the current tape bit is dumped as 0 or 1.

Errors:
    ProgramError: an unknown non-whitespace character or unmatched brace.

Decisions:
    * Initial tape contents are unstated. The author's REFRACTRAN reduction
      explicitly starts both tape halves and the current bit at zero;
      this interpreter uses that initial state, origin pointer and forward
      entry at the first instruction.
    * Whitespace is ignored, matching the spaced code examples. Other
      characters are rejected; braces must pair even when never visited.
    * Final-current-bit output is an adapter dump, not a new instruction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

from esolangs.languages.retrograde.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


class _State(NamedTuple):
    cursor: int
    pointer: int
    direction: int
    left: int
    right: int


def _bit(state: _State) -> int:
    """Return the current cell; negative coordinates occupy the left mask."""
    p = state.pointer
    return (state.right >> p if p >= 0 else state.left >> (-p - 1)) & 1


type _Image = tuple[str, tuple[int, ...], tuple[int, ...]]


def _parse(source: str) -> _Image:
    """Return commands, paired cursor indices and original source offsets."""
    code: list[str] = []
    offsets: list[int] = []
    pairs: list[int] = []
    stack: list[int] = []
    for offset, c in enumerate(source):
        if c.isspace():
            continue
        if c not in "*<>{}/\\":
            raise syntax_error(
                f"unknown Retrograde command {c!r}", "use * < > { } / \\"
            )
        i = len(code)
        code.append(c)
        offsets.append(offset)
        pairs.append(i)
        if c == "{":
            stack.append(i)
        elif c == "}":
            if not stack:
                raise syntax_error("unmatched closing brace", "pair each { with }")
            j = stack.pop()
            pairs[j], pairs[i] = i, j
    if stack:
        raise syntax_error("unmatched opening brace", "pair each { with }")
    return "".join(code), tuple(pairs), tuple(offsets)


def _advance(state: _State, code: str, pairs: tuple[int, ...]) -> _State:
    """Execute one command and advance in the resulting direction."""
    cursor, pointer, direction, left, right = state
    c = code[cursor]
    if c == "*" or (c == "/" and direction == 1) or (c == "\\" and direction == -1):
        if pointer >= 0:
            right ^= 1 << pointer
        else:
            left ^= 1 << (-pointer - 1)
    elif c == ">":
        pointer += direction
    elif c == "<":
        pointer -= direction
    elif c in "{}" and _bit(state):
        cursor = pairs[cursor]
        direction = -direction
    # Skip the Python constructor wrapper.
    # [interpreter_ablations.speedup_adoption_20261103]
    return tuple.__new__(_State, (cursor + direction, pointer, direction, left, right))


_WORKSPACE_MODEL = WorkspaceModel(
    "retrograde-v1",
    ("instruction", "pointer", "direction", "left", "right", "printed", "input_cursor"),
)


class _Machine:
    """Exact packed tape halves and the two cursors."""

    def __init__(self, code: str | _Image, io: IO) -> None:
        self.code, self.pairs, self.offsets = (
            _parse(code) if isinstance(code, str) else code
        )
        self.state = tuple.__new__(_State, (0, 0, 1, 0, 0))
        self.io = io
        self.printed = False

    @property
    def halted(self) -> bool:
        """Whether execution has left the source and dumped its final bit."""
        return self.printed

    @property
    def ip(self) -> int | None:
        """The original source offset of the next command, or None at the dump."""
        i = self.state.cursor
        return self.offsets[i] if 0 <= i < len(self.offsets) else None

    @property
    def ptr(self) -> int:
        """The signed tape coordinate."""
        return self.state.pointer

    @property
    def memory(self) -> list[int]:
        """Cells spanning the origin, pointer and every nonzero cell."""
        low = min(0, self.ptr, -self.state.left.bit_length())
        high = max(0, self.ptr, self.state.right.bit_length() - 1)
        return [
            (self.state.right >> p if p >= 0 else self.state.left >> (-p - 1)) & 1
            for p in range(low, high + 1)
        ]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        return _WORKSPACE_MODEL.capture(
            instruction=self.state.cursor,
            pointer=self.state.pointer,
            direction=self.state.direction,
            left=self.state.left,
            right=self.state.right,
            printed=self.printed,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return all mutable state, including the input cursor."""
        return (*self.state, self.printed, self.io.progress())

    def step(self) -> None:
        """Execute a command, or dump the final bit after source exit."""
        if self.halted:
            return
        if not 0 <= self.state.cursor < len(self.code):
            self.io.print_str(str(_bit(self.state)))
            self.printed = True
        else:
            self.state = _advance(self.state, self.code, self.pairs)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain parsed instructions and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("retrograde machines require text source")
    if options:
        raise TypeError("retrograde machines accept no runtime options")

    image = _parse(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    """Run Retrograde and dump its final current bit."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run Retrograde and dump its final current bit."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
