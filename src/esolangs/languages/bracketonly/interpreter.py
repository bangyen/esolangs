"""BracketOnly evaluates pairs of parenthesized groups in source order.

The first group sums to a function ID. The second supplies the arguments.
The Fibonacci example requires zero-initialized memory and an integer
write result. A write returns the value stored. If returns its chosen arm,
and while sums its body results. XOR takes two arguments as the operation
and Bogen specify. Division truncates toward zero. Whitespace is ignored.
The published cat omits its while condition; the truth machine gives both.

Input/output:
    Inp reads a whitespace-delimited integer. Inpc reads one Unicode
    character. Both raise at EOF. Output has no implicit delimiter.

Errors:
    ProgramError: malformed groups or a non-parenthesis token.
    InputExhaustedError: reading at EOF.
    ArgumentError: malformed numeric input.
    HaltError: invalid function ID or arity, zero divisor, descending
    random interval, negative index, or out-of-range character output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from math import prod
from operator import and_, eq, ge, gt, le, lt, ne, not_, or_, sub, xor
from typing import TYPE_CHECKING, cast

from esolangs.exceptions import HaltError
from esolangs.languages.bracketonly._functions import Function
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._machine import RandomRuntimePlan, RuntimePlan
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._vm_views import sparse_cell, sparse_memory
from esolangs.runtime.io import ScriptedIO, _BufferedOutput
from esolangs.runtime.memory import format_integer, trunc_div, trunc_mod
from esolangs.runtime.randomness import FirstDraw, draw
from esolangs.runtime.source_hints import syntax_error

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Mapping
    from typing import Any

    from esolangs.runtime._lifecycle import CompletionReport
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime.io import IO
    from esolangs.runtime.randomness import Randomness

_ARITIES = (
    0,
    None,
    None,
    2,
    2,
    2,
    0,
    0,
    1,
    1,
    2,
    3,
    2,
    1,
    2,
    2,
    2,
    2,
    1,
    2,
    2,
    2,
    2,
    2,
    2,
)
_PURE: dict[Function, Callable[..., int]] = {
    Function.ONE: lambda: 1,
    Function.ADD: lambda *args: sum(args),
    Function.MUL: lambda *args: prod(args),
    Function.SUB: sub,
    Function.DIV: trunc_div,
    Function.MOD: trunc_mod,
    Function.AND: and_,
    Function.OR: or_,
    Function.XOR: xor,
    Function.NOT: not_,
    Function.LT: lt,
    Function.GT: gt,
    Function.EQ: eq,
    Function.NE: ne,
    Function.LE: le,
    Function.GE: ge,
}
_WORKSPACE = WorkspaceModel(
    "bracketonly-v1", ("top", "frames", "memory", "input_cursor", "draws")
)


@dataclass(frozen=True, slots=True)
class _Group:
    start: int
    calls: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Call:
    function: _Group
    arguments: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Source:
    calls: tuple[_Call, ...]
    root: tuple[int, ...]


def _parse(code: str) -> _Source:
    """Retain paired groups in a flat arena, including arbitrarily deep source."""
    calls: list[_Call] = []
    starts = [0]
    groups: list[list[_Group]] = [[]]

    def pair(groups: list[_Group]) -> tuple[int, ...]:
        if len(groups) % 2:
            raise syntax_error(
                "BracketOnly requires an even number of groups",
                "pair every function group with an argument group",
            )
        start = len(calls)
        calls.extend(
            _Call(fn, args.calls)
            for fn, args in zip(groups[::2], groups[1::2], strict=True)
        )
        return tuple(range(start, len(calls)))

    for pos, char in enumerate(code):
        if char == "(":
            starts.append(pos)
            groups.append([])
        elif char == ")" and len(groups) > 1:
            nested = _Group(starts.pop(), pair(groups.pop()))
            groups[-1].append(nested)
        elif not char.isspace():
            raise syntax_error(
                f"unexpected BracketOnly character at offset {pos}",
                "use only balanced parentheses",
            )
    if len(groups) != 1:
        raise syntax_error(
            "unclosed BracketOnly group", "close every opening parenthesis"
        )
    root = pair(groups[0])
    return _Source(tuple(calls), root)


type _FrameState = tuple[int, int | None, int, tuple[int, ...], int]
type _BranchState = tuple[int, tuple[_FrameState, ...], tuple[tuple[int, int], ...]]


@dataclass(slots=True)
class _Frame:
    node: int
    function: Function | None = None
    offset: int = 0
    values: list[int] = field(default_factory=list)
    total: int = 0

    def snapshot(self) -> _FrameState:
        # Proof packets transport plain integers and tuples.
        function = int(self.function) if self.function is not None else None
        return self.node, function, self.offset, tuple(self.values), self.total


def _advance(
    call: _Call, function: Function | None, offset: int, count: int, *, truth: bool
) -> int | None:
    """Select the next child, or leave the current call ready to reduce."""
    if function == Function.IF:
        if not count:
            return call.arguments[0]
        return call.arguments[1 if truth else 2] if count == 1 else None
    if function == Function.WHILE:
        if not count:
            return call.arguments[0]
        return call.arguments[1] if count == 1 and truth else None
    nodes = call.function.calls if function is None else call.arguments
    return nodes[offset] if offset < len(nodes) else None


class _Machine:
    def __init__(self, source: _Source, io: IO, rng: Randomness | None) -> None:
        self.source = source
        self.io = io
        self.rng = rng
        self.draws = 0
        self.top = 0
        self.frames: list[_Frame] = []
        self.memory: dict[int, int] = {}
        self._rejected = RejectedInput()
        self._writer = _BufferedOutput()

    @property
    def halted(self) -> bool:
        return not self.frames and self.top == len(self.source.root)

    @property
    def _debug_memory(self) -> list[int]:
        return sparse_memory(self.memory)

    def memory_at(self, index: int) -> int | None:
        return sparse_cell(self.memory, index)

    @property
    def ip(self) -> int | None:
        if self.halted:
            return None
        node = self.frames[-1].node if self.frames else self.source.root[self.top]
        return self.source.calls[node].function.start

    def _state(self) -> tuple[Hashable, ...]:
        cursor = self._rejected.cursor(self.io.progress())
        accepted = self._writer.accepted
        return (
            self.top,
            tuple(frame.snapshot() for frame in self.frames),
            tuple(sorted(self.memory.items())),
            cursor
            if accepted is None
            else WorkspaceVariant("pending_output", (cursor, accepted)),
            self.draws,
        )

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(_WORKSPACE, self._state())

    def snapshot(self) -> tuple[object, ...]:
        return self._rejected.snapshot(self._state())

    def branching_snapshot(self) -> _BranchState:
        """Capture the branch state without the output or the sampled RNG."""
        self._rejected.raise_if_rejected()
        return (
            self.top,
            tuple(frame.snapshot() for frame in self.frames),
            tuple(sorted(self.memory.items())),
        )

    def branching_halted(self, state: object) -> bool:
        top, frames, _ = cast(_BranchState, state)
        return not frames and top == len(self.source.root)

    def branching_successors(
        self, state: object, limit: int
    ) -> tuple[_BranchState, ...] | None:
        """Fork one step, leaving input-dependent transitions undecided."""
        top, frames, memory = cast(_BranchState, state)
        count = 1
        if frames:
            node, function, offset, values, _ = frames[-1]
            if offset == len(self.source.calls[node].arguments):
                if function in {Function.INP, Function.INPC}:
                    return None
                if function == Function.RND:
                    lo, hi = values
                    count = max(1, hi - lo + 1)
        if count > limit:
            return None
        branch = _Machine(self.source, ScriptedIO(), None)
        children = []
        for choice in range(count):
            branch.rng = FirstDraw(choice)
            branch.top = top
            branch.frames = [
                _Frame(
                    node,
                    Function(function) if function is not None else None,
                    offset,
                    list(values),
                    total,
                )
                for node, function, offset, values, total in frames
            ]
            branch.memory = dict(memory)
            branch.step()
            children.append(branch.branching_snapshot())
        return tuple(children)

    def _finish(self, value: int) -> None:
        self.frames.pop()
        if self.frames:
            self.frames[-1].values.append(value)

    def _set_function(self, frame: _Frame, count: int) -> None:
        number = sum(frame.values)
        if not 0 <= number < len(_ARITIES):
            raise HaltError("unknown BracketOnly function ID")
        function = Function(number)
        expected = _ARITIES[function]
        if expected is not None and expected != count:
            raise HaltError(
                f"BracketOnly {function.name.lower()} needs {expected} arguments"
            )
        frame.function, frame.offset = function, 0
        frame.values.clear()

    def _output(self, function: Function, value: int) -> None:
        io = self.io
        if function == Function.OUT:
            self._writer.write(
                io, format_integer(value), first=partial(io.print_num, value)
            )
        else:
            if not 0 <= value <= 0x10FFFF:
                raise HaltError("BracketOnly output is outside the Unicode range")
            char = chr(value)
            self._writer.write(io, char, first=partial(io.print_char, char))

    def _apply(self, function: Function, values: list[int]) -> int:
        if function in _PURE:
            if function in {Function.DIV, Function.MOD} and not values[1]:
                raise HaltError("BracketOnly division by zero")
            return int(_PURE[function](*values))
        if function == Function.INP:
            return self._rejected.read(self.io, self.io.input_num)
        if function == Function.INPC:
            return self._rejected.read(self.io, self.io.input_char)
        if function in {Function.OUT, Function.OUTC}:
            self._output(function, values[0])
            return values[0]
        if function == Function.RND:
            lo, hi = values
            if lo > hi:
                raise HaltError("BracketOnly rnd needs an ascending interval")
            value = lo + draw(self.rng, hi - lo + 1)
            self.draws += 1
            return value
        address = values[0]
        if address < 0:
            raise HaltError("BracketOnly array indices must be nonnegative")
        if function == Function.READ:
            return self.memory.get(address, 0)
        value = values[1]
        if value:
            self.memory[address] = value
        else:
            self.memory.pop(address, None)
        return value

    def step(self) -> None:
        if self.halted:
            return
        if not self.frames:
            self.frames.append(_Frame(self.source.root[self.top]))
            self.top += 1
            return
        frame = self.frames[-1]
        call = self.source.calls[frame.node]
        function = frame.function
        values = frame.values
        child = _advance(
            call, function, frame.offset, len(values), truth=bool(values and values[0])
        )
        if child is not None:
            self.frames.append(_Frame(child))
            if function not in {Function.IF, Function.WHILE}:
                frame.offset += 1
        elif function is None:
            self._set_function(frame, len(call.arguments))
        elif function == Function.IF:
            self._finish(values[1])
        elif function == Function.WHILE:
            if len(values) == 2:
                frame.total += values[1]
                values.clear()
            else:
                self._finish(frame.total)
        else:
            self._finish(self._apply(function, values))


def _drive(source: _Source, io: IO, rng: Randomness | None) -> CompletionReport:
    return drive(_Machine(source, io, rng), policy=Completion.HALTED)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the parsed groups with fresh state for each invocation."""
    if not isinstance(source, str):
        raise TypeError("BracketOnly machines require text source")
    if options.keys() - {"rng"}:
        raise TypeError("BracketOnly machines accept only the rng runtime option")
    image = _parse(source)
    return RandomRuntimePlan(partial(_Machine, image), partial(_drive, image)).bind(
        options.get("rng")
    )


def _execute(code: str, io: IO, rng: Randomness | None = None) -> CompletionReport:
    return _drive(_parse(code), io, rng)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Execute a BracketOnly program."""
    _execute(code, io, rng)


if __name__ == "__main__":
    script_main(run)
