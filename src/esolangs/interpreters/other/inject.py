"""Interpreter for Inject.

The state is the program's own text: ``name;`` written once opens a
block and twice closes it; ``send`` writes a block, ``readto`` overwrites
it with a stdin line, ``inject`` rewrites it by regex, and ``skip`` is
the only control flow -- skip the block a next-line label begins, else
jump to the innermost enclosing block's start, else exit.  ``skipif X``
(at least one line) and ``skipq X Y`` (equal) are conditional skips.

Decisions: blocks are lists of lines and ``send`` terminates each with a
newline (the cat program needs it).  ``readto`` at EOF raises
:class:`EOFError`; an empty line stores an empty block (cat terminates
on empty input).  A label, blank line or non-command line is a no-op
(the truth machine falls through a bare ``0``).  Block structure is
fixed at parse; a written-in ``foo;`` is inert.  The innermost block is
the shortest span.  ``inject`` uses :mod:`re`, a malformed regex raising
:class:`~esolangs.exceptions.HaltError`.  A label written a third time,
left open, unknown, or unparsable raises :class:`ValueError`; invalid
runtime operations raise ``HaltError``.  Running off the end halts.

The wiki's truth machine has its cases exchanged under its own prose
(``skipq data 0`` fires on ``0`` and clause 2 loops); the prose is kept
because the cat example depends on the same "only executes if" wording.
``tests/interpreters/test_inject.py`` runs both.  :func:`_advance` is
pure over an immutable ``_State`` whose *lines* are state: a rewrite
moves every later line, the executing one included.  Output is collected
(a ``send`` makes many writes); ``readto``'s line arrives as an argument.
"""

import re
from collections.abc import Mapping, Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

# A label line is exactly a name and a semicolon; the semicolon is not part
# of the name.  Surrounding whitespace is not significant -- the wiki's own
# examples are written flush left, but nothing keys off the indentation.
_LABEL = re.compile(r"(\w+);")


def _spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Return each label's ``(begin, end)`` delimiter line numbers.

    A third occurrence, or a block left open, is a syntax error.
    """
    opened: dict[str, int] = {}
    spans: dict[str, tuple[int, int]] = {}
    for i, line in enumerate(lines):
        match = _LABEL.fullmatch(line.strip())
        if match is None:
            continue
        name = match.group(1)
        if name in spans:
            raise ValueError(f"label written more than twice: {name}")
        if name in opened:
            spans[name] = (opened.pop(name), i)
        else:
            opened[name] = i
    if opened:
        raise ValueError(f"unclosed label-block: {sorted(opened)[0]}")
    return spans


#: A label's two delimiter line numbers, by name.
type _Spans = Mapping[str, tuple[int, int]]

#: One instant of a run: ``(lines, spans, ind, done)`` -- the program text,
#: the label spans over it, the line cursor, and whether ``skip``'s third
#: clause has exited.  A value, not a record: :func:`_advance` returns a new
#: tuple rather than editing one in place.
#:
#: The lines are *in* here because they are the memory: ``readto`` and
#: ``inject`` rewrite the running program, and the spans move with them.
type _State = tuple[Sequence[str], _Spans, int, bool]


def _span(spans: _Spans, name: str) -> tuple[int, int]:
    """Return ``name``'s delimiters, rejecting a label that has none."""
    if name not in spans:
        raise ValueError(f"unknown label: {name}")
    return spans[name]


def _contents(state: _State, name: str) -> list[str]:
    """Return the lines strictly between a label's two delimiters."""
    lines, spans, _, _ = state
    begin, end = _span(spans, name)
    return list(lines[begin + 1 : end])


def _replaced(state: _State, name: str, body: list[str]) -> _State:
    """Return ``state`` with a block's contents overwritten.

    A length change moves the pointer too when the block sits before the
    executing line, or a ``readto`` into an earlier block re-executed itself.
    """
    lines, spans, ind, done = state
    begin, end = _span(spans, name)
    grown = [*lines[: begin + 1], *body, *lines[end:]]
    shift = len(body) - (end - begin - 1)
    if not shift:
        return (grown, spans, ind, done)
    if begin < ind:
        ind += shift
    # Only positions strictly after the opening delimiter move: an
    # overlapping block that begins earlier keeps its own start and has its
    # end pushed along, which is what keeps the two nestings consistent
    # after a rewrite.
    moved = {
        label: (b + shift * (b > begin), e + shift * (e > begin))
        for label, (b, e) in spans.items()
    }
    return (grown, moved, ind, done)


def _begins_block(state: _State, index: int) -> str | None:
    """Return the label beginning a block at ``index``, if any."""
    lines, spans, _, _ = state
    if index >= len(lines):
        return None
    match = _LABEL.fullmatch(lines[index].strip())
    if match is None:
        return None
    name = match.group(1)
    span = spans.get(name)
    return name if span is not None and span[0] == index else None


def _innermost(state: _State) -> str | None:
    """Return the shortest block strictly containing the pointer."""
    _, spans, ind, _ = state
    inside = [n for n, (b, e) in spans.items() if b < ind < e]
    if not inside:
        return None
    return min(inside, key=lambda n: spans[n][1] - spans[n][0])


def _skipped(state: _State) -> _State:
    """Return the state after ``skip``'s three-clause jump."""
    lines, spans, ind, _ = state
    ahead = _begins_block(state, ind + 1)
    if ahead is not None:
        return (lines, spans, spans[ahead][1] + 1, False)
    inner = _innermost(state)
    if inner is not None:
        return (lines, spans, spans[inner][0], False)
    return (lines, spans, ind, True)


def _injected(state: _State, rest: str) -> _State:
    """Run ``inject X=S/R``: substitute ``S`` with ``R`` in block ``X``."""
    name, sep, expression = rest.partition("=")
    if not sep:
        raise ValueError(f"inject needs a label and a regex: {rest}")
    # The pattern cannot contain a slash, so the *first* slash is the
    # separator and everything after it is the replacement -- which may
    # itself contain slashes.
    pattern, sep, replacement = expression.partition("/")
    if not sep:
        raise ValueError(f"inject needs a replacement: {rest}")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise HaltError(f"invalid regex: {pattern}") from exc
    body = [compiled.sub(replacement, line) for line in _contents(state, name)]
    return _replaced(state, name, body)


def _advance(state: _State, line_in: str | None = None) -> tuple[_State, list[str]]:
    """Return the state after one line, and everything it printed.

    Pure; ``send`` reports its lines, ``readto``'s line arrives as ``line_in``.
    """
    lines, spans, ind, done = state
    line = lines[ind].strip()

    # A blank line and a label line are both no-ops: control runs straight
    # through a block's delimiters.
    if not line or _LABEL.fullmatch(line):
        return (lines, spans, ind + 1, done), []

    command, _, rest = line.partition(" ")
    rest = rest.strip()
    output: list[str] = []

    if command == "send":
        output = [text + "\n" for text in _contents(state, rest)]
    elif command == "readto":
        # An empty line stores an *empty* block rather than one empty line:
        # the cat example loops on ``skipif`` ("at least one line") and
        # terminates on empty input, which only happens if a blank line
        # leaves nothing behind.
        value = line_in or ""
        state = _replaced(state, rest, [value] if value else [])
        lines, spans, ind, done = state
    elif command == "inject":
        state = _injected(state, rest)
        lines, spans, ind, done = state
    elif command == "skip":
        if rest:
            raise ValueError(f"skip takes no argument: {line}")
        return _skipped(state), output
    elif command == "skipif":
        if len(_contents(state, rest)) >= 1:
            return _skipped(state), output
    elif command == "skipq":
        left, _, right = rest.partition(" ")
        right = right.strip()
        if not left or not right:
            raise ValueError(f"skipq takes two labels: {line}")
        if _contents(state, left) == _contents(state, right):
            return _skipped(state), output
    # Anything else is a *data* line and executes as a no-op.  This is
    # forced by the wiki's truth machine: on the falling-through branch
    # control jumps the ``data`` block, lands on the ``0`` block's
    # delimiter, and flows through the bare ``0`` inside it.  It is also
    # the language's namesake working as designed -- ``readto`` and
    # ``inject`` write arbitrary text into blocks that control can later
    # flow through, so the dispatch is "a command word runs, everything
    # else is text".

    return (lines, spans, ind + 1, done), output


class _Machine:
    """The run state: the program's lines, its label spans, and the pointer."""

    def __init__(self, code: str | list[str], io: IO) -> None:
        self.lines = code.split("\n") if isinstance(code, str) else list(code)
        self.spans = _spans(self.lines)
        self.io = io
        self.ind = 0
        self.done = False

    @property
    def halted(self) -> bool:
        return self.done or self.ind >= len(self.lines)

    # The VM's language-shaped view.

    @property
    def ip(self) -> int:
        """The line cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """Each labelled block's line count, in label order.

        The one numeric view the language can test (``skipif``).
        """
        return [
            self.spans[name][1] - self.spans[name][0] - 1 for name in sorted(self.spans)
        ]

    @property
    def stack(self) -> list[object]:
        """The labels enclosing the cursor, innermost last."""
        inside = [
            name for name, (begin, end) in self.spans.items() if begin < self.ind < end
        ]
        ordered = sorted(inside, key=lambda n: self.spans[n][1] - self.spans[n][0])
        return list(reversed(ordered))

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The program text is the memory, so it has to go in whole: a loop
        # that keeps rewriting a block is not a repeat.  The input cursor
        # separates a re-read from a genuine cycle.
        return (self.ind, self.done, tuple(self.lines), self.io.position())

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transition works on."""
        return (self.lines, self.spans, self.ind, self.done)

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        lines, spans, self.ind, self.done = state
        self.lines = list(lines)
        self.spans = dict(spans)

    def step(self) -> None:
        """Execute one line, advancing the pointer.

        The shell: ``readto``'s line is read before, ``send``'s lines written after.
        """
        # A halted machine ignores a further step, so a caller can drive it
        # without checking first.
        if self.halted:
            return

        line = self.lines[self.ind].strip()
        command, _, _ = line.partition(" ")

        # ``readto`` is the one command that needs its input before the
        # transition can run, and it must be read even at EOF: the port
        # raises there, which is the language's documented halt for it.
        line_in = self.io.input_str() if command == "readto" else None

        state, output = _advance(self._state, line_in)
        self._restore(state)
        for text in output:
            self.io.print_str(text)


def run(code: str | list[str], io: IO) -> None:
    """Run an Inject program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
