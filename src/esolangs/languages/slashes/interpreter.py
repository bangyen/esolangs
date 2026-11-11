r"""/// (Slashalash): a program that rewrites itself until nothing is left.

The source is consumed from the left.  A plain character is printed, and
``\x`` prints ``x``.  ``/pattern/replacement/`` is a rule: it is removed,
then the leftmost ``pattern`` in the rest of the source is replaced by
``replacement``, again and again until none is left, and reading resumes.
Inside a rule ``\`` escapes one character too.  The run ends when the
source is empty.

An incomplete rule halts; an empty pattern diverges.  No stdin is read, so
EOF does not arise, and no source is invalid, so no ProgramError arises.
"""

from collections.abc import Mapping
from functools import partial
from typing import Any

from esolangs.languages.slashes.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO

#: ``(source, rule)``: the unread program, and the ``(pattern, replacement)``
#: being applied to it, or ``None`` while reading.
type _State = tuple[str, tuple[str, str] | None]


def _field(source: str) -> tuple[str, str] | None:
    """Read one escaped, slash-terminated field; return it and the rest."""
    chars: list[str] = []
    at = 0
    while at < len(source):
        char = source[at]
        if char == "/":
            return "".join(chars), source[at + 1 :]
        if char == "\\":
            at += 1
            if at == len(source):
                return None
            char = source[at]
        chars.append(char)
        at += 1
    return None


def _rule(source: str) -> _State:
    """Parse the rule after a ``/``; an incomplete one empties the source."""
    first = _field(source)
    second = None if first is None else _field(first[1])
    if first is None or second is None:
        return "", None
    return second[1], (first[0], second[0])


def _advance(state: _State) -> tuple[_State, str]:
    """Return the state after one substitution or one read, and its output."""
    source, rule = state
    if rule is not None:
        pattern, replacement = rule
        if not pattern:
            return state, ""  # an empty pattern matches forever
        at = source.find(pattern)
        if at < 0:
            return (source, None), ""
        return (source[:at] + replacement + source[at + len(pattern) :], rule), ""
    if not source:
        return state, ""
    if source[0] == "/":
        return _rule(source[1:]), ""
    if source[0] == "\\":
        return (source[2:], None), source[1:2]
    return (source[1:], None), source[0]


_WORKSPACE_MODEL = WorkspaceModel(
    "slashes-v1", ("source", "pattern", "replacement", "input_cursor")
)


class _Machine:
    """The unread source and the rule being applied to it."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.state: _State = (code, None)
        self.io = io

    @property
    def halted(self) -> bool:
        return self.state == ("", None)

    @property
    def ip(self) -> None:
        return None

    @property
    def memory(self) -> list[int]:
        return [ord(c) for c in self.state[0]]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        source, rule = self.state
        pattern, replacement = rule if rule is not None else (None, "")
        return _WORKSPACE_MODEL.capture(
            source=source,
            pattern=pattern,
            replacement=replacement,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        # Flat, as the ledger's exact workspace bound measures it.
        source, rule = self.state
        return (source, *(rule or (None, "")), self.io.progress())

    def step(self) -> None:
        self.state, output = _advance(self.state)
        if output:
            self.io.print_str(output)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Bind source; each IO-bound construction owns fresh runtime state."""
    if not isinstance(source, str):
        raise TypeError("/// machines require text source")
    if options:
        raise TypeError("/// machines accept no runtime options")

    return RuntimePlan(partial(_Machine, source), partial(_execute, source))


def _execute(code: str, io: IO) -> CompletionReport:
    """Execute /// using literal leftmost rewriting."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Execute /// using literal leftmost rewriting."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
