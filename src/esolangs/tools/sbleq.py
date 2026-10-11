"""Boolean-function generator for s*bleq."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.branch_decoder import hoisted_tree as _sbleq_hoisted
from esolangs.tools.helpers import (
    _validate_truth_table,
    in_input_order,
)
from esolangs.tools.packed_decoder import _packed_build, _sbleq_constant, packed_decoder
from esolangs.tools.wrap import balance_program, balance_score, wrap_grid


def sbleq(truth_table: str) -> str:
    """Read once, then choose a shared tree or packed decoder.

    Each branch destroys its input once; value cells never alias indirect
    targets. Constants consume all inputs before printing.
    """
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _sbleq_constant(n, truth_table[0])
    tree = in_input_order(truth_table, _sbleq_shared)
    if len(truth_table) <= 16:
        return tree
    packed = packed_decoder(truth_table)
    return tree if len(tree) < len(packed) else packed


def _sbleq_shared(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one order's shared tree; see :func:`_sbleq_hoisted`."""
    return _sbleq_hoisted(truth_table, perm, share=True)


def _balance(table: str, default: str) -> str:
    """Retain the old constant tree/decoder when its grid is more balanced."""
    candidate = balance_program(default, "sbleq")
    if len(set(table)) == 1:
        n = len(table).bit_length() - 1
        legacy = _sbleq_hoisted(table, tuple(range(n)), share=True)
        if len(table) > 16:
            legacy = min(
                legacy, _packed_build(table, keep_constant_layout=True), key=len
            )
        return min(candidate, balance_program(legacy, "sbleq"), key=balance_score)
    if len(table) > 16:
        legacy = min(
            in_input_order(table, _sbleq_shared), _packed_build(table), key=len
        )
        return min(candidate, balance_program(legacy, "sbleq"), key=balance_score)
    return candidate


LANGUAGE = Language(
    "S*bleq",
    "tape_based.sbleq",
    boolean=sbleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    balance=_balance,
    eof="a failed read leaves the cell alone and the program runs on",
)
