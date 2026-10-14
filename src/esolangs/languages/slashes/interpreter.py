r"""/// (Slashalash): a program that rewrites itself until nothing is left.

The source is consumed from the left.  A plain character is printed, and
``\x`` prints ``x``.  ``/pattern/replacement/`` is a rule: it is removed,
then the leftmost ``pattern`` in the rest of the source is replaced by
``replacement``, again and again until none is left, and reading resumes.
Inside a rule ``\`` escapes one character too.  The run ends when the
source is empty.

An incomplete rule halts; an empty pattern diverges. No stdin is read, so
EOFError does not arise. Source has no invalid characters or ValueError cases.
"""

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
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

    def snapshot(self) -> tuple[object, ...]:
        # Flat, as the ledger's exact workspace bound measures it.
        source, rule = self.state
        return (source, *(rule or (None, "")), self.io.progress())

    def step(self) -> None:
        self.state, output = _advance(self.state)
        if output:
            self.io.print_str(output)


def run(code: str, io: IO) -> None:
    """Execute /// using literal leftmost rewriting."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
