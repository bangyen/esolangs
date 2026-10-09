"""Exact primes for the number-theoretic languages: segments and a test."""

import math
from collections.abc import Iterator


def prime_segments(min_width: int) -> Iterator[tuple[int, int, list[int]]]:
    """Yield primes in consecutive intervals of at least ``min_width``.

    A local segmented Eratosthenes sieve keeps Python-int base primes only
    through the square root. Unlike SymPy's machine-word sieve, it has no
    representational ceiling. Segments grow to ``sqrt(start)``: revisiting
    the base-prime list then costs ``O(Q / log Q)`` through endpoint ``Q``
    instead of the fixed-width implementation's ``O(Q**(3/2))``.
    """
    base: list[int] = []
    base_candidate = 2
    start = 2
    while True:
        width = max(min_width, math.isqrt(start) + 1)
        stop = start + width
        limit = math.isqrt(stop - 1)
        while base_candidate <= limit:
            root = math.isqrt(base_candidate)
            for prime in base:
                if prime > root:
                    base.append(base_candidate)
                    break
                if not base_candidate % prime:
                    break
            else:
                base.append(base_candidate)
            base_candidate = 3 if base_candidate == 2 else base_candidate + 2

        composite = bytearray(width)
        for prime in base:
            first = max(prime * prime, -(-start // prime) * prime)
            offset = first - start
            composite[offset::prime] = b"\1" * (-(-(width - offset) // prime))
        yield (
            start,
            stop,
            [
                value
                for offset, marked in enumerate(composite)
                if not marked and (value := start + offset) >= 2
            ],
        )
        start = stop


def isprime64(number: int) -> bool:
    """Return whether ``number < 2**64`` is prime, deterministically."""
    if number < 2:
        return False
    for prime in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if number % prime == 0:
            return number == prime
    odd = number - 1
    shifts = 0
    while not odd & 1:
        shifts += 1
        odd >>= 1
    # Sinclair's seven bases, proven for every number below 2**64.  A base
    # the number divides says nothing, so it is skipped rather than read as
    # a witness of compositeness (73 divides 450775, for one).
    for base in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if base % number == 0:
            continue
        value = pow(base, odd, number)
        if value in (1, number - 1):
            continue
        for _ in range(shifts - 1):
            value = value * value % number
            if value == number - 1:
                break
        else:
            return False
    return True
