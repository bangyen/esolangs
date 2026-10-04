"""Boolean-function generator for Factor.

Ascending primes encode Brainfuck instructions by residue modulo eleven
and run length by exponent. A compact tree tests inputs in stream order
and puts the answer in the final input's unused flag. Multiplication loops
build and subtract the ASCII offsets; only this tree is encoded.

Retiring alternate trees and weighted reordering adds 4.26% to the
three-input digit total, 0.061% to the seeded five-input sample.
"""

import heapq
import sys
from collections.abc import Iterator

from esolangs._brainfuck import BrainfuckDialect
from esolangs.factor_primes import prime_segments
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    decision_tree_body,
    move_text,
)

__all__ = ["factor"]

#: A prime's residue mod 11 selects the instruction it stands for.
_BF_RESIDUE = {">": 1, "<": 2, "+": 3, "-": 4, ".": 5, ",": 6, "[": 7, "]": 8}

# Exact prime enumeration, in bounded segments. ``isprime`` becomes a BPSW
# probable-prime test above 2**64; Factor is uncapped, so it cannot certify the
# primes in a total encoding. The chunk is only a segment width, never a cap.
_FACTOR_PRIME_CHUNK = 20000

#: 48 as ``_SPAN`` iterations adding ``_STEP``, which is what lets one loop
#: fill two cells: counting to 48 twice costs 96 characters, this costs 29.
_SPAN = 6
_STEP = _ASCII_ZERO // _SPAN


def _primes() -> Iterator[int]:
    """Yield every prime in ascending order, the stream a program draws from."""
    return (
        prime
        for _start, _stop, segment in prime_segments(_FACTOR_PRIME_CHUNK)
        for prime in segment
    )


def _spans(code: str) -> list[tuple[int, int]]:
    """Return ``(length, prime)`` per maximal run, in program order.

    The stream is shared across runs, so a run's prime is fixed by how many
    runs precede it -- which is why a program with fewer characters can
    encode smaller even when it has more runs.
    """
    primes = _primes()
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(code):
        j = i
        while j < len(code) and code[j] == code[i]:
            j += 1
        residue = _BF_RESIDUE[code[i]]
        out.append((j - i, next(p for p in primes if p % 11 == residue)))
        i = j
    return out


def _encode(code: str) -> int:
    """Encode a Brainfuck program as the Factor integer for it.

    A run folds into one exponent. Prime powers multiply smallest-width
    first: a growing accumulator was 12.5s of a 14.4s build at thirteen
    inputs (120860 runs) against 0.7s, and width balance gives the
    arithmetic bound.
    """
    powers = [prime**length for length, prime in _spans(code)]
    heap = [(value.bit_length(), serial, value) for serial, value in enumerate(powers)]
    heapq.heapify(heap)
    serial = len(heap)
    while len(heap) > 1:
        _a_bits, _a_serial, a = heapq.heappop(heap)
        _b_bits, _b_serial, b = heapq.heappop(heap)
        product = a * b
        heapq.heappush(heap, (product.bit_length(), serial, product))
        serial += 1
    return heap[0][2] if heap else 1


def _program(truth_table: str) -> str:
    """Build the compact tree in input order, using the final input's flag."""
    n = _validate_truth_table(truth_table)
    perm = tuple(range(n))
    result = 2 * n - 1
    scratch, multiplier = result + 1, result + 2
    after_reads = 2 * (n - 1)
    back = scratch - after_reads

    build = (
        ">" * multiplier
        + "+" * _SPAN
        + "[-"
        + "<"
        + "+" * _STEP  # the scratch counter
        + "<"
        + "+" * _STEP  # the answer cell, offset in the same pass
        + ">>"
        + "]"
        + "<" * multiplier
    )
    reads = "".join("," + (">>" if k < n - 1 else "") for k in range(n))
    dedent = (
        ">" * back
        + "[-"
        + "<" * scratch
        + "-"
        + ">>-" * (n - 1)
        + ">" * back
        + "]"
        + "<" * back
    )
    body, pos = decision_tree_body(
        truth_table,
        ">",
        "<",
        perm,
        after_reads,
        binary_leaves=True,
        result=result,
    )
    return build + reads + dedent + body + move_text(pos, result, ">", "<") + "."


def factor(
    truth_table: str,
    *,
    cell_modulus: int | None = 256,
    tape_size: int | None = None,
    boundary: str = "clamp",
    eof: str = "error",
) -> str:
    """Build a Factor program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Total, with no digit ceiling (the old
    4300/16000/500000 budgets were size policy): CPython's
    ``sys.get_int_max_str_digits()`` is raised to a bit-length estimate
    (``log10(2) < 0.30103``, never under-counting) and put back.
    """
    n = _validate_truth_table(truth_table)
    BrainfuckDialect(cell_modulus, tape_size, boundary, eof).require_cells(2 * n + 2)
    number = _encode(_program(truth_table))
    digits = int(number.bit_length() * 0.30103) + 1
    limit = sys.get_int_max_str_digits()
    if limit == 0 or digits <= limit:  # 0 is CPython's "unlimited"
        return str(number)
    sys.set_int_max_str_digits(digits + 1)
    try:
        return str(number)
    finally:
        sys.set_int_max_str_digits(limit)
