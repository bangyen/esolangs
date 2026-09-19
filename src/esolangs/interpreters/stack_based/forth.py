"""Interpreter for Forþ.

Digits 0-9 and A-F push, ``:`` duplicates, ``+``/``-``/``*``/``/``/``%``
do arithmetic (top on the right), ``~`` complements, ``.`` prints the top
as a character, ``,`` reads a line pushing each byte (rightmost on top),
``(``/``[`` branch/loop while the top is nonzero, ``{`` stores a scope
under the number atop the stack, ``;`` calls it, ``o`` reverses, ``c``
rotates three, ``v`` swaps two; anything else is ignored.

Arithmetic wraps to signed 32-bit and ``/``/``%`` truncate toward zero
(C++11).  An empty-stack pop halts with :class:`HaltError`; the other
invalid operations (binary op under two values, ``c`` under three,
division by zero, unterminated bracket) abort only the innermost scope,
as the cross-check's discarded status did.  ``,`` raises
:class:`EOFError` at end of input (the cross-check exits 3) and pushes
unsigned bytes; ``.`` prints the low byte (``& 0xFF``), so ``.`` on
``-1`` prints 0xFF.

:class:`_Machine` has an explicit call stack (one frame per scope);
``halted`` is true once no frame remains and a repeated
:meth:`_Machine.snapshot` proves a loop.  A top-level abort sets
``_Machine.error`` so :func:`run` raises :class:`HaltError`.
"""

import sys
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def _wrap32(value: int) -> int:
    """Wrap ``value`` to a signed 32-bit integer (C++ ``int`` arithmetic)."""
    return (value + 2**31) % 2**32 - 2**31


def _trunc_div(a: int, b: int) -> int:
    """C++-style integer division, truncating toward zero."""
    return int(a / b)


def _trunc_mod(a: int, b: int) -> int:
    """C++-style remainder (the sign of the dividend)."""
    return a - _trunc_div(a, b) * b


@dataclass(frozen=True)
class _Frame:
    """One active scope: its code, cursor, and whether it is a ``[`` loop body."""

    code: str
    pc: int = 0
    loop: bool = False


#: One instant of a run: ``(stack, table, frames, error)`` -- the shared
#: operand stack, the scope table ``{`` fills and ``;`` calls, the frame
#: stack, and whether the *top-level* scope aborted.
#:
#: The frames are the reason this is a stack rather than a cursor: ``;``
#: and all three bracket forms push one, and a ``[`` body is re-pushed
#: whenever it finishes with a nonzero top.  A frame carries its own code,
#: because a called scope runs text that is not the program's.
#:
#: ``error`` is state and not an exception: an abort ends the innermost
#: scope the way completing it would, and only at the top level does it
#: mean the run failed.  ``run`` reads it after the loop.
type _Frames = tuple[_Frame, ...]
type _State = tuple[tuple[int, ...], dict[int, str], _Frames, bool]


def _top(stack: tuple[int, ...]) -> int:
    """Return the top of ``stack``, halting when there is none."""
    if not stack:
        raise HaltError("the stack is empty, so there is no top value to read")
    return stack[-1]


def _at(frame: _Frame, pc: int) -> _Frame:
    """Return ``frame`` with its cursor moved to ``pc``."""
    return _Frame(frame.code, pc, frame.loop)


def _finalize(state: _State) -> _State:
    """Pop completed frames, re-running a ``[`` body while its top holds.

    A fresh pass is finalized by a later step, so an empty body is a no-op
    step whose repeated snapshot proves a hang.
    """
    stack, table, frames, error = state
    while frames and frames[-1].pc >= len(frames[-1].code):
        frame = frames[-1]
        if frame.loop and _top(stack) != 0:
            return (
                stack,
                table,
                (*frames[:-1], _Frame(frame.code, 0, loop=True)),
                error,
            )
        frames = frames[:-1]
    return (stack, table, frames, error)


def _abort(state: _State) -> _State:
    """End the innermost scope on an invalid operation (status 3).

    Behaves like the scope completing; a top-level scope halts with
    ``error`` set.
    """
    stack, table, frames, error = state
    top_level = len(frames) == 1
    frame = frames[-1]
    ended = (stack, table, (*frames[:-1], _at(frame, len(frame.code))), error)
    stack, table, frames, error = _finalize(ended)
    return (stack, table, frames, error or top_level)


def _scan(frame: _Frame, add: str, sub: str) -> tuple[str, int] | None:
    """Return a bracket's body and the cursor past it, or ``None`` if open."""
    start = frame.pc - 1
    pc = frame.pc
    match = 1
    while True:
        if pc >= len(frame.code):
            return None
        inner = frame.code[pc]
        pc += 1
        if inner == add:
            match += 1
        elif inner == sub:
            match -= 1
        # Tested after the advance, so the cursor ends one *past* the
        # closing bracket rather than on it.
        if match == 0:
            break
    return (frame.code[start + 1 : pc - 1], pc)


def _advance(state: _State, line: str | None = None) -> _State:
    """Return the state after executing one command of the active frame.

    Pure; ``.``'s value is read by the caller first, ``,``'s line arrives
    as ``line``.  An abort is a value, not a raise, which is why a called
    scope's invalid operation is swallowed and a top-level one fails.
    """
    state = _finalize(state)
    stack, table, frames, error = state
    if not frames:
        return state
    frame = frames[-1]
    if frame.pc >= len(frame.code):
        return state  # a finished pass (an empty loop body) is a no-op step

    char = frame.code[frame.pc]
    frames = (*frames[:-1], _at(frame, frame.pc + 1))
    frame = frames[-1]
    state = (stack, table, frames, error)

    if "0" <= char <= "9":
        return ((*stack, ord(char) - 48), table, frames, error)
    if "A" <= char <= "F":
        return ((*stack, ord(char) - 55), table, frames, error)
    if char == ":":
        return ((*stack, _top(stack)), table, frames, error)
    if char == "~":
        return ((*stack[:-1], ~_top(stack)), table, frames, error)
    if char == ".":
        # The print already happened in the shell; this only pops.
        _top(stack)
        return (stack[:-1], table, frames, error)
    if char == ",":
        read = tuple(ord(ch) & 0xFF for ch in (line or ""))
        return ((*stack, *read), table, frames, error)
    if char == ";":
        scope = table.get(_top(stack), "")
        return (stack[:-1], table, (*frames, _Frame(scope)), error)
    if char == "o":
        return (tuple(reversed(stack)), table, frames, error)
    if char == "c":
        if len(stack) < 3:
            return _abort(state)
        return ((*stack[:-3], *stack[-2:], stack[-3]), table, frames, error)
    if char in "([{":
        sub = ")" if char == "(" else "]" if char == "[" else "}"
        found = _scan(frame, char, sub)
        if found is None:
            # The scan walked to the end without closing, and the original
            # left the cursor there before aborting.
            ended = (stack, table, (*frames[:-1], _at(frame, len(frame.code))), error)
            return _abort(ended)
        scope, pc = found
        frames = (*frames[:-1], _at(frame, pc))
        state = (stack, table, frames, error)
        if char == "(":
            if _top(stack):
                return (stack, table, (*frames, _Frame(scope)), error)
            return state
        if char == "[":
            if _top(stack):
                return (stack, table, (*frames, _Frame(scope, 0, loop=True)), error)
            return state
        return (stack, {**table, _top(stack): scope}, frames, error)
    if char in "+-*/%v":
        if len(stack) < 2:
            return _abort(state)
        two, one = stack[-1], stack[-2]
        rest = stack[:-2]
        # Both operands are consumed before the divisor is tested, so a
        # zero-divisor abort leaves the stack without them.
        popped = (rest, table, frames, error)
        if char == "+":
            return ((*rest, _wrap32(one + two)), table, frames, error)
        if char == "-":
            return ((*rest, _wrap32(one - two)), table, frames, error)
        if char == "*":
            return ((*rest, _wrap32(one * two)), table, frames, error)
        if char == "/":
            if two == 0:
                return _abort(popped)
            return ((*rest, _wrap32(_trunc_div(one, two))), table, frames, error)
        if char == "%":
            if two == 0:
                return _abort(popped)
            return ((*rest, _wrap32(_trunc_mod(one, two))), table, frames, error)
        # The arm admits only ``+-*/%v`` and the other five are handled, so
        # this is ``v``: the swap.
        return ((*rest, two, one), table, frames, error)
    return state


class _Machine:
    """Per-run Forþ state: the shared stack, scope table, and call stack.

    A ``[`` loop that never exhausts its top is a finite-state cycle the
    hang detector can prove.
    """

    def __init__(self, code: str, io: IO) -> None:
        """Start with the top-level ``code`` as the only frame."""
        self.io = io
        self.stack: tuple[int, ...] = ()
        self.table: dict[int, str] = {}
        self.frames: tuple[_Frame, ...] = (_Frame(code),)
        self.error = False  # the top-level scope aborted (status 3)
        # Where the top-level frame ends, kept because ``ip`` still has to
        # report a position after that frame has been popped.
        self._length = len(code)

    @property
    def halted(self) -> bool:
        """Whether every scope has completed."""
        return not self.frames

    # The VM's language-shaped view: a stack language with a frame stack and
    # no addressable cells.

    #: ``ip`` is a position, but not one on the source text: each live frame's pc,
    #: outermost first.
    #: Declared rather than left to the default so that a tuple nobody has
    #: classified is a missing answer instead of this one.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        """Each live frame's pc, outermost first.

        No frames means the top-level one finished at the end of the
        program, which is what is reported then.
        """
        frames = self.frames
        return tuple(f.pc for f in frames) if frames else (self._length,)

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.stack,
            frozenset(self.table.items()),
            tuple((f.code, f.pc, f.loop) for f in self.frames),
            self.io.position(),
        )

    def frame_entry_key(self, frame: _Frame) -> tuple[object, ...]:
        """Return the state a called scope needs to replay an ancestor.

        Scope text plus the shared stack and scope table; ``loop``
        distinguishes a stored scope from a bracket body with the same text.
        See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        return (
            frame.code,
            frame.loop,
            self.stack,
            frozenset(self.table.items()),
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.stack, self.table, self.frames, self.error)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        stack, table, frames, self.error = state
        self.stack = stack
        self.table = table
        self.frames = frames

    def step(self) -> None:
        """Execute one command of the active frame.

        Finished frames are finalized first, as the original did, so the
        ports see the frame about to run.
        """
        if self.halted:
            return
        state = _finalize(self._state)
        stack, _table, frames, _error = state
        char = ""
        if frames and frames[-1].pc < len(frames[-1].code):
            char = frames[-1].code[frames[-1].pc]

        # The cursor moves past the command before the command runs, and
        # the original had already written that when anything it did
        # raised -- an empty stack, or the input port at EOF.  Committing
        # the advance up front reproduces that for every route out.
        #
        # A bracket walks further than one place: its scan runs before the
        # condition is tested, so a raise afterwards leaves the cursor past
        # the whole body.
        stack, table, frames, error = state
        if frames and frames[-1].pc < len(frames[-1].code):
            frame = _at(frames[-1], frames[-1].pc + 1)
            if char in "([{":
                sub = ")" if char == "(" else "]" if char == "[" else "}"
                found = _scan(frame, char, sub)
                frame = _at(frame, found[1] if found else len(frame.code))
            frames = (*frames[:-1], frame)
        self._restore((stack, table, frames, error))

        line = None
        if char == ",":
            line = self.io.input_str()
        elif char == "." and stack:
            self.io.print_char(chr(stack[-1] & 0xFF))

        self._restore(_advance(state, line))


def run(code: str, io: IO) -> None:
    """Run a Forþ program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    if machine.error:
        raise HaltError("the top-level scope aborted, which Forþ reports as status 3")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
