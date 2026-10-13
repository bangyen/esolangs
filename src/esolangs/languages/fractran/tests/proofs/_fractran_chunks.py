"""Direct chunk exponents with exact cleanup; no permutation rank selection."""

from collections.abc import Iterator

from esolangs.generation.helpers import TEMPLATE_CHAR
from esolangs.languages.fractran.tests.proofs._fractran_order import (
    _linear_primes,
    bit_decoder,
)


def chunk_width(n: int) -> int:
    return max(1, n - n.bit_length())


def mapped_chunk_width(n: int) -> int:
    """Return a power-of-ten width below the feature construction's width."""
    return 10 ** (len(str(chunk_width(n))) - 1)


def decimal_progression(count: int, step: int = 1) -> Iterator[str]:
    """Yield decimal multiples of ``step`` without wide binary conversion."""
    digits = bytearray(b"0")
    stride = str(step)[::-1].encode("ascii")
    for _ in range(count):
        yield digits[::-1].decode("ascii")
        carry = 0
        position = 0
        while position < len(stride) or carry:
            if position == len(digits):
                digits.append(ord("0"))
            value = digits[position] - ord("0") + carry
            if position < len(stride):
                value += stride[position] - ord("0")
            carry, digit = divmod(value, 10)
            digits[position] = ord("0") + digit
            position += 1


def mapped_chunk_template(table: str) -> str:
    """Load the selected chunk directly from its mapping numerator."""
    n = len(table).bit_length() - 1
    assert len(table) == 1 << n
    width = mapped_chunk_width(n)
    k = (len(table) + width - 1) // width
    inputs = [prime for prime in _linear_primes(40 + n) if prime > 149][:n]
    start = "*".join(["29", "103^2", *(f"{prime}^{TEMPLATE_CHAR}" for prime in inputs)])
    loaders = [f"107^{1 << (n - 1 - i)}/{prime}" for i, prime in enumerate(inputs)]
    # All chunk values fit this dictionary: its O(2**width * n) text is O(T).
    # Power-of-ten strides append zeros to the unit counter; both counters
    # use amortized constant digit updates, with O(n)-bit scalar addresses.
    literals = list(decimal_progression(1 << width))
    suffix = "0" * (len(str(width)) - 1)
    mappings = [
        f"109*7^{literals[int(table[position : position + width][::-1], 2)]}"
        f"/29*107^{number + suffix if number != '0' else '0'}"
        for position, number in zip(
            range(0, len(table), width), decimal_progression(k), strict=True
        )
    ]
    return " ".join([start, *loaders, *reversed(mappings), *bit_decoder()[1]])


def chunk_template(table: str) -> str:
    n = len(table).bit_length() - 1
    assert len(table) == 1 << n
    width = chunk_width(n)
    digits = [
        1 + int(table[position : position + width][::-1], 2)
        for position in range(0, len(table), width)
    ]
    k = len(digits)
    primes = [prime for prime in _linear_primes(40 + n + k) if prime > 149]
    inputs, features = primes[:n], primes[n : n + k]
    start = "*".join(
        [
            "29",
            "103^2",
            *(f"{prime}^{TEMPLATE_CHAR}" for prime in inputs),
            *(
                f"{prime}^{digit}"
                for prime, digit in zip(features, digits, strict=True)
            ),
        ]
    )
    loaders = [f"107^{1 << (n - 1 - i)}/{prime}" for i, prime in enumerate(inputs)]
    mappings = [f"13^{i + 1}/29*107^{width * i}" for i in reversed(range(k))]
    transfers = []
    for i in reversed(range(k)):
        transfers.extend(
            (
                f"17^{i + 1}*7/13^{i + 1}*{features[i]}",
                f"23/13^{i + 1}",
            )
        )
    bridges = [f"13^{i + 1}/17^{i + 1}" for i in reversed(range(k))]
    cleanup = [
        f"1/{prime}^{digit}" for prime, digit in zip(features, digits, strict=True)
    ]
    return " ".join(
        [
            start,
            *loaders,
            *mappings,
            *transfers,
            *bridges,
            "109/23*7",
            *bit_decoder()[1],
            *cleanup,
        ]
    )
