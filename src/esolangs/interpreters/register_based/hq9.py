"""Interpreter for HQ9+.

ASCII H/Q are case-insensitive; other characters are ignored. H prints
"Hello, world!" plus newline; Q prints exact source without adding a newline.
9 prints 99 descending verses and the store verse, two lines per verse with
one blank line between verses. These formatting choices pin the wiki's
varying implementations. + increments an unbounded accumulator. No input,
EOFError, ValueError or HaltError arises.
"""

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

type _State = tuple[int, int]


def _bottles(count: int) -> str:
    return f"{count} bottle{'s' if count != 1 else ''}" if count else "no more bottles"


def _verse(count: int) -> str:
    bottles = _bottles(count)
    if count:
        action = f"Take one down and pass it around, {_bottles(count - 1)}"
    else:
        action = "Go to the store and buy some more, 99 bottles"
    return (
        f"{bottles.capitalize()} of beer on the wall, {bottles} of beer.\n"
        f"{action} of beer on the wall.\n"
    )


_SONG = "\n".join(_verse(count) for count in range(99, -1, -1))


def _advance(state: _State, code: str) -> tuple[_State, str | None]:
    ind, accumulator = state
    command = code[ind]
    output = None
    if command in "Hh":
        output = "Hello, world!\n"
    elif command in "Qq":
        output = code
    elif command == "9":
        output = _SONG
    elif command == "+":
        accumulator += 1
    return (ind + 1, accumulator), output


class _Machine:
    """Source position and accumulator."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.state: _State = (0, 0)

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.code)

    @property
    def ip(self) -> int:
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        return [self.state[1]]

    @property
    def stack(self) -> list[object]:
        return []

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.position())

    def step(self) -> None:
        if self.halted:
            return
        self.state, output = _advance(self.state, self.code)
        if output is not None:
            self.io.print_str(output)


def run(code: str, io: IO) -> None:
    """Run HQ9+ in source order."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
