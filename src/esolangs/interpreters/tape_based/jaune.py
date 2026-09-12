r"""Interpreter for Jaune."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The two command shapes, kept.
# operator appears in both,.
# inside ``cmd.op == "?"`` the.
# that its ``arg`` is an.
# without testing what.
_CountedOp = Literal[
    "^", "v", "v+", "v-", "v?", "v!", "v@", ">", "<", "#", "&", "%", "+", "-", ";", "."
]
_NumberedOp = Literal[":", "?", "!", "$", "@"]

# Spelling the alphabets as.
# what lets ``in`` narrow a.
# constructors below take it.
_BARE: frozenset[_CountedOp] = frozenset(("^", ">", "<", "#", "&", "%", "."))
_NUMBERED: frozenset[_NumberedOp] = frozenset((":", "?", "!", "$", "@"))

# The grammar makes ``v`` a.
# it: ``v+``/``v-`` count,.
# ``v@`` names the subroutine.
# _Numbered carrying a runtime.
# a plain ``int`` and ``_find``.
# .
# ``v:`` and ``v$`` are.
# marker read at runtime has no.
# the parsed argument and the.
# execute.
# dropping them at parse keeps.
_READ_OPERAND: dict[str, _CountedOp] = {
    "+": "v+",
    "-": "v-",
    "?": "v?",
    "!": "v!",
    "@": "v@",
}
_READ_MARKER = ":$"


@dataclass
class _Counted:
    r"""A Jaune command with no operand, or with a repeat count."""

    op: _CountedOp
    arg: int | None = None


@dataclass
class _Numbered:
    r"""A Jaune command whose operator requires a number: ``:?!$@``."""

    op: _NumberedOp
    arg: int


_Command = _Counted | _Numbered


def _parse(code: str) -> list[_Command]:
    r"""Parse a program into commands, expanding counts and number operands."""
    out: list[_Command] = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in _BARE:
            out.append(_Counted(c))
            i += 1
        elif c == ";":
            out.append(_Counted(";"))
            i += 1
        elif c == "v":
            # 'v' reads a digit; as an.
            # count, and for 'v?'/'v!'/'v@'.
            if i + 1 < n and (read := _READ_OPERAND.get(code[i + 1])) is not None:
                out.append(_Counted(read))
                i += 2
            elif i + 1 < n and code[i + 1] in _READ_MARKER:
                i += 2  # a read marker defines.
            else:
                out.append(_Counted("v"))
                i += 1
        elif c in "+-":
            # a run like ++ is a counted.
            j = i
            while j < n and code[j] == c:
                j += 1
            count = j - i
            out.append(_Counted("+" if c == "+" else "-", count))
            i = j
        elif c.isdigit():
            j = i
            while j < n and code[j].isdigit():
                j += 1
            num = int(code[i:j])
            if j < n and (op := code[j]) in _NUMBERED:
                out.append(_Numbered(op, num))
                i = j + 1
            elif j < n and code[j] in "+-":
                # "-" reaches here as a counted.
                # the numbered operators above.
                out.append(_Counted("+" if code[j] == "+" else "-", num))
                i = j + 1
            else:
                # a bare number with no.
                i = j
        elif c in ":-?!$@":
            # a bare operator with no.
            raise ValueError(f"command {c!r} requires a number")
        else:
            i += 1  # ignore anything else.
    return out


# : One instant of a run:.
# : the cell pointer, the ``#``.
#: stack of return positions.
# :.
# : The commands and the label.
# : its program once and never.
#: than carrying them.
type _State = tuple[tuple[int, ...], int, int, int, tuple[int, ...]]


def _set(cells: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    r"""Return ``cells`` with the cell at ``ptr`` set to ``value``."""
    return (*cells[:ptr], value, *cells[ptr + 1 :])


def _find(commands: Sequence[_Command], op: str, num: int | None) -> int | None:
    r"""Return the index of the ``op`` marker whose argument is ``num``."""
    for i, cmd in enumerate(commands):
        if cmd.op == op and cmd.arg == num:
            return i
    return None


def _advance(
    state: _State,
    commands: Sequence[_Command],
    value: int | None = None,
) -> _State:
    r"""Return the state after executing ``cmd``."""
    cells, ptr, hold, pos, calls = state
    cmd = commands[pos]
    c = cmd.op

    if c == "^":
        pass  # printed by the caller; the.
    elif c == "v":
        cells = _set(cells, ptr, value if value is not None else 0)
    elif c in ("v+", "v-"):
        val = value if value is not None else 0
        cells = _set(cells, ptr, cells[ptr] + (val if c == "v+" else -val))
    elif c == ">":
        ptr += 1
        if ptr == len(cells):
            cells = (*cells, 0)
    elif c == "<":
        # Clamped at cell 0, as.
        # to insert a fresh cell and.
        # grew the tape leftward; the.
        # previous cell" and nothing.
        # gap, and clamping is the one.
        ptr = max(0, ptr - 1)
    elif c == "#":
        hold = cells[ptr]
    elif c == "&":
        cells = _set(cells, ptr, cells[ptr] + hold)
    elif c == "%":
        cells = _set(cells, ptr, 0)
    elif c == "+":
        cells = _set(cells, ptr, cells[ptr] + (cmd.arg or 1))
    elif c == "-":
        cells = _set(cells, ptr, cells[ptr] - (cmd.arg or 1))
    elif c == "?":
        target = _find(commands, ":", cmd.arg)
        if target is None:
            raise HaltError(f"jump to undefined label {cmd.arg}")
        if cells[ptr] != 0:
            return (cells, ptr, hold, target, calls)
    elif c == "!":
        target = _find(commands, ":", cmd.arg)
        if target is None:
            raise HaltError(f"jump to undefined label {cmd.arg}")
        if cells[ptr] == 0:
            return (cells, ptr, hold, target, calls)
    elif c == "@":
        target = _find(commands, "$", cmd.arg)
        if target is None:
            raise HaltError(f"call to undefined subroutine {cmd.arg}")
        return (cells, ptr, hold, target, (*calls, pos + 1))
    elif c in ("v?", "v!"):
        # The read names the label, so.
        # rather than a parsed one.
        # branch is taken -- the.
        # command at all -- so input.
        num = value if value is not None else 0
        target = _find(commands, ":", num)
        if target is None:
            raise HaltError(f"jump to undefined label {num}")
        taken = cells[ptr] != 0 if c == "v?" else cells[ptr] == 0
        if taken:
            return (cells, ptr, hold, target, calls)
    elif c == "v@":
        num = value if value is not None else 0
        target = _find(commands, "$", num)
        if target is None:
            raise HaltError(f"call to undefined subroutine {num}")
        return (cells, ptr, hold, target, (*calls, pos + 1))
    elif c == ";":
        if not calls:
            raise HaltError("; with no active subroutine call")
        return (cells, ptr, hold, calls[-1], calls[:-1])
    elif c == ".":
        return (cells, ptr, hold, len(commands), calls)
    # ":" and "$" are positions.
    # subroutine definition -- so.

    return (cells, ptr, hold, pos + 1, calls)


class _Machine:
    r"""One Jaune run: cells, pointer, hold cell, and parsed commands."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.commands = _parse(code)
        self.cells: tuple[int, ...] = (0,)
        self.ptr = 0
        self.hold = 0
        self.pos = 0
        self.call_stack: tuple[int, ...] = ()

    @property
    def halted(self) -> bool:
        return self.pos >= len(self.commands)

    # The VM's language-shaped.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.pos

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.cells)

    @property
    def stack(self) -> list[object]:
        r"""The stack."""
        return list(self.call_stack)

    @property
    def frames(self) -> tuple[int, ...]:
        r"""The live subroutine calls, outermost first."""
        return self.call_stack

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.pos,
            self.cells,
            self.ptr,
            self.hold,
            self.call_stack,
            self.io.position(),
        )

    def frame_entry_key(self, _frame: object) -> tuple[object, ...]:
        r"""Return the state a subroutine needs to replay an ancestor."""
        return (
            self.pos,
            self.cells,
            self.ptr,
            self.hold,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (
            self.cells,
            self.ptr,
            self.hold,
            self.pos,
            self.call_stack,
        )

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        self.cells, self.ptr, self.hold, self.pos, self.call_stack = state

    def step(self) -> None:
        r"""Execute one command, advancing (or jumping) the position."""
        if self.halted:
            return
        cmd = self.commands[self.pos]

        value = None
        if cmd.op == "^":
            self.io.print_num(self.cells[self.ptr])
        elif cmd.op in ("v", "v+", "v-", "v?", "v!", "v@"):
            ch = self.io.input_str()
            value = ord(ch[0]) - 48 if ch else 0

        self._restore(_advance(self._state, self.commands, value))


def run(code: str, io: IO) -> None:
    r"""Run a Jaune program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
