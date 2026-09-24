"""Boolean-function generator for Factor.

A Factor program is an integer whose factorization is a Brainfuck program:
ascending primes give the instruction order, a prime's residue mod 11 gives
the instruction, and its exponent gives the run length.  So Factor pays
``sum(L_i * log10(p_i))`` decimal digits over the maximal runs -- a *position*
weight, since the primes come from one ascending stream, not a character
count.  Emitting Brainfuck's shortest program is therefore the wrong
objective, and this used to do exactly that.

Two things follow.  The ASCII offsets are worth folding even though folding
makes the Brainfuck program *longer* in runs: one multiply loop builds 48
into a scratch cell and the answer cell together, and one loop subtracts it
from every input, replacing ``48 * (n + 1)`` characters with 29.  That is
-25% to -45% of the digits over the tables measured, and it never lost --
456 tables, exhaustive through three inputs and sampled to six.  A plain
tree candidate was dropped for never winning one of them.

And the input order wants choosing by digits rather than by characters,
which is what :func:`~esolangs.tools.helpers.best_input_order` measures:
worth -6% on NAND3, nothing on most tables.  Scoring needs no
multiplication, since the digit count is ``floor(sum(L_i log10 p_i)) + 1``,
so only the winner is ever encoded.
"""

import heapq
import math
import sys
from collections.abc import Iterator

from esolangs.factor_primes import prime_segments
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _GREEDY_ORDER_MAX_ARITY,
    _greedy_input_order,
    _validate_truth_table,
    decision_tree_body,
    move_text,
    permute_truth_table,
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


def _digit_cost(code: str) -> float:
    """Return ``log10`` of the integer ``code`` encodes to.

    The decimal length is this floored plus one, so comparing candidates
    needs no multiplication.  Two candidates within a digit of each other can
    rank by floating-point error; the loser is then one digit worse.
    """
    return math.fsum(length * math.log10(prime) for length, prime in _spans(code))


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


def _program(truth_table: str, perm: tuple[int, ...]) -> str:
    """Build the Brainfuck program Factor encodes, for one input order.

    Input ``k`` is read into cell ``2k`` with its flag at ``2k + 1`` and the
    answer at ``2n``, the layout the shared tree body expects.  Above the
    tree, one multiply loop puts 48 in the scratch cell at ``2n + 1`` and in
    the answer cell, and one loop takes 48 off every input; the answer cell
    therefore already holds ``'0'`` when the tree runs, so a ``'1'`` leaf's
    single ``+`` finishes it and the print below the tree is bare.
    """
    n = _validate_truth_table(truth_table)
    scratch, multiplier = 2 * n + 1, 2 * n + 2
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
    body, pos = decision_tree_body(truth_table, ">", "<", perm, after_reads)
    return build + reads + dedent + body + move_text(pos, 2 * n, ">", "<") + "."


def factor(truth_table: str) -> str:
    """Build a Factor program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Total, with no digit ceiling (the old
    4300/16000/500000 budgets were size policy): CPython's
    ``sys.get_int_max_str_digits()`` is raised to a bit-length estimate
    (``log10(2) < 0.30103``, never under-counting) and put back.
    """
    n = _validate_truth_table(truth_table)
    identity = tuple(range(n))
    candidates = [_program(truth_table, identity)]
    if n <= _GREEDY_ORDER_MAX_ARITY:
        greedy = _greedy_input_order(truth_table, n)
        if greedy != identity:
            candidates.append(
                _program(permute_truth_table(truth_table, greedy), greedy)
            )

    number = _encode(min(candidates, key=_digit_cost))
    digits = int(number.bit_length() * 0.30103) + 1
    limit = sys.get_int_max_str_digits()
    if limit == 0 or digits <= limit:  # 0 is CPython's "unlimited"
        return str(number)
    sys.set_int_max_str_digits(digits + 1)
    try:
        return str(number)
    finally:
        sys.set_int_max_str_digits(limit)
