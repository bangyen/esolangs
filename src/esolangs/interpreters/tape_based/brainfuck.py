"""Interpreter for Brainfuck.

The tape is 8-bit wrapping and grows rightward, ``<`` is clamped at the
left edge, and loops are matching-bracket.  The transpiler targets are held
to these same semantics, which is what lets each one be verified
end-to-end.

The execution model is a pure function over an immutable :class:`_State`:
:func:`_advance` maps a state and a command to the next state, and never
mutates what it is given.  The tape is a tuple, so a state is a value that
can be stored, compared, and hashed as it stands -- which is what
``snapshot`` returns directly rather than rebuilding.  The one effect a
command can have, ``.`` and ``,``'s I/O, is pushed to the edge: the two
character commands are handled in :func:`_step_effect` before the pure
transition runs, so :func:`_advance` itself is total and side-effect free.

:class:`_Machine` is the mutable shell the interpreter protocol requires
(``esolangs.vm`` wraps it, ``run_until_halt_or_cycle`` steps it, and
``factor.py`` drives a decoded program through it).  It holds one
:class:`_State` and rebinds it each step, so the mutation lives in exactly
one assignment and every rule about what brainfuck *does* stays in the pure
layer.

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
    tuple directly, and that was the order it returned before the state
    became a value.  Reordering the fields would silently reorder every
    snapshot with it.
    """

    ind: int
    ptr: int
    tape: tuple[int, ...]


def _write(state: _State, value: int) -> _State:
    """Return ``state`` with the cell under the pointer set to ``value``.

    The tape is rebuilt around the one changed cell.  Slicing keeps this a
    single expression, and the tape here is the handful of cells a
    brainfuck program actually touches, not a preallocated array.
    """
    tape = state.tape
    return state._replace(tape=(*tape[: state.ptr], value, *tape[state.ptr + 1 :]))


def _move(state: _State, delta: int) -> _State:
    """Return ``state`` with the pointer moved by ``delta``.

    ``<`` at the left edge is clamped rather than an error, and a ``>``
    past the right end grows the tape by one zero cell -- the two edge
    rules the module docstring pins, both of which live here so no caller
    repeats them.
    """
    ptr = state.ptr + delta
    if ptr < 0:  # ``<`` at the left edge: clamped, so the state is unchanged.
        return state
    tape = (*state.tape, 0) if ptr == len(state.tape) else state.tape
    return state._replace(tape=tape, ptr=ptr)


def _jump(state: _State, code: str, brackets: dict[int, int]) -> _State:
    """Return ``state`` with the code position taken through a bracket.

    Both brackets are the same rule with the test inverted: ``[`` jumps
    when the cell is zero and ``]`` jumps when it is not.  The jump lands
    on the partner, and the caller's unconditional increment then steps
    past it, which is why neither branch adds one here.
    """
    char = code[state.ind]
    cell = state.tape[state.ptr]
    if (char == "[" and cell == 0) or (char == "]" and cell != 0):
        return state._replace(ind=brackets[state.ind])
    return state


def _advance(state: _State, code: str, brackets: dict[int, int]) -> _State:
    """Return the state after executing the command at ``state.ind``.

    Pure: it reads ``state`` and returns a new one, and every command that
    is not I/O is decided entirely here.  ``.`` and ``,`` reach the
    ``io`` object, so their *effect* is done by the caller and this
    function sees only what they leave behind -- ``.`` changes no state at
    all, and ``,``'s new cell value arrives already written.

    Anything that is not one of the eight commands is a comment and falls
    through to the shared increment, which is also what makes the code
    position advance exactly once per call.
    """
    char = code[state.ind]
    if char == ">":
        state = _move(state, 1)
    elif char == "<":
        state = _move(state, -1)
    elif char == "+":
        state = _write(state, (state.tape[state.ptr] + 1) % 256)
    elif char == "-":
        state = _write(state, (state.tape[state.ptr] - 1) % 256)
    elif char in "[]":
        state = _jump(state, code, brackets)
    return state._replace(ind=state.ind + 1)


def _step_effect(state: _State, code: str, io: IO) -> _State:
    """Run the I/O for the command at ``state.ind``, if it has any.

    This is the whole of the interpreter's contact with the outside world.
    ``.`` writes and returns the state untouched; ``,`` reads and returns
    the state with the byte already stored, so that :func:`_advance` has
    nothing left to do for either.  Every other command returns ``state``
    unchanged.
    """
    char = code[state.ind]
    if char == ".":
        io.print_char(chr(state.tape[state.ptr]))
    elif char == ",":
        return _write(state, io.input_char())
    return state


class _Machine:
    """A Brainfuck run: one immutable :class:`_State`, rebound per step.

    The protocol the rest of the library expects (``step``, ``halted``,
    ``snapshot``, and the ``ind``/``ptr``/``tape`` attributes ``vm.py``
    reads) is mutable by construction, so this class supplies it.  All it
    does is hold the current state and the two constants a transition
    needs; the rules themselves are the pure functions above.
    """

    __slots__ = ("brackets", "code", "io", "state")

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = matches(code)
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
        return self.state.ind >= len(self.code)

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
        """Execute one command, advancing the code position."""
        if self.halted:
            return
        state = _step_effect(self.state, self.code, self.io)
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
