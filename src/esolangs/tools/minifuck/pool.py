"""The Minifuck embed and the pool (cells 0..7) the endgame prints through."""

from esolangs.tools.minifuck.sim import _Joint, _walk_to

# First embedded bit; the pool is cells 0..7, plus room for the walk-in.
_BASE = 16

# Between embedded bits (a plain ``[x`` run correlates the prefix-XORs).
_SEP = "[x<[x"


# ASCII '0' (0b00110000) or '1' (0b00110001): cells 0..6 fixed, cell 7 answer.
_POOL = (0, 0, 1, 1, 0, 0, 0)

# ``.`` reads cells 0..7 as one byte.
_POOL_WIDTH = len(_POOL) + 1

# ``[<`` lands at ``(acc-1) + v``, ``[x<[<`` at ``(acc-1) + NOT v``; the
# digit is ``NOT(v XOR cell7)``, so read polarity is what makes a table
# and its complement both printable.
_READS = ("[<", "[x<[<")


def _embed(n: int) -> _Joint:
    """Emit the embed: each input's run once, separated by :data:`_SEP`."""
    j = _Joint(n)
    _walk_to(j, _BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        j.emit("[x")
        if i + 1 < n:
            j.emit(_SEP)
    return j


# The verdict is invariant in the walk out (9..39), so the key omits it.
_PROBE_WALK_OUT = _POOL_WIDTH + 1

#: Cells 0 to ``_POOL_WIDTH - 1``: the window a pool verdict depends on.
_POOL_MASK = (1 << _POOL_WIDTH) - 1
