r"""Interpreter for Eval.

Commands manipulate two stacks: 0 pushes 0, \\ pushes the current stack index,
^ duplicates, + and - adjust the top, = moves a value to the other stack, ;
pops, ~ switches stacks, * reverses, ? skips the next command on a zero pop,
and ! evaluates the popped string as a program.

Arithmetic on a non-numeric top, or ``!`` on a non-string value, is an invalid
operation and halts the program with :class:`~esolangs.exceptions.HaltError`.

The execution model is a pure function over an immutable ``_Core``: the two
stacks and the active index.  :func:`_iterate` maps a core and a command to
the next core, and never mutates what it is given.

``!`` evaluates a string as a program.  That nested program runs on an
explicit *frame stack* rather than through Python recursion: ``!`` pushes a
frame and returns, and the next ``step()`` continues inside it.  MyScript's
machine is built the same way, and for the same reasons.

Doing it this way is what makes nesting visible to the rest of the library.
One command is one ``step()`` however deep it sits, so the VM's step budget
counts honestly; every intermediate state reaches ``snapshot()``, so the
state-cycle detector can prove a nested loop; and nesting depth is data
rather than Python stack, so a self-referential program no longer dies with
``RecursionError``.  Running a nested program to completion inside its
caller's step hid all three.

A frame stack is also what lets the *ancestor* check apply.  Endless
recursion pushes a frame per call and pops none, so the whole-state
snapshot grows forever and never repeats -- the unbounded-growth class
:func:`esolangs.vm.run_until_halt_or_cycle` cannot decide.
:func:`esolangs.vm.run_until_halt_or_ancestor` decides it instead, by
comparing each pushed frame against the ones beneath it, and
:meth:`_Machine.frame_entry_key` is what it compares.

Because a step is one command again, it prints at most once, so the effects
stay in the shell the way every other interpreter here does it.

:class:`_Machine` accepts the program in its constructor, as the other
interpreters do.  It stores the text in the first frame rather than parsing
it, because Eval's commands are one character wide.
"""

from __future__ import annotations

import sys
from collections.abc import Hashable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: A value on a stack: Eval's stacks hold both.
type _Val = int | str

#: The part of a run the pure layer owns: ``(ptr, (stack0, stack1))`` -- the
#: active stack index and both stacks.  A value, not a record: every
#: transition below returns a new one rather than editing one in place.
#:
#: The code cursor is *not* in here.  Cursors belong to frames: a nested
#: ``!`` gets its own, while the stacks are shared by every frame.
type _Core = tuple[int, tuple[tuple[_Val, ...], tuple[_Val, ...]]]

#: One frame on the call stack: the program it is running and how far in.
#: A plain tuple, rebuilt rather than edited, so the whole stack is a value
#: the cycle detector can hash.
type _Frame = tuple[str, int]

#: Every value an Eval command can change: the shared two-stack core and the
#: immutable call-frame stack.  Program text lives in its frame; ports stay
#: in the shell.
type _State = tuple[_Core, tuple[_Frame, ...]]


class _Fault(Exception):  # noqa: N818 - an internal signal, not an error type
    """Raised inside the pure layer for an invalid operation.

    The shell turns it into the :class:`HaltError` the language documents.
    It carries nothing: a step is one command now, so anything printed
    before the fault was printed by an earlier step and is already out.
    A caller never sees this type.
    """


def _pushed(core: _Core, value: _Val) -> _Core:
    """Return ``core`` with ``value`` pushed on the active stack."""
    ptr, stacks = core
    active = (*stacks[ptr], value)
    return (ptr, (active, stacks[1]) if ptr == 0 else (stacks[0], active))


def _popped(core: _Core) -> tuple[_Core, _Val]:
    """Return ``core`` without its top, and the value that was on top.

    An empty stack is an invalid operation.
    """
    ptr, stacks = core
    if not stacks[ptr]:
        raise _Fault
    rest, value = stacks[ptr][:-1], stacks[ptr][-1]
    return (ptr, (rest, stacks[1]) if ptr == 0 else (stacks[0], rest)), value


def _iterate(
    core: _Core, sym: str, ind: int
) -> tuple[_Core, int, _Val | None, str | None]:
    """Execute one command, returning core, index, any output, any call.

    Pure: it reads ``core`` and returns a new one, and reaches no ``IO``.
    A ``.`` reports the value it would print and a ``!`` reports the
    program it would enter; the shell prints the one and pushes a frame for
    the other.  Both are ``None`` for every other command.

    ``!`` deliberately does *not* run the nested program here.  Returning
    it to the caller is what puts it on the frame stack, and that is what
    makes each of its commands a step of its own.
    """
    ptr, stacks = core
    char = sym[ind]
    output: _Val | None = None
    call: str | None = None
    if char == "`":
        core = _pushed(core, 1 - ptr)
    elif char == "^":
        if not stacks[ptr]:
            raise _Fault
        core = _pushed(core, stacks[ptr][-1])
    elif char == "0":
        core = _pushed(core, 0)
    elif char in "+-":
        core, value = _popped(core)
        if not isinstance(value, int):
            raise _Fault
        core = _pushed(core, value + (1 if char == "+" else -1))
    elif char == ".":
        core, output = _popped(core)
    elif char == "=":
        core, value = _popped(core)
        ptr, stacks = core
        other = (*stacks[1 - ptr], value)
        core = (ptr, (stacks[0], other) if ptr == 0 else (other, stacks[1]))
    elif char == ";":
        core, _value = _popped(core)
    elif char == "~":
        core = (ptr ^ 1, stacks)
    elif char == "*":
        reversed_ = stacks[ptr][::-1]
        core = (ptr, (reversed_, stacks[1]) if ptr == 0 else (stacks[0], reversed_))
    elif char == "?":
        core, value = _popped(core)
        if not value:
            ind += 1
    elif char == "!":
        core, value = _popped(core)
        if not isinstance(value, str):
            raise _Fault
        call = value
    elif char in "\"'":
        # A literal runs to the next quote, or to the end of the program
        # when there is none -- which is what ``partition`` returns either
        # way, with no unmatched case to fall back on.
        text = sym[ind + 1 :].partition('"')[0].replace("`", '"')
        ind += len(text) + 1
        core = _pushed(core, f'"{text}"' if char == "'" else text)
    return core, ind + 1, output, call


class _Machine:
    """Two stacks with an index choosing the active one, and a frame stack."""

    ptr: int
    stk: tuple[tuple[_Val, ...], tuple[_Val, ...]]
    io: IO
    sym: str
    frames: tuple[_Frame, ...]

    def __init__(self, code: str, io: IO) -> None:
        """Build a state running ``code``."""
        self.ptr = 0
        self.stk = ((), ())
        self.io = io
        self.sym = code
        self.frames = ((code, 0),) if code else ()

    @property
    def ind(self) -> int:
        """The innermost frame's cursor.

        The outermost frame's cursor when nothing is nested, which is what
        this meant before the frame stack existed.  Past the end once every
        frame has returned, so ``halted`` still reads as it did.
        """
        return self.frames[-1][1] if self.frames else len(self.sym)

    @property
    def halted(self) -> bool:
        """Whether every frame has returned."""
        return not self.frames

    # The VM's language-shaped view: two stacks and an active index, so
    # ``stack`` is whichever one ``ptr`` selects and there are no
    # addressable cells.

    @property
    def ip(self) -> tuple[int, int]:
        """The call depth and the innermost frame's cursor.

        A pair rather than a bare cursor, because a cursor alone no longer
        says where a run is: the same position means different things in
        the top-level program and in a nested one.
        """
        return (len(self.frames), self.ind)

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the active stack."""
        return []

    @property
    def stack(self) -> list[int | str]:
        """The active stack, the one ``ptr`` currently selects.

        Eval's stacks hold strings as well as ints, which the VM's
        ``Sequence[object]`` accepts as it stands.
        """
        return list(self.stk[self.ptr])

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        The whole frame stack goes in, not just the innermost cursor: two
        runs sitting at the same position in the same nested program go on
        to different places if their callers differ.  That is what lets a
        nested loop be proved rather than merely time out.
        """
        return (
            self.ptr,
            self.stk,
            tuple(self.frames),
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        """The complete changing state at the command boundary."""
        return ((self.ptr, self.stk), self.frames)

    def _restore(self, state: _State) -> None:
        """Write a pure command transition back onto the machine shell."""
        (self.ptr, self.stk), self.frames = state

    def frame_entry_key(self, frame: _Frame) -> Hashable:
        """Return what ``frame`` is about to run, for the ancestor check.

        Two frames with equal keys replay each other.  For Eval that is the
        program text and the cursor into it -- but also *both stacks*,
        because frames here share one store rather than carrying their own
        bindings: the same program run twice does different things if the
        values beneath it differ, and only the stacks say so.

        The input cursor joins them for the reason Fargo and Forbin include
        it, though Eval never reads input at all, so it never varies.

        See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        sym, ind = frame
        return (
            sym,
            ind,
            self.ptr,
            self.stk,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command of the innermost frame.

        One command, however deep -- so a nested program's commands are
        steps in their own right.  An exhausted frame pops, which is a step
        too; that is what returning from a call costs.

        The print and the :class:`HaltError` live here because this is the
        shell.  A step prints at most once now, so there is nothing to
        collect: the fault carries no outputs, since anything printed
        before it was printed by an earlier step and is already out.
        """
        core, frames = self._state
        if not frames:
            return
        sym, ind = frames[-1]
        if ind >= len(sym):
            self._restore((core, frames[:-1]))
            return
        try:
            core, ind, output, call = _iterate(core, sym, ind)
        except _Fault:
            raise HaltError from None
        if output is not None:
            self.io.print_value(output)
        frames = (*frames[:-1], (sym, ind))
        if call is not None:
            # The nested program becomes a frame of its own rather than
            # running here, which is what makes its commands steps.
            frames = (*frames, (call, 0))
        self._restore((core, frames))


def run(code: str, io: IO) -> None:
    """Run an Eval program."""
    state = _Machine(code, io)
    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
