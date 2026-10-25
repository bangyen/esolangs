"""NTT root sets for the large-degree Polynomial root search.

Past :data:`_NTT_MIN_DEGREE` the peels' candidates are screened through the
root sets of two prime fields, found by exhaustive evaluation.
"""

import re
from collections.abc import Iterator

from esolangs.languages.polynomial.interpreter.peel import _PEEL_MAX_IMAGINARY_EXPONENT
from esolangs.languages.polynomial.interpreter.primality import _first_primes

#: Degree above which the candidate search runs through NTT root sets
#: instead of enumerating (real roots) and factoring over
#: :data:`_PEEL_MODULUS` (quadratics).  The NTT path pays a fixed ~0.45s
#: to evaluate the polynomial over both fields, so it loses below the
#: crossover and wins above it superlinearly.  Measured on generated
#: programs, enumerated against screened: degree 74 is 298ms against
#: 457ms, degree 118 is 687ms against 479ms -- the crossover -- and then
#: degree 314 is 5.3s against 0.7s, degree 912 is 78s against 2.6s, and
#: degree 2260 (dense n=10) extrapolates to ~15 minutes against 44s.
_NTT_MIN_DEGREE = 100

#: The two prime fields the large-degree path finds roots in, as ``(m, c,
#: k, g)`` with ``m = c * 2**k + 1`` prime and ``g`` a primitive root.
#: Both are ``1 (mod 4)`` so ``sqrt(-1)`` exists (the same constraint
#: :data:`_PEEL_MODULUS` carries, for the same pairing).  The first field
#: is where quadratic candidates are *paired* -- its size bounds the
#: recoverable real part at ``m // 2`` and sets the spurious-pair rate --
#: and the second only cross-checks, killing all but ~0.2% of the spurious
#: pairs before the trial division.  ``test_ntt_field_constants``
#: re-derives all four numbers of each.
_NTT_FIELDS = ((163841, 5, 15, 3), (65537, 1, 16, 3))

#: Nonzero bytes in a packed root mask; see :func:`_iter_bits`.
_NONZERO_BYTE = re.compile(rb"[^\x00]")


def _ntt_radix2(vec: list[int], modulus: int, root: int) -> list[int]:
    """Transform ``vec`` in place: ``out[t] = sum_j vec[j] * root**(j*t)``.

    Iterative radix-2; ``len(vec)`` a power of two, ``root`` of that order.
    """
    size = len(vec)
    j = 0
    for i in range(1, size):
        bit = size >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            vec[i], vec[j] = vec[j], vec[i]
    span = 2
    while span <= size:
        step = pow(root, size // span, modulus)
        half = span >> 1
        powers = [1] * half
        for i in range(1, half):
            powers[i] = powers[i - 1] * step % modulus
        for start in range(0, size, span):
            for i in range(half):
                low = vec[start + i]
                high = vec[start + i + half] * powers[i] % modulus
                vec[start + i] = (low + high) % modulus
                vec[start + i + half] = (low - high) % modulus
        span <<= 1
    return vec


def _roots_mod(coefficients: list[int], field: tuple[int, int, int, int]) -> set[int]:
    """Return every root of the polynomial in the prime field, exactly.

    Evaluates at all field points: the group has order ``c * 2**k``, so
    ``f(g**t)`` over ``t`` is a DFT computed as ``c`` NTTs and a combining
    pass.  Repeated roots and irreducible factors need no special machinery.
    """
    modulus, cofactor, log_size, generator = field
    group = modulus - 1
    size = 1 << log_size
    degree = len(coefficients) - 1
    folded = [0] * group
    for i, coefficient in enumerate(coefficients):
        j = (degree - i) % group
        folded[j] = (folded[j] + coefficient) % modulus
    sub_root = pow(generator, cofactor, modulus)
    parts = []
    for r in range(cofactor):
        part = folded[r::cofactor]
        part += [0] * (size - len(part))
        parts.append(_ntt_radix2(part, modulus, sub_root))
    if cofactor == 1:
        values = parts[0]
    else:
        values = [0] * group
        mask = size - 1
        for r, part in enumerate(parts):
            if r == 0:
                for t in range(group):
                    values[t] = part[t & mask]
            else:
                twiddle = pow(generator, r, modulus)
                w = 1
                for t in range(group):
                    values[t] = (values[t] + w * part[t & mask]) % modulus
                    w = w * twiddle % modulus
    roots = {pow(generator, t, modulus) for t, v in enumerate(values) if v == 0}
    if coefficients[-1] % modulus == 0:
        roots.add(0)
    return roots


def _iter_bits(mask: int, size: int) -> Iterator[int]:
    """Yield the set bit positions of ``mask``, a ``size``-bit integer.

    ``mask & -mask`` copies the whole integer per bit; a compiled byte scan
    finds nonzero bytes at C speed.
    """
    raw = mask.to_bytes((size + 7) >> 3, "little")
    for match in _NONZERO_BYTE.finditer(raw):
        index = match.start()
        byte = raw[index]
        base = index << 3
        while byte:
            low = byte & -byte
            yield base + low.bit_length() - 1
            byte ^= low


def _quadratic_candidates_ntt(
    prime_count: int,
    root_sets: tuple[set[int], set[int]],
    real_bound: int,
) -> Iterator[tuple[int, int]]:
    """Propose ``(a, p**(2*b))`` pairs from the two fields' root sets.

    Roots pairing at distance ``2*i*p**b`` in the first field propose every
    lift of ``a`` through ``real_bound``; the second field checks each lift.
    Spurious pairs survive at the product of the densities (~0.2% on dense
    n=10) and die in trial division.
    """
    field_data = []
    for (modulus, _, _, generator), roots in zip(_NTT_FIELDS, root_sets, strict=True):
        mask = 0
        for root in roots:
            mask |= 1 << root
        field_data.append(
            (modulus, pow(generator, (modulus - 1) // 4, modulus), roots, mask)
        )
    for base in _first_primes(prime_count):
        # If the instruction prime equals one field, its conjugate roots
        # coincide there.  Pair in the other field and use the collision as
        # the cross-check; every generated prime is therefore recoverable.
        primary = 1 if base == field_data[0][0] else 0
        yield from sorted(
            _ntt_pairs(base, field_data[primary], field_data[1 - primary], real_bound)
        )


def _ntt_pairs(
    base: int,
    paired: tuple[int, int, set[int], int],
    check: tuple[int, int, set[int], int],
    real_bound: int,
) -> set[tuple[int, int]]:
    """Return ``(a, base**(2*b))`` candidates: paired, then checked.

    Each field is ``(modulus, sqrt(-1), roots, root bitmask)``.
    """
    m0, i0, _roots0, mask0 = paired
    m1, i1, roots1, _mask1 = check
    candidates: set[tuple[int, int]] = set()
    full = (1 << m0) - 1
    power0 = base % m0
    power1 = base % m1
    square = base * base
    for _exponent in range(_PEEL_MAX_IMAGINARY_EXPONENT):
        delta = 2 * i0 * power0 % m0
        rotated = ((mask0 << delta) | (mask0 >> (m0 - delta))) & full
        hits = mask0 & rotated
        if hits:
            offset0 = i0 * power0 % m0
            offset1 = i1 * power1 % m1
            for r in _iter_bits(hits, m0):
                residue = (r - offset0) % m0
                first = residue + ((-real_bound - residue + m0 - 1) // m0) * m0
                for real in range(first, real_bound + 1, m0):
                    if (real + offset1) % m1 in roots1 and (
                        real - offset1
                    ) % m1 in roots1:
                        candidates.add((real, square))
        power0 = power0 * base % m0
        power1 = power1 * base % m1
        square *= base * base
    return candidates


def _ntt_real_bound(degree: int) -> int:
    """Return the real-part lift window for a polynomial of ``degree``.

    A generated DAG operand is a label plus a span or byte delta: labels
    total at most the instruction count, spans at most 48 times it, and
    the tree and parking cases add at most 51, so ``|a| < 50 * degree``
    once the NTT path starts above degree 100 -- measured at most 2.03
    times the degree over the dense, nested-dense and witness tables at
    n <= 10.  The window only proposes candidates: acceptance is exact
    division, and a root past the window stays in the remainder, which
    ``_remainder_roots`` recovers exactly, so the window's size costs
    speed only, never correctness, for hand-written programs too.
    """
    return max(_NTT_FIELDS[0][0] // 2, 50 * degree)
