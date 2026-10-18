"""Snapshot-bit bounds."""

from esolangs.languages.sstack.interpreter import _parse


def workspace(n: int, p: str) -> int:
    """Every path stacks all n input bytes (6 bits) beside '1' and '0'."""
    bl = int.bit_length
    return 6 * n + 12 + bl(len(_parse(p))) + bl(n)
