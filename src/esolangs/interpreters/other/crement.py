"""Pure-core interpreter for Crement.

Each instruction stores an opcode, polarity, address, and data. ``ADDRESS``
and ``DATA`` copy their own data plus or minus one into another instruction;
``JUMP`` branches when its data has the selected sign. Execution past the
program halts. Negative instruction addresses are undefined and raise
:class:`~esolangs.exceptions.HaltError`.

The execution model is :func:`_advance`, a pure function over an immutable
program and instruction pointer. The mutable VM shell only replaces that
state once per step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from esolangs.exceptions import HaltError, ProgramError
from esolangs.interpreters.io import IO

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPERATOR = re.compile(r"([+-])([ADJ])")
_TERM = re.compile(r"([+-]?)(@|[0-9]+|[A-Za-z_][A-Za-z0-9_]*)")


@dataclass(frozen=True)
class _Instruction:
    """One resolved Crement instruction."""

    opcode: str
    polarity: int
    address: int
    data: int


@dataclass(frozen=True)
class _State:
    """Crement's immutable instruction pointer and self-modifying program."""

    ip: int
    program: tuple[_Instruction, ...]


def _number(source: str, labels: dict[str, int], here: int) -> int:
    """Resolve one signed sum of literals, labels, and ``@``."""
    position = 0
    value = 0
    terms = 0
    while position < len(source):
        match = _TERM.match(source, position)
        if match is None or (position and not match.group(1)):
            raise ProgramError(f"invalid number: {source}")
        sign, atom = match.groups()
        if atom == "@":
            term = here
        elif atom.isdigit():
            term = int(atom)
        else:
            try:
                term = labels[atom]
            except KeyError:
                raise ProgramError(f"undefined label: {atom}") from None
        value += -term if sign == "-" else term
        position = match.end()
        terms += 1
    if not terms:
        raise ProgramError("a number must contain at least one term")
    return value


def _source_lines(code: str) -> list[list[str]]:
    """Return tokenized instruction lines with comments removed."""
    return [
        stripped.split()
        for line in code.splitlines()
        if (stripped := line.split("*", 1)[0].strip())
    ]


def _parse(code: str) -> tuple[_Instruction, ...]:
    """Parse standard non-macro Crement source."""
    lines = _source_lines(code)
    labels: dict[str, int] = {}
    for address, tokens in enumerate(lines):
        if tokens[0].startswith(":"):
            label = tokens[0][1:]
            if not _NAME.fullmatch(label):
                raise ProgramError(f"invalid label: {label}")
            if label in labels:
                raise ProgramError(f"duplicate label: {label}")
            labels[label] = address

    program = []
    for address, tokens in enumerate(lines):
        fields = tokens[1:] if tokens[0].startswith(":") else tokens
        if len(fields) != 3:
            raise ProgramError(f"instruction {address} must have three fields")
        operator, address_source, data_source = fields
        match = _OPERATOR.fullmatch(operator)
        if match is None:
            raise ProgramError(f"invalid opcode: {operator}")
        sign, opcode = match.groups()
        program.append(
            _Instruction(
                opcode,
                1 if sign == "+" else -1,
                _number(address_source, labels, address),
                _number(data_source, labels, address),
            )
        )
    return tuple(program)


def _advance(state: _State) -> _State:
    """Return the next state without mutating ``state``."""
    if state.ip >= len(state.program):
        return state
    if state.ip < 0:
        raise HaltError(f"Crement executed negative address {state.ip}")

    instruction = state.program[state.ip]
    if instruction.opcode == "J":
        condition = instruction.data * instruction.polarity > 0
        target = instruction.address if condition else state.ip + 1
        if target < 0:
            raise HaltError(f"Crement jumped to negative address {target}")
        return _State(target, state.program)

    target = instruction.address
    program = state.program
    if target < 0:
        raise HaltError(f"Crement wrote to negative address {target}")
    if target < len(program):
        value = instruction.data + instruction.polarity
        changed = replace(
            program[target],
            address=value if instruction.opcode == "A" else program[target].address,
            data=value if instruction.opcode == "D" else program[target].data,
        )
        program = (*program[:target], changed, *program[target + 1 :])
    return _State(state.ip + 1, program)


class _Machine:
    """Mutable VM shell around Crement's pure transition."""

    def __init__(self, code: str, io: IO | None = None) -> None:
        self.io = io if io is not None else IO()
        self.state = _State(0, _parse(code))

    @property
    def halted(self) -> bool:
        """Whether execution has passed the final instruction."""
        return self.state.ip >= len(self.state.program)

    @property
    def ip(self) -> int:
        """Return the current instruction address."""
        return self.state.ip

    @property
    def memory(self) -> list[object]:
        """Return the self-modifying instruction store."""
        return list(self.state.program)

    @property
    def stack(self) -> list[object]:
        """Return Crement's empty stack."""
        return []

    def snapshot(self) -> _State:
        """Return the complete immutable execution state."""
        return self.state

    def step(self) -> None:
        """Advance one instruction."""
        self.state = _advance(self.state)


def run(code: str, io: IO) -> None:
    """Run a Crement program until it executes past its final instruction."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
