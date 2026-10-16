"""Gaussian integer roots: sparse gap chunks, ``p``-adic lifting, a 2-D lattice.

The general search for what the peels leave, deterministic polynomial time
in the source length.
"""

from esolangs.languages.polynomial.interpreter.primality import (
    _is_proven_prime,
    _require_sympy,
)

#: The lattice argument needs ``P > _LATTICE_MARGIN * B**2`` for Cauchy's root
#: bound ``B``: minimum ``sqrt(P)`` then exceeds ``sqrt(16/3) * B`` with room,
#: which forces both nearest-plane roundings (``docs/proofs/index.md``).
_LATTICE_MARGIN = 16


#: A Gaussian integer ``re + im*i`` as an exact pair.
type _Gaussian = tuple[int, int]

#: Sparse polynomial: ``(exponent, coefficient)`` pairs, exponents ascending,
#: coefficients nonzero.
type _Terms = list[tuple[int, int]]


def _gaussian_pow(base: _Gaussian, exponent: int) -> _Gaussian:
    """Return ``base**exponent`` in ``Z[i]`` by square-and-multiply."""
    result_re, result_im = 1, 0
    base_re, base_im = base
    while exponent:
        if exponent & 1:
            result_re, result_im = (
                result_re * base_re - result_im * base_im,
                result_re * base_im + result_im * base_re,
            )
        exponent >>= 1
        if exponent:
            base_re, base_im = (
                base_re * base_re - base_im * base_im,
                2 * base_re * base_im,
            )
    return result_re, result_im


def _sparse_value(chunk: _Terms, point: _Gaussian) -> _Gaussian:
    """Evaluate ``sum c * x**(e - e_0)`` at ``point``: sparse Horner in ``Z[i]``."""
    value_re, value_im = chunk[-1][1], 0
    for index in range(len(chunk) - 2, -1, -1):
        step_re, step_im = _gaussian_pow(point, chunk[index + 1][0] - chunk[index][0])
        value_re, value_im = (
            value_re * step_re - value_im * step_im + chunk[index][1],
            value_re * step_im + value_im * step_re,
        )
    return value_re, value_im


def _gap_chunks(terms: _Terms) -> list[_Terms]:
    """Cut a sparse polynomial at every gap no root of norm >= 4 can bridge.

    With ``S`` the absolute coefficient sum of the chunk so far and ``g``
    the next gap, ``2**g > S`` (equivalently ``g >= S.bit_length()``) forces
    every Gaussian integer root ``alpha`` with ``|alpha| >= 2`` of what is
    left to be a root of both sides: if the upper part were nonzero at
    ``alpha`` it would be a nonzero Gaussian integer, so ``|alpha|**g`` could
    not exceed ``S``.  Inside a chunk every gap is below
    ``log2(t * H) + 1``, which bounds the chunk's degree.
    """
    chunks: list[_Terms] = []
    current: _Terms = [terms[0]]
    mass = abs(terms[0][1])
    for exponent, coefficient in terms[1:]:
        if exponent - current[-1][0] >= mass.bit_length():
            chunks.append(current)
            current, mass = [], 0
        current.append((exponent, coefficient))
        mass += abs(coefficient)
    chunks.append(current)
    return chunks


def _vanishes_at(terms: _Terms, point: _Gaussian) -> bool:
    """Whether the sparse polynomial is zero at ``point`` (``|point| >= 2``).

    Exact: by :func:`_gap_chunks` the polynomial vanishes there iff every
    chunk does, and each chunk has polynomially bounded degree however
    large the exponents.
    """
    return bool(terms) and all(
        _sparse_value(chunk, point) == (0, 0) for chunk in _gap_chunks(terms)
    )


def _sparse_multiplicity(terms: _Terms, point: _Gaussian) -> int:
    """Return the multiplicity of the root ``point`` (``|point| >= 2``).

    For ``alpha != 0`` the multiplicity is the least ``j`` with
    ``(x d/dx)**j f (alpha) != 0``: ``(x d/dx)**j`` is ``x**j d**j/dx**j``
    plus lower derivatives, a unitriangular change.  The operator keeps the
    support and multiplies each coefficient by its exponent, so every
    iterate is sparse too; Hajos' lemma stops the loop within ``t - 1``.
    """
    multiplicity = 0
    while _vanishes_at(terms, point):
        multiplicity += 1
        terms = [(e, c * e) for e, c in terms if e]
    return multiplicity


def _mod_rem(dividend: list[int], divisor: list[int], prime: int) -> list[int]:
    """Remainder of ``dividend / divisor`` over GF(``prime``), descending lists."""
    rest = [k % prime for k in dividend]
    inverse = pow(divisor[0], -1, prime)
    size = len(divisor)
    while len(rest) >= size:
        factor = rest[0] * inverse % prime
        if factor:
            for index in range(1, size):
                rest[index] = (rest[index] - factor * divisor[index]) % prime
        rest.pop(0)
    while rest and not rest[0]:
        rest.pop(0)
    return rest


def _squarefree_mod(coefficients: list[int], prime: int) -> bool:
    """Whether reduction mod ``prime`` keeps the degree and stays squarefree."""
    reduced = [k % prime for k in coefficients]
    if not reduced[0]:
        return False
    degree = len(reduced) - 1
    left = reduced
    right = [k * (degree - i) % prime for i, k in enumerate(reduced[:-1])]
    while right and not right[0]:
        right.pop(0)
    if not right:
        # The derivative vanishes mod p: a p-th power, never squarefree.
        return degree == 0
    while right:
        left, right = right, _mod_rem(left, right, prime)
    return len(left) == 1


def _value_mod(coefficients: list[int], point: int, modulus: int) -> int:
    """Horner mod ``modulus``."""
    value = 0
    for coefficient in coefficients:
        value = (value * point + coefficient) % modulus
    return value


def _hensel_lift(
    coefficients: list[int], roots: list[int], prime: int, target: int
) -> list[int]:
    """Lift simple roots mod ``prime`` to roots mod ``target`` (a power of it).

    Newton's iteration doubles the precision each step because the
    derivative is a unit at a simple root.  The coefficients are reduced
    once per precision, not once per root.
    """
    degree = len(coefficients) - 1
    derivative = [k * (degree - i) for i, k in enumerate(coefficients[:-1])]
    modulus = prime
    while modulus < target:
        modulus = min(modulus * modulus, target)
        reduced = [k % modulus for k in coefficients]
        slope_poly = [k % modulus for k in derivative]
        roots = [
            (
                root
                - _value_mod(reduced, root, modulus)
                * pow(_value_mod(slope_poly, root, modulus), -1, modulus)
            )
            % modulus
            for root in roots
        ]
    return roots


def _round_div(numerator: int, denominator: int) -> int:
    """Nearest integer to ``numerator / denominator`` (``denominator > 0``)."""
    return (2 * numerator + denominator) // (2 * denominator)


def _dot(left: tuple[int, int], right: tuple[int, int]) -> int:
    """Euclidean inner product in ``Z**2``."""
    return left[0] * right[0] + left[1] * right[1]


def _gauss_reduce(
    first: tuple[int, int], second: tuple[int, int]
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Lagrange--Gauss reduction: ``|b1| <= |b2|`` and ``|<b1, b2>| <= |b1|**2/2``."""
    if _dot(first, first) > _dot(second, second):
        first, second = second, first
    while True:
        mu = _round_div(_dot(first, second), _dot(first, first))
        second = (second[0] - mu * first[0], second[1] - mu * first[1])
        if _dot(second, second) >= _dot(first, first):
            return first, second
        first, second = second, first


def _nearest_plane(
    basis: tuple[tuple[int, int], tuple[int, int]], target: tuple[int, int]
) -> tuple[int, int]:
    """Return ``target`` minus Babai's nearest-plane lattice vector, exactly.

    On a Lagrange--Gauss-reduced basis of a lattice whose minimum exceeds
    ``sqrt(16/3) B``, a coset vector of norm at most ``B`` is the one
    returned: both roundings are forced (see the proof in
    ``docs/proofs/index.md#polynomial-bound``).
    """
    first, second = basis
    gram11, gram12 = _dot(first, first), _dot(first, second)
    determinant = gram11 * _dot(second, second) - gram12 * gram12
    along_second = _round_div(
        _dot(target, second) * gram11 - gram12 * _dot(target, first), determinant
    )
    rest = (target[0] - along_second * second[0], target[1] - along_second * second[1])
    along_first = _round_div(_dot(rest, first), gram11)
    return rest[0] - along_first * first[0], rest[1] - along_first * first[1]


def _root_prime(coefficients: list[int]) -> int:
    """Return the least prime ``p = 1 (mod 4)`` keeping ``coefficients`` squarefree.

    ``p`` must not divide the leading coefficient or the discriminant, and
    only ``O(d (d + log H))`` primes do, so ``p`` is polynomial in the input.
    ``1 (mod 4)`` gives ``sqrt(-1)`` in the ``p``-adic integers.
    """
    candidate = 5
    while not (
        _is_proven_prime(candidate) and _squarefree_mod(coefficients, candidate)
    ):
        candidate += 4
    return candidate


def _dense_gaussian_roots(coefficients: list[int]) -> set[_Gaussian]:
    """Return every nonzero Gaussian integer root of a dense integer polynomial.

    Deterministic and polynomial time, no factorization over ``Z``: take the
    squarefree part; pick the least prime ``p = 1 (mod 4)`` that keeps it
    squarefree of full degree; find its roots mod ``p`` by exhausting GF(p)
    (``p`` is polynomially bounded); Hensel-lift each to ``P = p**k >
    16 B**2`` (:data:`_LATTICE_MARGIN`) with ``B`` Cauchy's root bound; a root
    ``a + c i`` maps to
    ``a + c*iota`` for a fixed ``iota = sqrt(-1) mod P``, so ``(a, c)`` is the
    short vector of a coset of ``{(u, v): u + v*iota = 0 (mod P)}`` --
    determinant ``P``, minimum at least ``sqrt(P)`` -- and nearest-plane
    rounding on a reduced basis returns it.  Every candidate is checked by
    exact evaluation, so the set is exactly the roots.
    """
    poly = _trim_zeros(coefficients)
    if len(poly) < 2:
        return set()
    # ``poly`` has a nonzero lead and degree >= 1, so its squarefree part does too.
    sp = _require_sympy()
    squarefree = [int(k) for k in sp.Poly(poly, sp.Symbol("x")).sqf_part().all_coeffs()]
    base = _root_prime(squarefree)
    residues = [r for r in range(base) if not _value_mod(squarefree, r, base)]
    if not residues:
        return set()
    modulus = _lift_modulus(poly, base)
    basis = _gaussian_lattice_basis(base, modulus)
    terms = [(len(poly) - 1 - i, k) for i, k in enumerate(poly) if k][::-1]
    found: set[_Gaussian] = set()
    for lifted in _hensel_lift(squarefree, residues, base, modulus):
        candidate = _nearest_plane(basis, (lifted, 0))
        if candidate != (0, 0) and _sparse_value(terms, candidate) == (0, 0):
            found.add(candidate)
    return found


def _trim_zeros(coefficients: list[int]) -> list[int]:
    """Drop the leading and trailing zeros of a descending coefficient list."""
    start = 0
    while start < len(coefficients) and not coefficients[start]:
        start += 1
    stop = len(coefficients)
    while stop > start and not coefficients[stop - 1]:
        stop -= 1
    return coefficients[start:stop]


def _lift_modulus(poly: list[int], base: int) -> int:
    """Return the least power of ``base`` above ``_LATTICE_MARGIN * B**2``.

    ``B`` is Cauchy's bound on the roots' absolute value.
    """
    lead = abs(poly[0])
    bound = 1 + -(-max(abs(k) for k in poly[1:]) // lead)
    modulus = base
    while modulus <= _LATTICE_MARGIN * bound * bound:
        modulus *= base
    return modulus


def _gaussian_lattice_basis(
    base: int, modulus: int
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Reduced basis of ``{(u, v): u + v*iota = 0 (mod modulus)}``.

    ``iota`` is ``sqrt(-1)`` mod ``base`` lifted to ``modulus``.
    """
    iota = next(r for r in range(2, base) if (r * r + 1) % base == 0)
    (iota,) = _hensel_lift([1, 0, 1], [iota], base, modulus)
    return _gauss_reduce((modulus, 0), ((-iota) % modulus, 1))
