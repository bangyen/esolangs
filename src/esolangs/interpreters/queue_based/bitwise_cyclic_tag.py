"""Interpreter for Bitwise Cyclic Tag.

A program is a bitstring executed cyclically over a data-bitstring that is
extensible to the right.  ``0`` deletes the leftmost data-bit.  ``1x`` is a
composite pair: it appends ``x`` to the right end when that leftmost bit is
1, and deletes nothing.  Execution starts at the leftmost program-bit and
halts when the data-string becomes empty; an initially empty program or
data-string halts at once, which is the wiki's own first sentence.

Two spec gaps are decided here, both because the wiki writes a system as
prose ("program 0011, data 1") and never fixes a file format:

- **The source carries both strings, separated by a comma**, program first.
  All whitespace is ignored, so a long program may be broken across lines
  without changing it.  A source with no comma is a program with an empty
  data-string, which halts immediately -- legal, and the wiki names it.
- **The answer is the bit the last ``0`` consumes**, printed once the run
  ends.  BCT has no I/O vocabulary at all, and the wiki says a simulated
  machine's "input and output" are "encoded in the sequence of deleted
  data-bits", so the last deletion is where a result already lives.  Nothing
  is printed when no ``0`` ever fires, which only a degenerate program does.

A character outside ``01,`` and a second comma raise :class:`ValueError`.
No operation can be invalid once a program parses -- every step either
deletes a bit that is there or appends one -- so no
:class:`~esolangs.exceptions.HaltError` arises.  Nothing is read, so no
``EOFError`` can come from here: a program's inputs are in its data-string.

Unlike its sibling in this directory the data-string is not threaded through
:func:`_advance` as a value.  A run appends ``Theta(T)`` bits, and copying
the string per append would cost ``Theta(T**2)`` for a generated program
that is meant to be linear, so the transition reads the leftmost bit as an
argument and returns the bit to append as an effect -- ``grapheme.py``'s
arrangement, for the same reason.  Deletion is a cursor, never a slice.
"""

from __future__ import annotations

from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: One instant of a run: ``(head, read, answer, printed)`` -- the program
#: position, the index of the leftmost live data-bit, the bit the last ``0``
#: consumed, and whether the answer has been printed.  The program and the
#: data-string are not in it: the program is fixed for the run, and the
#: data-string is the store the transition takes a view of.
type _State = tuple[int, int, str | None, bool]


def _parse(code: str) -> tuple[str, str, tuple[int, ...]]:
    """Return the program, the initial data-string, and each bit's offset.

    Whitespace is dropped, so a wrapped program parses as written -- which
    is also why the offsets are kept: a program position is not an index
    into the source a caller handed in, and a debugger wants the source.
    """
    kept = [(at, c) for at, c in enumerate(code) if not c.isspace()]
    stray = next((c for _at, c in kept if c not in "01,"), None)
    if stray is not None:
        raise ValueError(
            f"{stray!r} is not a Bitwise Cyclic Tag bit; a source is 0s and "
            f"1s, with one ',' between the program and the data-string"
        )
    commas = [i for i, (_at, c) in enumerate(kept) if c == ","]
    if len(commas) > 1:
        # Two commas is almost always three fields, which means the writer
        # expected a syntax this language does not have.  Naming the count
        # beats "unexpected ','" at a position they then have to count to.
        raise ValueError(
            f"a Bitwise Cyclic Tag source has one ',' at most, got "
            f"{len(commas)}: the program, then the data-string"
        )
    split = commas[0] if commas else len(kept)
    program = "".join(c for _at, c in kept[:split])
    data = "".join(c for _at, c in kept[split + 1 :])
    return program, data, tuple(at for at, _c in kept[:split])


def _advance(state: _State, program: str, bit: str) -> tuple[_State, str | None]:
    """Return the state after one command, and the bit to append.

    Pure.  ``bit`` is the leftmost live data-bit, which the shell reads out
    of the store; the append leaves as the return value.  A ``1`` takes the
    program-bit after it as its operand, cyclically, so a one-bit program
    ``1`` is its own operand.
    """
    head, read, answer, printed = state
    size = len(program)
    if program[head] == "0":
        # The deleted bit *is* the answer, overwritten each time, so the one
        # that survives the run is the last one deleted.
        return ((head + 1) % size, read + 1, bit, printed), None
    operand = program[(head + 1) % size]
    return ((head + 2) % size, read, answer, printed), operand if bit == "1" else None


class _Machine:
    """Per-run state: the program position, and a cursor into the data."""

    #: Whether the answer is written on the step *after* the halt.  It
    #: belongs to the language, not to whoever is stepping it: ``run`` ends
    #: its loop with one more ``step()``, so a caller who stops at ``halted``
    #: has driven the program correctly and still holds none of its output.
    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        """Parse ``code`` into the program and the initial data-string."""
        self.io = io
        self.program, data, self.offsets = _parse(code)
        #: The data-string, append-only.  ``read`` is where the live part
        #: starts; the bits behind it are deleted, and kept only so that
        #: nothing has to be copied.
        self.data = list(data)
        self.state: _State = (0, 0, None, False)

    # The language's own names, as views on the state rather than fields of
    # their own, so there is one place a step can change.

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
        return self.state[2]

    @property
    def live(self) -> str:
        """The data-string as it stands, the deleted prefix dropped."""
        return "".join(self.data[self.state[1] :])

    @property
    def halted(self) -> bool:
        """Whether the data-string is empty, the program included.

        An empty program halts at once however much data there is: there is
        no command to execute and none will appear.
        """
        return not self.program or self.state[1] >= len(self.data)

    # The VM's language-shaped view: the data-string is the store, and there
    # is no stack.

    @property
    def ip(self) -> int | None:
        """Where in the *source* the command about to run was written.

        The default ``offset`` shape, which the program position is not: the
        comma and any whitespace sit in the source and not in the program,
        so the two part company on the first newline a wrapper inserts.
        ``None`` for an empty program, which has no command to point at.
        """
        return self.offsets[self.state[0]] if self.program else None

    @property
    def memory(self) -> list[int]:
        """The live data-string, leftmost first."""
        return [int(bit) for bit in self.data[self.state[1] :]]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        The *live* data-string, not the whole list: the deleted prefix is
        unreachable, so two instants that differ only there are the same
        instant and a detector must see them as one.  ``printed`` stays out,
        as the detector compares states of a running machine.
        """
        head, read, answer, _printed = self.state
        return (self.program, head, self.live, answer, read, self.io.position())

    def step(self) -> None:
        """Execute one command, printing the answer once the data runs out."""
        head, read, answer, printed = self.state
        if self.halted:
            if not printed and answer is not None:
                self.io.print_str(answer)
            self.state = (head, read, answer, True)
            return
        self.state, append = _advance(self.state, self.program, self.data[read])
        if append is not None:
            self.data.append(append)


def run(code: str, io: IO) -> None:
    """Run a BCT program, printing the bit its last deletion consumed."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    machine.step()  # the post-halt step prints the answer


if __name__ == "__main__":
    script_main(run)
