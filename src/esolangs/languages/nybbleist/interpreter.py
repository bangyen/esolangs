"""Nybbleist stores four-bit values in X, Y and a shared stack/queue.

Commands:
    * pushes at the back, < removes from the front and > from the back.
    ? reads and ! writes a nybble. +, -, ^ and & add, subtract, XOR
    and NAND modulo 16. $ swaps the registers. : defines a label,
    # jumps, % jumps on an empty deque and ~ divides a register by
    two and jumps on an odd remainder. @ halts.
    Brackets run with a fresh deque and restore the caller's deque.
    A label after ] makes the block callable. | restores the deque
    from that block's previous completion.

Input/output:
    Bytes are split and joined high nybble first, as in the ASCII
    examples. One text code point represents each byte.

Errors:
    ProgramError: malformed commands, labels or brackets.
    ArgumentError: input code points outside the byte range.
    InputExhaustedError: a read at EOF.
    HaltError: removing from an empty deque or jumping to a missing label.

Decisions:
    Whitespace is ignored and registers start at zero. Labels are local
    to their bracket scope and resolve after the division in ~. A named
    bracket also executes when reached in order, and | starts with empty
    history. An odd final output nybble is padded with a low zero. The
    wiki's shorter ASCII decrement tests X, so input @ prints O under
    the stated instructions. The longer example prints the preceding ?.
"""

from __future__ import annotations

from collections import deque
from functools import partial
from operator import add, sub, xor
from typing import TYPE_CHECKING, NamedTuple

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.languages.nybbleist.syntax import DIGITS, VARIABLES, parse
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._state import WorkspaceModel, WorkspaceVariant
from esolangs.runtime.io import _BufferedOutput

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from typing import Any

    from esolangs.languages.nybbleist.syntax import Instruction, Program
    from esolangs.runtime._lifecycle import CompletionReport
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime._state import WorkspaceSnapshot
    from esolangs.runtime.io import IO

_WORKSPACE = WorkspaceModel(
    "nybbleist-v1",
    ("ip", "registers", "deque", "frames", "history", "buffers", "input_cursor"),
)
_ARITHMETIC: dict[str, Callable[[int, int], int]] = {
    "+": add,
    "-": sub,
    "^": xor,
    "&": lambda left, right: ~(left & right),
}

type Registers = tuple[int, int]


class _Frame(NamedTuple):
    resume: int
    stack: deque[int]


def _value(symbol: str, regs: Registers) -> int:
    return regs[VARIABLES.index(symbol)] if symbol in VARIABLES else int(symbol, 16)


def _store(symbol: str, value: int, regs: Registers) -> Registers:
    return (value, regs[1]) if symbol == "X" else (regs[0], value)


def _advance(op: str, args: str, regs: Registers) -> tuple[Registers, bool]:
    """Apply register instructions and return whether a shift branches."""
    if op == "$":
        return (regs[1], regs[0]), False
    register = args[0]
    left = _value(register, regs)
    if op == "~":
        return _store(register, left >> 1, regs), bool(left & 1)
    right = _value(args[1], regs)
    return _store(register, _ARITHMETIC[op](left, right) & 15, regs), False


class _Machine:
    ip_shape = "opaque"

    def __init__(self, program: Program, io: IO) -> None:
        self.program = program
        self.io = io
        self.pc = 0
        self._registers: Registers = (0, 0)
        self._stack: deque[int] = deque()
        self._frames: list[_Frame] = []
        self._history: dict[int, deque[int]] = {}
        self._incoming: int | None = None
        self._outgoing: int | None = None
        self._rejected = RejectedInput()
        self._writer = _BufferedOutput()

    @property
    def halted(self) -> bool:
        return self.pc >= len(self.program.code) and self._outgoing is None

    @property
    def ip(self) -> int | None:
        return self.pc if self.pc < len(self.program.code) else None

    @property
    def memory(self) -> dict[str, int]:
        return dict(zip(VARIABLES, self._registers, strict=True))

    @property
    def stack(self) -> tuple[int, ...]:
        return tuple(self._stack)

    def snapshot(self) -> tuple[object, ...]:
        return self._rejected.snapshot(self.workspace_snapshot().parts)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        buffers = (self._incoming, self._outgoing)
        return _WORKSPACE.capture(
            ip=self.pc,
            registers=self._registers,
            deque=self.stack,
            frames=tuple((frame.resume, tuple(frame.stack)) for frame in self._frames),
            history=tuple(
                (scope, tuple(stack)) for scope, stack in sorted(self._history.items())
            ),
            buffers=(
                buffers
                if self._writer.accepted is None
                else WorkspaceVariant(
                    "pending_output", (*buffers, self._writer.accepted)
                )
            ),
            input_cursor=self._rejected.cursor(self.io.progress()),
        )

    def _read_byte(self) -> int:
        value = self.io.input_char()
        if value > 255:
            raise ArgumentError("Nybbleist input must be a byte")
        return value

    def _read(self) -> int:
        if self._incoming is not None:
            value, self._incoming = self._incoming, None
            return value
        value = self._rejected.read(self.io, self._read_byte)
        self._incoming = value & 15
        return value >> 4

    def _write(self, value: int) -> None:
        if self._outgoing is None:
            self._outgoing = value
        else:
            self._writer.write(self.io, chr(self._outgoing * 16 + value))
            self._outgoing = None

    def _enter(self, resume: int) -> None:
        self._frames.append(_Frame(resume, self._stack))
        self._stack = deque()

    def _jump(self, scope: int, label: str, regs: Registers) -> int:
        name = "".join(DIGITS[_value(symbol, regs)] for symbol in label)
        target = self.program.labels[scope].get(name)
        if target is None:
            raise HaltError(f"Nybbleist label {name} is missing in this scope")
        if target.call:
            self._enter(self.pc + 1)
        return target.destination

    def _transfer(self, instruction: Instruction) -> int:
        op, args, scope, resume = instruction
        match op:
            case "[":
                self._enter(resume)
            case "]":
                self._history[scope] = self._stack
                frame = self._frames.pop()
                self._stack = frame.stack
                return frame.resume
            case "|":
                self._stack = deque(self._history.get(scope, ()))
            case "#" | "%" if op == "#" or not self._stack:
                return self._jump(scope, args, self._registers)
            case "~":
                regs, taken = _advance(op, args, self._registers)
                target = self._jump(scope, args[1:], regs) if taken else self.pc + 1
                self._registers = regs
                return target
            case "@":
                return len(self.program.code)
        return self.pc + 1

    def _data(self, op: str, args: str) -> None:
        match op:
            case "?":
                self._registers = _store(args, self._read(), self._registers)
            case "!":
                self._write(_value(args, self._registers))
            case "*":
                self._stack.append(_value(args, self._registers))
            case "<" | ">":
                if not self._stack:
                    raise HaltError("Nybbleist cannot remove from an empty deque")
                value = self._stack.popleft() if op == "<" else self._stack.pop()
                self._registers = _store(args, value, self._registers)
            case _:
                self._registers, _ = _advance(op, args, self._registers)

    def step(self) -> None:
        if self.pc < len(self.program.code):
            instruction = self.program.code[self.pc]
            if instruction.op in "[]|#%~@":
                self.pc = self._transfer(instruction)
            else:
                self._data(instruction.op, instruction.args)
                self.pc += 1
        # Control has advanced, so a failed flush retries only the padding.
        if self.pc >= len(self.program.code) and self._outgoing is not None:
            self._write(0)


def _drive(program: Program, io: IO) -> CompletionReport:
    return drive(_Machine(program, io), policy=Completion.HALTED)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Bind scope and jump targets once, with a fresh deque on each run."""
    if not isinstance(source, str) or options:
        raise TypeError("Nybbleist requires text source without runtime options")
    program = parse(source)
    return RuntimePlan(partial(_Machine, program), partial(_drive, program))


def _execute(code: str, io: IO) -> CompletionReport:
    return _drive(parse(code), io)


def run(code: str, io: IO) -> None:
    """Execute a Nybbleist program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
