"""Boolean-function generators for tape-based languages."""

# Every language whose construction reads on its own owns a file; what is
# left here is brainfuck and Factor, which is brainfuck's program under an
# integer encoding rather than a construction of its own.  The rest are
# re-exported so this module stays the import site the package and tests
# already use.
from esolangs.tools.brainif import brainif as brainif

# Re-exported in the ``x as x`` form: the registry, the wrapper and the
# suite all reach a construction by this module's name.
from esolangs.tools.circlefuck import (
    circlefuck as circlefuck,
)
from esolangs.tools.dimensional import dimensional
from esolangs.tools.factor import (
    _BF_RESIDUE as _BF_RESIDUE,
)
from esolangs.tools.factor import factor as factor
from esolangs.tools.helpers import (
    _ASCII_ONE as _ASCII_ONE,
)
from esolangs.tools.helpers import (
    _ASCII_ZERO as _ASCII_ZERO,
)
from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    decision_tree_body,
    move_text,
)
from esolangs.tools.jaune import (
    _jaune_ordered as _jaune_ordered,
)
from esolangs.tools.jaune import jaune as jaune
from esolangs.tools.painfuck import painfuck as painfuck
from esolangs.tools.rotfuck import rotfuck
from esolangs.tools.sbleq import (
    _sbleq_hoisted as _sbleq_hoisted,
)
from esolangs.tools.sbleq import sbleq as sbleq
from esolangs.tools.six_five import six_five
from esolangs.tools.slow_acv_mammalian import slow_acv_mammalian
from esolangs.tools.suffolk import suffolk as suffolk
from esolangs.tools.three_d_brainfuck import (
    three_d_brainfuck as three_d_brainfuck,
)

__all__ = [
    "bf_tree",
    "brainfuck",
    "brainif",
    "circlefuck",
    "dimensional",
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


#: Brainfuck's move tokens.  This builder used to take them as parameters so
#: Dimensional could pass ``>0``/``<0``; Dimensional builds its own reads and
#: print around :func:`decision_tree_body` now, and every call here passes
#: these, so they are named rather than threaded.
_RIGHT, _LEFT = ">", "<"


def bf_tree(truth_table: str) -> str:
    """Build a decision-tree brainfuck program for the given truth table.

    Each input is normalized into cell
    ``2i`` with its flag at ``2i + 1``: a node sets the flag, tests ``[b]``
    and clears the flag inside, then tests ``[flag]`` for the zero side,
    so exactly one side fires and both cells are left zero.  O(2**n).
    The flag replaced a precomputed ``1 - b`` per input (O(n**2): n == 10
    sparse went 2,646 -> 754 chars).  A leaf only records its bit (``+`` or
    nothing) and one ``.`` sits below the tree; with the fold, n == 10 xor
    went 77,939 -> 18,495.  A constant subtree collapses to a leaf; the
    reads are unconditional above the tree, so a folded program consumes
    its input the same way.  Factor most wants this: it refuses tables
    whose integer encoding exceeds Python's digit limit.
    """
    return best_input_order(truth_table, _bf_ordered)


def _bf_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's program; see :func:`bf_tree`.

    ``truth_table`` is already permuted; ``perm`` is spent only in the cell
    a node tests, ``2 * perm[i]``.  The reads above the tree are untouched.
    """
    n = _validate_truth_table(truth_table)

    cells: list[str] = []
    pos = 0

    def move(target: int) -> None:
        nonlocal pos
        delta = target - pos
        cells.append(_RIGHT * delta if delta >= 0 else _LEFT * -delta)
        pos = target

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero
    for i in range(n):
        cells.append(",")
        # ``append`` of the run, not ``extend`` over its characters: the run
        # is 48 long and the join sees the same text either way.
        cells.append("-" * _ASCII_ZERO)
        if i < n - 1:
            move(pos + 2)

    # The tree itself, which Factor also builds around its own prologue.
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, pos)
    cells.append(body)

    # One print, below the tree.  Exactly one leaf fires, leaving 0 or 1 in
    # the result cell, so the ASCII offset is paid once here instead of at
    # every leaf -- which is what the whole tree used to spend most of its
    # characters on.
    cells.append(move_text(pos, 2 * n, _RIGHT, _LEFT))
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    return "".join(cells)
