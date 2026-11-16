"""Onecode (Fergusq) uses integer variables and addressed memory.

Commands:
    Expressions assign with `~`, dereference with `*`, and use integer
    arithmetic, comparisons and Boolean operators. Lists and NUL-terminated
    strings initialize consecutive cells. Labels and conditional or
    unconditional gotos redirect execution.

Input/output:
    Getc reads a Unicode code point. Getn reads a signed decimal token.
    Putc writes one character and putn writes decimal without a separator.

Errors:
    ProgramError: malformed syntax or bad labels.
    InputExhaustedError: an input request at EOF.
    ArgumentError: a getn token is not an integer.
    HaltError: division by zero, a list used as an integer, or invalid output.

Decisions:
    The operator table sets precedence. Operands evaluate left to right.
    Integers are unbounded and division truncates toward zero. Unset variables
    and cells read zero. A memory store returns its first value or zero for
    an empty list. Output calls return zero. Falling off the end halts.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import partial
from operator import add, mul, sub
from typing import TYPE_CHECKING

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.languages.onecode_fergusq._syntax import Op, _Value, parse
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import _BufferedOutput
from esolangs.runtime.memory import format_integer, parse_integer, trunc_div

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping
    from typing import Any

    from esolangs.runtime._lifecycle import CompletionReport
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime.io import IO

_BINARY: dict[str, Callable[[int, int], int]] = {
    "+": add,
    "-": sub,
    "*": mul,
    "/": trunc_div,
    "=": lambda a, b: int(a == b),
    "<": lambda a, b: int(a < b),
    ">": lambda a, b: int(a > b),
    "&": lambda a, b: int(bool(a) and bool(b)),
    "|": lambda a, b: int(bool(a) or bool(b)),
    "^": lambda a, b: int(bool(a) != bool(b)),
}
_DECIMAL = re.compile(r"[+-]?[0-9]+")
_WORKSPACE = WorkspaceModel(
    "onecode-fergusq-v1", ("ip", "variables", "memory", "stack", "input_cursor")
)


def _scalar(value: _Value) -> int:
    if not isinstance(value, int):
        raise HaltError("Onecode requires an integer here")
    return value


def _advance(operator: str, left: _Value, right: _Value) -> int:
    """Evaluate a binary operator without changing the machine."""
    a, b = _scalar(left), _scalar(right)
    if operator == "/" and b == 0:
        raise HaltError("Onecode division by zero")
    return _BINARY[operator](a, b)


def _putc(code: int) -> str:
    if not 0 <= code <= 0x10FFFF or 0xD800 <= code <= 0xDFFF:
        raise HaltError("Onecode putc requires a Unicode scalar")
    return chr(code)


def _store[K](memory: dict[K, int], address: K, value: int) -> None:
    if value:
        memory[address] = value
    else:
        memory.pop(address, None)


class _Machine:
    """Postfix instructions put an I/O boundary at each input or output."""

    ip_shape = "opaque"

    def __init__(self, code: tuple[Op, ...], io: IO) -> None:
        self.code = code
        self.io = io
        self.pc = 0
        self.variables: dict[str, int] = {}
        self.memory: dict[int, int] = {}
        self.stack: list[_Value] = []
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
        if self._writer.accepted is not None:
            cursor = WorkspaceVariant("pending_output", (cursor, self._writer.accepted))
        return (
            self.pc,
            tuple(sorted(self.variables.items())),
            tuple(sorted(self.memory.items())),
            tuple(self.stack),
            cursor,
        )

    def snapshot(self) -> tuple[object, ...]:
        return self._rejected.snapshot(self._state())

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(_WORKSPACE, self._state())

    def _getn(self) -> int:
        token = self.io.input_token()
        if not _DECIMAL.fullmatch(token):
            raise ArgumentError("Onecode getn requires a signed decimal integer")
        return parse_integer(token)

    def step(self) -> None:
        if self.halted:
            return
        op, arg = self.code[self.pc]
        stack = self.stack
        match op:
            case "literal":
                assert not isinstance(arg, str)
                stack.append(arg)
            case "pack":
                assert isinstance(arg, int)
                start = len(stack) - arg
                stack[start:] = [tuple(_scalar(value) for value in stack[start:])]
            case "load_var":
                assert isinstance(arg, str)
                stack.append(self.variables.get(arg, 0))
            case "store_var":
                assert isinstance(arg, str)
                _store(self.variables, arg, _scalar(stack[-1]))
            case "load_cell":
                stack[-1] = self.memory.get(_scalar(stack[-1]), 0)
            case "store_cell":
                address, value = _scalar(stack[-2]), stack[-1]
                cells = (value,) if isinstance(value, int) else value
                for index, cell in enumerate(cells, address):
                    _store(self.memory, index, cell)
                stack[-2:] = [cells[0] if cells else 0]
            case "getc" | "getn":
                read = self.io.input_char if op == "getc" else self._getn
                stack.append(self._rejected.read(self.io, read))
            case "putc" | "putn":
                value = _scalar(stack[-1])
                text = _putc(value) if op == "putc" else format_integer(value)
                self._writer.write(self.io, text)
                stack[-1] = 0
            case "not":
                stack[-1] = int(not _scalar(stack[-1]))
            case "neg":
                stack[-1] = -_scalar(stack[-1])
            case "jump":
                assert isinstance(arg, int)
                self.pc = arg
                return
            case "jump_if":
                branch = _scalar(stack[-1])
                stack.pop()
                if branch:
                    assert isinstance(arg, int)
                    self.pc = arg
                    return
            case "discard":
                stack.pop()
            case _:
                stack[-2:] = [_advance(op, stack[-2], stack[-1])]
        self.pc += 1


def _drive(code: tuple[Op, ...], io: IO) -> CompletionReport:
    return drive(_Machine(code, io), policy=Completion.HALTED)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain parsed source and allocate fresh state for every invocation."""
    if not isinstance(source, str) or options:
        raise TypeError("Onecode requires text source without runtime options")
    code = parse(source)
    return RuntimePlan(partial(_Machine, code), partial(_drive, code))


def _execute(code: str, io: IO) -> CompletionReport:
    return _drive(parse(code), io)


def run(code: str, io: IO) -> None:
    """Execute a standalone Onecode program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
