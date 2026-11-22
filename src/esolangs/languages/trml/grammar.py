"""Parse Trml's meta-description and match its declared terms."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from esolangs.runtime.source_hints import syntax_error

_ATOM = re.compile(r"\(([^()]+)\)|[^()]+")


@dataclass(frozen=True, slots=True)
class Variable:
    """A variable occurrence in a declaration or rewrite pattern."""

    name: str


type Pattern = tuple[str | Variable, ...]
type Rule = tuple[Pattern, Pattern]
type Chart = list[set[int]]


def _pattern(source: str) -> Pattern:
    atoms = [
        Variable(match[1]) if match[1] is not None else match[0]
        for match in _ATOM.finditer(source)
    ]
    if sum(
        len(atom) if isinstance(atom, str) else len(atom.name) + 2 for atom in atoms
    ) != len(source):
        raise syntax_error(
            "unmatched parentheses in Trml pattern",
            "enclose each metavariable name in one pair",
        )
    return tuple(atoms)


def parse(source: str) -> tuple[tuple[Pattern, ...], tuple[Rule, ...], str]:
    """Read declarations, rules, and the initial object text."""
    description, separator, subject = "".join(source.split()).partition("$")
    if not separator or "$" in subject or not description.endswith(";"):
        raise syntax_error(
            "Trml needs semicolon-terminated statements followed by '$'",
            "put one $ between the description and object text",
        )
    terms: list[Pattern] = []
    rules: list[Rule] = []
    for statement in description[:-1].split(";"):
        left, colon, right = statement.partition(":")
        if not left or ":" in right:
            raise syntax_error(
                "empty or malformed Trml statement",
                "use one colon in a rule and no colon in a declaration",
            )
        lhs = _pattern(left)
        if colon:
            rhs = _pattern(right)
            variables = {part for part in lhs if isinstance(part, Variable)}
            if any(
                isinstance(part, Variable) and part not in variables for part in rhs
            ):
                raise syntax_error(
                    "unbound Trml replacement variable",
                    "bind the replacement variable on the left side of the rule",
                )
            rules.append((lhs, rhs))
        else:
            terms.append(lhs)
    return tuple(terms), tuple(rules), subject


def matches(
    atoms: Pattern, text: str, start: int, chart: Chart
) -> Iterator[tuple[int, dict[Variable, str]]]:
    """Match atoms in order, preferring the shortest declared binding."""
    states: list[tuple[int, int, dict[Variable, str]]] = [(0, start, {})]
    while states:
        index, position, captures = states.pop()
        if index == len(atoms):
            yield position, captures
            continue
        atom = atoms[index]
        literal = atom if isinstance(atom, str) else captures.get(atom)
        if literal is not None:
            if text.startswith(literal, position):
                states.append((index + 1, position + len(literal), captures))
            continue
        assert isinstance(atom, Variable)
        states.extend(
            (index + 1, end, {**captures, atom: text[position:end]})
            for end in sorted(chart[position], reverse=True)
        )


def term_chart(terms: tuple[Pattern, ...], text: str) -> Chart:
    """Find all finite, nonempty term spans, including left-recursive ones."""
    chart: Chart = [set() for _ in range(len(text) + 1)]
    for position in range(len(text) - 1, -1, -1):
        ends = chart[position]
        # Later starts are settled. Only declarations that begin with a
        # variable can depend on a new endpoint at this same start.
        while True:
            old_size = len(ends)
            for term in terms:
                ends.update(end for end, _ in matches(term, text, position, chart))
            if len(ends) == old_size:
                break
    return chart
