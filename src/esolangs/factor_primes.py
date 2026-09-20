"""Exact arbitrary-precision prime segments for Factor."""

import math
from collections.abc import Iterator


def prime_segments(width: int) -> Iterator[tuple[int, int, list[int]]]:
    """Yield the primes in consecutive ``width``-integer intervals.

    A local segmented Eratosthenes sieve keeps Python-int base primes only
    through the square root. Unlike SymPy's machine-word sieve, it has no
    representational ceiling.
    """
    base: list[int] = []
    base_candidate = 2
    start = 2
    while True:
        stop = start + width
        limit = math.isqrt(stop - 1)
        while base_candidate <= limit:
            root = math.isqrt(base_candidate)
            if all(base_candidate % prime for prime in base if prime <= root):
                base.append(base_candidate)
            base_candidate = 3 if base_candidate == 2 else base_candidate + 2

        composite = bytearray(width)
        for prime in base:
            first = max(prime * prime, -(-start // prime) * prime)
            if first >= stop:
                continue
            offset = first - start
            composite[offset::prime] = b"\1" * (-(-(width - offset) // prime))
        yield start, stop, [
            value
            for offset, marked in enumerate(composite)
            if not marked and (value := start + offset) >= 2
        ]
        start = stop
