"""Subleq packed-table decoder with O(T) rendered size.

Chunks contain n bits apiece: O(T/n) decimal values of O(n) digits. The
O(n) read instructions use O(log T) address digits, hence O(n**2) source,
which is O(T). Selection scans chunks; division extracts the requested bit.
Packed chunks have no subtrees to fold or share.
"""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.sbleq import _sbleq_packed
from esolangs.tools.wrap import wrap_grid


def subleq(truth_table: str) -> str:
    """Build the shared packed decoder with direct jumps and byte I/O."""
    return _sbleq_packed(truth_table, direct=True)


LANGUAGE = Language(
    "Subleq",
    "tape_based.subleq",
    boolean=subleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
)
