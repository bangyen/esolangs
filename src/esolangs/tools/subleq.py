"""Subleq shared residual DAG or packed-table decoder, both O(T) text.

Hoisted reads normalize bytes before direct branches. Equal residuals share
one entry; constant subtrees and ignored tests disappear. O(T/n) distinct
residuals have O(n)-digit addresses. Packed chunks remain the source-size floor.
"""

from typing import Any

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Payload, Shape
from esolangs.tools.helpers import _validate_truth_table, in_input_order
from esolangs.tools.sbleq import _packed_build, _sbleq_hoisted, _sbleq_packed
from esolangs.tools.wrap import balance_program, balance_score, wrap_grid


def subleq(truth_table: str) -> str:
    """Compare shared trees with packed decoders; constants read and print."""
    _validate_truth_table(truth_table)
    packed = _sbleq_packed(truth_table, direct=True)
    if len(set(truth_table)) == 1:
        return packed
    return min(packed, in_input_order(truth_table, _subleq_shared), key=len)


def _subleq_shared(table: str, perm: tuple[int, ...]) -> str:
    """Fold constants and equal halves; emit each residual once."""
    return _sbleq_hoisted(table, perm, share=True, direct=True)


def _payload(state: Any) -> Payload:
    """Split out memory, mutable code included, and pc; no control stack."""
    data, pc, _cursor = state
    return data, (), pc, 0


def _balance(table: str, default: str) -> str:
    """Retain the literal decoder when its grid is more balanced."""
    candidate = balance_program(default, "subleq")
    legacy = _packed_build(table, direct=True, keep_constant_layout=True)
    return min(candidate, balance_program(legacy, "subleq"), key=balance_score)


LANGUAGE = Language(
    "Subleq",
    "tape_based.subleq",
    payload=_payload,
    boolean=subleq,
    # Shared tree or packed lookup.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    balance=_balance,
)
