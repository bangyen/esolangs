"""Interpreter for Grapheme.

Each uppercase letter is a command; the stack holds unbounded integers,
strings and functions, with an untyped variable map.  ``E``/``F``/``H``
toggle string/int/function mode, accumulating characters into a value
pushed when the mode ends.

Gaps decided: underflow, math or ``Y`` on a function, a negative ``N``
integer (alphabet ``A``-``J``), a function as a variable name, an
undeclared ``D`` variable and division by zero halt
(:class:`~esolangs.exceptions.HaltError`); a character outside
``A``-``Z`` is malformed (:class:`ValueError`); ``G``/``I``/``Q``/``Z``
run a function in a fresh normal-mode context sharing stack and
variables; ``W`` reads a line and raises :class:`EOFError` at end of
input; ``N`` on a function returns its body.

:class:`_Machine` has an explicit call stack (one frame per active call),
so ``halted`` is true once no frame remains and a repeated
:meth:`_Machine.snapshot` proves a loop; unbounded growth (``HKHKZ``)
needs the wall-clock bound.  :func:`_advance` is pure over an immutable
``_State`` (variables, tuple call stack) and returns *collected effects*
``(pops, pushes, reverse)`` on the value stack, which stays a list in the
shell: 200,000 commands of ``HKHKZ`` take 0.21s against a list and 445s
against a rebuilt tuple.  The invariant that makes reporting sound:
**every command pops before it pushes**, so operands are read at
``stack[-1 - pops]``.  Finishing a frame (flush the mode buffer, pop, or
rewind for ``Z``) is part of the transition, reading the *virtual* depth.

The old ``steps``/``limit`` budget is gone: unbounded pushes are what
``esolangs.run``'s ``timeout`` catches, and ancestor replay is decided by
:func:`esolangs.vm.run_until_halt_or_ancestor`.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from typing import Final, Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_FUNC: Final = "func"

# A Grapheme value is a number, a string, or a function -- and a function
# is always the pair ``(_FUNC, body)``, built in the two places a frame's
# buffer is closed.  Naming the three lets the checker see that the
# conversions below handle every one, so none needs a trailing assertion
# for a fourth kind that cannot exist, and the function body no longer has
# to be cast to str at each use.
_Function = tuple[Literal["func"], str]
_Value = int | str | _Function


def _int_from(buf: list[str]) -> int:
    """Parse an intmode buffer: ``res = (res + digit) * 10`` per letter."""
    res = 0
    for c in buf:
        res = (res + (ord(c) - 64 if c != "Z" else 0)) * 10
    return res


def _to_int(value: _Value) -> int:
    """Convert a value to an integer (the ``J`` command)."""
    if isinstance(value, int):
        return value
    if isinstance(value, tuple):  # function -> number of commands
        return len(value[1])
    res = 0
    for c in value:
        if c == "F":
            break
        res = (res + (ord(c) - 64 if c != "Z" else 0)) * 10
    return res


def _to_str(value: _Value) -> str:
    """Convert a value to a string (the ``N`` command)."""
    if isinstance(value, str):
        return value
    if isinstance(value, tuple):  # function -> its body
        return value[1]
    digits = "JABCDEFGHI"  # J = 0, A = 1, ..., I = 9
    if value == 0:
        return "J"
    res: list[str] = []
    while value:
        res.append(digits[value % 10])
        value //= 10
    return "".join(reversed(res))


def _as_num(value: _Value) -> int:
    """Math operand: an integer, or the ord of a string's first character."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return ord((value or "\0")[0])
    raise HaltError("math on a function is undefined")


def _truthy(value: _Value) -> bool:
    """Falsy values are zero, the empty string, and the empty function."""
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return value[1] != ""


#: One call context: ``(code, pc, mode, buf, pending_at, repeat)``.
#:
#: A tuple rather than a record, so the whole call stack is a value that
#: :meth:`_Machine.snapshot` can hash -- Eval's frames are tuples for the
#: same reason.  ``repeat`` carries ``Z``'s body: a frame holding one is
#: rewound instead of popped while the stack is non-empty.
type _Frame = tuple[str, int, str, tuple[str, ...], int, str]

#: The part of a run the pure layer owns: the variables and the call stack.
#: The value stack is deliberately absent; see the module docstring.
type _Vars = Mapping[_Value, _Value]
type _State = tuple[_Vars, tuple[_Frame, ...]]

#: A read-only view of the live value stack, which the pure layer indexes
#: but never writes.
type _StackView = Sequence[_Value]

#: What a step wants done to the value stack: how many to remove from the
#: top, what to add after that, and whether ``P`` reversed what was left.
#: Applied in exactly that order.
type _StackFx = tuple[int, tuple[_Value, ...], bool]


#: The command that opens each mode, and the one that closes it.  The two
#: are the same letter: ``E`` opens string mode and ``E`` ends it.  Naming
#: them once keeps the open and close arms from drifting apart.
_OPENS: Final = {"E": "string", "F": "int", "H": "func"}
_CLOSES: Final = {mode: char for char, mode in _OPENS.items()}


def _frame(code: str, repeat: str = "") -> _Frame:
    """Build a fresh frame for ``code``, at the start and in no mode."""
    return (code, 0, "", (), -1, repeat)


def _pop(view: _StackView, pops: int) -> tuple[int, _Value]:
    """Read the next value down the stack, and the pop count that consumes it.

    Sound only because every command pops before it pushes.
    """
    if pops >= len(view):
        raise HaltError("popped an empty stack")
    return pops + 1, view[-1 - pops]


def _flush_of(frame: _Frame) -> tuple[_Value, ...]:
    """Return what an unterminated mode leaves behind, as at end of program."""
    _, _, mode, buf, _, _ = frame
    if mode == "string":
        return ("".join(buf),)
    if mode == "int":
        return (_int_from(list(buf)),)
    if mode == "func":
        return ((_FUNC, "".join(buf)),)
    return ()


def _finished(state: _State, view: _StackView, fx: _StackFx) -> tuple[_State, _StackFx]:
    """Flush the top frame's mode and pop it -- or rewind it, for ``Z``.

    ``Z``'s emptiness test reads the *virtual* depth.
    """
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
    """Execute one command: the new state, the stack effects, any output.

    Pure.  ``Y`` reports its value (the shell picks ``print_str`` or
    ``print_value`` by type); ``W``'s line arrives as ``line_in``.
    """
    variables, frames = state
    frame = frames[-1]
    code, pc, mode, buf, pending_at, repeat = frame

    pops = 0
    pushes: tuple[_Value, ...] = ()
    reverse = False

    # A frame whose code has run out never reaches here: the shell flushes
    # and pops it without spending a step, so ``pc`` indexes a command.
    c = code[pc]

    # In a mode, every character but the closing one is data.
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
        pops, a = _pop(view, pops)
        pops, b = _pop(view, pops)
        pushes = (_as_num(a) - _as_num(b),)
    elif c == "R":
        pops, a = _pop(view, pops)
        pops, b = _pop(view, pops)
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
            # execute the next command, then skip the one after it
            pending_at = pc
        else:
            # skip the next command entirely
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
        # a string read from input and executed via G/I may carry any
        # character; reject it like the top-level program validation would
        raise ValueError(f"unhandled command {c!r}")

    pc += 1
    if pending_at >= 0 and pc == pending_at + 2:
        pc += 1
        pending_at = -1

    frames = (*frames[:-1], (code, pc, mode, buf, pending_at, repeat))

    if body is not None:
        frames = (*frames, _frame(body, call_repeat))

    # a command that left the current frame finished (the program ended or
    # a call returned) is completed now, so a caller sees ``halted`` as
    # soon as the last command runs instead of one step later.
    state = (variables, frames)
    fx = (pops, pushes, reverse)
    while frames and frames[-1][1] >= len(frames[-1][0]):
        state, fx = _finished(state, view, fx)
        frames = state[1]

    return state, fx, output


class _Machine:
    """Shared stack, variables, step counter, and call stack for a run."""

    def __init__(self, code: str, io: IO) -> None:
        """Build a machine running ``code`` as its top-level frame."""
        if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in code):
            raise ValueError(
                "Grapheme programs may only contain uppercase Latin letters"
            )
        self.stack: list[_Value] = []
        self.vars: _Vars = {}
        self.io = io
        self.frames: tuple[_Frame, ...] = (_frame(code),)
        # Where the top-level frame ends, so ``ip`` can still report a
        # position once every frame has been popped.
        self._top_length = len(code)

    @property
    def halted(self) -> bool:
        return not self.frames

    # The VM's language-shaped view: a stack language whose call frames each
    # carry their own cursor, and with no addressable cells.

    #: ``ip`` is a position, but not one on the source text: each active frame's pc,
    #: root-to-leaf.
    #: Declared rather than left to the default so that a tuple nobody has
    #: classified is a missing answer instead of this one.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        """Each active frame's pc, root-to-leaf.

        Depth-sensitive: ``(5,)`` matches only a top-level frame at pc 5,
        not ``(2, 5)``.  No frames means the program finished at its end.
        """
        if self.frames:
            return tuple(f[1] for f in self.frames)
        return (self._top_length,)

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # A frame is already a tuple of its six fields, so the call stack
        # goes in as it stands rather than being unpacked field by field --
        # which is what a frame being a value rather than a record buys.
        return (
            tuple(self.stack),
            frozenset(self.vars.items()),
            self.frames,
            self.io.position(),
        )

    def frame_entry_key(self, frame: _Frame) -> tuple[object, ...]:
        """Return the state a called function needs to replay an ancestor.

        Function text, ``Z``'s repeat mode, and immutable copies of the
        stack and variables.  See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        code, _, _, _, _, repeat = frame
        return (
            code,
            repeat,
            tuple(self.stack),
            frozenset(self.vars.items()),
            self.io.position(),
        )

    def _apply(self, fx: _StackFx) -> None:
        """Apply a step's stack effects, in order: pops, reverse, pushes.

        No command currently reverses *and* pushes; fixing the order here
        keeps that from becoming a question.
        """
        pops, pushes, reverse = fx
        if pops:
            del self.stack[len(self.stack) - pops :]
        if reverse:
            self.stack.reverse()
        self.stack.extend(pushes)

    def step(self) -> None:
        """Execute one command, finishing any frames that are now complete."""
        if self.halted:
            return

        code, pc, mode, _, _, _ = self.frames[-1]

        # A frame whose code has run out does no work and costs no step: it
        # only flushes and pops, which the transition does.
        if pc >= len(code):
            (self.vars, self.frames), fx = _finished(
                (self.vars, self.frames), self.stack, (0, (), False)
            )
            self._apply(fx)
            return

        # ``W`` reads only when it is a *command*.  Inside a mode every
        # character is data, so a ``W`` accumulating into a string must not
        # touch the port -- reading there turns a program that prints into
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
    """Run a Grapheme program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
