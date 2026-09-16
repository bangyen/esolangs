"""Boolean-function generators for tape-based languages."""

import sys

from esolangs.exceptions import GeneratorCapError

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


#: Digits :func:`factor` renders without being asked twice.  Sized from the
#: measured worst case at ten inputs, which the tree's two size changes --
#: printing once below itself, and dropping the complement construction --
#: cut by 4.3x together: n=10 parity encodes to 104659 digits (was 454832),
#: n=10 dense to 77278 (was 328772).  So this clears the whole reach of the
#: construction with room and still names a ceiling rather than removing one.
#: Past it the caller passes ``max_digits`` and says how big is fine.
#:
#: The budget is deliberately left at 500000 rather than tightened to the new
#: worst case: n=11 parity now encodes to 219455 digits where it used to need
#: 952366 and was refused outright, so the headroom this constant already had
#: is what an arity lift would spend.  Whether n=11 is *supported* is a
#: question for the contract sweep, not for this constant.
#:
#: Sized to the construction's reach rather than to whatever arity the
#: boolean suite currently sweeps, deliberately: the old 16000 was pinned to
#: a five-input suite and became the *only* thing stopping this generator at
#: n=6, so the budget had to be re-argued the moment the sweep moved.  This
#: one does not.  Raising it costs 2.8s and 78MB at the ten-input worst
#: case, and an n=6 program built past the old ceiling executes correctly on
#: all 64 rows.
_DEFAULT_MAX_DIGITS = 500_000


_BF_RESIDUE = {">": 1, "<": 2, "+": 3, "-": 4, ".": 5, ",": 6, "[": 7, "]": 8}


def _factor_encode(code: str) -> int:
    """Encode a brainfuck program as the Factor integer for it.

    The decoder sorts the prime factors ascending, so the encoder walks
    primes upward and hands each instruction the next prime with the right
    residue modulo 11 (Dirichlet's theorem guarantees one always exists).  A
    run of identical instructions is folded into one prime's exponent, which
    keeps the integer small while decoding to the same run.
    """
    from sympy import isprime

    number = 1
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
        number *= prime ** (j - i)
        candidate = prime + 1
        i = j
    return number


def factor(truth_table: str, *, max_digits: int = _DEFAULT_MAX_DIGITS) -> str:
    """Build a Factor program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    A Factor program is a single integer whose prime factorization decodes
    to brainfuck, so the generator reuses :func:`brainfuck`'s truth-table
    program unchanged and encodes it with :func:`_factor_encode` (walk primes
    upward, handing each instruction the next one with the right residue
    mod 11; Dirichlet's theorem guarantees one always exists).

    Folding the constant subtrees of that program is what turns some
    otherwise unrenderable tables into runnable ones, since the cap below is
    on the encoded integer's size.

    ``max_digits`` bounds how long the rendered integer may be, defaulting
    to :data:`_DEFAULT_MAX_DIGITS`.  This is a program-size cap, not an
    ``n`` cap: sparse tables (e.g. an all-zero or all-one table) stay small
    at any ``n``, while dense tables grow the underlying brainfuck program
    (and so the encoded integer) quickly.

    The bound used to be CPython's own ``sys.get_int_max_str_digits()``,
    which is a DoS guard against quadratic conversions rather than anything
    Factor says -- and at its 4300-digit default it stopped this generator
    at n=3, since n=4 parity needs 6390 digits.  A Factor program *is* one
    integer, so that guard is not a property of the language to be reported
    but a limit to be lifted: the render raises it to fit and puts it back,
    and :func:`esolangs.interpreters.tape_based.factor._parse` does the same
    on the way in, so what is generated here is what the interpreter runs.

    The check estimates the digit count from the integer's bit length
    (``log10(2) ~= 0.30103``) to avoid paying for the same oversized
    conversion just to reject it.
    """
    number = _factor_encode(brainfuck(truth_table))
    # Estimated from the bit length (``log10(2) ~= 0.30103``) and rounded
    # up, so it never *under*-counts: the point is to reject an oversized
    # integer without paying for the conversion that would size it exactly.
    digits = int(number.bit_length() * 0.30103) + 1
    if digits > max_digits:
        raise GeneratorCapError(
            f"the Factor boolean generator's encoded integer needs about "
            f"{digits} digits, over the {max_digits}-digit limit this call "
            "allows -- try a sparser table, or fewer inputs",
        )
    limit = sys.get_int_max_str_digits()
    if digits <= limit:
        return str(number)
    # Process-global, so it is borrowed for the render and handed back.
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
