"""Exact arbitrary-precision prime segments for Factor."""

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
