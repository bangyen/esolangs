r"""Interpreter for ROTfuck."""

import sys

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_CYCLE = "+-><,.[]"
_COMMANDS = frozenset(_CYCLE)


# : One instant of a run:.
# : pointer, the cursor, and.
# : :func:`_advance` maps.
# :.
# : ``rot`` is the language.
# : *effective* command at a.
# : steps along the cycle, so.
# : reading -- which is why it.
#: not.
type _State = tuple[tuple[int, ...], int, int, int]


# : Each command's index in.
# : than a ``str.index`` scan.
# : steps is.
# : membership test, since a.
_OPCODE = {ch: i for i, ch in enumerate(_CYCLE)}


def _at(chars: tuple[str, ...], rot: int, i: int) -> str:
    r"""Return the effective command at ``i`` under rotation ``rot``."""
    code = _OPCODE.get(chars[i], -1)
    return _CYCLE[(code + rot) % 8] if code >= 0 else chars[i]


def _forward(chars: tuple[str, ...], rot: int, i: int) -> int | None:
    r"""Return the ``]`` matching the effective ``[`` at ``i``, if any."""
    depth = 1
    j = i + 1
    while j < len(chars):
        ch = _at(chars, rot, j)
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return None


def _backward(chars: tuple[str, ...], rot: int, i: int) -> int | None:
    r"""Return the ``[`` matching the effective ``]`` at ``i``, if any."""
    depth = 1
    j = i - 1
    while j >= 0:
        ch = _at(chars, rot, j)
        if ch == "]":
            depth += 1
        elif ch == "[":
            depth -= 1
            if depth == 0:
                return j
        j -= 1
    return None


class _Program:
    r"""A ROTfuck program with an implicit rotation count."""

    def __init__(self, code: str) -> None:
        r"""Store ``code`` with a zero rotation count."""
        # The source never changes --.
        # tuple every caller wants is.
        # lookup.
        # to read one character, which.
        self._chars = tuple(code)
        self._rot = 0

    def rotate(self) -> None:
        r"""Advance the rotation count by one (a command executed)."""
        self._rot += 1

    def rotation(self) -> int:
        r"""Return how many commands have executed (the implicit rotation)."""
        return self._rot

    def set_rotation(self, rot: int) -> None:
        r"""Set the rotation count, for a caller that computed it elsewhere."""
        self._rot = rot

    def chars(self) -> tuple[str, ...]:
        r"""Return the unrotated source characters."""
        return self._chars

    def at(self, i: int) -> str:
        r"""Return the effective command at ``i`` under the current rotation."""
        return _at(self._chars, self._rot, i)


def _advance(state: _State, chars: tuple[str, ...], byte: int | None = None) -> _State:
    r"""Return the state after executing the command under the cursor."""
    tape, ptr, ind, rot = state
    char = _at(chars, rot, ind)

    if char == ">":
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
    elif char == "<":
        if ptr:
            ptr -= 1
    elif char == "+":
        tape = (*tape[:ptr], (tape[ptr] + 1) % 256, *tape[ptr + 1 :])
    elif char == "-":
        tape = (*tape[:ptr], (tape[ptr] - 1) % 256, *tape[ptr + 1 :])
    elif char == ",":
        # Reduced like ``+`` and ``-``.
        # whole code point, so an input.
        # otherwise put that code point.
        # docstring describes, and left.
        # the next ``+`` reduced what.
        tape = (
            *tape[:ptr],
            (byte if byte is not None else 0) % 256,
            *tape[ptr + 1 :],
        )
    elif char == "[" and tape[ptr] == 0:
        rot += 1
        partner = _forward(chars, rot, ind)
        if partner is None:
            raise HaltError("an executed '[' has no bracket partner")
        return (tape, ptr, partner + 1, rot)
    elif char == "]" and tape[ptr] != 0:
        rot += 1
        partner = _backward(chars, rot, ind)
        if partner is None:
            raise HaltError("an executed ']' has no bracket partner")
        return (tape, ptr, partner + 1, rot)

    if char in _COMMANDS:
        rot += 1
    return (tape, ptr, ind + 1, rot)


class _Machine:
    r"""Per-run ROTfuck state: the rotating program, tape, pointer, and."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Start with an empty tape at the origin and a fresh program."""
        self.io = io
        self.prog = _Program(code)
        self.tape: tuple[int, ...] = (0,)
        self.ptr = 0
        self.ind = 0
        self._size = len(code)

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the source."""
        return self.ind >= self._size

    # The VM's language-shaped.
    # tape.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.tape)

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.prog.rotation(),
            self.tape,
            self.ptr,
            self.ind,
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (self.tape, self.ptr, self.ind, self.prog.rotation())

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        self.tape, self.ptr, self.ind, rot = state
        self.prog.set_rotation(rot)

    def step(self) -> None:
        r"""Execute one command, advancing the cursor and rotation."""
        if self.halted:
            return
        char = self.prog.at(self.ind)

        byte = None
        if char == ".":
            self.io.print_char(chr(self.tape[self.ptr]))
        elif char == ",":
            byte = self.io.input_char()

        chars = self.prog.chars()
        try:
            self._restore(_advance(self._state, chars, byte))
        except HaltError:
            # A jumping bracket rotates.
            # one leaves the rotation.
            # The original mutated the.
            # keeping that means recording.
            self.prog.rotate()
            raise


def run(code: str, io: IO) -> None:
    r"""Run a ROTfuck program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
