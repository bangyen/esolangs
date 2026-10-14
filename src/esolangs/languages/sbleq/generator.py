"""Boolean-function generator for s*bleq."""

from esolangs.generation.branch_decoder import hoisted_tree as _sbleq_hoisted
from esolangs.generation.helpers import (
    _validate_truth_table,
    in_input_order,
)
from esolangs.generation.packed_decoder import (
    _packed_build,
    _sbleq_constant,
    packed_decoder,
)
from esolangs.generation.wrap import balance_program, balance_score, wrap_grid
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Tables up to this many rows keep the shared tree; larger ones also try
#: the packed decoder.
_TREE_ROWS = 16


def sbleq(truth_table: str) -> str:
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
    """Retain the old constant tree/decoder when its grid is more balanced."""
    candidate = balance_program(default, "sbleq")
    constant = len(set(table)) == 1
    large = len(table) > _TREE_ROWS
    if not constant and not large:
        return candidate
    n = len(table).bit_length() - 1
    legacy = [
        _sbleq_hoisted(table, tuple(range(n)))
        if constant
        else in_input_order(table, _sbleq_hoisted)
    ]
    if large:
        legacy.append(_packed_build(table, keep_constant_layout=constant))
    old = balance_program(min(legacy, key=len), "sbleq")
    return min(candidate, old, key=balance_score)


LANGUAGE = Language(
    "S*bleq",
    "sbleq",
    category="tape_based",
    boolean=sbleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    balance=_balance,
    eof="a failed read leaves the cell alone and the program runs on",
)
