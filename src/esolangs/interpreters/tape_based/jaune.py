"""Interpreter for Jaune.

A brainfuck-like cell array with a hold cell.  ``^`` prints the cell as a
decimal, ``v`` reads a digit, ``>``/``<`` move, ``#`` copies to the hold,
``&`` adds it back, ``%`` zeroes, ``+``/``-`` with an optional count
adjust.  ``(number):`` labels, ``?``/``!`` jump when nonzero/zero, ``$``
defines a subroutine, ``@`` calls it, ``;`` returns, ``.`` ends the main
program.  A repeated command like ``^^`` is a counted command; ``v`` as an
operand reads a digit as the count or the label/subroutine name.

Gaps decided: ``v`` stores ``ord(c) - 48`` and raises :class:`EOFError`
at end of input; the tape is unbounded to the right and ``<`` at cell 0
clamps (the wiki says only "previous cell"; see Streetcode's ``_``);
cells are plain integers, as JauneJS's ``+=`` is; a read operand is
consumed whether or not the branch is taken and may name any integer;
``v:`` and ``v$`` define nothing and are dropped at parse, as the
compiler's ``prep`` does; an undefined label or subroutine, or ``;`` with
no active call, raises :class:`~esolangs.exceptions.HaltError`; a
command missing its required number is :class:`ValueError`; an infinite
loop is bounded by the caller's ``timeout``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.persistent import (
    Chunked,
    append,
    chunked,
    flatten,
    get,
    length,
    put,
)

# The two command shapes, kept apart by their operators.  Because no
# operator appears in both, comparing ``cmd.op`` discriminates the union:
# inside ``cmd.op == "?"`` the checker knows the command is a _Numbered and
# that its ``arg`` is an ``int``, so the jumps and the call read the operand
# without testing what :func:`_parse` has already guaranteed.
_CountedOp = Literal[
    "^", "v", "v+", "v-", "v?", "v!", "v@", ">", "<", "#", "&", "%", "+", "-", ";", "."
]
_NumberedOp = Literal[":", "?", "!", "$", "@"]

# Spelling the alphabets as typed containers rather than plain strings is
# what lets ``in`` narrow a parsed character to its operator type, so the
# constructors below take it directly instead of casting.
_BARE: frozenset[_CountedOp] = frozenset(("^", ">", "<", "#", "&", "%", "."))
_NUMBERED: frozenset[_NumberedOp] = frozenset((":", "?", "!", "$", "@"))

# The grammar makes ``v`` a ``number``, so every operator taking one admits
# it: ``v+``/``v-`` count, ``v?``/``v!`` name the label to jump to, and
# ``v@`` names the subroutine to call.  Each is its own op rather than a
# _Numbered carrying a runtime operand, which is what keeps ``_Numbered.arg``
# a plain ``int`` and ``_find`` matching against static markers only.
#
# ``v:`` and ``v$`` are admitted by the grammar and deliberately absent: a
# marker read at runtime has no findable identity, since ``_find`` matches
# the parsed argument and the markers are fall-through positions that never
# execute.  The compiler's ``prep`` strips both (``compilers/jaune.py``), so
# dropping them at parse keeps the two engines agreeing.
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
    """A Jaune command with no operand, or with a repeat count."""

    op: _CountedOp
    arg: int | None = None


@dataclass
class _Numbered:
    """A Jaune command whose operator requires a number: ``:?!$@``.

    :func:`_parse` raises on a bare one, so ``arg`` is a plain ``int``.
    """

    op: _NumberedOp
    arg: int


_Command = _Counted | _Numbered


def _parse(code: str) -> list[_Command]:
    """Parse a program into commands, expanding counts and number operands."""
    out: list[_Command] = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in "+-" and i + 1 < n and code[i + 1].isdigit():
            j = i + 1
            while j < n and code[j].isdigit():
                j += 1
            if j < n and (code[j] in _NUMBERED or code[j] in "+-"):
                num = int(code[i:j])
                op = code[j]
                if op in _NUMBERED:
                    out.append(_Numbered(op, num))
                elif op == "+":
                    out.append(_Counted("+", num))
                else:
                    out.append(_Counted("-", num))
                i = j + 1
            else:
                out.append(_Counted("+" if c == "+" else "-", 1))
                i += 1
        elif c in _BARE:
            out.append(_Counted(c))
            i += 1
        elif c == ";":
            out.append(_Counted(";"))
            i += 1
        elif c == "v":
            # 'v' reads a digit; as an operand ('v+') the read value is the
            # count, and for 'v?'/'v!'/'v@' the label or subroutine named.
            if i + 1 < n and (read := _READ_OPERAND.get(code[i + 1])) is not None:
                out.append(_Counted(read))
                i += 2
            elif i + 1 < n and code[i + 1] in _READ_MARKER:
                i += 2  # a read marker defines nothing: dropped, as prep does
            else:
                out.append(_Counted("v"))
                i += 1
        elif c in "+-":
            # a run like ++ is a counted command (repeat); a bare + is +1
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
                # "-" reaches here as a counted subtract, never as a jump:
                # the numbered operators above do not include it.
                out.append(_Counted("+" if code[j] == "+" else "-", num))
                i = j + 1
            else:
                # a bare number with no operator: ignore (no-op)
                i = j
        elif c in ":-?!$@":
            # a bare operator with no number: malformed
            raise ValueError(f"command {c!r} requires a number")
        else:
            i += 1  # ignore anything else
    return out


#: One instant of a run: ``(cells, ptr, hold, pos, calls)`` -- the tape,
#: the cell pointer, the ``#`` hold register, the command cursor, and the
#: stack of return positions.
#:
#: The commands and the label and subroutine tables stay out: Jaune parses
#: its program once and never rewrites it, so a step is handed them rather
#: than carrying them.
type _State = tuple[Chunked[int], int, int, int, tuple[int, ...]]


def _set(cells: Chunked[int], ptr: int, value: int) -> Chunked[int]:
    """Return ``cells`` with the cell at ``ptr`` set to ``value``."""
    return put(cells, ptr, value)


def _markers(commands: Sequence[_Command]) -> dict[tuple[str, int | None], int]:
    """Return the index of the first marker for each ``op`` and argument.

    Built once per program: scanning per jump made Theta(T) jumps over
    Theta(T) commands pay Theta(T) each.
    """
    marks: dict[tuple[str, int | None], int] = {}
    for i, cmd in enumerate(commands):
        marks.setdefault((cmd.op, cmd.arg), i)
    return marks


def _advance(
    state: _State,
    commands: Sequence[_Command],
    marks: dict[tuple[str, int | None], int],
    value: int | None = None,
) -> _State:
    """Return the state after executing ``cmd``.

    ``marks`` is :func:`_markers` for ``commands``, required rather than
    rebuilt per step.  Pure: ``^``'s cell is carried forward and the three
    reading forms arrive as ``value``.  ``>`` past the edge appends a cell;
    ``<`` at 0 moves nothing.  Taken jumps, calls and returns set the
    cursor outright and return early.
    """
    cells, ptr, hold, pos, calls = state
    cmd = commands[pos]
    c = cmd.op

    if c == "^":
        pass  # printed by the caller; the cell is unchanged
    elif c == "v":
        cells = _set(cells, ptr, value if value is not None else 0)
    elif c in ("v+", "v-"):
        val = value if value is not None else 0
        cells = _set(cells, ptr, get(cells, ptr) + (val if c == "v+" else -val))
    elif c == ">":
        ptr += 1
        if ptr == length(cells):
            cells = append(cells, 0)
    elif c == "<":
        # Clamped at cell 0, as brainfuck clamps its own ``<``.  This used
        # to insert a fresh cell and leave the pointer where it was, which
        # grew the tape leftward; the wiki says only "Moves pointer to the
        # previous cell" and nothing about bounds, so both readings filled a
        # gap, and clamping is the one the rest of this package uses.
        ptr = max(0, ptr - 1)
    elif c == "#":
        hold = get(cells, ptr)
    elif c == "&":
        cells = _set(cells, ptr, get(cells, ptr) + hold)
    elif c == "%":
        cells = _set(cells, ptr, 0)
    elif c == "+":
        cells = _set(
            cells, ptr, get(cells, ptr) + (cmd.arg if cmd.arg is not None else 1)
        )
    elif c == "-":
        cells = _set(
            cells, ptr, get(cells, ptr) - (cmd.arg if cmd.arg is not None else 1)
        )
    elif c == "?":
        target = marks.get((":", cmd.arg))
        if target is None:
            raise HaltError(f"jump to undefined label {cmd.arg}")
        if get(cells, ptr) != 0:
            return (cells, ptr, hold, target, calls)
    elif c == "!":
        target = marks.get((":", cmd.arg))
        if target is None:
            raise HaltError(f"jump to undefined label {cmd.arg}")
        if get(cells, ptr) == 0:
            return (cells, ptr, hold, target, calls)
    elif c == "@":
        target = marks.get(("$", cmd.arg))
        if target is None:
            raise HaltError(f"call to undefined subroutine {cmd.arg}")
        return (cells, ptr, hold, target, (*calls, pos + 1))
    elif c in ("v?", "v!"):
        # The read names the label, so the operand is the digit just taken
        # rather than a parsed one.  The read happens whether or not the
        # branch is taken -- the grammar evaluates the number to have a
        # command at all -- so input advances either way.
        num = value if value is not None else 0
        target = marks.get((":", num))
        if target is None:
            raise HaltError(f"jump to undefined label {num}")
        cell = get(cells, ptr)
        taken = cell != 0 if c == "v?" else cell == 0
        if taken:
            return (cells, ptr, hold, target, calls)
    elif c == "v@":
        num = value if value is not None else 0
        target = marks.get(("$", num))
        if target is None:
            raise HaltError(f"call to undefined subroutine {num}")
        return (cells, ptr, hold, target, (*calls, pos + 1))
    elif c == ";":
        if not calls:
            raise HaltError("; with no active subroutine call")
        return (cells, ptr, hold, calls[-1], calls[:-1])
    elif c == ".":
        return (cells, ptr, hold, len(commands), calls)
    # ":" and "$" are positions rather than commands -- a label and a
    # subroutine definition -- so execution falls through them in place.

    return (cells, ptr, hold, pos + 1, calls)


class _Machine:
    """One Jaune run: cells, pointer, hold cell, and parsed commands."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.commands = _parse(code)
        # Label and subroutine targets, matched once: the program is parsed
        # and never rewritten, so every jump can read its target instead of
        # searching the command list for it.
        self.marks = _markers(self.commands)
        self.cells: Chunked[int] = chunked((0,))
        self.ptr = 0
        self.hold = 0
        self.pos = 0
        self.call_stack: tuple[int, ...] = ()

    @property
    def halted(self) -> bool:
        return self.pos >= len(self.commands)

    # The VM's language-shaped view: Cell tape + hold register; ip the command position.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.pos

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(flatten(self.cells))

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.call_stack)

    @property
    def frames(self) -> tuple[int, ...]:
        """The live subroutine calls, outermost first."""
        return self.call_stack

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.pos,
            self.cells,
            self.ptr,
            self.hold,
            self.call_stack,
            self.io.position(),
        )

    def frame_entry_key(self, _frame: object) -> tuple[object, ...]:
        """Return the state a subroutine needs to replay an ancestor.

        The live ``pos`` after ``@`` jumps, the tape and hold, and the input
        position.  See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        return (
            self.pos,
            self.cells,
            self.ptr,
            self.hold,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (
            self.cells,
            self.ptr,
            self.hold,
            self.pos,
            self.call_stack,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self.cells, self.ptr, self.hold, self.pos, self.call_stack = state

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the position.

        The reading forms take a line here and convert it; an empty line
        reads as zero, the package convention (:meth:`io.IO.input_char`),
        since the wiki says nothing about an empty read.
        """
        if self.halted:
            return
        cmd = self.commands[self.pos]

        value = None
        if cmd.op == "^":
            self.io.print_num(get(self.cells, self.ptr))
        elif cmd.op in ("v", "v+", "v-", "v?", "v!", "v@"):
            ch = self.io.input_str()
            value = ord(ch[0]) - 48 if ch else 0

        self._restore(_advance(self._state, self.commands, self.marks, value))


def run(code: str, io: IO) -> None:
    """Run a Jaune program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
