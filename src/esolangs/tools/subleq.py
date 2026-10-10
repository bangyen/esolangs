"""Subleq packed-table decoder with O(T) rendered size.

Chunks contain n bits apiece: O(T/n) decimal values of O(n) digits. The
O(n) read instructions use O(log T) address digits, hence O(n**2) source,
which is O(T). Selection scans chunks; division extracts the requested bit.
Packed chunks have no subtrees to fold or share.
"""

from typing import Any

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Payload, Shape
from esolangs.tools.packed_decoder import packed_decoder
from esolangs.tools.wrap import wrap_grid


def subleq(truth_table: str) -> str:
    """Build the shared packed decoder with direct jumps and byte I/O."""
    return packed_decoder(truth_table, direct=True)


def _payload(state: Any) -> Payload:
    """Split out memory, mutable code included, and pc; no control stack."""
    data, pc, _cursor = state
    return data, (), pc, 0


LANGUAGE = Language(
    "Subleq",
    "tape_based.subleq",
    payload=_payload,
    boolean=subleq,
    # Not a tree: an indexed table read.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
)
