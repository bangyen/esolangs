"""Direct chunk exponents with exact cleanup; no permutation rank selection."""

from esolangs.tools.helpers import TEMPLATE_CHAR
from tests.proofs._fractran_order import _linear_primes, bit_decoder


def chunk_width(n: int) -> int:
    return max(1, n - n.bit_length())


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
