"""Literal integer multiplication model: https://esolangs.org/wiki/Fractran.

Two fractions, numerators/denominators 1..4, starts 1..10, twelve steps.
No production factorization, index, parser or generator supplies expectations.
The final-value print and source notation follow the public adapter contract.
"""

from itertools import product

import pytest

from esolangs.languages.fractran.interpreter import _Machine
from esolangs.languages.fractran.tests.prime_factors import _factor
from esolangs.runtime._state import WorkspaceVariant
from tests.interpreters.oracle_support import observed, overread
from tests.support import workspace_oracle as workspace

_WORKSPACE = workspace.workspace_model("fractran-v1", "register printed input_cursor")


def _register(value, indexed):
    return WorkspaceVariant(
        "prime_exponents" if indexed else "integer",
        (frozenset(_factor(value).items()) if indexed else value,),
    )


def _model(start, rules, offsets):
    number, printed, output = start, False, ""
    trace = []
    for tick in range(13):
        available = [i for i, (a, b) in enumerate(rules) if number * a % b == 0]
        index = available[0] if available else None
        halted = printed and index is None
        row = (
            (number, printed, None if index is None else offsets[index]),
            halted,
            output,
            0,
            0,
        )
        trace.append(row)
        if halted:
            return None, trace + [row] * 3
        if tick == 12:
            break
        if index is None:
            printed, output = True, str(number)
        else:
            a, b = rules[index]
            number = number * a // b
    return None, trace


def _check(factory, start, rules, *, powers=False):
    tokens = [str(start), *(f"{a}/{b}" for a, b in rules)]
    if powers:
        tokens = [
            f"{token}^1" if "/" not in token else token.replace("/", "^1/") + "^1"
            for token in tokens
        ]
    source = ", ".join(tokens)
    offsets, at = [], len(tokens[0]) + 2
    for token in tokens[1:]:
        offsets.append(at)
        at += len(token) + 2

    bases = (start, *(part for rule in rules for part in rule))
    indexed = max(bases) <= max(256, len(source))
    workspace.agrees(
        _model(start, rules, offsets),
        (factory, source, "unused\n"),
        (_WORKSPACE, lambda row: (_register(row[0][0], indexed), row[0][1], row[-1])),
        lambda m: (m.value, m.printed, m.ip),
        cap=12,
        context=source,
    )


def check_raw_fractran():
    fractions = tuple(product(range(1, 5), repeat=2))
    for start, first, second in product(range(1, 11), fractions, fractions):
        _check(_Machine, start, (first, second))
    for start in (1, 2, 12, 75):
        for rules in ((), ((1, 2),), ((3, 2), (1, 3)), ((4, 2), (2, 4))):
            _check(_Machine, start, rules, powers=True)
    for source in ("", "0", "-1", "2 1/0", "2 0/1", "2 bad", "2^x 1/2"):
        assert observed(_Machine, source, "unused", lambda m: m.value) == (
            "syntax",
            [(None, False, "", 0, 0)],
        )

    class SkipsProduct(_Machine):
        def step(self):
            self.printed = True

    class PrintsTwice(_Machine):
        def step(self):
            super().step()
            if self.halted:
                self.io.print_num(self.value)

    for factory, start, rules in (
        (SkipsProduct, 2, ((3, 2),)),
        (PrintsTwice, 1, ()),
        (overread(_Machine), 1, ()),
    ):
        with pytest.raises(AssertionError):
            _check(factory, start, rules)

    _check(_Machine, 257, ((1, 257),))
    _check(_Machine, 2, ((1, 2),) * 17)

    workspace.check_erasures(_WORKSPACE, _check, _Machine, 2, ((3, 2), (1, 3)))
