"""Subleq packed-table decoder with O(T) rendered size.

Chunks contain n bits apiece: O(T/n) decimal values of O(n) digits. The
O(n) read instructions use O(log T) address digits, hence O(n**2) source,
which is O(T). Selection scans chunks; division extracts the requested bit.
"""

from esolangs.tools.sbleq import _sbleq_packed


def subleq(truth_table: str) -> str:
    """Build the shared packed decoder with direct jumps and byte I/O."""
    return _sbleq_packed(truth_table, direct=True)
