"""Interpreter for Nope.

Every source, including empty source, prints exactly "Nope." and halts.
No parsing or input is performed; no newline is appended.  No error arises
under the constant-language semantics.
"""

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime.io import IO

type _State = bool


def _advance(state: _State) -> tuple[_State, str | None]:
    return True, None if state else "Nope."


class _Machine:
    """One constant-output transition, independent of source."""

    def __init__(self, code: str, io: IO) -> None:  # noqa: ARG002 - source is ignored
        self.io = io
        self.state: _State = False

    @property
    def halted(self) -> bool:
        return self.state

    @property
    def ip(self) -> int:
        return int(self.state)

    def snapshot(self) -> tuple[object, ...]:
        return (self.state, self.io.progress())

    def step(self) -> None:
        self.state, output = _advance(self.state)
        if output is not None:
            self.io.print_str(output)


def _execute(code: str, io: IO) -> CompletionReport:
    """Print the constant answer once."""
    return drive(_Machine(code, io))


def run(code: str, io: IO) -> None:
    """Print the constant answer once."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
