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

Eval needs a richer shape than the other interpreters here, because ``!``
runs a whole program *inside one step* -- and that program can print any
number of times, and can fault after it has already printed.  So the pure
layer cannot simply leave I/O to the shell: it collects the values a step
prints, in order, and reports whether the step ended in a fault.  The shell
writes the collected values out and only then raises.  That ordering is the
language's: a nested program that prints twice and then faults has printed
twice.

This is minifuck's ``_Effect`` shape widened from one effect to a list of
them, which is what nesting costs.

:class:`State` keeps its name and its ``of`` constructor: the VM builds
this one through ``.of()`` rather than the usual ``_Machine(code, io)``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

#: A value on a stack: Eval's stacks hold both.
type _Val = int | str

#: The part of a run the pure layer owns: ``(ptr, (stack0, stack1))`` -- the
#: active stack index and both stacks.  A value, not a record: every
#: transition below returns a new one rather than editing one in place.
#:
#: The code cursor is *not* in here.  A nested ``!`` runs its own program to
#: completion with its own cursor, so the cursor belongs to whoever is
#: driving a program rather than to the stacks the programs share.
type _Core = tuple[int, tuple[tuple[_Val, ...], tuple[_Val, ...]]]


class _Fault(Exception):  # noqa: N818 - an internal signal, not an error type
    """Raised inside the pure layer to unwind to the step that started it.

    It carries the values printed before the fault, so the shell can write
    them out before raising the :class:`HaltError` the language documents.
    A caller never sees this type.
    """

    def __init__(self, outputs: list[_Val]) -> None:
        super().__init__("eval fault")
        self.outputs = outputs


def _pushed(core: _Core, value: _Val) -> _Core:
    """Return ``core`` with ``value`` pushed on the active stack."""
    ptr, stacks = core
    active = (*stacks[ptr], value)
    return (ptr, (active, stacks[1]) if ptr == 0 else (stacks[0], active))


def _popped(core: _Core, outputs: list[_Val]) -> tuple[_Core, _Val]:
    """Return ``core`` without its top, and the value that was on top.

    An empty stack is an invalid operation, and the fault carries the
    outputs written so far so they are not lost on the way out.
    """
    ptr, stacks = core
    if not stacks[ptr]:
        raise _Fault(outputs)
    rest, value = stacks[ptr][:-1], stacks[ptr][-1]
    return (ptr, (rest, stacks[1]) if ptr == 0 else (stacks[0], rest)), value


def _iterate(
    core: _Core,
    sym: str,
    ind: int,
    outputs: list[_Val],
) -> tuple[_Core, int]:
    """Execute one command of ``sym`` at ``ind``, returning core and index.

    Pure with respect to the outside world: printing appends to ``outputs``
    rather than reaching an ``IO``, which is what lets a nested ``!`` run
    here at all -- its prints join the same list, in order, and the shell
    writes them once the step is over.

    ``!`` recurses through :func:`_execute`, so a program evaluated inside
    a step runs to completion before the step ends.  That is the language's
    rule, not an implementation choice: the cursor of the outer program
    does not advance until the inner one finishes.
    """
    ptr, stacks = core
    char = sym[ind]
    if char == "`":
        core = _pushed(core, 1 - ptr)
    elif char == "^":
        if not stacks[ptr]:
            raise _Fault(outputs)
        core = _pushed(core, stacks[ptr][-1])
    elif char == "0":
        core = _pushed(core, 0)
    elif char in "+-":
        core, value = _popped(core, outputs)
        if not isinstance(value, int):
            raise _Fault(outputs)
        core = _pushed(core, value + (1 if char == "+" else -1))
    elif char == ".":
        core, value = _popped(core, outputs)
        outputs.append(value)
    elif char == "=":
        core, value = _popped(core, outputs)
        ptr, stacks = core
        other = (*stacks[1 - ptr], value)
        core = (ptr, (stacks[0], other) if ptr == 0 else (other, stacks[1]))
    elif char == ";":
        core, _value = _popped(core, outputs)
    elif char == "~":
        core = (ptr ^ 1, stacks)
    elif char == "*":
        reversed_ = stacks[ptr][::-1]
        core = (ptr, (reversed_, stacks[1]) if ptr == 0 else (stacks[0], reversed_))
    elif char == "?":
        core, value = _popped(core, outputs)
        if not value:
            ind += 1
    elif char == "!":
        core, value = _popped(core, outputs)
        if not isinstance(value, str):
            raise _Fault(outputs)
        core = _execute(core, value, outputs)
    elif char in "\"'":
        # A literal runs to the next quote, or to the end of the program
        # when there is none -- which is what ``partition`` returns either
        # way, with no unmatched case to fall back on.
        text = sym[ind + 1 :].partition('"')[0].replace("`", '"')
        ind += len(text) + 1
        core = _pushed(core, f'"{text}"' if char == "'" else text)
    return core, ind + 1


def _execute(core: _Core, sym: str, outputs: list[_Val]) -> _Core:
    """Run a whole program to completion (a nested ``!`` evaluation)."""
    ind = 0
    while ind < len(sym):
        core, ind = _iterate(core, sym, ind, outputs)
    return core


@dataclass
class State:
    """Two stacks with an index choosing the active one, and the code cursor."""

    ptr: int = 0
    stk: list[list[int | str]] = field(default_factory=lambda: [[], []])
    io: IO = field(default_factory=IO)
    sym: str = ""
    ind: int = 0

    @classmethod
    def of(cls, code: str, io: IO) -> State:
        """Build a state running ``code``.

        The program is the ``sym`` field, so positionally it sits behind
        ``io`` and a caller could not simply pass ``(code, io)`` the way
        every other interpreter here is built.  Naming the two makes the
        construction the same shape as everyone else's.
        """
        return cls(io=io, sym=code)

    @property
    def halted(self) -> bool:
        """Whether the code cursor has run off the program."""
        return self.ind >= len(self.sym)

    # The VM's language-shaped view: two stacks and an active index, so
    # ``stack`` is whichever one ``ptr`` selects and there are no
    # addressable cells.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.ind

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
        return self.stk[self.ptr]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ptr,
            tuple(tuple(s) for s in self.stk),
            self.ind,
            self.io.position(),
        )

    def step(self) -> None:
        """Execute one command, advancing the code cursor.

        The printing and the :class:`HaltError` both live here: this is the
        shell, so it is where an effect or a raise belongs.  The pure layer
        hands back everything the step printed, and a fault brings its
        outputs with it -- so a nested program that printed twice and then
        faulted has printed twice, exactly as the eager original did.
        """
        if self.halted:
            return
        core: _Core = (self.ptr, (tuple(self.stk[0]), tuple(self.stk[1])))
        outputs: list[_Val] = []
        try:
            core, ind = _iterate(core, self.sym, self.ind, outputs)
        except _Fault as fault:
            for value in fault.outputs:
                self.io.print_value(value)
            raise HaltError from None
        for value in outputs:
            self.io.print_value(value)
        self.ptr, stacks = core
        self.stk = [list(stacks[0]), list(stacks[1])]
        self.ind = ind


def run(code: str, io: IO) -> None:
    """Run an Eval program."""
    state = State.of(code, io)
    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
