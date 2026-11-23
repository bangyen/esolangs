"""Model Trml (https://esolangs.org/wiki/Trml, rev. 140496) on short strings.

Use the interpreter's shortest-binding convention for ambiguous splits.
"""

import re
from itertools import product

from esolangs.languages.trml.interpreter import prepare_machine
from tests.interpreters.oracle_support import checker

_STEPS = 16


def _expand(parts, bindings):
    return "".join(bindings[part] if i % 2 else part for i, part in enumerate(parts))


def _substitutions(parts, terms):
    names = tuple(dict.fromkeys(parts[1::2]))
    for values in product(terms, repeat=len(names)):
        yield dict(zip(names, values, strict=True))


def _terms(declarations, text):
    # Close over string values rather than tracking endpoints in the subject.
    substrings = {
        text[start:end] for end in range(1, len(text) + 1) for start in range(end)
    }
    terms = set()
    while True:
        expanded = {
            _expand(parts, bindings)
            for parts in declarations
            for bindings in _substitutions(parts, terms)
        }
        new = terms | (expanded & substrings)
        if new == terms:
            return sorted(terms, key=lambda term: (len(term), term))
        terms = new


def _predict(source, _stdin):
    description, text = "".join(source.split()).split("$")
    declarations, rules = [], []
    for statement in description.rstrip(";").split(";"):
        patterns = tuple(
            re.split(r"\(([^()]+)\)", part) for part in statement.split(":")
        )
        if len(patterns) == 1:
            declarations.append(patterns[0])
        else:
            rules.append(patterns)

    trace = [(text, False, "", 0, 0)]
    for _ in range(_STEPS):
        terms = _terms(declarations, text)
        candidates = []
        for index, (before, after) in enumerate(rules):
            for bindings in _substitutions(before, terms):
                match = _expand(before, bindings)
                start = text.find(match)
                if start >= 0:
                    result = (
                        text[:start]
                        + _expand(after, bindings)
                        + text[start + len(match) :]
                    )
                    candidates.append((start, index, result))
        if not candidates:
            trace.extend([(text, True, text, 0, 0)] * 4)
            return None, trace
        # Product order prefers shorter bindings. Stable min preserves it.
        _, _, text = min(candidates, key=lambda match: match[:2])
        trace.append((text, False, "", 0, 0))
    raise AssertionError("Trml model fixture exceeded its step bound")


def _machine(source, io):
    return prepare_machine(source, {})(io)


_check = checker(_predict, lambda machine: machine.text, cap=_STEPS)


def check_raw_trml():
    for description, subject, rewrites in (
        ("ab:C;a:L;b:R;", "bab", ("Rab", "RC")),
        ("a;b;a:L;ab:R;", "ab", ("Lb",)),
        ("a;aa;p(x)(y)!:(x);", "paaa!", ("a",)),
        ("a;aa;p(x)!:(x);", "paa!", ("aa",)),
        ("a;b;(x)b;z(x)!:(x);", "zabb!", ("abb",)),
        ("a;b;(x)b;p(x)=(x)!:Y;", "pab=ab!", ("Y",)),
        ("a;b;(x)b;p(x)=(x)!:Y;", "pab=bb!", ()),
        ("a;b;p(x)(x);z(x)!:Y;", "zpaa!zpab!", ("Yzpab!",)),
        ("a;a:;", "a", ("",)),
    ):
        _, trace = _check(_machine, f"{description}${subject}", "unused")
        assert tuple(text for text, halted, *_ in trace if not halted) == (
            subject,
            *rewrites,
        )
