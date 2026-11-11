"""Interpreter for HQ9+.

ASCII H/Q are case-insensitive; other characters are ignored.  H prints
"Hello, world!" plus newline.  Q prints exact source without adding a
newline.  9 prints 99 descending verses and the store verse, two lines per
verse with one blank line between verses.  + increments an unbounded
accumulator.  No input is read, so EOF never arises, and no error arises.

Decisions:
    * H's text: the spec's `Print "hello, world"` links to the Hello,
      world! page and gives no punctuation.
    * 9's text: the spec names the song and no text.
"""

from collections.abc import Mapping
from functools import partial
from typing import Any

from esolangs.languages.hq9.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO

type _State = tuple[int, int]

_WORKSPACE_MODEL = WorkspaceModel(
    "hq9-v1", ("instruction", "accumulator", "input_cursor")
)


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
        self.size = len(code)
        self.io = io
        self.state: _State = (0, 0)

    @property
    def halted(self) -> bool:
        return self.state[0] >= self.size

    @property
    def ip(self) -> int:
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        return [self.state[1]]

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.progress())

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture named semantic fields independently of cycle grouping."""
        instruction, accumulator = self.state
        return _WORKSPACE_MODEL.capture(
            instruction=instruction,
            accumulator=accumulator,
            input_cursor=self.io.progress(),
        )

    def step(self) -> None:
        if self.halted:
            return
        self.state, output = _advance(self.state, self.code)
        if output is not None:
            self.io.print_str(output)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Bind fresh machines; hq9 has no runtime options."""
    if not isinstance(source, str):
        raise TypeError("hq9 machines require text source")
    if options:
        raise TypeError("hq9 machines accept no runtime options")
    return RuntimePlan(partial(_Machine, source), partial(_execute, source))


def _execute(code: str, io: IO) -> CompletionReport:
    """Run HQ9+ in source order."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run HQ9+ in source order."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
