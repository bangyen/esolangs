"""Interpreter for ROTfuck.

Brainfuck whose program rotates: every executed command turns all
non-comment characters one step around ``+-><,.[]``.  A comment is passed
over without rotating: only executed commands advance the rotation.
Tape as plain Brainfuck: 8-bit.  The rotation count is tracked and the
effective character derived, not the text rewritten.  Brackets seek their
partner in the program as it stands, then the program rotates; a jump, ``[``
or ``]``, resumes at the instruction after the partner (partner + 1).
Unbalanced sources are legal.

Errors:
    InputExhaustedError: ``,`` at EOF.
    ArgumentError: A ``rotation`` setting other than ``backward`` or
        ``forward`` (the interpreter itself raises ValueError).
    HaltError: A partnerless bracket that fires: the run aborts with this
        error (not a clean halt), before that bracket rotates.

Decisions:
    * Direction (``rotation``).  The prose turns ``+`` into ``-``, but then
      the wiki's one-character cat ``,[`` fires a ``]`` with no ``[`` and
      prints nothing.  Turned the other way (``+`` into ``]``) it reads
      ``<.`` after the ``,`` and echoes one character.  Examples outrank
      prose, so the default is ``"backward"``; ``"forward"`` follows the
      prose.  The wiki Hello World prints no greeting in either direction.
    * The rotation comes "after the instruction is executed", and the jump
      is part of executing it, so a bracket seeks before the rotation.
    * ``<`` at the leftmost cell grows the tape a zero cell on the left (the
      spec says nothing about the left edge, so a cell left of the start is
      allowed).
"""

from collections.abc import Mapping
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.languages.rotfuck.dialect import ROTFUCK_CYCLES, validate_rotation
from esolangs.languages.rotfuck.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO

_COMMANDS = frozenset(ROTFUCK_CYCLES["forward"])


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

_WORKSPACE_MODEL = WorkspaceModel(
    "rotfuck-v1", ("rotation", "tape", "pointer", "instruction", "input_cursor")
)


def _at(chars: tuple[str, ...], rot: int, i: int, cycle: str) -> str:
    """Return the effective command at ``i`` under rotation ``rot``.

    The index is a cycle scan: the 46% scan share the old comment cited
    came from a different workload, and the table earned nothing
    measurable on this repo's fresh-machine-per-row workload.
    """
    char = chars[i]
    if char not in cycle:
        # A comment: passed over without rotating.
        return char
    return cycle[(cycle.index(char) + rot) % 8]


def _partner(
    chars: tuple[str, ...], rot: int, i: int, cycle: str, step: int
) -> int | None:
    """Return the bracket matching the effective one at ``i``, if any.

    ``step`` is 1 to scan right from a ``[`` and -1 to scan left from a ``]``.
    """
    opener, closer = ("[", "]") if step == 1 else ("]", "[")
    depth = 1
    j = i + step
    while 0 <= j < len(chars):
        ch = _at(chars, rot, j, cycle)
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return j
        j += step
    return None


def _jump(chars: tuple[str, ...], rot: int, ind: int, cycle: str) -> int:
    """Return the cursor after the firing bracket at ``ind``: one past its partner."""
    char = _at(chars, rot, ind, cycle)
    partner = _partner(chars, rot, ind, cycle, 1 if char == "[" else -1)
    if partner is None:
        raise HaltError(
            f"an executed '{char}' has no bracket partner",
            hint="pair each executed [ with a matching ]",
        )
    return partner + 1


type _Image = tuple[tuple[str, ...], str]


def _prepare_source(code: str, rotation: str) -> _Image:
    return tuple(code), ROTFUCK_CYCLES[validate_rotation(rotation)]


class _Program:
    """A ROTfuck program with an implicit rotation count."""

    def __init__(self, chars: tuple[str, ...], cycle: str) -> None:
        """Bind immutable source to a zero rotation count."""
        self._chars = chars
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
    cycle: str = ROTFUCK_CYCLES["backward"],
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

    def __init__(
        self, code: str | _Image, io: IO, *, rotation: str = "backward"
    ) -> None:
        """Start with an empty tape at the origin and a fresh program."""
        self.io = io
        chars, cycle = (
            _prepare_source(code, rotation) if isinstance(code, str) else code
        )
        self.prog = _Program(chars, cycle)
        self.tape: tuple[int, ...] = (0,)
        self.ptr = 0
        self.ind = 0
        self._size = len(chars)

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

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        return _WORKSPACE_MODEL.capture(
            rotation=self.prog.rotation(),
            tape=self.tape,
            pointer=self.ptr,
            instruction=self.ind,
            input_cursor=self.io.progress(),
        )

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


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain the source characters and selected rotation cycle."""
    if not isinstance(source, str):
        raise TypeError("rotfuck machines require text source")
    if options.keys() - {"rotation"}:
        raise TypeError("rotfuck machines accept only the rotation runtime option")
    image = _prepare_source(source, options.get("rotation", "backward"))
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(
    code: str | _Image, io: IO, *, rotation: str = "backward"
) -> CompletionReport:
    """Run a ROTfuck program through its pure transition."""
    return drive(_Machine(code, io, rotation=rotation), policy=CAPABILITIES.completion)


def run(code: str, io: IO, *, rotation: str = "backward") -> None:
    """Run a ROTfuck program through its pure transition."""
    _execute(code, io, rotation=rotation)


if __name__ == "__main__":
    script_main(run)
