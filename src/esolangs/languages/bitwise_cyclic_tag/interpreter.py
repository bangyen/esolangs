"""Interpreter for Bitwise Cyclic Tag.

A program is a bitstring executed cyclically over a data-bitstring extensible
to the right.  ``0`` deletes the leftmost data-bit; ``1x`` is a composite pair
appending ``x`` to the right end when that leftmost bit is 1, deleting nothing.
Execution starts at the leftmost program-bit and halts when the data-string
empties; an initially empty program or data-string halts at once, per the
wiki's first sentence.

Two spec gaps are decided here, the wiki writing a system as prose ("program
0011, data 1") and never fixing a file format.  The source carries both strings
separated by a comma, program first, all whitespace ignored so a long program
may be broken across lines; with no comma it is a program and no data.  And the
answer is the bit the last ``0`` consumes, printed once the run ends: BCT has no
I/O vocabulary, and the wiki puts a simulated machine's "input and output" in
"the sequence of deleted data-bits", so the last deletion is where a result
already lives.  Nothing is printed when no ``0`` ever fires.

A character outside ``01,`` and a second comma raise :class:`ValueError`; no
operation can be invalid once a program parses, so no
:class:`~esolangs.exceptions.HaltError` arises, and nothing is read so no
``EOFError`` comes from here.
"""

from __future__ import annotations

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: ``(head, read)``: program position and leftmost live data-bit.  The program
#: is fixed and the data-string is the store, so neither is in here; nor is the
#: answer, which is the bit just before ``read`` since only ``0`` advances it.
type _State = tuple[int, int]


def _parse(code: str) -> tuple[str, str, tuple[int, ...]]:
    """Return the program, the initial data-string, and each bit's source offset.

    Offsets, because whitespace is dropped: a program position is not a place
    in the source, and a debugger wants the source.
    """
    kept = [(at, c) for at, c in enumerate(code) if not c.isspace()]
    stray = next((c for _at, c in kept if c not in "01,"), None)
    if stray is not None:
        raise syntax_error(
            f"{stray!r} is not a Bitwise Cyclic Tag bit; a source is 0s and "
            f"1s, with one ',' between the program and the data-string",
            "write program,data using only bits; for example 0,1",
        )
    commas = [i for i, (_at, c) in enumerate(kept) if c == ","]
    if len(commas) > 1:
        # Almost always three fields, a syntax this language does not have;
        # the count beats an offset the reader then has to count to.
        raise syntax_error(
            f"a Bitwise Cyclic Tag source has one ',' at most, got "
            f"{len(commas)}: the program, then the data-string",
            "keep at most one comma separating the program from its data",
        )
    split = commas[0] if commas else len(kept)
    program = "".join(c for _at, c in kept[:split])
    data = "".join(c for _at, c in kept[split + 1 :])
    return program, data, tuple(at for at, _c in kept[:split])


# The data-string is not threaded through :func:`_advance`: a run appends ``Theta(T)``
# bits and copying per append would cost ``Theta(T**2)`` for a program meant to be
# linear, so the append leaves as an effect (``grapheme.py``'s arrangement) and
# deletion is a cursor, not a slice.
def _advance(state: _State, program: str, bit: str) -> tuple[_State, str | None]:
    """Return the state after one command, and the bit to append.

    Pure; ``bit`` is the leftmost live data-bit.  A ``1`` takes the program-bit
    after it as its operand, cyclically, so ``1`` alone is its own operand.
    """
    head, read = state
    size = len(program)
    if program[head] == "0":
        return ((head + 1) % size, read + 1), None
    operand = program[(head + 1) % size]
    return ((head + 2) % size, read), operand if bit == "1" else None


class _Machine:
    """Per-run state: the program position, and a cursor into the data."""

    #: The answer is written on the step *after* the halt, so a caller that
    #: stops at ``halted`` has driven the program right and holds no output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into the program and the initial data-string."""
        self.io = io
        self.program, data, self.offsets = _parse(code)
        self.data = list(data)
        self.state: _State = (0, 0)
        self.printed = False

    @property
    def head(self) -> int:
        """The program position, an index into the cyclic program."""
        return self.state[0]

    @property
    def read(self) -> int:
        """Where the live data-string starts."""
        return self.state[1]

    @property
    def answer(self) -> str | None:
        """The bit the last ``0`` consumed, if one has."""
        read = self.state[1]
        return self.data[read - 1] if read else None

    @property
    def live(self) -> str:
        """The data-string as it stands, the deleted prefix dropped."""
        return "".join(self.data[self.state[1] :])

    @property
    def halted(self) -> bool:
        """Whether the data-string is empty, or the program is."""
        return not self.program or self.state[1] >= len(self.data)

    @property
    def ip(self) -> int | None:
        """Where in the *source* the command about to run was written.

        The default ``offset`` shape, which the program position is not: a
        wrapper's newlines are in the source, not the program.  ``None`` for an
        empty program, having no command to point at.
        """
        return self.offsets[self.state[0]] if self.program else None

    @property
    def memory(self) -> list[int]:
        """The live data-string, leftmost first."""
        return [int(bit) for bit in self.data[self.state[1] :]]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        The *live* data-string, the unreachable deleted prefix dropped so two
        instants differing only there are one.  ``printed`` stays out.
        """
        head, read = self.state
        return (self.program, head, self.live, self.answer, read, self.io.progress())

    def step(self) -> None:
        """Execute one command, printing the answer once the data runs out."""
        if self.halted:
            if not self.printed and self.answer is not None:
                self.io.print_str(self.answer)
            self.printed = True
            return
        read = self.state[1]
        self.state, append = _advance(self.state, self.program, self.data[read])
        if append is not None:
            self.data.append(append)


def run(code: str, io: IO) -> None:
    """Run a BCT program, printing the bit its last deletion consumed."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
