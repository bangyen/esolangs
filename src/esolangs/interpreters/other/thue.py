"""Interpreter for Thue.

John Colagioia's 2000 string-rewriting language.  Each line before the
separator is a rule ``lhs::=rhs``; everything after it, newlines included, is
the starting state.  A step replaces one occurrence of some rule's ``lhs``
with its ``rhs``, and the program ends when no ``lhs`` occurs.  ``:::`` as a
right-hand side substitutes a line of input; a ``~`` prefix prints the rest.

Which occurrence of which rule is the spec's choice, and it is random, so this
interpreter *draws* it through the shared
:mod:`~esolangs.interpreters.randomness` hook rather than pinning a tie-break:
pinned, every Thue program whose rules overlap would quietly compute whatever
this file preferred.  ``rng`` fixes the draw where a caller needs
reproducibility, and the branching protocol below lets the hang proof search
*every* draw rather than sample one, as Befunge's ``?`` does.  A program whose
rewrites never collide has one in every state it reaches, so no draw can
change it -- which is how the generated programs stay reproducible without
pinning the language, asserted by their suite.

The separator is the first ``::=`` line with nothing but whitespace on either
side, and a ``~`` rule whose text is empty prints a newline and nothing else;
both are the spec's, the second Vogel's convention that the wiki carries.  A
rule line with no ``::=`` at all is refused rather than skipped, which is a
decision: the spec does not say whether a blank line or a comment may sit
there, and a loud rejection beats guessing.

A source with no separator line, a rule line without ``::=``, and a rule with
an empty left-hand side (it would match everywhere, so no run could make
progress past it) raise :class:`ValueError`.  Nothing at runtime is invalid,
so no :class:`~esolangs.exceptions.HaltError` arises: a state no rule matches
is the normal end.  A ``:::`` rule with no input left propagates ``EOFError``.
"""

from __future__ import annotations

from esolangs._drive import drive
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import Randomness, draw
from esolangs.interpreters.source_hints import syntax_error

_SEPARATOR = "::="
#: The right-hand side that reads a line of input instead of text.
_INPUT = ":::"
#: The right-hand side prefix that prints the rest instead of substituting it.
_OUTPUT = "~"

#: A rule: its left-hand side and its right-hand side, verbatim.
type _Rule = tuple[str, str]
#: One rewrite a step could make: which rule, and at what offset.
type _Match = tuple[int, int]
#: The whole run as a value: the string being rewritten, and nothing else --
#: where the next rewrite lands is a draw, not state.
type _State = str


def _separator(lines: list[str]) -> int | None:
    """Return the index of the line that ends the rules, or ``None``.

    The spec's shape, not an exact ``::=``: a ``::=`` line whose two sides
    are "either empty, or consisting entirely of whitespace".  Requiring the
    bare string made ``  ::=  `` a *rule* whose left-hand side was two
    spaces, which then rewrote the state's own whitespace.
    """
    for index, line in enumerate(lines):
        head, found, tail = line.partition(_SEPARATOR)
        if found and not head.strip() and not tail.strip():
            return index
    return None


def _parse(code: str) -> tuple[tuple[_Rule, ...], str]:
    """Return the rules and the starting state.

    The state is every line after the separator, rejoined, so a multi-line
    state survives.
    """
    lines = code.split("\n")
    cut = _separator(lines)
    if cut is None:
        raise syntax_error(
            "a Thue program needs a '::=' line with nothing but whitespace on "
            "either side, to separate its rules from its starting state",
            ("insert a line containing only ::= between the rules and starting state"),
        )
    rules = []
    for line in lines[:cut]:
        head, found, tail = line.partition(_SEPARATOR)
        if not found:
            raise syntax_error(
                f"Thue rule line has no '::=': {line!r}",
                "write each rule as left::=right",
            )
        if not head:
            raise syntax_error(
                f"Thue rule {line!r} has an empty left-hand side, which "
                f"matches everywhere and so never lets a run finish",
                "give the rule a nonempty left-hand side",
            )
        rules.append((head, tail))
    return tuple(rules), "\n".join(lines[cut + 1 :])


def _matches(state: _State, rules: tuple[_Rule, ...]) -> tuple[_Match, ...]:
    """Return every rewrite a step could make, in rule then position order.

    Occurrences may overlap -- ``aa`` occurs twice in ``aaa`` -- because the
    spec draws among *occurrences*, and skipping the overlapping ones would
    silence half the draws for a rule like that.
    """
    found: list[_Match] = []
    for index, (lhs, _rhs) in enumerate(rules):
        at = state.find(lhs)
        while at >= 0:
            found.append((index, at))
            at = state.find(lhs, at + 1)
    return tuple(found)


def _advance(
    state: _State, rules: tuple[_Rule, ...], match: _Match, line: str | None = None
) -> tuple[_State, str | None]:
    """Return the state after one rewrite, and the text to print.

    Pure: a ``:::`` rule's line arrives as ``line`` and a ``~`` rule's text
    leaves as the return value.
    """
    index, at = match
    lhs, rhs = rules[index]
    out = None
    if rhs == _INPUT:
        replacement = line or ""
    elif rhs.startswith(_OUTPUT):
        replacement = ""
        # Vogel's convention: no newline after the text, except that an
        # empty string *is* one.
        out = rhs[len(_OUTPUT) :] or "\n"
    else:
        replacement = rhs
    return state[:at] + replacement + state[at + len(lhs) :], out


class _Machine:
    """The run state: the rewritten string, against fixed rules."""

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        self.rules, state = _parse(code)
        self.state: _State = state
        self.io = io
        self._rng = rng

    @property
    def halted(self) -> bool:
        """Whether no rule's left-hand side occurs any more."""
        return not _matches(self.state, self.rules)

    #: The position is in the *state*, not the source: a rewrite happens on
    #: a string the program text does not contain after the first step.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        """The first rewrite available and where it matches, or empty at the end.

        The first, not the one the next step draws: reading a position must
        not consume randomness.
        """
        found = _matches(self.state, self.rules)
        return found[0] if found else ()

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the state string."""
        return []

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.state, self.io.position())

    # The all-draws search, over the string alone: a ``:::`` rule declines to
    # fork, and a ``~`` rule's output cannot change what matches later.

    def branching_snapshot(self) -> _State:
        """Return the current state as the search's starting point."""
        return self.state

    def branching_halted(self, state: object) -> bool:
        """Report whether no rule matches ``state``."""
        return not _matches(str(state), self.rules)

    def branching_successors(
        self, state: object, _limit: int
    ) -> tuple[_State, ...] | None:
        """Return the state after every rewrite the draw could choose.

        ``None`` declines, as Modulous's ``INP`` does: a ``:::`` rule wants a
        line of input, which a pure search has no business taking.
        """
        text = str(state)
        found = _matches(text, self.rules)
        if any(self.rules[index][1] == _INPUT for index, _at in found):
            return None
        return tuple(_advance(text, self.rules, match)[0] for match in found)

    def step(self) -> None:
        """Perform one rewrite, drawing which one among those available."""
        found = _matches(self.state, self.rules)
        if not found:
            return
        match = found[draw(self._rng, len(found))]
        line = self.io.input_str() if self.rules[match[0]][1] == _INPUT else None
        self.state, out = _advance(self.state, self.rules, match, line)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Run a Thue program."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
