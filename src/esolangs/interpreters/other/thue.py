"""Interpreter for Thue.

John Colagioia's 2000 string-rewriting language.  Each line before the
separator is a rule ``lhs::=rhs``; everything after it, newlines included, is
the starting state.  A step replaces one occurrence of some rule's ``lhs``
with its ``rhs``, and the program ends when no ``lhs`` occurs.  ``:::`` as a
right-hand side substitutes a line of input; a ``~`` prefix prints the rest.

Which occurrence of which rule is the spec's choice, and it is random, so this
interpreter *draws* it through the shared
:mod:`~esolangs.interpreters.randomness` hook rather than pinning a tie-break:
pinned, overlapping rules would compute whatever this file preferred.  ``rng``
fixes the draw for reproducibility, and the branching protocol below lets the
hang proof search *every* draw, as Befunge's ``?`` does.  A program whose
rewrites never collide has one in every state, so no draw can change it --
how the generated programs stay reproducible, asserted by their suite.

The separator is the first ``::=`` line with nothing but whitespace on either
side, and a ``~`` rule whose text is empty prints a newline and nothing else;
both are the spec's, the second Vogel's convention that the wiki carries.  A
rule line with no ``::=`` is refused (the spec is silent on comments; a loud
rejection beats guessing), but a blank one is skipped, as wiki examples use.
A whitespace left side before a nonblank right one (the spec leaves it open;
the original ends the rules there) is a rule that rewrites that whitespace.

A source with no separator line, a rule line without ``::=``, and a rule with
an empty left-hand side (it would match everywhere, so no run could make
progress past it) raise :class:`ValueError`.  Nothing at runtime is invalid,
so no :class:`~esolangs.exceptions.HaltError` arises: a state no rule matches
is the normal end.  A ``:::`` rule with no input left propagates ``EOFError``.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from itertools import accumulate

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
    for line in filter(str.strip, lines[:cut]):
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


def _rewrite(rhs: str, line: str | None) -> tuple[str, str | None]:
    """Return what a rule with right side ``rhs`` substitutes, and what it prints."""
    if rhs == _INPUT:
        return line or "", None
    if rhs.startswith(_OUTPUT):
        # Vogel's convention: no newline after the text, except that an
        # empty string *is* one.
        return "", rhs[len(_OUTPUT) :] or "\n"
    return rhs, None


def _advance(
    state: _State, rules: tuple[_Rule, ...], match: _Match, line: str | None = None
) -> tuple[_State, str | None]:
    """Return the state after one rewrite, and the text to print.

    Pure: a ``:::`` rule's line arrives as ``line`` and a ``~`` rule's text
    leaves as the return value.
    """
    index, at = match
    lhs, rhs = rules[index]
    replacement, out = _rewrite(rhs, line)
    return state[:at] + replacement + state[at + len(lhs) :], out


#: Characters a block of :class:`_Text` holds, give or take a factor of two.
_BLOCK = 256
#: Blocks a draw's first walk sums together.
_GROUP = 64


class _Text:
    """The state cut into blocks, each rule's occurrences indexed per block.

    What :func:`_matches` finds, kept current by rescanning only the blocks a
    rewrite touches, so a step costs a block and not the whole state:
    ``a::=b`` over ``a*N`` rebuilt and rescanned all of it every step
    (1.6 s at N=4k).  ``occ[rule][block]`` lists the offsets in that block
    where the rule's left side starts, in order; it may run on into the next.
    """

    def __init__(self, text: str, lhss: list[str]) -> None:
        self.lhss = lhss
        #: How far an occurrence can run past the block it starts in.
        self.reach = max(map(len, lhss), default=1) - 1
        self.blocks: list[str] = []
        self.occ: list[list[list[int]]] = [[] for _ in lhss]
        #: Per rule, each block's occurrence count, and their total.
        self.counts: list[list[int]] = [[] for _ in lhss]
        self.totals = [0] * len(lhss)
        #: Per rule, the counts summed by runs of ``_GROUP`` blocks, so a
        #: draw walks groups and then one group.
        self.groups: list[list[int]] = []
        self._splice(0, 0, [], text)

    def __str__(self) -> str:
        return "".join(self.blocks)

    def select(self, k: int) -> tuple[int, int, int]:
        """Return the ``k``-th occurrence in rule then position order.

        As ``(rule, block, index into occ[rule][block])``.
        """
        rule = 0
        while k >= self.totals[rule]:
            k -= self.totals[rule]
            rule += 1
        group, k = _locate(self.groups[rule], k)
        block, k = _locate(self.counts[rule][group * _GROUP : (group + 1) * _GROUP], k)
        return rule, group * _GROUP + block, k

    def first(self) -> _Match | None:
        """Return the first occurrence as ``(rule, offset)``, or ``None``."""
        if not any(self.totals):
            return None
        rule, block, _index = self.select(0)
        before = sum(map(len, self.blocks[:block]))
        return rule, before + self.occ[rule][block][0]

    def replace(self, rule: int, block: int, index: int, replacement: str) -> None:
        """Rewrite that occurrence of ``rule`` to ``replacement``."""
        at = self.occ[rule][block][index]
        end = at + len(self.lhss[rule])
        stop = block + 1
        text = self.blocks[block]
        size = len(text) - (end - at) + len(replacement)
        if self.reach <= at and end <= len(text) and 0 < size <= 2 * _BLOCK:
            self._patch(block, at, end, text[:at] + replacement + text[end:])
            return
        # The occurrence may run on into the next blocks; take them in.
        while len(text) < end:
            text += self.blocks[stop]
            stop += 1
        if len(replacement) <= 2 * _BLOCK:
            self._splice(block, stop, [], text[:at] + replacement + text[end:])
        else:
            # A long right side stays one block, shared with the rule, until
            # a rewrite lands in it.  Cut up at once, each of 1000 rewrites
            # by a 200,000-character side added 782 blocks to reindex.
            self._splice(block, stop, [*_cut(text[:at]), replacement], text[end:])

    def _splice(self, start: int, stop: int, pieces: list[str], text: str) -> None:
        """Replace blocks ``start:stop`` by ``pieces`` then ``text``; reindex."""
        # Absorb what follows until the block is a full one, so deletions
        # cannot leave a trail of tiny blocks -- but not a long block.
        while (
            len(text) < _BLOCK
            and stop < len(self.blocks)
            and len(text) + len(self.blocks[stop]) <= 2 * _BLOCK
        ):
            text += self.blocks[stop]
            stop += 1
        pieces = [*pieces, *_cut(text)]
        for rule, occ in enumerate(self.occ):
            counts = self.counts[rule]
            self.totals[rule] -= sum(counts[start:stop])
            counts[start:stop] = [0] * len(pieces)
            occ[start:stop] = [[] for _ in pieces]
        self.blocks[start:stop] = pieces
        # Earlier blocks whose occurrences may run into the new text.
        first, behind = start, 0
        while first > 0 and behind < self.reach:
            first -= 1
            behind += len(self.blocks[first])
        for block in range(first, start + len(pieces)):
            self._scan(block)
        self.groups = [
            [sum(counts[i : i + _GROUP]) for i in range(0, len(counts), _GROUP)]
            for counts in self.counts
        ]

    def _patch(self, block: int, at: int, end: int, text: str) -> None:
        """Set ``block`` to ``text``, which rewrote its ``at:end`` in place.

        Rescans only around the rewrite: an occurrence wholly before it
        stands, and one wholly after it moves by the change in length.
        Needs ``at >= reach``, so no earlier block sees the change.
        """
        delta = len(text) - len(self.blocks[block])
        self.blocks[block] = text
        window = self._window(block)
        stop = min(end + delta, len(text))
        for rule, lhs in enumerate(self.lhss):
            occ = self.occ[rule]
            old = occ[block]
            low = at - len(lhs) + 1
            first, last = bisect_left(old, low), bisect_left(old, end)
            found = _starts(window, lhs, low, stop)
            change = len(found) - (last - first)
            self.totals[rule] += change
            self.counts[rule][block] += change
            self.groups[rule][block // _GROUP] += change
            occ[block] = [*old[:first], *found, *(s + delta for s in old[last:])]

    def _scan(self, block: int) -> None:
        """Re-find every rule's occurrences starting in ``block``."""
        window = self._window(block)
        size = len(self.blocks[block])
        for rule, lhs in enumerate(self.lhss):
            starts = _starts(window, lhs, 0, size)
            self.totals[rule] += len(starts) - self.counts[rule][block]
            self.counts[rule][block] = len(starts)
            self.occ[rule][block] = starts

    def _window(self, block: int) -> str:
        """Return ``block`` and the ``reach`` characters after it."""
        text, need, after = self.blocks[block], self.reach, block + 1
        while need > 0 and after < len(self.blocks):
            text += self.blocks[after][:need]
            need -= len(self.blocks[after])
            after += 1
        return text


def _cut(text: str) -> list[str]:
    """Return ``text`` as blocks."""
    if len(text) <= 2 * _BLOCK:
        return [text] if text else []
    return [text[i : i + _BLOCK] for i in range(0, len(text), _BLOCK)]


def _locate(counts: list[int], k: int) -> tuple[int, int]:
    """Return the index whose count holds the ``k``-th item, and ``k`` in it."""
    ends = list(accumulate(counts))
    index = bisect_right(ends, k)
    return index, k - (ends[index - 1] if index else 0)


def _starts(text: str, lhs: str, low: int, high: int) -> list[int]:
    """Return where ``lhs`` occurs in ``text`` starting in ``low:high``."""
    out: list[int] = []
    limit = high + len(lhs) - 1
    at = text.find(lhs, max(low, 0), limit)
    while at >= 0:
        out.append(at)
        at = text.find(lhs, at + 1, limit)
    return out


class _Machine:
    """The run state: the rewritten string, against fixed rules."""

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        self.rules, state = _parse(code)
        self._text = _Text(state, [lhs for lhs, _rhs in self.rules])
        self.io = io
        self._rng = rng

    @property
    def state(self) -> _State:
        """The string being rewritten."""
        return str(self._text)

    @property
    def halted(self) -> bool:
        """Whether no rule's left-hand side occurs any more."""
        return not any(self._text.totals)

    #: The position is in the *state*, not the source: a rewrite happens on
    #: a string the program text does not contain after the first step.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        """The first rewrite available and where it matches, or empty at the end.

        The first, not the one the next step draws: reading a position must
        not consume randomness.
        """
        found = self._text.first()
        return found if found is not None else ()

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.state, self.io.progress())

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
        count = sum(self._text.totals)
        if not count:
            return
        rule, block, index = self._text.select(draw(self._rng, count))
        rhs = self.rules[rule][1]
        replacement, out = _rewrite(rhs, self.io.input_str() if rhs == _INPUT else None)
        self._text.replace(rule, block, index, replacement)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Run a Thue program."""
    machine = _Machine(code, io, rng)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
