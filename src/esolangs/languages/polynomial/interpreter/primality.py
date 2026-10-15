"""Proven primality for the Polynomial root search.

Every range gets a proof: :func:`~esolangs.factor_primes.isprime64` below
``2**64`` and AKS (:func:`_aks`) above it, so a cold parse never believes a
probable prime.
"""

import math
from collections.abc import Iterator
from itertools import islice
from typing import Any

try:
    import sympy as sp
except ModuleNotFoundError:  # optional ``math`` extra
    sp = None

from esolangs.exceptions import MissingDependencyError
from esolangs.factor_primes import isprime64


def _require_sympy() -> Any:
    """Return SymPy or name the extra that installs it."""
    if sp is None:
        raise MissingDependencyError(
            "Polynomial requires optional mathematics support; "
            "install it with `pip install 'esolangs[math]'`"
        )
    return sp


def _integer_root(number: int, degree: int) -> int:
    """Return ``floor(number ** (1 / degree))`` for ``number >= 0``, exactly.

    Integer Newton from above: ``O(log number)`` steps of ``degree``-th
    powers, so polynomial in the bit length however wide ``number`` is.
    """
    if number < 2 or degree == 1:
        return number
    guess = 1 << -(-number.bit_length() // degree)
    while True:
        better = ((degree - 1) * guess + number // guess ** (degree - 1)) // degree
        if better >= guess:
            return guess
        guess = better


def _prime_power(number: int, max_exponent: int) -> tuple[int, int] | None:
    """Return ``(p, v)`` with ``number == p**v``, ``p`` prime, ``v <= max_exponent``.

    ``None`` otherwise.  The representation is unique, so the first ``v``
    whose integer root is an exact prime is the answer.
    """
    if number < 2:
        return None
    for exponent in range(1, max_exponent + 1):
        base = _integer_root(number, exponent)
        if base < 2:
            break
        if base**exponent == number and _is_proven_prime(base):
            return base, exponent
    return None


#: Below this, :func:`~esolangs.factor_primes.isprime64` is a proof:
#: Miller--Rabin with Sinclair's
#: seven bases is deterministic through ``2**64``.  Above it SymPy's
#: ``isprime`` is BPSW -- a compositeness verdict is still a witness, but
#: "prime" is not a proof -- so a probable prime there is certified by
#: :func:`_aks` before it is believed.
_EXACT_ISPRIME_LIMIT = 1 << 64


def _is_proven_prime(number: int) -> bool:
    """Return whether ``number`` is prime, with a proof in every range.

    Deterministic Miller--Rabin below :data:`_EXACT_ISPRIME_LIMIT`; above
    it BPSW screens composites (its "composite" is a witness) and AKS
    certifies the rest, so the answer is never probabilistic.
    """
    if number < _EXACT_ISPRIME_LIMIT:
        return isprime64(number)
    if not _require_sympy().isprime(number):
        return False
    return _aks(number)


def _totient(number: int) -> int:
    """Euler's phi by trial division; only ever called on AKS's small ``r``."""
    result, rest, factor = number, number, 2
    while factor * factor <= rest:
        if rest % factor == 0:
            while rest % factor == 0:
                rest //= factor
            result -= result // factor
        factor += 1
    if rest > 1:
        result -= result // rest
    return result


def _cyclic_mul(left: list[int], right: list[int], modulus: int) -> list[int]:
    """Multiply in ``Z_modulus[x] / (x**r - 1)`` by Kronecker substitution.

    Both operands are ``r`` reduced residues; one big-integer product
    replaces the ``r**2`` coefficient products.
    """
    size = len(left)
    width = (2 * modulus.bit_length() + size.bit_length() + 8) // 8
    packed_left = int.from_bytes(
        b"".join(k.to_bytes(width, "little") for k in left), "little"
    )
    packed_right = int.from_bytes(
        b"".join(k.to_bytes(width, "little") for k in right), "little"
    )
    raw = (packed_left * packed_right).to_bytes(width * 2 * size, "little")
    out = [0] * size
    for index in range(2 * size - 1):
        value = int.from_bytes(raw[index * width : (index + 1) * width], "little")
        if value:
            out[index % size] += value
    return [k % modulus for k in out]


def _aks(number: int) -> bool:
    """Agrawal--Kayal--Saxena: a deterministic polynomial-time primality proof.

    ``L = number.bit_length() >= log2 number`` stands in for the logarithm,
    which only strengthens both conditions: ``r`` has ``ord_r(number) > L**2``
    and the congruence is checked for ``a <= isqrt(phi(r) * L**2)``, which is
    at least ``sqrt(phi(r)) log2 number`` and still below ``r``.  Slow in
    practice past ``2**64`` -- it is the certificate the proof needs, reached
    only by a BPSW probable prime that large.
    """
    if number < 2:
        return False
    bits = number.bit_length()
    if any(
        _integer_root(number, exponent) ** exponent == number
        for exponent in range(2, bits + 1)
    ):
        return False
    square = bits * bits
    modulus = _aks_modulus(number, square)
    if any(
        1 < math.gcd(base, number) < number
        for base in range(2, min(modulus, number - 1) + 1)
    ):
        return False
    if number <= modulus:
        return True
    limit = math.isqrt(_totient(modulus) * square)
    return all(_aks_congruence(number, modulus, base) for base in range(1, limit + 1))


def _aks_modulus(number: int, square: int) -> int:
    """Return the least ``r`` coprime to ``number`` with ``ord_r(number) > square``."""
    modulus = 2
    while True:
        if math.gcd(modulus, number) == 1:
            value, order = number % modulus, 1
            while order <= square and value != 1:
                value = value * number % modulus
                order += 1
            if order > square:
                return modulus
        modulus += 1


def _aks_congruence(number: int, modulus: int, base: int) -> bool:
    """Whether ``(x + a)**n == x**n + a`` mod ``(x**r - 1, n)``, for ``a = base``."""
    # Square-and-multiply over the cyclic coefficient array.
    power = [0] * modulus
    power[0] = 1
    factor = [0] * modulus
    factor[0] = base % number
    # The x term of (x + base): slot 1, wrapped for the cyclic array.
    factor[1 % modulus] += 1
    exponent = number
    while exponent:
        if exponent & 1:
            power = _cyclic_mul(power, factor, number)
        exponent >>= 1
        if exponent:
            factor = _cyclic_mul(factor, factor, number)
    expected = [0] * modulus
    expected[number % modulus] = 1
    expected[0] = (expected[0] + base) % number
    return power == expected


def _first_primes(count: int) -> Iterator[int]:
    """Yield the first ``count`` primes; ``primerange(2, n*n + 3)`` holds > ``n``."""
    return islice(_require_sympy().primerange(2, count * count + 3), count)
