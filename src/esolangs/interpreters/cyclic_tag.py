"""Cyclic tag interpreter.

Productions are semicolon-separated, followed by a comma and the initial bit
queue. Whitespace is ignored; empty productions are valid. The package prints
the final deleted bit on halt. Invalid source raises ValueError; no stdin is
read, so EOFError does not arise. Appends are effects to avoid copying the queue.
"""

from __future__ import annotations

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.source_hints import syntax_error

#: ``(head, read, answer, printed)``: program position, leftmost live data-bit,
#: the final deleted bit, and whether it is printed.  The program is fixed
#: and the data-string is the store, so neither is in here.
type _State = tuple[int, int, str | None, bool]


def _parse(code: str) -> tuple[tuple[str, ...], str, tuple[int, ...]]:
    """Parse semicolon-separated productions and comma-separated initial data."""
    kept = [(at, c) for at, c in enumerate(code) if not c.isspace()]
    source = "".join(c for _, c in kept)
    if any(c not in "01;," for c in source) or source.count(",") != 1:
        raise syntax_error(
            "Cyclic tag requires productions,queue using bits and semicolons",
            (
                "write semicolon-separated bit productions, then a comma "
                "and bit queue; for example 1;0,1"
            ),
        )
    rules, data = source.split(",")
    if ";" in data:
        raise syntax_error(
            "Cyclic tag queue contains a semicolon",
            "put semicolons only before the comma; the queue is a bit string",
        )
    productions = tuple(rules.split(";"))
    offsets = [kept[0][0]]
    offsets.extend(kept[i + 1][0] for i, (_at, c) in enumerate(kept) if c == ";")
    return productions, data, tuple(offsets)


def _advance(
    state: _State, program: tuple[str, ...], bit: str
) -> tuple[_State, str | None]:
    """Delete one queue bit, conditionally append, and advance the rule."""
    head, read, _answer, printed = state
    return ((head + 1) % len(program), read + 1, bit, printed), (
        program[head] if bit == "1" else None
    )


class _Machine:
    """Cyclic production pointer and append-only queue store."""

    dumps_on_the_post_halt_step = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.program, initial, self.offsets = _parse(code)
        self.data = list(initial)
        self.state: _State = (0, 0, None, False)

    @property
    def halted(self) -> bool:
        return self.read == len(self.data)

    @property
    def head(self) -> int:
        return self.state[0]

    @property
    def read(self) -> int:
        return self.state[1]

    @property
    def live(self) -> str:
        return "".join(self.data[self.read :])

    @property
    def ip(self) -> int:
        return self.offsets[self.head]

    @property
    def memory(self) -> list[int]:
        return [int(c) for c in self.live]

    def snapshot(self) -> tuple[object, ...]:
        # Deleted prefixes cannot affect a later transition.
        return (self.head, self.live, self.state[2:], self.io.progress())

    def step(self) -> None:
        if self.halted:
            position, cursor, answer, printed = self.state
            if answer is not None and not printed:
                self.io.print_str(answer)
            self.state = (position, cursor, answer, True)
        else:
            self.state, append = _advance(
                self.state, self.program, self.data[self.read]
            )
            if append:
                self.data.extend(append)


def run(code: str, io: IO) -> None:
    """Print the final deleted queue bit."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
