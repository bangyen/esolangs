"""Subleq Boolean program generator: a shared residual DAG or a packed-table decoder.

Hoisted reads normalize bytes before direct branches. Equal residuals share
one entry; constant subtrees and ignored tests disappear. O(T/n) distinct
residuals have O(n)-digit addresses. Packed chunks remain the source-size floor.
Unused byte-I/O branch operands are zero; literal-bearing constant cells stay.

Size:
    O(T) text either way, the shorter of the two; n=10 random 1847: 1,981
    chars, n=10 parity: 537 chars. Constants use 7n+7 chars and n+1 commands;
    written bits are loaded-image bits + 4 + bl(3n+3) + bl(n).
"""

from esolangs.generation.branch_decoder import hoisted_tree
from esolangs.generation.helpers import _validate_truth_table, in_input_order
from esolangs.generation.packed_decoder import packed_decoder
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


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


def subleq_request(request: GenerationRequest) -> Program:
    """Emit source through the declared generation request interface."""
    return subleq(request.table)
