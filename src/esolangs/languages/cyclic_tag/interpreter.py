"""Cyclic tag interpreter.

Source is ``p0;p1;...;pk,queue``: bit-string productions, a comma, then the
initial bit queue.  Whitespace is ignored and productions may be empty.  Each
step deletes the queue's first bit and, if it was 1, appends the current
production; either way the next production comes up.  The queue running dry
halts the machine, which then prints the last deleted bit.

Input/output:
    No stdin is read.  The output is the last deleted bit.

Errors:
    ProgramError: Not exactly one comma, a character outside ``01;,``, or a
        semicolon in the queue.
"""

from __future__ import annotations

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


def _parse(code: str) -> tuple[tuple[str, ...], list[str], tuple[int, ...]]:
    """Return the productions, the queue, and each production's source offset."""
    positions = [at for at, c in enumerate(code) if not c.isspace()]
    source = "".join(code[at] for at in positions)
    if source.count(",") != 1 or not set(source) <= set("01;,"):
        raise syntax_error(
            "Cyclic tag requires productions,queue using bits and semicolons",
            (
                "write semicolon-separated bit productions, then a comma "
                "and bit queue; for example 1;0,1"
            ),
        )
    rules, queue = source.split(",")
    if ";" in queue:
        raise syntax_error(
            "Cyclic tag queue contains a semicolon",
            "put semicolons only before the comma; the queue is a bit string",
        )
    # A production starts the source or follows a semicolon, and the comma
    # always comes later, so an empty production still has a character.
    starts = [0, *(i + 1 for i, c in enumerate(source) if c == ";")]
    return tuple(rules.split(";")), list(queue), tuple(positions[i] for i in starts)


def _advance(read: int, program: tuple[str, ...], bit: str) -> tuple[int, str]:
    """Delete the front bit; a 1 returns the production to append."""
    return read + 1, program[read % len(program)] if bit == "1" else ""


class _Machine:
    """An append-only queue and a count of the bits deleted from its front.

    Every step deletes exactly one bit, so that count also picks the
    production and names the last deleted bit: it is the whole control state.
    """

    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.program, self.data, self._starts = _parse(code)
        # Deleting advances ``read`` rather than shifting ``data``: O(1) a step.
        self.read = 0
        self.printed = False

    @property
    def halted(self) -> bool:
        return self.read == len(self.data)

    @property
    def head(self) -> int:
        """The index of the production the next step uses."""
        return self.read % len(self.program)

    @property
    def answer(self) -> str | None:
        """The last deleted bit, or None before the first deletion."""
        return self.data[self.read - 1] if self.read else None

    @property
    def live(self) -> str:
        return "".join(self.data[self.read :])

    @property
    def ip(self) -> int:
        return self._starts[self.head]

    @property
    def memory(self) -> list[int]:
        return [int(c) for c in self.live]

    def snapshot(self) -> tuple[object, ...]:
        # Deleted bits cannot affect a later step, except the answer.  It and
        # its printed flag are one output latch: the workspace ledger's +1 bit.
        latch = (self.answer, self.printed)
        return (self.head, self.live, latch, self.io.progress())

    def step(self) -> None:
        if not self.halted:
            # The append is an effect so the growing queue is never copied.
            self.read, append = _advance(self.read, self.program, self.data[self.read])
            self.data.extend(append)
        elif self.answer is not None and not self.printed:
            self.io.print_str(self.answer)
            self.printed = True


def run(code: str, io: IO) -> None:
    """Print the last bit deleted before the queue empties."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
