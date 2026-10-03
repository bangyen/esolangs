"""Exact first-match indexing for sources with small factor bases."""

from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass
from functools import cache
from itertools import pairwise
from math import prod

type Factors = tuple[tuple[int, int], ...]
type Rule = tuple[Factors, Factors]

_POWER = re.compile(r"^(\d+)(?:\^(\d+))?$")


def integer(value: Factors) -> int:
    """Return the integer represented by prime exponents."""
    return prod(p**e for p, e in value)


def advance(value: Factors, delta: Factors) -> Factors:
    """Return the exact product after a selected fraction."""
    result = dict(value)
    for p, e in delta:
        exponent = result.get(p, 0) + e
        if exponent:
            result[p] = exponent
        else:
            result.pop(p, None)
    return tuple(sorted(result.items()))


@dataclass(frozen=True)
class Index:
    """Guard buckets in source order; monotone thresholds admit binary search."""

    initial: Factors
    rules: tuple[Rule, ...]
    literal: tuple[tuple[Factors, Factors], ...]
    offsets: tuple[int, ...]
    groups: dict[int, tuple[tuple[int, int], ...]]
    keys: dict[int, tuple[int, ...] | None]
    unconditional: int | None

    def choose(self, value: Factors) -> tuple[int | None, int]:
        """Return the first applicable fraction and candidate inspections."""
        store = dict(value)
        best, probes = self.unconditional, 0
        for p, exponent in value:
            group = self.groups.get(p)
            if group is None:
                continue
            keys = self.keys[p]
            start = bisect_left(keys, -exponent) if keys is not None else 0
            for j in range(start, len(group)):
                index, threshold = group[j]
                if best is not None and index >= best:
                    break
                if threshold > exponent:
                    continue
                probes += 1
                if all(store.get(q, 0) >= e for q, e in self.rules[index][0]):
                    best = index
                    break
        return best, probes


def compile_index(code: str) -> Index | None:
    """Compile small bases exactly; leave expensive factorization to the literal VM."""
    tokens = [(m.start(), m.group()) for m in re.finditer(r"[^\s,]+", code)]
    if not tokens:
        return None
    # Dense generated sources use only O(log T log log T)-sized bases.
    # This bound prevents factoring arbitrary large literals during loading.
    limit = max(
        256,
        len(code).bit_length() ** 2,
        (tokens[0][1].count("*") + 1) ** 2,
    )

    @cache
    def factor(base: int) -> Factors:
        result: dict[int, int] = {}
        p = 2
        while p * p <= base:
            while base % p == 0:
                result[p] = result.get(p, 0) + 1
                base //= p
            p += 1
        if base > 1:
            result[base] = result.get(base, 0) + 1
        return tuple(result.items())

    def product(text: str) -> Factors | None:
        result: dict[int, int] = {}
        for term in text.split("*"):
            match = _POWER.fullmatch(term)
            if match is None:
                return None
            base = int(match[1])
            if not 1 <= base <= limit:
                return None
            exponent = 1 if match[2] is None else int(match[2])
            for p, e in factor(base):
                result[p] = result.get(p, 0) + e * exponent
        return tuple(sorted((p, e) for p, e in result.items() if e))

    initial = product(tokens[0][1])
    if initial is None:
        return None
    rules: list[Rule] = []
    literal: list[tuple[Factors, Factors]] = []
    groups: dict[int, list[tuple[int, int]]] = {}
    unconditional = None
    for index, (_offset, token) in enumerate(tokens[1:]):
        head, slash, tail = token.partition("/")
        numerator, denominator = product(head), product(tail if slash else "1")
        if numerator is None or denominator is None:
            return None
        literal.append((numerator, denominator))
        delta = advance(numerator, tuple((p, -e) for p, e in denominator))
        guard = tuple((p, -e) for p, e in delta if e < 0)
        rules.append((guard, delta))
        if guard:
            p, threshold = guard[0]
            groups.setdefault(p, []).append((index, threshold))
        elif unconditional is None:
            unconditional = index
    packed = {p: tuple(group) for p, group in groups.items()}
    keys: dict[int, tuple[int, ...] | None] = {}
    for p, group in packed.items():
        negative = tuple(-threshold for _, threshold in group)
        keys[p] = negative if all(a <= b for a, b in pairwise(negative)) else None
    return Index(
        initial,
        tuple(rules),
        tuple(literal),
        tuple(offset for offset, _ in tokens),
        packed,
        keys,
        unconditional,
    )
