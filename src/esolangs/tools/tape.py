"""Boolean-function generators for tape-based languages."""

import heapq
import sys

from esolangs.factor_primes import prime_segments

# Every language whose construction reads on its own owns a file; what is
# left here is brainfuck and the four dialects built directly on it.  The
# rest are re-exported so this module stays the import site the package and
# tests already use.
from esolangs.tools.brainif import brainif as brainif

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
from esolangs.tools.circlefuck import (
    _circlefuck_ordered as _circlefuck_ordered,
)
from esolangs.tools.circlefuck import (
    circlefuck as circlefuck,
)
from esolangs.tools.dimensional import dimensional, dimensional_tree
from esolangs.tools.helpers import (
    _ASCII_ONE as _ASCII_ONE,
)
from esolangs.tools.helpers import (
    _ASCII_ZERO as _ASCII_ZERO,
)
from esolangs.tools.helpers import (
    decision_tree_program,
)
from esolangs.tools.jaune import (
    _jaune_ordered as _jaune_ordered,
)
from esolangs.tools.jaune import jaune as jaune
from esolangs.tools.rotfuck import rotfuck
from esolangs.tools.sbleq import (
    _sbleq_hoisted as _sbleq_hoisted,
)
from esolangs.tools.sbleq import sbleq as sbleq
from esolangs.tools.six_five import six_five
from esolangs.tools.slow_acv_mammalian import slow_acv_mammalian
from esolangs.tools.suffolk import suffolk as suffolk

__all__ = [
    "bf_tree",
    "brainfuck",
    "brainif",
    "circlefuck",
    "dimensional",
    "dimensional_tree",
    "factor",
    "jaune",
    "painfuck",
    "rotfuck",
    "sbleq",
    "six_five",
    "slow_acv_mammalian",
    "suffolk",
    "three_d_brainfuck",
]


def brainfuck(truth_table: str) -> str:
    """Build a brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  This is :func:`bf_tree`.  A
    branch-free minterm sum used to compete; once the tree folded constant
    subtrees it won on every table at n <= 4 but the two constant ones,
    where it costs 277 characters at n == 4 against the minterm's 253
    (1.1x, down from 2.5x), not worth a second construction.
    """
    return bf_tree(truth_table)


_BF_RESIDUE = {">": 1, "<": 2, "+": 3, "-": 4, ".": 5, ",": 6, "[": 7, "]": 8}

# Exact prime enumeration, in bounded segments. ``isprime`` becomes a BPSW
# probable-prime test above 2**64; Factor is uncapped, so it cannot certify the
# primes in a total encoding. The chunk is only a segment width, never a cap.
_FACTOR_PRIME_CHUNK = 20000


def _factor_encode(code: str) -> int:
    """Encode a brainfuck program as the Factor integer for it.

    Exact sieved primes ascend with the right residue mod 11 (Dirichlet), a
    run folds into one exponent. Prime powers multiply smallest-width first:
    a growing accumulator was 12.5s of a 14.4s build at thirteen inputs
    (120860 runs) against 0.7s, and width balance gives the arithmetic bound.
    """
    powers: list[int] = []
    primes = (
        prime
        for _start, _stop, segment in prime_segments(_FACTOR_PRIME_CHUNK)
        for prime in segment
    )
    i = 0
    while i < len(code):
        residue = _BF_RESIDUE[code[i]]
        j = i
        while j < len(code) and code[j] == code[i]:
            j += 1
        prime = next(prime for prime in primes if prime % 11 == residue)
        powers.append(prime ** (j - i))
        i = j
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


def factor(truth_table: str) -> str:
    """Build a Factor program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Encodes :func:`brainfuck`'s program
    with :func:`_factor_encode`; total, with no digit ceiling (the old
    4300/16000/500000 budgets were size policy): n=13 parity is 966568
    digits, built in 3s.  CPython's ``sys.get_int_max_str_digits()`` is
    raised to a bit-length estimate (``log10(2) < 0.30103``, never
    under-counting) and put back.
    """
    number = _factor_encode(brainfuck(truth_table))
    digits = int(number.bit_length() * 0.30103) + 1
    limit = sys.get_int_max_str_digits()
    if limit == 0 or digits <= limit:  # 0 is CPython's "unlimited"
        return str(number)
    sys.set_int_max_str_digits(digits + 1)
    try:
        return str(number)
    finally:
        sys.set_int_max_str_digits(limit)


def three_d_brainfuck(truth_table: str) -> str:
    """Build a 3D Brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  :func:`brainfuck`'s tree with
    ``e``/``w`` for the moves, since ``>``/``<`` are no-ops.
    """
    return brainfuck(truth_table).translate(str.maketrans("><", "ew"))


# The interpreter's two substitution cycles, in the order the cross-check
# scans them: Painfuck source is pre-shifted here so the trans table recovers
# the intended commands.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def painfuck(truth_table: str) -> str:
    """Build a Painfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  :func:`brainfuck`'s tree with
    ``>``/``<`` as ``rl``/``l``, ``+``/``-`` as ``ps``/``s`` and
    ``[``/``]``/``,``/``.`` as ``a``/``b``/``j``/``u``, each command
    pre-shifted ``k`` steps back along its cycle to undo the interpreter's
    substitution.
    """
    code = (
        brainfuck(truth_table)
        .replace(">", "rl")
        .replace("<", "l")
        .replace("+", "ps")
        .replace("-", "s")
        .replace("[", "a")
        .replace("]", "b")
        .replace(",", "j")
        .replace(".", "u")
    )
    out: list[str] = []
    k = 0
    for char in code:
        for cycle in _CYCLES:
            p = cycle.find(char)
            if p != -1:
                out.append(cycle[(p - k) % len(cycle)])
                k += 1
                break
        else:
            # every command the brainfuck generator emits maps to a command
            # in _CYCLES, so this branch is unreachable by construction
            raise ValueError(
                f"Painfuck command {char!r} is not in a cycle"
            )  # pragma: no cover
    return "".join(out)


def bf_tree(truth_table: str) -> str:
    """Build a decision-tree brainfuck program for the given truth table.

    :func:`decision_tree_program`, shared with :func:`dimensional_tree`:
    O(2**n) characters against the minterm evaluator's O(n * 2**n); XOR-n
    measures 0.2K..4.9K at n = 2..8 against the minterm's 1.4K..33M.
    """
    return decision_tree_program(truth_table, ">", "<")
