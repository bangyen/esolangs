"""NB uses case-insensitive N/B tokens and unary `NB` literals.

Commands:
    B and BNB read into variables beginning with NN. N and NBN print
    a character or an integer. Infix runs of four, five and six Bs
    add, subtract and multiply. BB/BN loop while an operand is nonzero.
    NBB ends with BNB, or uses BNN and BBB to select an else arm.

Input/output:
    Character I/O takes ASCII. Integer input takes a signed decimal token.
    Integer output has no separator.

Errors:
    ProgramError: invalid tokens, operands or block delimiters.
    InputExhaustedError: a read at EOF.
    ArgumentError: non-ASCII input or a malformed integer input token.
    HaltError: character output outside ASCII.

Decisions:
    Whitespace separates tokens. Within a simple if, BNB is an integer
    read when it has a variable operand. A variable followed by an
    arithmetic operator begins the statement after the closing BNB.
    Variables start at zero and hold unbounded signed integers. Zero
    is computed since an empty token cannot spell a unary literal.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import partial
from operator import add, mul, sub
from typing import TYPE_CHECKING, NamedTuple

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import _BufferedOutput
from esolangs.runtime.memory import format_integer
from esolangs.runtime.source_hints import syntax_error

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping
    from typing import Any

    from esolangs.runtime._lifecycle import CompletionReport
    from esolangs.runtime._program import RunnerProgram
    from esolangs.runtime.io import IO

_VARIABLE = re.compile(r"NN[NB]*")
_UNARY = re.compile(r"(?:NB)+")
_ARITHMETIC: dict[str, Callable[[int, int], int]] = {
    "BBBB": add,
    "BBBBB": sub,
    "BBBBBB": mul,
}
_WORKSPACE = WorkspaceModel("nb-v1", ("ip", "variables", "input_cursor"))

type _Operand = int | str


class _Instruction(NamedTuple):
    code: str
    operand: _Operand = 0
    variable: str = ""
    target: int = 0


def _syntax(message: str) -> ValueError:
    return syntax_error(f"NB {message}", "separate N/B tokens and close each block")


def _operand(token: str) -> _Operand:
    if _VARIABLE.fullmatch(token):
        return token
    if _UNARY.fullmatch(token):
        return len(token) // 2
    raise _syntax(f"expected a number or variable, got {token!r}")


def _parse(source: str) -> tuple[_Instruction, ...]:
    tokens = [*source.upper().split(), "", ""]
    code: list[_Instruction] = []
    blocks: list[int] = []

    def close(expected: str, delimiter: str) -> int:
        if not blocks or code[blocks[-1]].code != expected:
            raise _syntax(f"{delimiter} has no matching {expected}")
        return blocks.pop()

    def target(index: int) -> None:
        instruction = code[index]
        code[index] = _Instruction(
            instruction.code, instruction.operand, instruction.variable, len(code)
        )

    pos = 0
    while token := tokens[pos]:
        following = tokens[pos + 1]
        match token:
            case "BN":
                opener = close("BB", token)
                code.append(_Instruction("BN", target=opener))
                target(opener)
            case "BNN":
                opener = close("NBB", token)
                blocks.append(len(code))
                code.append(_Instruction("BNN"))
                target(opener)
            case "BBB":
                target(close("BNN", token))
            case "BNB" if (
                blocks
                and code[blocks[-1]].code == "NBB"
                and (
                    not _VARIABLE.fullmatch(following) or tokens[pos + 2] in _ARITHMETIC
                )
            ):
                target(close("NBB", token))
            case "B" | "BNB":
                if not _VARIABLE.fullmatch(following):
                    raise _syntax(f"{token} requires a variable")
                code.append(_Instruction(token, variable=following))
                pos += 1
            case "BB" | "NBB" | "N" | "NBN":
                if token in {"BB", "NBB"}:
                    blocks.append(len(code))
                code.append(_Instruction(token, _operand(following)))
                pos += 1
            case _:
                if not _VARIABLE.fullmatch(token) or following not in _ARITHMETIC:
                    raise _syntax(f"unknown instruction at {token!r}")
                code.append(_Instruction(following, _operand(tokens[pos + 2]), token))
                pos += 2
        pos += 1
    if blocks:
        raise _syntax(f"unclosed {code[blocks[-1]].code} block")
    return tuple(code)


def _advance(
    op: str, value: int, current: int, pc: int, target: int
) -> tuple[int, int | None]:
    """Return the next instruction and any arithmetic store."""
    if op in {"BN", "BNN"} or (op in {"BB", "NBB"} and not value):
        return target, None
    update = _ARITHMETIC[op](current, value) if op in _ARITHMETIC else None
    return pc + 1, update


class _Machine:
    ip_shape = "opaque"

    def __init__(self, code: tuple[_Instruction, ...], io: IO) -> None:
        self.code = code
        self.io = io
        self.pc = 0
        self.memory: dict[str, int] = {}
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
        return self.pc, tuple(sorted(self.memory.items())), cursor

    def snapshot(self) -> tuple[object, ...]:
        return self._rejected.snapshot(self._state())

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        return WorkspaceSnapshot(_WORKSPACE, self._state())

    def _read_char(self) -> int:
        char = self.io.input_char()
        if char > 127:
            raise ArgumentError("NB character input requires ASCII")
        return char

    def step(self) -> None:
        if self.halted:
            return
        op, operand, variable, target = self.code[self.pc]
        value = operand if isinstance(operand, int) else self.memory.get(operand, 0)
        next_pc, update = _advance(
            op, value, self.memory.get(variable, 0), self.pc, target
        )
        if op in {"B", "BNB"}:
            read = self._read_char if op == "B" else self.io.input_num
            self.memory[variable] = self._rejected.read(self.io, read)
        elif op == "N":
            if not 0 <= value <= 127:
                raise HaltError("NB character output requires ASCII")
            self._writer.write(self.io, chr(value))
        elif op == "NBN":
            self._writer.write(self.io, format_integer(value))
        elif update is not None:
            self.memory[variable] = update
        self.pc = next_pc


def _drive(code: tuple[_Instruction, ...], io: IO) -> CompletionReport:
    return drive(_Machine(code, io), policy=Completion.HALTED)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Compile delimiters once and allocate fresh state for each run."""
    if not isinstance(source, str) or options:
        raise TypeError("NB requires text source without runtime options")
    code = _parse(source)
    return RuntimePlan(partial(_Machine, code), partial(_drive, code))


def _execute(code: str, io: IO) -> CompletionReport:
    return _drive(_parse(code), io)


def run(code: str, io: IO) -> None:
    """Execute an NB program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
