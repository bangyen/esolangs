"""Exact first-match indexing for sources with small factor bases."""

from __future__ import annotations

import re
from array import array
from bisect import bisect_left
from dataclasses import dataclass
from functools import cache
from itertools import pairwise
from math import isqrt, prod

type Factors = tuple[tuple[int, int], ...]
type Rule = tuple[Factors, Factors]

_POWER = re.compile(r"^(\d+)(?:\^(\d+))?$")

#: Every source may name bases up to this, however short it is.
SMALL_BASE = 256


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


def _least_factors(top: int) -> array[int]:
    """Return each integer's least prime factor, through ``top``.

    Descending ``p`` writes every multiple from ``p * p``; a smaller divisor
    writes later, so the least one stays.  Composite ``p`` are harmless.
    """
    least = array("L", range(top + 1))
    for p in range(isqrt(top), 1, -1):
        least[p * p :: p] = array("L", [p]) * len(range(p * p, top + 1, p))
    return least


def compile_index(code: str) -> Index | None:
    """Compile small bases exactly; leave expensive factorization to the literal VM."""
    tokens = [(m.start(), m.group()) for m in re.finditer(r"[^\s,]+", code)]
    if not tokens:
        return None
    # A base costs at least its digits, so one no larger than the source is
    # cheap to factor: a sieve to the largest such base, linear in the source.
    # Larger literals are left to the literal VM rather than factored.
    limit = max(
        SMALL_BASE,
        len(code),
        (tokens[0][1].count("*") + 1) ** 2,
    )
    named = (int(m[1]) for m in re.finditer(r"(?:^|[\s,/*])(\d+)", code))
    least = _least_factors(max((b for b in named if b <= limit), default=1))

    @cache
    def factor(base: int) -> Factors:
        result: dict[int, int] = {}
        while base > 1:
            p = least[base]
            result[p] = result.get(p, 0) + 1
            base //= p
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
            # The largest guard prime is the most selective: a bucket keyed
            # on a prime many rules share would be scanned rule by rule.
            p, threshold = guard[-1]
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
