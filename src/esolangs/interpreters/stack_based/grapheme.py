"""Interpreter for Grapheme.

A Turing-complete stack language whose program text is a series of
independent uppercase Latin letters, each one a command.  The stack holds
unbounded signed integers, strings, and functions; an untyped variable
system maps names (integers or strings) to values.  ``E``/``F``/``H`` toggle
string/int/function mode, in which characters accumulate into a value pushed
when the mode ends (``E``/``F``/``H`` cannot appear inside the value, so
strings are uppercase letters without ``E`` and integers are letter digits).

Decisions for gaps in the wiki spec (documented):
- popping an empty stack, math on a function, ``Y`` on a function, a
  negative integer in ``N`` (whose letter alphabet is only ``A``-``J``),
  a function as a variable name, an undeclared variable in ``D``, and
  division by zero are invalid operations (:class:`~esolangs.exceptions
  .HaltError`), and a character outside ``A``-``Z`` is malformed
  (:class:`ValueError`);
- ``G``/``I``/``Q``/``Z`` run a function in a fresh normal-mode context
  sharing the stack and variables, so a function cannot leave the caller in
  a mid-string/int/function mode;
- ``W`` reads a whole line and raises :class:`EOFError` when input is
  exhausted;
- a function value is the command string between its ``H``s, so ``N`` on a
  function returns exactly that body.

The interpreter runs on a :class:`_Machine` with an explicit call stack (one
frame per active ``G``/``I``/``Q``/``Z`` call), so it is step-capable:
``step()`` executes one command, ``halted`` is true once no frame remains,
and a repeated :meth:`_Machine.snapshot` proves a loop (e.g. ``Z`` re-running
a function whose net effect on the stack is a no-op).  A program whose stack
keeps growing without repeating a state is not caught this way and needs a
wall-clock bound instead.

The execution model is a pure function over an immutable ``_State`` -- the
variables and the call stack -- paired with *collected effects* on the value
stack.  :func:`_advance` returns the next state, what it wants done to the
stack, and anything it printed; :meth:`_Machine.step` rebinds the two fields
and applies the effects, so the mutation lives in exactly one place.  A
frame is a tuple rather than a record for the same reason Eval's is: the
call stack is then a value, which is what lets :meth:`snapshot` hash it and
the cycle detector prove a loop.

The value stack is the one thing *not* threaded, and the reason is cost.  A
Grapheme program can push without bound -- ``HKHKZ`` does, which is exactly
the class a snapshot repeat cannot catch and ``esolangs.run``'s wall-clock
``timeout`` is the backstop for -- so rebuilding a stack tuple per command
is quadratic in the stack's depth.  Measured, it is not a constant factor:
200,000 commands of ``HKHKZ`` take 0.21s against a mutable list and 445s
against a rebuilt tuple.  So the stack stays a list in
the shell, and a step reports its intent as ``(pops, pushes, reverse)``
instead: a count to remove, the values to add, and whether ``P`` reversed
what was left.  COD's per-cod transition reports what it wants done for the
same reason.

That model leans on an invariant worth stating, because nothing enforces it:
**every command pops before it pushes.**  The pure layer therefore reads its
operands from the live stack by index -- ``stack[-1 - pops]``, counting up as
it goes -- and never has to see a value it has itself pushed.

Finishing a frame is part of the transition, not of the shell.  A frame
whose code has run out flushes any open mode buffer onto the stack and is
then popped -- or, for ``Z``, rewound to its start while the stack is
non-empty.  None of that touches a port, and doing it inside the step is
what makes ``halted`` true as soon as the last command runs rather than one
step later.  The emptiness tests there read the stack's *virtual* depth --
its length less the pending pops, plus the pending pushes -- since the
effects have not been applied yet.

There was once a ``steps``/``limit`` budget here, checked at the top of
every step and excluded from ``snapshot`` because it rises every step and
could never repeat.  It is gone: the class it guarded -- an unbounded
push, which never revisits a state -- is exactly what ``esolangs.run``'s
wall-clock ``timeout`` exists to catch, and a step count local to this
interpreter only duplicated it.  Recursion depth is a separate guard
(``_advance`` raises past 500 call frames) and stays, because a runaway
call stack is a different failure than an unbounded value stack and this
one *is* part of the state ``snapshot`` hashes.
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


#: One call context: ``(code, depth, pc, mode, buf, pending_at, repeat)``.
#:
#: A tuple rather than a record, so the whole call stack is a value that
#: :meth:`_Machine.snapshot` can hash -- Eval's frames are tuples for the
#: same reason.  ``repeat`` carries ``Z``'s body: a frame holding one is
#: rewound instead of popped while the stack is non-empty.
type _Frame = tuple[str, int, int, str, tuple[str, ...], int, str]

#: The part of a run the pure layer owns: the variables and the call stack.
#: Both are small -- recursion is capped at 500 frames and a frame is seven
#: fields -- so rebuilding them per step costs nothing.  The value stack is
#: deliberately absent; see the module docstring.
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


def _frame(code: str, depth: int, repeat: str = "") -> _Frame:
    """Build a fresh frame for ``code``, at the start and in no mode."""
    return (code, depth, 0, "", (), -1, repeat)


def _pop(view: _StackView, pops: int) -> tuple[int, _Value]:
    """Read the next value down the stack, and the pop count that consumes it.

    The pure layer never edits the stack, so a pop is bookkeeping: the value
    is read at ``-1 - pops`` and the count goes up.  This is sound only
    because every command pops before it pushes, so a read can never need a
    value this same step has pushed.
    """
    if pops >= len(view):
        raise HaltError("popped an empty stack")
    return pops + 1, view[-1 - pops]


def _flush_of(frame: _Frame) -> tuple[_Value, ...]:
    """Return what an unterminated mode leaves behind, as at end of program."""
    _, _, _, mode, buf, _, _ = frame
    if mode == "string":
        return ("".join(buf),)
    if mode == "int":
        return (_int_from(list(buf)),)
    if mode == "func":
        return ((_FUNC, "".join(buf)),)
    return ()


def _finished(state: _State, view: _StackView, fx: _StackFx) -> tuple[_State, _StackFx]:
    """Flush the top frame's mode and pop it -- or rewind it, for ``Z``.

    Pure, and part of the step rather than the shell: nothing here reaches
    a port, and running it inside the transition is what makes ``halted``
    true as soon as the last command does its work.

    ``Z``'s "while the stack is non-empty" test reads the *virtual* depth,
    since the effects collected so far have not been applied yet.
    """
    variables, frames = state
    frame = frames[-1]
    pops, pushes, reverse = fx
    pushes = (*pushes, *_flush_of(frame))
    fx = (pops, pushes, reverse)

    code, depth, _, _, _, _, repeat = frame
    if repeat and len(view) - pops + len(pushes) > 0:
        rewound = (code, depth, 0, "", (), -1, repeat)
        return (variables, (*frames[:-1], rewound)), fx
    return (variables, frames[:-1]), fx


def _advance(
    state: _State, view: _StackView, line_in: str | None = None
) -> tuple[_State, _StackFx, _Value | None]:
    """Execute one command: the new state, the stack effects, any output.

    Pure: it reads ``state`` and ``view`` and returns new values, and
    reaches no ``IO``.  ``Y`` reports the value it would write -- the shell
    picks ``print_str`` or ``print_value`` on its type -- and ``W``'s line
    arrives as ``line_in``.

    The stack is reported rather than rebuilt: see the module docstring for
    why, and for the pop-before-push invariant the reporting relies on.
    """
    variables, frames = state
    frame = frames[-1]
    code, depth, pc, mode, buf, pending_at, repeat = frame

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
            grown = (code, depth, pc + 1, "", (), pending_at, repeat)
        else:
            grown = (code, depth, pc + 1, mode, (*buf, c), pending_at, repeat)
        return (variables, (*frames[:-1], grown)), (pops, pushes, reverse), None

    body: str | None = None
    call_repeat = ""
    output: _Value | None = None
    new_depth = depth + 1

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

    frames = (*frames[:-1], (code, depth, pc, mode, buf, pending_at, repeat))

    if body is not None:
        if new_depth > 500:
            raise HaltError("recursion limit exceeded")
        frames = (*frames, _frame(body, new_depth, call_repeat))

    # a command that left the current frame finished (the program ended or
    # a call returned) is completed now, so a caller sees ``halted`` as
    # soon as the last command runs instead of one step later.
    state = (variables, frames)
    fx = (pops, pushes, reverse)
    while frames and frames[-1][2] >= len(frames[-1][0]):
        state, fx = _finished(state, view, fx)
        frames = state[1]

    return state, fx, output


class _Machine:
    """Shared stack, variables, step counter, and call stack for a run."""

    def __init__(self, io: IO) -> None:
        self.stack: list[_Value] = []
        self.vars: _Vars = {}
        self.io = io
        self.frames: tuple[_Frame, ...] = ()
        # Where the top-level frame ends, so ``ip`` can still report a
        # position once every frame has been popped.  ``of()`` sets it with
        # the frame it pushes; a machine built bare has no program yet.
        self._top_length = 0

    @classmethod
    def of(cls, code: str, io: IO) -> _Machine:
        """Build a machine running ``code`` as its top-level frame.

        The constructor takes no program -- a machine is a shared stack that
        frames run against -- so validating the alphabet and pushing the
        first frame had to happen in the caller.  ``run`` and the VM adapter
        each carried their own copy of both, which is the shape that lets
        the two drift.
        """
        if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in code):
            raise ValueError(
                "Grapheme programs may only contain uppercase Latin letters"
            )
        machine = cls(io)
        machine.frames = (_frame(code, 0),)
        machine._top_length = len(code)
        return machine

    @property
    def halted(self) -> bool:
        return not self.frames

    # The VM's language-shaped view: a stack language whose call frames each
    # carry their own cursor, and with no addressable cells.

    @property
    def ip(self) -> tuple[int, ...]:
        """Each active frame's pc, root-to-leaf.

        Every call frame (``G``/``I``/``Q``/``Z`` push one) contributes its
        ``pc``, so this grows and shrinks with recursion depth instead of
        folding every frame into the active one's position.  A breakpoint on
        a specific position is therefore depth-sensitive: ``(5,)`` matches
        only a single top-level frame at pc 5, not pc 5 one call deeper
        (``(2, 5)``).

        A frame is only ever popped once its own pc reaches the end of its
        code, so no frames at all means the top-level one finished at the
        end of the program -- which is what is reported then.
        """
        if self.frames:
            return tuple(f[2] for f in self.frames)
        return (self._top_length,)

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # A frame is already a tuple of its seven fields, so the call stack
        # goes in as it stands rather than being unpacked field by field --
        # which is what a frame being a value rather than a record buys.
        return (
            tuple(self.stack),
            frozenset(self.vars.items()),
            self.frames,
            self.io.position(),
        )

    def _apply(self, fx: _StackFx) -> None:
        """Apply a step's stack effects, in order: pops, reverse, pushes.

        The order is what the commands mean: an operand is consumed before
        its result is pushed, and ``P`` reverses what is left rather than
        what a later push will add.  No command currently reverses *and*
        pushes, so nothing depends on the last two being in this order --
        fixing it here is what keeps that from becoming a question.
        """
        pops, pushes, reverse = fx
        if pops:
            del self.stack[len(self.stack) - pops :]
        if reverse:
            self.stack.reverse()
        self.stack.extend(pushes)

    def step(self) -> None:
        """Execute one command, finishing any frames that are now complete.

        The two ports live here rather than in the transition: this is the
        shell.  ``W``'s line is read before the transition runs and ``Y``'s
        value is written after it, dispatched on the value's type.
        """
        if self.halted:
            return

        code, _, pc, mode, _, _, _ = self.frames[-1]

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
    machine = _Machine.of(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
