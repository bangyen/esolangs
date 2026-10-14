"""Interpreter for Jaune.

A cell array with a hold cell.  ``^`` prints the cell as a
decimal, ``v`` reads a digit, ``>``/``<`` move, ``#`` copies to the hold,
``&`` adds it back, ``%`` zeroes, ``+``/``-`` with an optional count
adjust.  ``(number):`` labels, ``?``/``!`` jump when nonzero/zero, ``$``
defines a subroutine, ``@`` calls it, ``;`` returns, ``.`` ends the main
program. Repeated ``+``/``-`` combine into a count; ``v`` as an operand
reads an integer as the count or the label/subroutine name.

Gaps decided: ``v`` reads whitespace-delimited signed integer tokens and raises
:class:`EOFError` at end of input. The tape grows both ways: ``<`` at the leftmost
cell adds a zero cell on the left (the wiki says only "previous cell", and
cells left of the start are allowed).
cells are plain integers, as JauneJS's ``+=`` is; a read operand is
consumed whether or not the branch is taken and may name any integer;
``v:`` and ``v$`` define nothing and are dropped at parse, as the
compiler's ``prep`` does; an undefined label or subroutine, or ``;`` with
no active call, raises :class:`~esolangs.exceptions.HaltError` (a jump
even when untaken); labels are program-wide and the first of a repeated
one wins; text outside the EBNF is skipped and the ``.`` is optional; a
command missing its required number is :class:`ValueError`; an infinite
loop is bounded by the caller's ``timeout``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.persistent import (
    Chunked,
    append,
    chunked,
    flatten,
    get,
    length,
    prepend,
    put,
)
from esolangs.runtime.source_hints import syntax_error

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
_BARE: frozenset[_CountedOp] = frozenset(("^", ">", "<", "#", "&", "%", ".", ";"))
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
# execute, so dropping them at parse loses nothing.
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


def _number_command(
    code: str, out: list[_Command], i: int, sign: Literal["+", "-"] | None
) -> int:
    """Append the command a digit run names, and return the new cursor.

    ``i`` points at the run's first character (the sign when one is given).
    When an operator follows the digits it consumes the number: a numbered
    operator takes it as its argument, ``+``/``-`` as a repeat count.  A run
    with no operator is a no-op -- except for a sign stranded from its
    digits, which is a lone +1/-1 whose digits re-parse on the next pass.
    """
    n = len(code)
    j = i + (1 if sign is not None else 0)
    k = j
    while k < n and code[k] in "0123456789":
        k += 1
    num = int(code[i:k])
    if k < n and (op := code[k]) in _NUMBERED:
        out.append(_Numbered(op, num))
        return k + 1
    if k < n and code[k] in "+-":
        # "-" reaches here as a counted subtract, never as a jump: the
        # numbered operators above do not include it.
        out.append(_Counted("+" if code[k] == "+" else "-", num))
        return k + 1
    if sign is not None:
        out.append(_Counted(sign, 1))
        return i + 1
    return k  # a bare number with no operator: ignore (no-op)


def _parse(code: str) -> list[_Command]:
    """Parse a program into commands, expanding counts and number operands."""
    out: list[_Command] = []
    i = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in "+-0123456789":
            # One token shape: an optional sign, digits, then an operator.
            # The sign rides on the number only when digits follow it; a
            # bare run of + or - counts repeats, and bare digits with no
            # operator are a no-op.
            if c in "+-":
                if i + 1 < n and code[i + 1] in "0123456789":
                    i = _number_command(code, out, i, "+" if c == "+" else "-")
                else:
                    # a run like ++ is a counted command (repeat)
                    j = i
                    while j < n and code[j] == c:
                        j += 1
                    out.append(_Counted("+" if c == "+" else "-", j - i))
                    i = j
            else:
                i = _number_command(code, out, i, None)
        elif c in _BARE:
            out.append(_Counted(c))
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
        elif c in ":?!$@":
            # a bare operator with no number: malformed
            raise syntax_error(
                f"command {c!r} requires a number",
                "put the required decimal number immediately before the command",
            )
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


def _markers(commands: Sequence[_Command]) -> dict[tuple[str, int | None], int]:
    """Return the index of the first marker for each ``op`` and argument.

    Built once per program: scanning per jump made Theta(T) jumps over
    Theta(T) commands pay Theta(T) each.
    """
    marks: dict[tuple[str, int | None], int] = {}
    for i, cmd in enumerate(commands):
        marks.setdefault((cmd.op, cmd.arg), i)
    return marks


def _label_target(marks: dict[tuple[str, int | None], int], num: int | None) -> int:
    """Return the marker index of label ``num``; HaltError when undefined."""
    target = marks.get((":", num))
    if target is None:
        raise HaltError(
            f"jump to undefined label {num}",
            hint="define the destination label or correct the jump target",
        )
    return target


def _sub_target(marks: dict[tuple[str, int | None], int], num: int | None) -> int:
    """Return the marker index of subroutine ``num``; HaltError when undefined."""
    target = marks.get(("$", num))
    if target is None:
        raise HaltError(
            f"call to undefined subroutine {num}",
            hint="define the subroutine or correct the call target",
        )
    return target


#: Everything one opcode's transition may need: the state, the command
#: list, the marker table, the command being executed, and the read value.
@dataclass
class _Step:
    state: _State
    commands: Sequence[_Command]
    marks: dict[tuple[str, int | None], int]
    cmd: _Command
    value: int | None


#: One opcode's transition: a step in, the next state out.
type _Handler = Callable[[_Step], _State]


def _h_print(step: _Step) -> _State:
    """``^``: the cell is unchanged; the caller prints it."""
    cells, ptr, hold, pos, calls = step.state
    return (cells, ptr, hold, pos + 1, calls)


def _h_read(step: _Step) -> _State:
    """``v``: store the read value in the cell."""
    cells, ptr, hold, pos, calls = step.state
    value = step.value if step.value is not None else 0
    return (put(cells, ptr, value), ptr, hold, pos + 1, calls)


def _h_read_adjust(step: _Step) -> _State:
    """``v+``/``v-``: add or subtract the read value."""
    cells, ptr, hold, pos, calls = step.state
    val = step.value if step.value is not None else 0
    delta = val if step.cmd.op == "v+" else -val
    return (put(cells, ptr, get(cells, ptr) + delta), ptr, hold, pos + 1, calls)


def _h_right(step: _Step) -> _State:
    """``>``: move right, appending a zero cell past the edge."""
    cells, ptr, hold, pos, calls = step.state
    ptr += 1
    if ptr == length(cells):
        cells = append(cells, 0)
    return (cells, ptr, hold, pos + 1, calls)


def _h_left(step: _Step) -> _State:
    """``<``: move left; at cell 0 the tape grows a zero cell on the left."""
    cells, ptr, hold, pos, calls = step.state
    if ptr:
        ptr -= 1
    else:
        cells = prepend(cells, 0)
    return (cells, ptr, hold, pos + 1, calls)


def _h_hold(step: _Step) -> _State:
    """``#``: copy the cell into the hold register."""
    cells, ptr, _hold, pos, calls = step.state
    return (cells, ptr, get(cells, ptr), pos + 1, calls)


def _h_add_hold(step: _Step) -> _State:
    """``&``: add the hold register back into the cell."""
    cells, ptr, hold, pos, calls = step.state
    return (put(cells, ptr, get(cells, ptr) + hold), ptr, hold, pos + 1, calls)


def _h_zero(step: _Step) -> _State:
    """``%``: zero the cell."""
    cells, ptr, hold, pos, calls = step.state
    return (put(cells, ptr, 0), ptr, hold, pos + 1, calls)


def _h_inc(step: _Step) -> _State:
    """``+``: add the repeat count; a bare ``+`` adds one."""
    cells, ptr, hold, pos, calls = step.state
    delta = step.cmd.arg if step.cmd.arg is not None else 1
    return (put(cells, ptr, get(cells, ptr) + delta), ptr, hold, pos + 1, calls)


def _h_dec(step: _Step) -> _State:
    """``-``: subtract the repeat count; a bare ``-`` subtracts one."""
    cells, ptr, hold, pos, calls = step.state
    delta = step.cmd.arg if step.cmd.arg is not None else 1
    return (put(cells, ptr, get(cells, ptr) - delta), ptr, hold, pos + 1, calls)


def _h_jump_nz(step: _Step) -> _State:
    """``?``: jump to the label when the cell is nonzero."""
    cells, ptr, hold, pos, calls = step.state
    target = _label_target(step.marks, step.cmd.arg)
    if get(cells, ptr) != 0:
        return (cells, ptr, hold, target, calls)
    return (cells, ptr, hold, pos + 1, calls)


def _h_jump_z(step: _Step) -> _State:
    """``!``: jump to the label when the cell is zero."""
    cells, ptr, hold, pos, calls = step.state
    target = _label_target(step.marks, step.cmd.arg)
    if get(cells, ptr) == 0:
        return (cells, ptr, hold, target, calls)
    return (cells, ptr, hold, pos + 1, calls)


def _h_call(step: _Step) -> _State:
    """``@``: call the subroutine, pushing the return position."""
    cells, ptr, hold, pos, calls = step.state
    target = _sub_target(step.marks, step.cmd.arg)
    return (cells, ptr, hold, target, (*calls, pos + 1))


def _h_read_jump(step: _Step) -> _State:
    """``v?``/``v!``: the read value names the label to jump to."""
    cells, ptr, hold, pos, calls = step.state
    num = step.value if step.value is not None else 0
    target = _label_target(step.marks, num)
    cell = get(cells, ptr)
    taken = cell != 0 if step.cmd.op == "v?" else cell == 0
    if taken:
        return (cells, ptr, hold, target, calls)
    return (cells, ptr, hold, pos + 1, calls)


def _h_read_call(step: _Step) -> _State:
    """``v@``: the read value names the subroutine to call."""
    cells, ptr, hold, pos, calls = step.state
    num = step.value if step.value is not None else 0
    target = _sub_target(step.marks, num)
    return (cells, ptr, hold, target, (*calls, pos + 1))


def _h_return(step: _Step) -> _State:
    """``;``: return to the most recent call site."""
    cells, ptr, hold, _pos, calls = step.state
    if not calls:
        raise HaltError(
            "; with no active subroutine call",
            hint="call a subroutine before returning with ;",
        )
    return (cells, ptr, hold, calls[-1], calls[:-1])


def _h_end(step: _Step) -> _State:
    """``.``: end the main program."""
    cells, ptr, hold, _pos, calls = step.state
    return (cells, ptr, hold, len(step.commands), calls)


def _h_fallthrough(step: _Step) -> _State:
    """``:`` and ``$`` are positions rather than commands: fall through."""
    cells, ptr, hold, pos, calls = step.state
    return (cells, ptr, hold, pos + 1, calls)


_HANDLERS: dict[str, _Handler] = {
    "^": _h_print,
    "v": _h_read,
    "v+": _h_read_adjust,
    "v-": _h_read_adjust,
    ">": _h_right,
    "<": _h_left,
    "#": _h_hold,
    "&": _h_add_hold,
    "%": _h_zero,
    "+": _h_inc,
    "-": _h_dec,
    "?": _h_jump_nz,
    "!": _h_jump_z,
    "@": _h_call,
    "v?": _h_read_jump,
    "v!": _h_read_jump,
    "v@": _h_read_call,
    ";": _h_return,
    ".": _h_end,
    ":": _h_fallthrough,
    "$": _h_fallthrough,
}


def _advance(
    state: _State,
    commands: Sequence[_Command],
    marks: dict[tuple[str, int | None], int],
    value: int | None = None,
) -> _State:
    """Return the state after executing the command at the cursor.

    ``marks`` is :func:`_markers` for ``commands``, required rather than
    rebuilt per step.  ``^``'s cell is carried forward and the reading forms
    arrive as ``value``; taken jumps, calls and returns set the cursor
    outright, and every other command falls through to the next one.
    """
    cmd = commands[state[3]]
    return _HANDLERS[cmd.op](_Step(state, commands, marks, cmd, value))


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
            self.io.progress(),
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
            self.io.progress(),
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

        Reads consume whitespace-delimited integer tokens from the shared
        cursor. Blank lines are skipped; exhaustion raises EOFError.
        Signed values are accepted independently of Boolean input encoding.
        """
        if self.halted:
            return
        cmd = self.commands[self.pos]

        value = None
        if cmd.op == "^":
            self.io.print_num(get(self.cells, self.ptr))
        elif cmd.op in ("v", "v+", "v-", "v?", "v!", "v@"):
            ch = self.io.input_token()
            value = int(ch)

        self._restore(_advance(self._state, self.commands, self.marks, value))


def run(code: str, io: IO) -> None:
    """Run a Jaune program."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
