"""Interpreter for Brainfuck.

The tape is 8-bit wrapping and grows rightward, ``<`` is clamped at the
left edge, and loops are matching-bracket.  The transpiler targets are held
to these same semantics, which is what lets each one be verified
end-to-end.

The execution model is a pure function over an immutable :class:`_State`:
:func:`_advance` maps a state and a command to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.  The
tape is a tuple, so a state is a value that can be stored, compared, and
hashed as it stands -- which is what ``snapshot`` returns directly rather
than rebuilding.

:class:`_Machine` is the mutable shell the interpreter protocol requires
(``esolangs.vm`` wraps it, ``run_until_halt_or_cycle`` steps it, and
``factor.py`` drives a decoded program through it).  It holds one
:class:`_State` and rebinds it each step, so the mutation lives in exactly
one assignment and every rule about what brainfuck *does* stays in the pure
layer.  The one effect a command can have, ``.`` and ``,``'s I/O, is done
by ``step`` before it calls the pure transition -- effects in the shell,
rules in the core.

The brainfuck spec defines ``[``/``]`` only for matched pairs; a program
with unbalanced brackets is malformed, so the interpreter rejects it with a
:class:`ValueError` rather than inventing a halt the language does not
specify.

The spec leaves EOF undefined for ``,`` (returning zero or leaving the cell
unchanged are both suggested); this interpreter instead raises
:class:`EOFError` when input is exhausted, so the classic `,[.,]` cat
program terminates with an error rather than a graceful halt.
"""

from __future__ import annotations

import sys
from typing import NamedTuple

from esolangs.interpreters.brackets import match_brackets as matches
from esolangs.interpreters.io import IO


class _State(NamedTuple):
    """One instant of a run: the tape, the pointer, and the code position.

    A NamedTuple rather than a mutable record because every transition
    below returns a new state instead of editing one in place.  The tape is
    a ``tuple`` for the same reason, and it buys the hashability that the
    cycle detector needs: ``snapshot`` can hand this object's fields back
    without copying a list into a tuple first.

    The code and its bracket map are deliberately *not* here.  Neither
    changes during a run, so carrying them in the state would put constant
    data in every value the cycle detector stores.  They are parameters to
    the transition functions instead.

    The field order is ``ind, ptr, tape`` because ``snapshot`` unpacks this
    tuple directly, and ``_advance`` and ``_step_effect`` unpack it
    positionally -- it is also the order ``snapshot`` returned before the
    state became a value.  Reordering the fields would silently reorder
    every snapshot with it.
    """

    ind: int
    ptr: int
    tape: tuple[int, ...]


def _written(tape: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    """Return ``tape`` with cell ``ptr`` set to ``value``.

    The tape is rebuilt around the one changed cell, which is what an
    immutable tape costs.  It is cheap here because a brainfuck tape is the
    handful of cells a program actually touches -- the repo's own generated
    programs finish in three to five -- not a preallocated array.
    """
    return (*tape[:ptr], value, *tape[ptr + 1 :])


def _advance(state: _State, code: str, brackets: dict[int, int]) -> _State:
    """Return the state after executing the command at ``state.ind``.

    Pure: it reads ``state`` and returns a new one, and every command that
    is not I/O is decided entirely here.  ``.`` and ``,`` reach the ``io``
    object, so their *effect* is done by the caller and this function sees
    only what they leave behind -- ``.`` changes no state at all, and
    ``,``'s new cell value arrives already written.

    The fields are unpacked to locals and a single :class:`_State` is built
    at the end, rather than each branch deriving a state from the last.
    That is a measured choice, not a style one: threading the state through
    per-branch ``_replace`` calls cost two rebuilds per step and made the
    interpreter ~5.6x slower than the mutable original, where building once
    is ~2x.  ``_replace`` goes through ``_make`` and a fresh ``__new__``,
    so it is the expensive way to say what ``_State(...)`` says directly.

    Anything that is not one of the eight commands is a comment and falls
    through to the shared increment, which is what makes the code position
    advance exactly once per call.
    """
    ind, ptr, tape = state
    char = code[ind]
    if char == ">":
        # A ``>`` past the right end grows the tape by one zero cell.
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
    elif char == "<":
        # ``<`` at the left edge is clamped rather than an error.
        if ptr:
            ptr -= 1
    elif char == "+":
        tape = _written(tape, ptr, (tape[ptr] + 1) % 256)
    elif char == "-":
        tape = _written(tape, ptr, (tape[ptr] - 1) % 256)
    elif (char == "[" and tape[ptr] == 0) or (char == "]" and tape[ptr] != 0):
        # Both brackets are one rule with the test inverted, and the jump
        # lands on the partner: the increment below steps past it.
        ind = brackets[ind]
    return _State(ind + 1, ptr, tape)


class _Machine:
    """A Brainfuck run: one immutable :class:`_State`, rebound per step.

    The protocol the rest of the library expects (``step``, ``halted``,
    ``snapshot``, and the ``ind``/``ptr``/``tape`` attributes ``vm.py``
    reads) is mutable by construction, so this class supplies it.  All it
    does is hold the current state and the two constants a transition
    needs; the rules themselves are the pure functions above.
    """

    __slots__ = ("brackets", "code", "io", "size", "state")

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = matches(code)
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here
        # rather than recomputed on every one of those reads.
        self.size = len(code)
        self.state = _State(ind=0, ptr=0, tape=(0,))

    # ``vm.py`` reads these three off the machine, and ``factor.py``
    # snapshots through it.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state.tape

    @property
    def ptr(self) -> int:
        return self.state.ptr

    @property
    def ind(self) -> int:
        return self.state.ind

    @property
    def halted(self) -> bool:
        return self.state.ind >= self.size

    # The VM's language-shaped view: Tape + pointer; ip is the code cursor, memory the
    # tape.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The state is already a hashable tuple of exactly the fields a
        # step can change, so this only appends the input cursor: a repeat
        # that ignores consumed input is not a real cycle.
        return (*self.state, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the code position.

        The two character commands are done here rather than in a function
        of their own: this is the shell, so it is where an effect belongs,
        and it keeps :func:`_advance` reachable in one call per step.
        ``.`` writes and changes no state; ``,`` reads and leaves the byte
        in the cell, so the pure transition then runs on what they left
        behind and never needs the ``io`` object at all.
        """
        state = self.state
        ind = state.ind
        if ind >= self.size:
            return
        char = self.code[ind]
        if char == ".":
            self.io.print_char(chr(state.tape[state.ptr]))
        elif char == ",":
            ptr = state.ptr
            byte = self.io.input_char()
            state = _State(ind, ptr, _written(state.tape, ptr, byte))
        self.state = _advance(state, self.code, self.brackets)


def run(code: str, io: IO) -> None:
    """Run a Brainfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
