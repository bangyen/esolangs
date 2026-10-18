"""Subleq Boolean program generator: a shared residual DAG or a packed-table decoder.

Hoisted reads normalize bytes before direct branches. Equal residuals share
one entry; constant subtrees and ignored tests disappear. O(T/n) distinct
residuals have O(n)-digit addresses. Packed chunks remain the source-size floor.

Size:
    O(T) text either way, the shorter of the two; n=10 random 1847: 2,000
    chars, n=10 parity: 552 chars.
"""

from typing import Any

from esolangs.generation.branch_decoder import hoisted_tree
from esolangs.generation.helpers import _validate_truth_table, in_input_order
from esolangs.generation.packed_decoder import packed_decoder
from esolangs.generation.wrap import wrap_grid
from esolangs.languages.subleq.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Payload, Shape


def subleq(truth_table: str) -> str:
    """Compare shared trees with packed decoders; constants read and print."""
    _validate_truth_table(truth_table)
    packed = packed_decoder(truth_table, direct=True)
    if len(set(truth_table)) == 1:
        return packed
    return min(packed, in_input_order(truth_table, _subleq_shared), key=len)


def _subleq_shared(table: str, perm: tuple[int, ...]) -> str:
    """Fold constants and equal halves; emit each residual once."""
    return hoisted_tree(table, perm, direct=True)


def _payload(state: Any) -> Payload:
    """Split out memory, mutable code included, and pc; no control stack."""
    data, pc, _cursor = state
    return data, (), pc, 0


LANGUAGE = Language(
    "Subleq",
    "subleq",
    category="tape_based",
    payload=_payload,
    boolean=subleq,
    # Shared tree or packed lookup.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    proof_workspace=(workspace, False, (3, 5)),
)
