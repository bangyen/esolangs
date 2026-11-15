"""Help. runs line-addressed instructions over sparse byte memory.

The truth machine fixes zero-based jumps, hexadecimal operands and
left-to-right subtraction. Division and modulo follow that operand order
and truncate toward zero. Blank and comment lines keep their addresses.
Unwritten bytes are zero. Wide addresses use little-endian cells and stores
wrap to their destination width. Reaching the end halts, as in Hello World.

Input/output:
    One reads one Latin-1 character, mny reads one line into consecutive
    bytes, and both raise at EOF (the published cat reads until EOF).
    Out emits its byte operands without a separator.

Errors:
    ProgramError: malformed opcode, operand or address.
    InputExhaustedError: a read at EOF.
    ArgumentError: a character outside Latin-1.
    HaltError: zero divisor, descending random range, invalid jump target
    or output outside the byte range.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial
from operator import add, mul, sub
from typing import TYPE_CHECKING

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._machine import RandomRuntimePlan, RuntimePlan
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import _BufferedOutput
from esolangs.runtime.memory import trunc_div, trunc_mod
from esolangs.runtime.randomness import draw
from esolangs.runtime.source_hints import syntax_error

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Mapping
    from typing import Any

    from esolangs.runtime._lifecycle import CompletionReport
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime.io import IO
    from esolangs.runtime.randomness import Randomness

_ARITHMETIC = {"add": add, "sub": sub, "mul": mul, "div": trunc_div, "mod": trunc_mod}
_BOOLEAN: dict[str, Callable[..., int]] = {
    "not": lambda a: int(not a),
    "and": lambda a, b: int(bool(a and b)),
    "or_": lambda a, b: int(bool(a or b)),
}
_ADDRESS = re.compile(r"([0-9a-fA-F]*)\$([0-9a-fA-F]+)")
_HEX = re.compile(r"[+-]?[0-9a-fA-F]+")
_READS = frozenset({"one", "mny"})
_WORKSPACE = WorkspaceModel("help-v1", ("ip", "memory", "input_cursor", "draws"))


@dataclass(frozen=True, slots=True)
class _Address:
    start: int
    width: int


type _Operand = int | _Address
type _Branch = tuple[int, tuple[tuple[int, int], ...]]


@dataclass(frozen=True, slots=True)
class _Instruction:
    operation: str
    operands: tuple[_Operand, ...] = ()
    destination: _Address | None = None


def _address(token: str) -> _Address:
    match = _ADDRESS.fullmatch(token)
    if match is None:
        raise syntax_error("Help. requires a memory address", "use $ followed by hex")
    extra, start = match.groups()
    return _Address(int(start, 16), int(extra or "0", 16) + 1)


def _operand(token: str) -> _Operand:
    if _HEX.fullmatch(token):
        return int(token, 16)
    return _address(token)


def _parse_line(line: str) -> _Instruction:
    tokens = line.partition(";")[0].split()
    if not tokens:
        return _Instruction("blank")
    op, *args = tokens
    if op in _ARITHMETIC or op == "rnd":
        if len(args) == 3:
            left, right, dest = args
            return _Instruction(op, (_operand(left), _operand(right)), _address(dest))
    elif op in {"if_", "jmp"}:
        if len(args) == 1:
            operand = _address(args[0]) if op == "if_" else _operand(args[0])
            return _Instruction(op, (operand,))
    elif op == "set":
        if len(args) == 2:
            return _Instruction(op, (_operand(args[1]),), _address(args[0]))
    elif op == "inp":
        if len(args) == 2 and args[0] in _READS:
            return _Instruction(args[0], destination=_address(args[1]))
    elif op == "boo":
        if len(args) >= 2 and args[1] in _BOOLEAN:
            dest, op, *values = args
            if len(values) == (1 if op == "not" else 2):
                return _Instruction(op, tuple(map(_operand, values)), _address(dest))
    elif op == "out" and args:
        return _Instruction(op, tuple(map(_operand, args)))
    elif op == "end" and not args:
        return _Instruction(op)
    raise syntax_error(
        f"invalid Help. instruction {op!r}", "check the opcode and operands"
    )


def _advance(
    op: str, args: tuple[int, ...], ip: int, end: int
) -> tuple[int, int | str | None]:
    """Return the next line and the operation's store or output."""
    if op in _ARITHMETIC:
        if op in {"div", "mod"} and args[1] == 0:
            raise HaltError("Help. division by zero")
        return ip + 1, _ARITHMETIC[op](*args)
    if op in _BOOLEAN:
        return ip + 1, _BOOLEAN[op](*args)
    if op == "set":
        return ip + 1, args[0]
    if op == "if_":
        return ip + (1 if args[0] else 2), None
    if op == "jmp":
        target = args[0]
        if not 0 <= target < end:
            raise HaltError("Help. jump target is outside the source")
        return target, None
    if op == "out":
        if any(not 0 <= value <= 255 for value in args):
            raise HaltError("Help. output operands must fit one byte")
        return ip + 1, "".join(map(chr, args))
    return (end if op == "end" else ip + 1), None


def _span(args: tuple[int, ...]) -> int:
    lo, hi = args
    if lo > hi:
        raise HaltError("Help. random interval is descending")
    return hi - lo + 1


def _store(memory: dict[int, int], dest: _Address, data: bytes) -> None:
    for address, byte in enumerate(data, dest.start):
        if byte:
            memory[address] = byte
        else:
            memory.pop(address, None)


def _write(memory: dict[int, int], dest: _Address, value: int) -> None:
    width = dest.width
    value %= 1 << (8 * width)
    _store(memory, dest, value.to_bytes(width, "little"))


def _arguments(instruction: _Instruction, memory: Mapping[int, int]) -> tuple[int, ...]:
    return tuple(
        operand
        if isinstance(operand, int)
        else int.from_bytes(
            bytes(memory.get(operand.start + i, 0) for i in range(operand.width)),
            "little",
        )
        for operand in instruction.operands
    )


class _Machine:
    def __init__(
        self, code: tuple[_Instruction, ...], io: IO, rng: Randomness | None
    ) -> None:
        self.code = code
        self.io = io
        self.rng = rng
        self.memory: dict[int, int] = {}
        self.pc = self.draws = 0
        self._rejected = RejectedInput()
        self._writer = _BufferedOutput()

    @property
    def halted(self) -> bool:
        return self.pc >= len(self.code)

    @property
    def ip(self) -> int | None:
        return None if self.halted else self.pc

    def _state(self) -> tuple[Hashable, ...]:
        cursor = self._rejected.cursor(self.io.progress())
        accepted = self._writer.accepted
        return (
            self.pc,
            tuple(sorted(self.memory.items())),
            cursor
            if accepted is None
            else WorkspaceVariant("pending_output", (cursor, accepted)),
            self.draws,
        )

    def snapshot(self) -> tuple[object, ...]:
        return self._rejected.snapshot(self._state())

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(_WORKSPACE, self._state())

    def branching_snapshot(self) -> _Branch:
        self._rejected.raise_if_rejected()
        return self.pc, tuple(sorted(self.memory.items()))

    def branching_halted(self, state: _Branch) -> bool:
        return state[0] >= len(self.code)

    def branching_successors(
        self, state: _Branch, limit: int
    ) -> tuple[_Branch, ...] | None:
        """Enumerate bounded draws. A read cannot fork a live input stream."""
        pc, cells = state
        if limit < 1:
            return None
        if self.branching_halted(state):
            return (state,)
        instruction = self.code[pc]
        op, dest = instruction.operation, instruction.destination
        if op in _READS:
            return None
        memory = dict(cells)
        args = _arguments(instruction, memory)
        if op == "rnd":
            span = _span(args)
            if span > limit:
                return None
            assert dest is not None
            result = []
            for offset in range(span):
                _write(memory, dest, args[0] + offset)
                result.append((pc + 1, tuple(sorted(memory.items()))))
            return tuple(result)
        pc, result_value = _advance(op, args, pc, len(self.code))
        if dest is not None:
            assert isinstance(result_value, int)
            _write(memory, dest, result_value)
        return ((pc, tuple(sorted(memory.items()))),)

    def _input(self, op: str) -> bytes:
        text = chr(self.io.input_char()) if op == "one" else self.io.input_str()
        try:
            return text.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise ArgumentError("Help. input characters must fit one byte") from exc

    def step(self) -> None:
        if self.halted:
            return
        instruction = self.code[self.pc]
        op, dest = instruction.operation, instruction.destination
        if op in _READS:
            assert dest is not None
            data = self._rejected.read(self.io, partial(self._input, op))
            _store(self.memory, dest, data)
            self.pc += 1
            return
        args = _arguments(instruction, self.memory)
        if op == "rnd":
            assert dest is not None
            _write(self.memory, dest, args[0] + draw(self.rng, _span(args)))
            self.pc += 1
            self.draws += 1
            return
        pc, value = _advance(op, args, self.pc, len(self.code))
        if dest is not None:
            assert isinstance(value, int)
            _write(self.memory, dest, value)
        elif isinstance(value, str):
            self._writer.write(self.io, value)
        self.pc = pc


def _program(source: str) -> tuple[_Instruction, ...]:
    return tuple(map(_parse_line, source.splitlines()))


def _drive(
    code: tuple[_Instruction, ...], io: IO, rng: Randomness | None
) -> CompletionReport:
    return drive(_Machine(code, io, rng), policy=Completion.HALTED)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain decoded instructions and bind a fresh machine per invocation."""
    if not isinstance(source, str):
        raise TypeError("Help. requires text source")
    if options.keys() - {"rng"}:
        raise TypeError("Help. accepts only the rng runtime option")
    code = _program(source)
    return RandomRuntimePlan(partial(_Machine, code), partial(_drive, code)).bind(
        options.get("rng")
    )


def _execute(code: str, io: IO, rng: Randomness | None = None) -> CompletionReport:
    return _drive(_program(code), io, rng)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Execute a Help. program."""
    _execute(code, io, rng)


if __name__ == "__main__":
    script_main(run)
