"""Subleq packed-table decoder with O(T) rendered size.

Chunks contain n bits apiece: O(T/n) decimal values of O(n) digits. The
O(n) read instructions use O(log T) address digits, hence O(n**2) source,
which is O(T). Selection scans chunks; division extracts the requested bit.
Repeated chunks share one payload through an address array when it is shorter.
"""

from typing import Any

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language, Payload, Shape
from esolangs.tools.sbleq import _packed_build, _sbleq_packed
from esolangs.tools.wrap import balance_program, balance_score, wrap_grid


def subleq(truth_table: str) -> str:
    """Build a packed decoder or a read-and-print constant with direct byte I/O."""
    return _sbleq_packed(truth_table, direct=True)


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
    # Not a tree: an indexed table read.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    balance=_balance,
)
