"""Exact root recovery for the Polynomial interpreter.

:mod:`esolangs.languages.polynomial.interpreter` reads instructions off the
roots of a program; this finds them.  Primality is proven in every range
(:mod:`.primality`), the two peels (:mod:`.peel`, screened through
:mod:`.ntt` at large degree) divide out what an instruction can encode, and
the rest goes to ``p``-adic lifting and a 2-D lattice (:mod:`.gaussian`), so
a cold parse is polynomial in the source length for every source.
"""

import functools
import math
from typing import NamedTuple

from esolangs.languages.polynomial.interpreter.gaussian import (
    _dense_gaussian_roots,
    _gap_chunks,
    _sparse_multiplicity,
)
from esolangs.languages.polynomial.interpreter.ntt import (
    _NTT_FIELDS,
    _NTT_MIN_DEGREE,
    _ntt_real_bound,
    _quadratic_candidates_ntt,
    _roots_mod,
)
from esolangs.languages.polynomial.interpreter.peel import (
    _divide_out_quadratics,
    _divide_quadratic,
    _peel_instruction_quadratics,
    _peel_prime_count,
    _peel_prime_power_roots,
)
from esolangs.languages.polynomial.interpreter.primality import _require_sympy


class _Root(NamedTuple):
    """A recovered root, exact: ``real + imag*i`` with integer parts.

    Mirrors ``complex``'s attributes but never rounds.
    """

    real: int
    imag: int


def _sparse_roots(terms: dict[int, int]) -> list[_Root]:
    """Return the Gaussian integer roots of norm >= 4 of a sparse polynomial.

    With multiplicity, in the shape :func:`_factor_roots` reports them (a
    real root repeated, a pair ``(a, c), (a, -c)`` repeated), and in time
    polynomial in the source length however large the exponents: cut at
    the unbridgeable gaps (:func:`_gap_chunks`), find the roots of one chunk
    (:func:`_dense_gaussian_roots`) -- every root of the whole is one of
    them -- and keep those at which every chunk of every needed
    ``(x d/dx)**j f`` vanishes (:func:`_sparse_multiplicity`).  Every
    instruction root has norm at least 4, so nothing :func:`convert` reads
    is lost; the unit-sized roots, whose powers do not shrink the gap
    argument, are left out.  An identically zero map has no roots here; the
    caller owns that case.
    """
    items = sorted((e, c) for e, c in terms.items() if c)
    if len(items) < 2:
        return []
    chunks = _gap_chunks(items)
    if any(len(chunk) < 2 for chunk in chunks):
        # A lone monomial chunk is nonzero at every alpha != 0.
        return []
    seed = min(chunks, key=lambda chunk: chunk[-1][0] - chunk[0][0])
    low = seed[0][0]
    dense = [0] * (seed[-1][0] - low + 1)
    for exponent, coefficient in seed:
        dense[len(dense) - 1 - (exponent - low)] = coefficient
    roots: list[_Root] = []
    for real, imag in sorted(
        _dense_gaussian_roots(dense), key=lambda r: (abs(r[1]), r)
    ):
        if imag < 0 or real * real + imag * imag < 4:
            continue
        multiplicity = _sparse_multiplicity(items, (real, imag))
        if imag:
            roots.extend([_Root(real, imag), _Root(real, -imag)] * multiplicity)
        else:
            roots.extend([_Root(real, 0)] * multiplicity)
    return roots


def _remainder_roots(coefficients: list[int]) -> list[_Root]:
    """Every integer and Gaussian root of what the peels left, with multiplicity.

    Replaces the ``factor_list`` fallback (Zassenhaus, exponential in the
    worst case) by :func:`_dense_gaussian_roots` and exact division, and
    reports what it did: each integer root repeated, each non-real pair
    ``(a, c), (a, -c)`` with ``c > 0`` repeated, integers first.
    """
    start = 0
    while start < len(coefficients) and not coefficients[start]:
        start += 1
    rest = coefficients[start:]
    if len(rest) <= 1:
        return []
    zeros = next(i for i, c in enumerate(reversed(rest)) if c)
    rest = rest[: len(rest) - zeros]
    reals: list[_Root] = [_Root(0, 0)] * zeros
    pairs: list[_Root] = []
    for real, imag in sorted(_dense_gaussian_roots(rest)):
        if imag < 0:
            continue
        if imag:
            while (quotient := _divide_quadratic(rest, real, imag * imag)) is not None:
                pairs.extend([_Root(real, imag), _Root(real, -imag)])
                rest = quotient
            continue
        while len(rest) > 1:
            deflated = [rest[0]]
            for coefficient in rest[1:]:
                deflated.append(coefficient + deflated[-1] * real)
            if deflated.pop():
                break
            reals.append(_Root(real, 0))
            rest = deflated
    return reals + pairs


@functools.lru_cache(maxsize=256)
def _factor_roots(coefficients: tuple[int, ...]) -> tuple[_Root, ...]:
    """Recover every integer and Gaussian integer root, with multiplicity.

    Both peels run first (exact divisions, remainders kept), so the general
    search sees only what neither recognised -- on a generated program
    usually nothing.  Past :data:`_NTT_MIN_DEGREE` the candidates are
    screened through the fields' root sets; same acceptance.  What is left
    goes to :func:`_remainder_roots`, deterministic polynomial time; it
    replaced a ``factor_list`` whose Zassenhaus recombination is
    exponential in the worst case.
    """
    _require_sympy()
    if len(coefficients) - 1 > _NTT_MIN_DEGREE:
        peeled, quadratics, remainder = _peel_screened(list(coefficients))
    else:
        peeled, remainder = _peel_prime_power_roots(list(coefficients))
        quadratics = []
        if len(remainder) > 1:
            quadratics, remainder = _peel_instruction_quadratics(remainder)
    roots = [_Root(root, 0) for root in peeled]
    for real, square in quadratics:
        imaginary = math.isqrt(square)
        roots.extend([_Root(real, imaginary), _Root(real, -imaginary)])
    roots.extend(_remainder_roots(remainder))
    return tuple(roots)


def _peel_screened(
    coefficients: list[int],
) -> tuple[list[int], list[tuple[int, int]], list[int]]:
    """Both peels with candidates screened through the NTT fields' root sets.

    Returns ``(real roots, quadratics, remainder)``.
    """
    root_sets = tuple(_roots_mod(coefficients, f) for f in _NTT_FIELDS)

    def in_every_field(candidate: int) -> bool:
        return all(
            candidate % field[0] in roots
            for field, roots in zip(_NTT_FIELDS, root_sets, strict=True)
        )

    peeled, remainder = _peel_prime_power_roots(list(coefficients), in_every_field)
    quadratics: list[tuple[int, int]] = []
    if len(remainder) > 1:
        # Streaming stops the prime window once exact division consumes
        # the source; dense n=8 otherwise times out collecting unused pairs.
        candidates = _quadratic_candidates_ntt(
            _peel_prime_count(len(coefficients) - 1),
            (root_sets[0], root_sets[1]),
            _ntt_real_bound(len(coefficients) - 1),
        )
        quadratics, remainder = _divide_out_quadratics(remainder, candidates)
    return peeled, quadratics, remainder


def _find_roots(coefficients: list[int]) -> list[_Root]:
    """Find the roots of an exact-integer polynomial."""
    return list(_factor_roots(tuple(coefficients)))
