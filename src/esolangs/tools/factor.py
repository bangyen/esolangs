"""Boolean-function generator for Factor.

Ascending primes encode Brainfuck instructions by residue modulo eleven
and run length by exponent. A compact tree tests inputs in stream order
and puts the answer in the final input's unused flag. Multiplication loops
build and subtract the ASCII offsets; only this tree is encoded.  Equal
sibling halves merge; repeated residuals emit in depth order after the prefix,
using one unused flag per level when the encoded integer is shorter and
the unchanged command bound admits it.
Same-level banks use unused descendant flags, and the mixed-depth bank unions
those with the one-per-depth picks so a block at any depth can defer; each
admitted bank is encoded separately so decimal size, rather than decoded text
length, selects it.
An ignored cell is read but not dedented.
"""

import heapq
from collections.abc import Iterator
from itertools import groupby

from esolangs._digits import digit_limit_for
from esolangs.factor_primes import prime_segments
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.constant_projection import balanced_projection
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    decision_tree_body,
    input_weights,
    move_text,
)
from esolangs.tools.shared_flag import shared_flag_tree
from esolangs.tools.wrap import balance_program, wrap_chars

__all__ = ["factor"]

#: A prime's residue mod ``_MODULUS`` selects the instruction it stands for.
_MODULUS = 11
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
    return [
        (len(list(run)), next(p for p in primes if p % _MODULUS == _BF_RESIDUE[char]))
        for char, run in groupby(code)
    ]


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
        product = heapq.heappop(heap)[2] * heapq.heappop(heap)[2]
        heapq.heappush(heap, (product.bit_length(), serial, product))
        serial += 1
    return heap[0][2] if heap else 1


def _program(
    truth_table: str,
    *,
    shared: bool = False,
    keep_constant_input: bool = False,
    multiple: bool = True,
    bank: bool = True,
    bank_only: bool = False,
    bank_ranked: bool = True,
) -> str:
    """Build the compact tree in input order, using the final input's flag.

    The tree tests the essential inputs only, so its last level is the last
    one the table reads and keeps its binary leaves; an ignored input is
    read and its cell left set.  The final-flag leaves are essential, not an
    optimisation: the last input's flag cell is the answer cell, so the plain
    flag test computes the wrong function.
    """
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)
    perm = tuple(i for i, weight in enumerate(weights) if weight)
    normalized = bool(perm) or keep_constant_input
    if len(table) == 1:
        # Keep the tree arity, but a constant never needs ASCII normalization.
        table, perm = truth_table, tuple(range(n))
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
        + "-" * (0 in perm)
        + "".join(">>" + "-" * (k in perm) for k in range(1, n))
        + ">" * back
        + "]"
        + "<" * back
    )
    body, pos = decision_tree_body(
        table,
        ">",
        "<",
        perm,
        after_reads,
        binary_leaves=True,
        result=result,
    )
    if truth_table == "10":
        # NOT at one input exceeded its 496-command bound by two moves.
        # Set the answer's extra one while already passing its cell.
        build = ">+" + build[1:]
        body, pos = "[->-<]", 0
    prefix = build + reads + (dedent if normalized else "")
    plain = prefix + body + move_text(pos, result, ">", "<") + "."
    if not shared:
        return plain
    # Six offset-building trips and 48 dedent trips, with no opener retest.
    prelude = 199 * n + 48 * len(perm) + 240
    candidate = shared_flag_tree(
        table,
        perm,
        after_reads,
        result,
        binary_leaves=True,
        command_budget=265 * n + 230 - prelude,
        multiple=multiple,
        bank=bank,
        bank_only=bank_only,
        bank_ranked=bank_ranked,
    )
    if candidate is None:
        return plain
    body, commands = candidate
    program = prefix + body + "."
    return (
        program
        if prelude + commands + 1 <= 265 * n + 231 and len(program) <= len(plain)
        else plain
    )


def factor(truth_table: str) -> str:
    """Build a Factor program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Total, with no digit ceiling: CPython's
    digit cap is raised to a bit-length estimate (``log10(2) < 0.30103``,
    never under-counting) and put back.
    """
    return _factor(truth_table)


def _factor(truth_table: str, *, keep_constant_input: bool = False) -> str:
    """Encode the tree, optionally retaining constant-input normalization."""
    plain = _program(truth_table, keep_constant_input=keep_constant_input)
    candidate = _program(
        truth_table,
        shared=True,
        bank_only=True,
        keep_constant_input=keep_constant_input,
    )
    layered = _program(
        truth_table, shared=True, bank=False, keep_constant_input=keep_constant_input
    )
    first = _program(
        truth_table,
        shared=True,
        bank_only=True,
        bank_ranked=False,
        keep_constant_input=keep_constant_input,
    )
    single = _program(
        truth_table,
        shared=True,
        multiple=False,
        keep_constant_input=keep_constant_input,
    )

    def encoded(code: str) -> str:
        number = _encode(code)
        with digit_limit_for(int(number.bit_length() * 0.30103) + 1):
            return str(number)

    return min(
        (
            encoded(code)
            for code in dict.fromkeys((plain, single, layered, first, candidate))
        ),
        key=len,
    )


def balance_factor(truth_table: str, default: str) -> str:
    """Keep the legacy constant encoding when its wrapped shape is better."""
    if len(set(truth_table)) > 1:
        return balance_program(default, "factor")
    return balanced_projection(
        default, _factor(truth_table, keep_constant_input=True), "factor"
    )


LANGUAGE = Language(
    "Factor",
    "tape_based.factor",
    # A one-character mutation can turn the deliberately factorable example
    # into a huge semiprime, unbounded work before the first VM step.
    # Twelve digits still exercise the same parser and factorization paths
    # and are the measured safe bound.
    fuzz_max_digits=12,
    boolean=factor,
    documented_sizes=(11_232, 22_500, 2.0),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
    balance=balance_factor,
)
