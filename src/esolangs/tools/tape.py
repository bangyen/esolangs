"""Boolean-function generators for tape-based languages."""

import sys

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
from esolangs.tools.circlefuck import (
    circlefuck_byte as circlefuck_byte,
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
from esolangs.tools.jaune import jaune_multiply as jaune_multiply
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
    "circlefuck_byte",
    "dimensional",
    "dimensional_tree",
    "factor",
    "jaune",
    "jaune_multiply",
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
    inputs (most significant first); the table length implies ``n``.

    This is :func:`bf_tree`, a decision tree sharing the bit tests.

    There used to be a second construction here -- a branch-free sum of
    minterms -- and ``bf`` returned whichever came out shorter, since the
    tree was full and so paid for every input on sparse tables where the
    minterm paid only per one-row.  Once the tree started folding constant
    subtrees it won on every table at n <= 4 but the two constant ones,
    where it now costs about 1.1x the minterm (271 characters at n == 4
    against the 253 the minterm measured before it was removed) -- a margin
    that no longer pays for a second construction and a dispatch to choose
    between them, and which used to be 2.5x.  A constant table is a single
    leaf, so what is left is almost entirely the reads: it gained nothing
    from the print-once leaf and everything from dropping the per-input
    complement construction.
    """
    return bf_tree(truth_table)


_BF_RESIDUE = {">": 1, "<": 2, "+": 3, "-": 4, ".": 5, ",": 6, "[": 7, "]": 8}


def _factor_encode(code: str) -> int:
    """Encode a brainfuck program as the Factor integer for it.

    The decoder sorts the prime factors ascending, so the encoder walks
    primes upward and hands each instruction the next prime with the right
    residue modulo 11 (Dirichlet's theorem guarantees one always exists).  A
    run of identical instructions is folded into one prime's exponent, which
    keeps the integer small while decoding to the same run.

    The prime powers are multiplied as a balanced tree rather than folded
    into one growing accumulator: the accumulator is priced by its own
    width at every step, which was 12.5s of a 14.4s build at thirteen
    inputs (120860 runs) against 0.7s for the tree.
    """
    from sympy import isprime

    powers: list[int] = []
    candidate = 2
    i = 0
    while i < len(code):
        residue = _BF_RESIDUE[code[i]]
        j = i
        while j < len(code) and code[j] == code[i]:
            j += 1
        prime = candidate
        while not (prime % 11 == residue and isprime(prime)):
            prime += 1
        powers.append(prime ** (j - i))
        candidate = prime + 1
        i = j
    while len(powers) > 1:
        pairs = [a * b for a, b in zip(powers[::2], powers[1::2], strict=False)]
        powers = pairs + powers[-1:] if len(powers) % 2 else pairs
    return powers[0] if powers else 1


def factor(truth_table: str) -> str:
    """Build a Factor program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    A Factor program is a single integer whose prime factorization decodes
    to brainfuck, so the generator reuses :func:`brainfuck`'s truth-table
    program unchanged and encodes it with :func:`_factor_encode`.  Total:
    the tree is finite, every run gets a prime, and the integer is
    arbitrary-precision on both sides -- this renders it and
    :func:`esolangs.interpreters.tape_based.factor._parse` reads it back,
    neither with a ceiling of its own.  It used to refuse past a digit
    budget (4300, then 16000, then 500000), each a size policy pinned to the
    arity the suite swept at the time rather than anything Factor says;
    n=13 parity is 966568 digits, built in 3s and decoded by the interpreter
    to the same brainfuck.

    The one limit in the way is CPython's ``sys.get_int_max_str_digits()``,
    a DoS guard against quadratic conversions.  It is process-global, so it
    is raised to what this render needs and put back.  The need is estimated
    from the bit length (``log10(2) < 0.30103``, so it never under-counts)
    rather than paid for with the conversion it is sizing.
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
    inputs (most significant first); the table length implies ``n``.

    3D Brainfuck's ``>``/``<`` set the generation pointer's heading (a no-op
    in this interpreter), so the array is walked along one axis with
    ``e``/``w`` instead; :func:`brainfuck`'s decision tree otherwise
    translates directly, so this folds constant subtrees because that does.
    """
    return brainfuck(truth_table).translate(str.maketrans("><", "ew"))


# The interpreter's two substitution cycles, in the order the cross-check
# scans them: Painfuck source is pre-shifted here so the trans table recovers
# the intended commands.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def painfuck(truth_table: str) -> str:
    """Build a Painfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Painfuck is brainfuck-compatible: the commands ``a``/``b`` are while-
    nonzero loops, ``j`` reads a byte and ``u`` prints one.
    :func:`brainfuck`'s decision tree translates directly (so this folds
    constant subtrees because that does), mapping BF's
    ``>``/``<`` (each one cell) to ``rl`` (+1) / ``l`` (-1), ``+``/``-`` to
    ``ps`` (+1) / ``s`` (-1), and ``[``/``]``/``,``/``.`` to ``a``/``b``/
    ``j``/``u``.  The interpreter then rewrites the source through two
    substitution cycles, so each emitted command is pre-shifted ``k`` steps
    back along its cycle (where ``k`` counts the commands so far) to undo it.
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

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The construction is :func:`decision_tree_program`, shared with
    :func:`dimensional_tree`.  The tree is O(2**n) characters (sharing the
    bit tests), versus the branch-free minterm evaluator's O(n * 2**n); for
    XOR-n it measures 0.2K..4.9K characters at n = 2..8, against the
    1.4K..33M the minterm measured before it was removed.
    """
    return decision_tree_program(truth_table, ">", "<")
