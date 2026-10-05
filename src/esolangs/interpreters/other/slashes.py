"""/// (Slashalash): repeated leftmost literal substitutions.

Backslash escapes one character in output, patterns, and replacements.
An incomplete rule halts; an empty pattern diverges. No stdin is read, so
EOFError does not arise. Source has no invalid characters or ValueError cases.
"""

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

type _State = tuple[str, str | None, str]


def _field(source: str) -> tuple[str, str] | None:
    """Read one escaped, slash-terminated field."""
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


def _advance(state: _State) -> tuple[_State, str]:
    """Perform one rule parse, substitution, or output character."""
    source, pattern, replacement = state
    if pattern is not None:
        if not pattern:
            return state, ""
        at = source.find(pattern)
        if at < 0:
            return (source, None, ""), ""
        return (
            source[:at] + replacement + source[at + len(pattern) :],
            pattern,
            replacement,
        ), ""
    if not source:
        return state, ""
    if source[0] == "\\":
        return (source[2:], None, ""), source[1:2]
    if source[0] != "/":
        return (source[1:], None, ""), source[0]
    first = _field(source[1:])
    if first is None:
        return ("", None, ""), ""
    pattern, rest = first
    second = _field(rest)
    if second is None:
        return ("", None, ""), ""
    replacement, rest = second
    return (rest, pattern, replacement), ""


class _Machine:
    """Remaining source and active substitution."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.state: _State = (code, None, "")
        self.io = io

    @property
    def halted(self) -> bool:
        return not self.state[0] and self.state[1] is None

    @property
    def ip(self) -> None:
        return None

    @property
    def memory(self) -> list[int]:
        return [ord(c) for c in self.state[0]]

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.position())

    def step(self) -> None:
        self.state, output = _advance(self.state)
        if output:
            self.io.print_str(output)


def run(code: str, io: IO) -> None:
    """Execute /// using literal leftmost rewriting."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
