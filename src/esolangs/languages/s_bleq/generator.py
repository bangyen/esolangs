"""S*bleq Boolean program generator: a shared branch tree, or a packed decoder.

Reads every input once; tables up to 16 rows use the hoisted shared tree,
larger ones also build the packed decoder and keep the shorter.  A constant
consumes all inputs before printing.

Size:
    n=10 random 1847: 2,976 chars, n=10 parity: 487 chars,
    n=10 and: 383 chars.
"""

from esolangs.generation.branch_decoder import hoisted_tree as _sbleq_hoisted
from esolangs.generation.helpers import (
    _validate_truth_table,
    in_input_order,
)
from esolangs.generation.packed_decoder import (
    _sbleq_constant,
    packed_decoder,
)
from esolangs.generation.wrap import balance_program, balance_score, wrap_grid
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Tables up to this many rows keep the shared tree; larger ones also try
#: the packed decoder.
_TREE_ROWS = 16


def s_bleq(truth_table: str) -> str:
    """Read once, then choose a shared tree or packed decoder.

    Each branch destroys its input once; value cells never alias indirect
    targets. Constants consume all inputs before printing.
    """
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _sbleq_constant(n, truth_table[0])
    tree = in_input_order(truth_table, _sbleq_hoisted)
    if len(truth_table) <= _TREE_ROWS:
        return tree
    packed = packed_decoder(truth_table)
    return tree if len(tree) < len(packed) else packed


def _balance(table: str, default: str) -> str:
    """Race the input-order tree and packed decoder on large non-constant tables."""
    candidate = balance_program(default, "s_bleq")
    if len(set(table)) == 1 or len(table) <= _TREE_ROWS:
        return candidate
    legacy = [in_input_order(table, _sbleq_hoisted), packed_decoder(table)]
    old = balance_program(min(legacy, key=len), "s_bleq")
    return min(candidate, old, key=balance_score)


LANGUAGE = Language(
    "S*bleq",
    "s_bleq",
    category="tape_based",
    boolean=s_bleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    balance=_balance,
    eof="a failed read leaves the cell alone and the program runs on",
)
