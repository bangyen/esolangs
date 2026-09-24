"""Boolean-function generators for tape-based languages."""

# Every language whose construction reads on its own owns a file; what is
# left here is brainfuck and Factor, which is brainfuck's program under an
# integer encoding rather than a construction of its own.  The rest are
# re-exported so this module stays the import site the package and tests
# already use.
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
    decision_tree_program,
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


def bf_tree(truth_table: str) -> str:
    """Build a decision-tree brainfuck program for the given truth table.

    :func:`decision_tree_program`, whose only caller this now is: O(2**n)
    characters against the minterm evaluator's O(n * 2**n); XOR-n measures
    0.2K..4.9K at n = 2..8 against the minterm's 1.4K..33M.
    """
    return decision_tree_program(truth_table, ">", "<")
