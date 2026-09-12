r"""Interpreter for Inject."""

import re
import sys
from collections.abc import Mapping, Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# A label line is exactly a.
# of the name.
# examples are written flush.
_LABEL = re.compile(r"(\w+);")


def _spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    r"""Return each label's ``(begin, end)`` delimiter line numbers."""
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


# : A label's two delimiter.
type _Spans = Mapping[str, tuple[int, int]]

# : One instant of a run:.
# : the label spans over it,.
# : clause has exited.
# : tuple rather than editing.
# :.
# : The lines are *in* here.
# : ``inject`` rewrite the.
type _State = tuple[Sequence[str], _Spans, int, bool]


def _span(spans: _Spans, name: str) -> tuple[int, int]:
    r"""Return ``name``'s delimiters, rejecting a label that has none."""
    if name not in spans:
        raise ValueError(f"unknown label: {name}")
    return spans[name]


def _contents(state: _State, name: str) -> list[str]:
    r"""Return the lines strictly between a label's two delimiters."""
    lines, spans, _, _ = state
    begin, end = _span(spans, name)
    return list(lines[begin + 1 : end])


def _replaced(state: _State, name: str, body: list[str]) -> _State:
    r"""Return ``state`` with a block's contents overwritten."""
    lines, spans, ind, done = state
    begin, end = _span(spans, name)
    grown = [*lines[: begin + 1], *body, *lines[end:]]
    shift = len(body) - (end - begin - 1)
    if not shift:
        return (grown, spans, ind, done)
    if begin < ind:
        ind += shift
    # Only positions strictly after.
    # overlapping block that begins.
    # end pushed along, which is.
    # after a rewrite.
    moved = {
        label: (b + shift * (b > begin), e + shift * (e > begin))
        for label, (b, e) in spans.items()
    }
    return (grown, moved, ind, done)


def _begins_block(state: _State, index: int) -> str | None:
    r"""Return the label beginning a block at ``index``, if any."""
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
    r"""Return the shortest block strictly containing the pointer."""
    _, spans, ind, _ = state
    inside = [n for n, (b, e) in spans.items() if b < ind < e]
    if not inside:
        return None
    return min(inside, key=lambda n: spans[n][1] - spans[n][0])


def _skipped(state: _State) -> _State:
    r"""Return the state after ``skip``'s three-clause jump."""
    lines, spans, ind, _ = state
    ahead = _begins_block(state, ind + 1)
    if ahead is not None:
        return (lines, spans, spans[ahead][1] + 1, False)
    inner = _innermost(state)
    if inner is not None:
        return (lines, spans, spans[inner][0], False)
    return (lines, spans, ind, True)


def _injected(state: _State, rest: str) -> _State:
    r"""Run ``inject X=S/R``: substitute ``S`` with ``R`` in block ``X``."""
    name, sep, expression = rest.partition("=")
    if not sep:
        raise ValueError(f"inject needs a label and a regex: {rest}")
    # The pattern cannot contain a.
    # separator and everything.
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
    r"""Return the state after one line, and everything it printed."""
    lines, spans, ind, done = state
    line = lines[ind].strip()

    # A blank line and a label line.
    # through a block's delimiters.
    if not line or _LABEL.fullmatch(line):
        return (lines, spans, ind + 1, done), []

    command, _, rest = line.partition(" ")
    rest = rest.strip()
    output: list[str] = []

    if command == "send":
        output = [text + "\n" for text in _contents(state, rest)]
    elif command == "readto":
        # An empty line stores an.
        # the cat example loops on.
        # terminates on empty input,.
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
    # Anything else is a *data*.
    # forced by the wiki's truth.
    # control jumps the ``data``.
    # delimiter, and flows through.
    # the language's namesake.
    # ``inject`` write arbitrary.
    # flow through, so the dispatch.
    # else is text".

    return (lines, spans, ind + 1, done), output


class _Machine:
    r"""The run state: the program's lines, its label spans, and the."""

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
        r"""The line cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""Each labelled block's line count, in label order."""
        return [
            self.spans[name][1] - self.spans[name][0] - 1 for name in sorted(self.spans)
        ]

    @property
    def stack(self) -> list[object]:
        r"""The labels enclosing the cursor, innermost last."""
        inside = [
            name for name, (begin, end) in self.spans.items() if begin < self.ind < end
        ]
        ordered = sorted(inside, key=lambda n: self.spans[n][1] - self.spans[n][0])
        return list(reversed(ordered))

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The program text is the.
        # that keeps rewriting a block.
        # separates a re-read from a.
        return (self.ind, self.done, tuple(self.lines), self.io.position())

    # -- one command.

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (self.lines, self.spans, self.ind, self.done)

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        lines, spans, self.ind, self.done = state
        self.lines = list(lines)
        self.spans = dict(spans)

    def step(self) -> None:
        r"""Execute one line, advancing the pointer."""
        # A halted machine ignores a.
        # without checking first.
        if self.halted:
            return

        line = self.lines[self.ind].strip()
        command, _, _ = line.partition(" ")

        # ``readto`` is the one command.
        # transition can run, and it.
        # raises there, which is the.
        line_in = self.io.input_str() if command == "readto" else None

        state, output = _advance(self._state, line_in)
        self._restore(state)
        for text in output:
            self.io.print_str(text)


def run(code: str | list[str], io: IO) -> None:
    r"""Run an Inject program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
