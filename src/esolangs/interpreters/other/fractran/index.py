"""Exact first-match indexing for sources with small factor bases."""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from functools import cache
from itertools import pairwise
from math import prod

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


def _least_primes(limit: int) -> list[int]:
    """Return least prime factors; Euler's sieve assigns each composite once."""
    least = [0] * (limit + 1)
    primes = []
    for candidate in range(2, limit + 1):
        if not least[candidate]:
            least[candidate] = candidate
            primes.append(candidate)
        for prime in primes:
            if prime > least[candidate]:
                break
            product = prime * candidate
            if product > limit:
                break
            least[product] = prime
    return least


def compile_index(code: str) -> Index | None:
    """Compile small bases exactly; leave expensive factorization to the literal VM."""
    tokens = [(m.start(), m.group()) for m in re.finditer(r"[^\s,]+", code)]
    if not tokens:
        return None
    # Shipped generators use small bases; dense initial products admit more.
    # Keep arbitrary large literals out of indexed factorization.
    limit = max(
        SMALL_BASE,
        len(code),
        (tokens[0][1].count("*") + 1) ** 2,
    )

    terms: dict[str, tuple[int, int]] = {}
    maximum = 1
    for position, (_offset, token) in enumerate(tokens):
        head, slash, tail = token.partition("/")
        products = (token,) if position == 0 else (head, tail if slash else "1")
        for text in products:
            for term in text.split("*"):
                if term in terms:
                    continue
                match = _POWER.fullmatch(term)
                if match is None:
                    return None
                base = int(match[1])
                if not 1 <= base <= limit:
                    return None
                exponent = 1 if match[2] is None else int(match[2])
                terms[term] = base, exponent
                maximum = max(maximum, base)
    # Sieve actual bases, never the quadratic admission limit. Cap scratch
    # space by source size; sparse large bases retain cached trial division.
    least = _least_primes(maximum) if maximum <= 8 * len(code) else None

    @cache
    def factor(base: int) -> Factors:
        result: dict[int, int] = {}
        if least is not None:
            while base > 1:
                prime = least[base]
                result[prime] = result.get(prime, 0) + 1
                base //= prime
            return tuple(result.items())
        p = 2
        while p * p <= base:
            while base % p == 0:
                result[p] = result.get(p, 0) + 1
                base //= p
            p += 1
        if base > 1:
            result[base] = result.get(base, 0) + 1
        return tuple(result.items())

    def product(text: str) -> Factors:
        result: dict[int, int] = {}
        for term in text.split("*"):
            base, exponent = terms[term]
            for p, e in factor(base):
                result[p] = result.get(p, 0) + e * exponent
        return tuple(sorted((p, e) for p, e in result.items() if e))

    initial = product(tokens[0][1])
    rules: list[Rule] = []
    literal: list[tuple[Factors, Factors]] = []
    groups: dict[int, list[tuple[int, int]]] = {}
    unconditional = None
    for index, (_offset, token) in enumerate(tokens[1:]):
        head, slash, tail = token.partition("/")
        numerator, denominator = product(head), product(tail if slash else "1")
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


class _Minimum:
    """Maintain source-order minima with point updates and prefix queries."""

    def __init__(self, values: list[int], absent: int) -> None:
        self.size = 1 << (max(1, len(values)) - 1).bit_length()
        self.absent = absent
        self.tree = [absent] * (2 * self.size)
        self.tree[self.size : self.size + len(values)] = values
        for i in range(self.size - 1, 0, -1):
            self.tree[i] = min(self.tree[2 * i], self.tree[2 * i + 1])

    def set(self, position: int, value: int) -> None:
        position += self.size
        self.tree[position] = value
        while position > 1:
            position //= 2
            value = min(self.tree[2 * position], self.tree[2 * position + 1])
            if self.tree[position] == value:
                break
            self.tree[position] = value

    def prefix(self, stop: int) -> int:
        left, right = self.size, self.size + stop
        result = self.absent
        while left < right:
            if left & 1:
                result = min(result, self.tree[left])
                left += 1
            if right & 1:
                right -= 1
                result = min(result, self.tree[right])
            left //= 2
            right //= 2
        return result


class Cursor:
    """Maintain exact guard eligibility while changing only affected exponents."""

    def __init__(self, index: Index) -> None:
        """Build threshold trees and secondary-guard dependencies."""
        self.version = 0
        self.index = index
        self.value = dict(index.initial)
        self.absent = len(index.rules)
        self.cleanup_start = self.absent
        for rule in range(self.absent - 1, -1, -1):
            delta = index.rules[rule][1]
            if not delta or any(change > 0 for _prime, change in delta):
                break
            self.cleanup_start = rule
        self.cleanup_position: int | None = None
        counts: dict[int, int] = {}
        for guard, _delta in index.rules:
            for prime, _threshold in guard:
                counts[prime] = counts.get(prime, 0) + 1
        grouped: dict[int, list[tuple[int, int]]] = {}
        for rule, (guard, _delta) in enumerate(index.rules):
            if guard:
                # Frequent anchors keep phase changes out of secondary scans.
                anchor, threshold = max(
                    guard, key=lambda item: (counts[item[0]], -item[0])
                )
                grouped.setdefault(anchor, []).append((threshold, rule))
        self.primes = tuple(grouped)
        self.anchors = {prime: group for group, prime in enumerate(grouped)}
        self.keys: list[tuple[int, ...]] = []
        self.rules: list[tuple[int, ...]] = []
        self.missing: list[list[int]] = []
        self.trees: list[_Minimum] = []
        watchers: dict[int, list[tuple[int, int, int]]] = {}
        for group, (anchor, entries) in enumerate(grouped.items()):
            entries.sort()
            self.keys.append(tuple(threshold for threshold, _rule in entries))
            rules = tuple(rule for _threshold, rule in entries)
            self.rules.append(rules)
            missing = []
            for position, rule in enumerate(rules):
                failures = 0
                for prime, threshold in index.rules[rule][0]:
                    if prime != anchor:
                        watchers.setdefault(prime, []).append(
                            (threshold, group, position)
                        )
                        failures += self.value.get(prime, 0) < threshold
                missing.append(failures)
            self.missing.append(missing)
            self.trees.append(
                _Minimum(
                    [
                        rule if failures == 0 else self.absent
                        for rule, failures in zip(rules, missing, strict=True)
                    ],
                    self.absent,
                )
            )
        self.watchers = {
            prime: tuple(sorted(entries)) for prime, entries in watchers.items()
        }
        self.watch_keys = {
            prime: tuple(threshold for threshold, _group, _position in entries)
            for prime, entries in self.watchers.items()
        }
        self.best = _Minimum(
            [
                self.trees[group].prefix(
                    bisect_right(self.keys[group], self.value.get(prime, 0))
                )
                for prime, group in self.anchors.items()
            ],
            self.absent,
        )
        self.guard_updates = 0
        self.factor_updates = 0

    def choose(self) -> tuple[int | None, int]:
        """Return the exact first eligible fraction and candidate inspections."""
        if self.cleanup_position is not None:
            probes = 0
            while self.cleanup_position < self.absent:
                probes += 1
                guard = self.index.rules[self.cleanup_position][0]
                if all(
                    self.value.get(prime, 0) >= exponent for prime, exponent in guard
                ):
                    return self.cleanup_position, probes
                self.cleanup_position += 1
            return None, probes
        rule = min(
            self.best.tree[1],
            self.absent
            if self.index.unconditional is None
            else self.index.unconditional,
        )
        return (None, 0) if rule == self.absent else (rule, 1)

    def advance(self, rule: int) -> None:
        """Update exponents and guards whose secondary thresholds were crossed."""
        if rule >= self.cleanup_start:
            # Pure removal cannot enable an earlier failed guard. Once this
            # suffix fires, retain its priority with a forward scan alone.
            self.cleanup_position = rule
            for prime, delta in self.index.rules[rule][1]:
                self.factor_updates += 1
                new = self.value.get(prime, 0) + delta
                if new:
                    self.value[prime] = new
                else:
                    self.value.pop(prime, None)
            self.version += 1
            return
        dirty = set()
        for prime, delta in self.index.rules[rule][1]:
            self.factor_updates += 1
            old = self.value.get(prime, 0)
            new = old + delta
            if new:
                self.value[prime] = new
            else:
                self.value.pop(prime, None)
            group = self.anchors.get(prime)
            if group is not None:
                dirty.add(group)
            keys = self.watch_keys.get(prime)
            if keys is None:
                continue
            left, right = (
                bisect_right(keys, min(old, new)),
                bisect_right(keys, max(old, new)),
            )
            for _threshold, group, position in self.watchers[prime][left:right]:
                self.guard_updates += 1
                missing = self.missing[group]
                missing[position] += 1 if new < old else -1
                self.trees[group].set(
                    position,
                    self.rules[group][position]
                    if missing[position] == 0
                    else self.absent,
                )
                dirty.add(group)
        for group in dirty:
            prime = self.primes[group]
            self.best.set(
                group,
                self.trees[group].prefix(
                    bisect_right(self.keys[group], self.value.get(prime, 0))
                ),
            )
        self.version += 1
