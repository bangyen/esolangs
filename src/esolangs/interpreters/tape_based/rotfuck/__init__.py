"""Interpreter for ROTfuck.

Brainfuck whose program rotates: every executed command turns all
non-comment characters one step around ``+-><,.[]``.  A comment is passed
over without rotating: only executed commands advance the rotation.

* **Direction** (``rotation``).  The prose turns ``+`` into ``-``, but then
  the wiki's one-character cat ``,[`` fires a ``]`` with no ``[`` and
  prints nothing.  Turned the other way (``+`` into ``]``) it reads ``<.``
  after the ``,`` and echoes one character.  Examples outrank prose, so the
  default is ``"backward"``; ``"forward"`` follows the prose.  The wiki
  Hello World prints no greeting in either direction.
* **Brackets** seek their partner in the program as it stands, then the
  program rotates: the rotation comes "after the instruction is executed",
  and the jump is part of executing it.  A jump lands one past the partner.
  A partnerless bracket that fires raises
  :class:`~esolangs.exceptions.HaltError` without rotating; unbalanced
  sources are legal.

Tape as plain Brainfuck: 8-bit, :class:`EOFError` on exhausted input, and
``<`` at the leftmost cell grows the tape a zero cell on the left (the spec
says nothing about the left edge, and brainfuck's page allows cells left of
the start).  The rotation count is tracked and the effective character
derived, not the text rewritten.
"""

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.tape_based.rotfuck._dialect import (
    ROTFUCK_CYCLES as CYCLES,
)
from esolangs.interpreters.tape_based.rotfuck._dialect import (
    rotation as validate_rotation,
)

_COMMANDS = frozenset(CYCLES["forward"])


#: One instant of a run: ``(tape, ptr, ind, rot)`` -- the cells, the cell
#: pointer, the cursor, and how many commands have executed.  A value
#: :func:`_advance` maps forward, with the tape as a ``tuple``.
#:
#: ``rot`` is the language.  The source text never changes, but the
#: *effective* command at a position is its character advanced ``rot``
#: steps along the cycle, so the rotation count is what a step is really
#: reading -- which is why it belongs in the state and the characters do
#: not.
type _State = tuple[tuple[int, ...], int, int, int]


#: Each command's index in each cycle, so the rotation is an addition rather
#: than a ``str.index`` scan.  The dict doubles as the membership test,
#: since a comment is exactly a character it does not hold.
_OPCODES = {cycle: {ch: i for i, ch in enumerate(cycle)} for cycle in CYCLES.values()}


def _at(chars: tuple[str, ...], rot: int, i: int, cycle: str) -> str:
    """Return the effective command at ``i`` under rotation ``rot``.

    Arithmetic on a precomputed opcode: the hottest function, and a cycle
    scan was 46% of a generated program's runtime.
    """
    code = _OPCODES[cycle].get(chars[i], -1)
    return cycle[(code + rot) % 8] if code >= 0 else chars[i]


def _forward(chars: tuple[str, ...], rot: int, i: int, cycle: str) -> int | None:
    """Return the ``]`` matching the effective ``[`` at ``i``, if any."""
    depth = 1
    j = i + 1
    while j < len(chars):
        ch = _at(chars, rot, j, cycle)
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return None


def _backward(chars: tuple[str, ...], rot: int, i: int, cycle: str) -> int | None:
    """Return the ``[`` matching the effective ``]`` at ``i``, if any."""
    depth = 1
    j = i - 1
    while j >= 0:
        ch = _at(chars, rot, j, cycle)
        if ch == "]":
            depth += 1
        elif ch == "[":
            depth -= 1
            if depth == 0:
                return j
        j -= 1
    return None


def _jump(chars: tuple[str, ...], rot: int, ind: int, cycle: str) -> int:
    """Return the cursor after the firing bracket at ``ind``: one past its partner."""
    char = _at(chars, rot, ind, cycle)
    seek = _forward if char == "[" else _backward
    partner = seek(chars, rot, ind, cycle)
    if partner is None:
        raise HaltError(
            f"an executed '{char}' has no bracket partner",
            hint="pair each executed [ with a matching ]",
        )
    return partner + 1


class _Program:
    """A ROTfuck program with an implicit rotation count."""

    def __init__(self, code: str, cycle: str) -> None:
        """Store ``code`` with a zero rotation count."""
        # The source never changes -- only the rotation count does -- so the
        # tuple every caller wants is built once here rather than per
        # lookup.  It was rebuilt on each ``at`` call, an O(len(code)) copy
        # to read one character, which alone was 15% of a run.
        self._chars = tuple(code)
        self._rot = 0
        self.cycle = cycle

    def rotation(self) -> int:
        """Return how many commands have executed (the implicit rotation)."""
        return self._rot

    def set_rotation(self, rot: int) -> None:
        """Set the rotation count, for a caller that computed it elsewhere."""
        self._rot = rot

    def chars(self) -> tuple[str, ...]:
        """Return the unrotated source characters."""
        return self._chars

    def at(self, i: int) -> str:
        """Return the effective command at ``i`` under the current rotation."""
        return _at(self._chars, self._rot, i, self.cycle)


def _advance(
    state: _State,
    chars: tuple[str, ...],
    byte: int | None = None,
    cycle: str = CYCLES["backward"],
) -> _State:
    """Return the state after executing the command under the cursor.

    A firing bracket seeks *before* the rotation and lands one past the
    partner.  A comment advances without rotating; a false-guarded bracket
    does rotate.
    """
    tape, ptr, ind, rot = state
    char = _at(chars, rot, ind, cycle)

    if char == ">":
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
    elif char == "<":
        # At cell 0 the tape grows a zero cell on the left, and index 0 is
        # now that cell; see the module docstring.
        if ptr:
            ptr -= 1
        else:
            tape = (0, *tape)
    elif char == "+":
        tape = (*tape[:ptr], (tape[ptr] + 1) % 256, *tape[ptr + 1 :])
    elif char == "-":
        tape = (*tape[:ptr], (tape[ptr] - 1) % 256, *tape[ptr + 1 :])
    elif char == ",":
        # Reduced like ``+`` and ``-`` above.  ``input_char`` returns a
        # whole code point, so an input line starting above U+00FF
        # otherwise put that code point on the 8-bit tape this module's
        # docstring describes, and left the cell disagreeing with itself:
        # the next ``+`` reduced what ``,`` had not.
        tape = (
            *tape[:ptr],
            (byte if byte is not None else 0) % 256,
            *tape[ptr + 1 :],
        )
    elif (char == "[") == (tape[ptr] == 0) and char in "[]":
        return (tape, ptr, _jump(chars, rot, ind, cycle), rot + 1)

    if char in _COMMANDS:
        rot += 1
    return (tape, ptr, ind + 1, rot)


class _Machine:
    """Per-run ROTfuck state: the rotating program, tape, pointer, and cursor.

    Rotation, tape and cursor determine the next command, so a revisit is a cycle.
    """

    def __init__(self, code: str, io: IO, *, rotation: str = "backward") -> None:
        """Start with an empty tape at the origin and a fresh program."""
        self.io = io
        self.prog = _Program(code, CYCLES[validate_rotation(rotation)])
        self.tape: tuple[int, ...] = (0,)
        self.ptr = 0
        self.ind = 0
        self._size = len(code)

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the source."""
        return self.ind >= self._size

    # The VM's language-shaped view: Rotating tape + cursor; ip the cursor, memory the
    # tape.

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.prog.rotation(),
            self.tape,
            self.ptr,
            self.ind,
            self.io.progress(),
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.tape, self.ptr, self.ind, self.prog.rotation())

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        ``tape`` stays the immutable tuple (a list was converted for no one).
        """
        self.tape, self.ptr, self.ind, rot = state
        self.prog.set_rotation(rot)

    def step(self) -> None:
        """Execute one command, advancing the cursor and rotation.

        Both ports consult the effective character, not the source one.
        """
        if self.halted:
            return
        char = self.prog.at(self.ind)

        byte = None
        if char == ".":
            self.io.print_char(chr(self.tape[self.ptr]))
        elif char == ",":
            byte = self.io.input_char()

        self._restore(_advance(self._state, self.prog.chars(), byte, self.prog.cycle))


def run(code: str, io: IO, *, rotation: str = "backward") -> None:
    """Run a ROTfuck program."""
    cycle = CYCLES[validate_rotation(rotation)]
    chars = tuple(code)
    tape = bytearray(1)
    ptr = 0
    ind = 0
    rot = 0
    while ind < len(chars):
        char = _at(chars, rot, ind, cycle)
        if char == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif char == "<":
            if not ptr:
                # Grow left as ``_advance`` does, but by doubling, so a
                # long leftward walk stays linear; the extra cells are zero
                # and nothing here reads an absolute index.
                ptr = len(tape)
                tape[:0] = bytes(ptr)
            ptr -= 1
        elif char == "+":
            tape[ptr] = (tape[ptr] + 1) % 256
        elif char == "-":
            tape[ptr] = (tape[ptr] - 1) % 256
        elif char == ".":
            io.print_char(chr(tape[ptr]))
        elif char == ",":
            tape[ptr] = io.input_char() % 256
        elif (char == "[") == (tape[ptr] == 0) and char in "[]":
            ind = _jump(chars, rot, ind, cycle)
            rot += 1
            continue

        if char in _COMMANDS:
            rot += 1
        ind += 1
