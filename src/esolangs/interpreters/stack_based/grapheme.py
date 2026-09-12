r"""Interpreter for Grapheme."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from typing import Final, Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_FUNC: Final = "func"

# A Grapheme value is a number,.
# is always the pair ``(_FUNC,.
# buffer is closed.
# conversions below handle.
# for a fourth kind that cannot.
# to be cast to str at each use.
_Function = tuple[Literal["func"], str]
_Value = int | str | _Function


def _int_from(buf: list[str]) -> int:
    r"""Parse an intmode buffer: ``res = (res + digit) * 10`` per letter."""
    res = 0
    for c in buf:
        res = (res + (ord(c) - 64 if c != "Z" else 0)) * 10
    return res


def _to_int(value: _Value) -> int:
    r"""Convert a value to an integer (the ``J`` command)."""
    if isinstance(value, int):
        return value
    if isinstance(value, tuple):  # function -> number of.
        return len(value[1])
    res = 0
    for c in value:
        if c == "F":
            break
        res = (res + (ord(c) - 64 if c != "Z" else 0)) * 10
    return res


def _to_str(value: _Value) -> str:
    r"""Convert a value to a string (the ``N`` command)."""
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):  # function -> its body.
        return value[1]
    digits = "JABCDEFGHI"  # J = 0, A = 1, ..., I = 9.
    if value == 0:
        return "J"
    res: list[str] = []
    while value:
        res.append(digits[value % 10])
        value //= 10
    return "".join(reversed(res))


def _as_num(value: _Value) -> int:
    r"""Math operand: an integer, or the ord of a string's first character."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return ord((value or "\0")[0])
    raise HaltError("math on a function is undefined")


def _truthy(value: _Value) -> bool:
    r"""Falsy values are zero, the empty string, and the empty function."""
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return value[1] != ""


# : One call context: ``(code,.
# :.
# : A tuple rather than a.
# : :meth:`_Machine.snapshot`.
# : same reason.
# : rewound instead of popped.
type _Frame = tuple[str, int, str, tuple[str, ...], int, str]

# : The part of a run the pure.
# : The value stack is.
type _Vars = Mapping[_Value, _Value]
type _State = tuple[_Vars, tuple[_Frame, ...]]

# : A read-only view of the.
#: but never writes.
type _StackView = Sequence[_Value]

# : What a step wants done to.
# : top, what to add after.
# : Applied in exactly that.
type _StackFx = tuple[int, tuple[_Value, ...], bool]


# : The command that opens each.
# : are the same letter: ``E``.
# : them once keeps the open.
_OPENS: Final = {"E": "string", "F": "int", "H": "func"}
_CLOSES: Final = {mode: char for char, mode in _OPENS.items()}


def _frame(code: str, repeat: str = "") -> _Frame:
    r"""Build a fresh frame for ``code``, at the start and in no mode."""
    return (code, 0, "", (), -1, repeat)


def _pop(view: _StackView, pops: int) -> tuple[int, _Value]:
    r"""Read the next value down the stack, and the pop count that consumes."""
    if pops >= len(view):
        raise HaltError("popped an empty stack")
    return pops + 1, view[-1 - pops]


def _flush_of(frame: _Frame) -> tuple[_Value, ...]:
    r"""Return what an unterminated mode leaves behind, as at end of."""
    _, _, mode, buf, _, _ = frame
    if mode == "string":
        return ("".join(buf),)
    if mode == "int":
        return (_int_from(list(buf)),)
    if mode == "func":
        return ((_FUNC, "".join(buf)),)
    return ()


def _finished(state: _State, view: _StackView, fx: _StackFx) -> tuple[_State, _StackFx]:
    r"""Flush the top frame's mode and pop it -- or rewind it, for ``Z``."""
    variables, frames = state
    frame = frames[-1]
    pops, pushes, reverse = fx
    pushes = (*pushes, *_flush_of(frame))
    fx = (pops, pushes, reverse)

    code, _, _, _, _, repeat = frame
    if repeat and len(view) - pops + len(pushes) > 0:
        rewound = (code, 0, "", (), -1, repeat)
        return (variables, (*frames[:-1], rewound)), fx
    return (variables, frames[:-1]), fx


def _advance(
    state: _State, view: _StackView, line_in: str | None = None
) -> tuple[_State, _StackFx, _Value | None]:
    r"""Execute one command: the new state, the stack effects, any output."""
    variables, frames = state
    frame = frames[-1]
    code, pc, mode, buf, pending_at, repeat = frame

    pops = 0
    pushes: tuple[_Value, ...] = ()
    reverse = False

    # A frame whose code has run.
    # and pops it without spending.
    c = code[pc]

    # In a mode, every character.
    if mode in _CLOSES:
        grown: _Frame
        if c == _CLOSES[mode]:
            pushes = _flush_of(frame)
            grown = (code, pc + 1, "", (), pending_at, repeat)
        else:
            grown = (code, pc + 1, mode, (*buf, c), pending_at, repeat)
        return (variables, (*frames[:-1], grown)), (pops, pushes, reverse), None

    body: str | None = None
    call_repeat = ""
    output: _Value | None = None
    if c == "A":
        pops, b = _pop(view, pops)
        pops, a = _pop(view, pops)
        pushes = (_as_num(a) + _as_num(b),)
    elif c == "B":
        pops, b = _pop(view, pops)
        pops, a = _pop(view, pops)
        pushes = (_as_num(a) - _as_num(b),)
    elif c == "R":
        pops, b = _pop(view, pops)
        pops, a = _pop(view, pops)
        if _as_num(b) == 0:
            raise HaltError("division by zero")
        pushes = (_as_num(a) // _as_num(b),)
    elif c == "S":
        pops, b = _pop(view, pops)
        pops, a = _pop(view, pops)
        pushes = (_as_num(a) * _as_num(b),)
    elif c == "C":
        pops, name = _pop(view, pops)
        pops, value = _pop(view, pops)
        if isinstance(name, tuple):
            raise HaltError("a function cannot name a variable")
        variables = {**variables, name: value}
    elif c == "D":
        pops, name = _pop(view, pops)
        if isinstance(name, tuple):
            raise HaltError("a function cannot name a variable")
        if name not in variables:
            raise HaltError(f"undeclared variable {name!r}")
        pushes = (variables[name],)
    elif c in _OPENS:
        mode, buf = _OPENS[c], ()
    elif c == "G":
        pops, value = _pop(view, pops)
        raw = value[1] if isinstance(value, tuple) and value[0] == _FUNC else value
        if not isinstance(raw, str):
            raise HaltError("G needs a string or a function")
        body = raw
    elif c == "I":
        pops, value = _pop(view, pops)
        if isinstance(value, tuple) and value[0] == _FUNC:
            body = value[1]
        else:
            pushes = (value,)
    elif c == "J":
        pops, value = _pop(view, pops)
        pushes = (_to_int(value),)
    elif c == "K":
        pops, value = _pop(view, pops)
        pushes = (value, value)
    elif c == "L":
        pops, a = _pop(view, pops)
        pops, b = _pop(view, pops)
        pushes = (a, b)
    elif c == "M":
        pops, _ = _pop(view, pops)
    elif c == "N":
        pops, value = _pop(view, pops)
        pushes = (_to_str(value),)
    elif c == "O":
        pops, value = _pop(view, pops)
        pushes = (len(value) if isinstance(value, str) else value,)
    elif c == "P":
        reverse = True
    elif c == "Q":
        pops, a = _pop(view, pops)
        pops, b = _pop(view, pops)
        if isinstance(a, tuple) and a[0] == _FUNC and _truthy(b):
            body = a[1]
    elif c == "T":
        pops, value = _pop(view, pops)
        pushes = (1 if not _truthy(value) else 0,)
    elif c == "U":
        pops, value = _pop(view, pops)
        if not _truthy(value):
            pc += 1
    elif c == "V":
        pops, a = _pop(view, pops)
        pops, b = _pop(view, pops)
        if not _truthy(a):
            pc += _to_int(b)
    elif c == "W":
        pushes = (line_in if line_in is not None else "",)
    elif c == "X":
        pops, value = _pop(view, pops)
        if _truthy(value):
            # execute the next command,.
            pending_at = pc
        else:
            # skip the next command.
            pc += 1
    elif c == "Y":
        pops, value = _pop(view, pops)
        if isinstance(value, tuple):
            raise HaltError("Y cannot output a function")
        output = value
    elif c == "Z":
        pops, value = _pop(view, pops)
        if (
            isinstance(value, tuple)
            and value[0] == _FUNC
            and len(view) - pops + len(pushes) > 0
        ):
            body = value[1]
            call_repeat = value[1]
    else:
        # a string read from input and.
        # character; reject it like the.
        raise ValueError(f"unhandled command {c!r}")

    pc += 1
    if pending_at >= 0 and pc == pending_at + 2:
        pc += 1
        pending_at = -1

    frames = (*frames[:-1], (code, pc, mode, buf, pending_at, repeat))

    if body is not None:
        frames = (*frames, _frame(body, call_repeat))

    # a command that left the.
    # a call returned) is completed.
    # soon as the last command runs.
    state = (variables, frames)
    fx = (pops, pushes, reverse)
    while frames and frames[-1][1] >= len(frames[-1][0]):
        state, fx = _finished(state, view, fx)
        frames = state[1]

    return state, fx, output


class _Machine:
    r"""Shared stack, variables, step counter, and call stack for a run."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Build a machine running ``code`` as its top-level frame."""
        if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in code):
            raise ValueError(
                "Grapheme programs may only contain uppercase Latin letters"
            )
        self.stack: list[_Value] = []
        self.vars: _Vars = {}
        self.io = io
        self.frames: tuple[_Frame, ...] = (_frame(code),)
        # Where the top-level frame.
        # position once every frame has.
        self._top_length = len(code)

    @property
    def halted(self) -> bool:
        return not self.frames

    # The VM's language-shaped.
    # carry their own cursor, and.

    # : ``ip`` is a position, but.
    #: root-to-leaf.
    # : Declared rather than left.
    # : classified is a missing.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""Each active frame's pc, root-to-leaf."""
        if self.frames:
            return tuple(f[1] for f in self.frames)
        return (self._top_length,)

    @property
    def memory(self) -> list[int]:
        r"""No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # A frame is already a tuple of.
        # goes in as it stands rather.
        # which is what a frame being a.
        return (
            tuple(self.stack),
            frozenset(self.vars.items()),
            self.frames,
            self.io.position(),
        )

    def frame_entry_key(self, frame: _Frame) -> tuple[object, ...]:
        r"""Return the state a called function needs to replay an ancestor."""
        code, _, _, _, _, repeat = frame
        return (
            code,
            repeat,
            tuple(self.stack),
            frozenset(self.vars.items()),
            self.io.position(),
        )

    def _apply(self, fx: _StackFx) -> None:
        r"""Apply a step's stack effects, in order: pops, reverse, pushes."""
        pops, pushes, reverse = fx
        if pops:
            del self.stack[len(self.stack) - pops :]
        if reverse:
            self.stack.reverse()
        self.stack.extend(pushes)

    def step(self) -> None:
        r"""Execute one command, finishing any frames that are now complete."""
        if self.halted:
            return

        code, pc, mode, _, _, _ = self.frames[-1]

        # A frame whose code has run.
        # only flushes and pops, which.
        if pc >= len(code):
            (self.vars, self.frames), fx = _finished(
                (self.vars, self.frames), self.stack, (0, (), False)
            )
            self._apply(fx)
            return

        # ``W`` reads only when it is a.
        # character is data, so a ``W``.
        # touch the port -- reading.
        # one that raises at EOF.
        line_in = None
        if mode == "" and code[pc] == "W":
            line_in = self.io.input_str()

        (self.vars, self.frames), fx, output = _advance(
            (self.vars, self.frames), self.stack, line_in
        )
        self._apply(fx)

        if output is not None:
            if isinstance(output, str):
                self.io.print_str(output)
            else:
                self.io.print_value(output)


def run(code: str, io: IO) -> None:
    r"""Run a Grapheme program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
