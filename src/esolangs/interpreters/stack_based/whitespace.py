r"""Interpreter for Whitespace.

Whitespace encodes an imperative stack machine in space, tab and line feed
alone; every other character is ignored.  Commands are grouped by an
Instruction Modification Parameter -- ``[Space]`` stack, ``[Tab][Space]``
arithmetic, ``[Tab][Tab]`` heap, ``[Tab][LineFeed]`` I/O, ``[LineFeed]``
flow -- with numbers and labels written in the same two tokens.

A program that ends inside a command, or names a label that never appears,
raises :class:`ValueError`; division or modulo by zero, an out-of-range copy,
and a return without a call raise :class:`~esolangs.exceptions.HaltError`.
EOF propagates from a read.  Integer division truncates toward zero, the
reference implementation's behaviour the wiki leaves unstated.
"""

from __future__ import annotations

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_SPACE, _TAB, _LINE = " ", "\t", "\n"
type _Instruction = tuple[str, int | str]
type _State = tuple[
    int, tuple[int, ...], tuple[tuple[int, int], ...], tuple[int, ...], bool
]
type _Effect = tuple[str, int] | None


def _read_heap(heap: tuple[tuple[int, int], ...], address: int) -> int:
    return next((value for index, value in heap if index == address), 0)


def _write_heap(
    heap: tuple[tuple[int, int], ...], address: int, value: int
) -> tuple[tuple[int, int], ...]:
    updated = dict(heap)
    if value:
        updated[address] = value
    else:
        updated.pop(address, None)
    return tuple(sorted(updated.items()))


def _pop(stack: tuple[int, ...]) -> tuple[int, tuple[int, ...]]:
    if not stack:
        raise HaltError("the stack is empty, so there is no top to pop")
    return stack[-1], stack[:-1]


def _trunc_div(left: int, right: int) -> int:
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) != (right < 0) else quotient


def _parse(code: str) -> tuple[list[_Instruction], list[int]]:
    """Return the instruction stream and each instruction's source offset."""
    tokens = [(index, char) for index, char in enumerate(code) if char in "\t\n "]
    cursor = 0
    count = len(tokens)

    def take() -> str:
        nonlocal cursor
        if cursor >= count:
            raise ValueError("Whitespace program ends inside an instruction")
        char = tokens[cursor][1]
        cursor += 1
        return char

    def number() -> int:
        negative = take() == _TAB
        value = 0
        while (bit := take()) != _LINE:
            value = value * 2 + (1 if bit == _TAB else 0)
        return -value if negative else value

    def label() -> str:
        chars = []
        while (char := take()) != _LINE:
            chars.append(char)
        return "".join(chars)

    instructions: list[_Instruction] = []
    offsets: list[int] = []
    while cursor < count:
        offsets.append(tokens[cursor][0])
        memory = take()
        if memory == _SPACE:
            command = take()
            if command == _SPACE:
                instructions.append(("push", number()))
            elif command == _LINE:
                kind = {_SPACE: "dup", _TAB: "swap", _LINE: "discard"}[take()]
                instructions.append((kind, 0))
            elif take() == _SPACE:
                instructions.append(("copy", number()))
            else:
                instructions.append(("slide", number()))
        elif memory == _TAB:
            command = take()
            if command == _LINE:
                kind = {
                    (_SPACE, _SPACE): "out_char",
                    (_SPACE, _TAB): "out_num",
                    (_TAB, _SPACE): "read_char",
                    (_TAB, _TAB): "read_num",
                }[(take(), take())]
                instructions.append((kind, 0))
            elif command == _TAB:
                instructions.append(({_SPACE: "store", _TAB: "retrieve"}[take()], 0))
            else:
                kind = {
                    (_SPACE, _SPACE): "add",
                    (_SPACE, _TAB): "sub",
                    (_SPACE, _LINE): "mul",
                    (_TAB, _SPACE): "div",
                    (_TAB, _TAB): "mod",
                }[(take(), take())]
                instructions.append((kind, 0))
        else:
            command = take()
            if command == _SPACE:
                instructions.append(
                    ({_SPACE: "mark", _TAB: "call", _LINE: "jump"}[take()], label())
                )
            elif command == _TAB:
                sub = take()
                if sub == _LINE:
                    instructions.append(("return", 0))
                else:
                    instructions.append(({_SPACE: "jz", _TAB: "jn"}[sub], label()))
            else:
                if take() != _LINE:
                    raise ValueError("Whitespace has no flow command with that prefix")
                instructions.append(("end", 0))
    return instructions, offsets


def _advance(
    state: _State,
    instructions: list[_Instruction],
    labels: dict[str, int],
    char_input: int | None = None,
    number_input: int | None = None,
) -> tuple[_State, _Effect]:
    """Return the next state and an output effect, if this command emits."""
    pc, stack, heap, calls, done = state
    if done:
        return state, None
    kind, *rest = instructions[pc]
    argument: int | str = rest[0] if rest else 0
    effect, jump = None, pc + 1

    if kind == "push":
        stack = (*stack, int(argument))
    elif kind == "dup":
        value, _ = _pop(stack)
        stack = (*stack, value, value)
    elif kind == "swap":
        first, stack = _pop(stack)
        second, stack = _pop(stack)
        stack = (*stack, first, second)
    elif kind == "discard":
        _, stack = _pop(stack)
    elif kind == "copy":
        depth = int(argument)
        if not 0 <= depth < len(stack):
            raise HaltError(
                f"'copy' asked for item {depth} of a {len(stack)}-item stack"
            )
        stack = (*stack, stack[-1 - depth])
    elif kind == "slide":
        depth = int(argument)
        if not stack:
            raise HaltError("'slide' needs a top item, and the stack is empty")
        below = stack[:-1]
        stack = (*(below[: max(0, len(below) - depth)]), stack[-1])
    elif kind in {"add", "sub", "mul", "div", "mod"}:
        right, stack = _pop(stack)
        left, stack = _pop(stack)
        if kind == "add":
            stack = (*stack, left + right)
        elif kind == "sub":
            stack = (*stack, left - right)
        elif kind == "mul":
            stack = (*stack, left * right)
        elif not right:
            raise HaltError(f"'{kind}' divides by zero")
        elif kind == "div":
            stack = (*stack, _trunc_div(left, right))
        else:
            stack = (*stack, left - _trunc_div(left, right) * right)
    elif kind == "store":
        value, stack = _pop(stack)
        address, stack = _pop(stack)
        heap = _write_heap(heap, address, value)
    elif kind == "retrieve":
        address, stack = _pop(stack)
        stack = (*stack, _read_heap(heap, address))
    elif kind in {"out_char", "out_num"}:
        value, stack = _pop(stack)
        effect = ("char", value & 0xFF) if kind == "out_char" else ("num", value)
    elif kind == "read_char":
        address, stack = _pop(stack)
        if char_input is None:
            raise HaltError("'read_char' reads and there is no input left")
        heap = _write_heap(heap, address, char_input)
    elif kind == "read_num":
        address, stack = _pop(stack)
        if number_input is None:
            raise HaltError("'read_num' reads and there is no input left")
        heap = _write_heap(heap, address, number_input)
    elif kind == "mark":
        pass
    elif kind in {"call", "jump", "jz", "jn"}:
        target = labels.get(str(argument))
        if target is None:
            raise HaltError(f"'{kind}' names the undefined label {argument!r}")
        if kind == "call":
            calls = (*calls, pc + 1)
            jump = target
        elif kind == "jump":
            jump = target
        else:
            value, stack = _pop(stack)
            if (value == 0) if kind == "jz" else (value < 0):
                jump = target
    elif kind == "return":
        if not calls:
            raise HaltError("'return' ran with no call to return from")
        jump, calls = calls[-1], calls[:-1]
    else:
        done = True
    return (jump, stack, heap, calls, done), effect


class _Machine:
    """Protocol shell holding one immutable Whitespace state value."""

    def __init__(self, code: str, io: IO) -> None:
        self.instructions, self.offsets = _parse(code)
        if not self.instructions:
            raise ValueError("Whitespace program is empty")
        self.io = io
        self.labels = {
            str(instruction[1]): index
            for index, instruction in enumerate(self.instructions)
            if instruction[0] == "mark"
        }
        self.state: _State = (0, (), (), (), False)

    @property
    def halted(self) -> bool:
        return self.state[4]

    #: The position is a character offset into the source a caller handed in,
    #: so the debugger can mark the token the pointer stands on.
    ip_shape = "offset"

    @property
    def ip(self) -> int | None:
        return None if self.halted else self.offsets[self.state[0]]

    @property
    def memory(self) -> list[int]:
        """The heap is indexed by popped addresses, not a flat store view."""
        return []

    @property
    def stack(self) -> list[object]:
        return list(self.state[1])

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.position())

    def step(self) -> None:
        if self.halted:
            return
        kind = self.instructions[self.state[0]][0]
        char_input = self.io.input_char() if kind == "read_char" else None
        number_input = self.io.input_num() if kind == "read_num" else None
        self.state, effect = _advance(
            self.state, self.instructions, self.labels, char_input, number_input
        )
        if effect:
            out_kind, value = effect
            if out_kind == "char":
                self.io.print_char(chr(value))
            else:
                self.io.print_num(value)


def run(code: str, io: IO) -> None:
    """Execute a Whitespace program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
