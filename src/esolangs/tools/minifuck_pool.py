"""The Minifuck embed and the pool (cells 0..7) the endgame prints through."""

from esolangs.tools.minifuck_sim import _clamp, _Joint, _walk_to

# First embedded bit; the pool is cells 0..7, plus room for the walk-in.
_BASE = 16

# Between embedded bits (a plain ``[x`` run correlates the prefix-XORs).
_SEPS = ("[x<[x", "[x[x[x", "[<[<[", "[[[[[", "[x[<[")
_SEP = _SEPS[0]


# ASCII '0' (0b00110000) or '1' (0b00110001): cells 0..6 fixed, cell 7 answer.
_POOL = (0, 0, 1, 1, 0, 0, 0)

# ``.`` reads cells 0..7 as one byte.
_POOL_WIDTH = len(_POOL) + 1

# ``[<`` lands at ``(acc-1) + v``, ``[x<[<`` at ``(acc-1) + NOT v``; the
# digit is ``NOT(v XOR cell7)``, so read polarity is what makes a table
# and its complement both printable.
_READS = ("[<", "[x<[<")


# Complements the bit a setter just wrote.  The ``x`` absorbs the cascade's
# skip flag, or the gadget eats the template's next instruction: ``<[``
# passed a tape+pointer probe and printed 0 of 12 on the real interpreter.
_FLIP = "<[x"


def _embed(
    n: int,
    settle: int = 0,
    sep: str = _SEP,
    flips: int = 0,
) -> _Joint:
    """Emit the embed: each input's run once, separated by :data:`_SEP`.

    ``settle`` re-crosses the region; ``flips`` complements selected inputs.
    Setters stay in name order.
    """
    j = _Joint(n)
    _walk_to(j, _BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        if (flips >> i) & 1:
            j.emit(_FLIP)
        j.emit("[x")
        if i + 1 < n:
            j.emit(sep)
    for _ in range(settle):
        _clamp(j)
        _walk_to(j, _BASE - 1)
    return j


# Pool codes carry a mark right, then park the pointer behind it.  Tried in
# order; similar-looking strings diverge on the live pool state.
def _step(carry: int = 1, backs: int = 1, *, odd: bool = True) -> str:
    """One step of a pool code: carry a mark right, then walk the pointer back.

    ``k`` brackets carry a mark ``ceil(k / 2)`` and leave a skip when ``k``
    is odd, so a carry of ``c`` is ``2 * c - 1`` with the skip and ``2 * c``
    without; the ``<`` run sets how far behind the mark the pointer ends.
    """
    return "[" * (2 * carry - odd) + "<" * backs


# ``(steps, core, {step: (backs, odd)})``; a default step carries one
# cell, the core two.  Measured not to compress: moving a core strands
# 22 / 18 / 6 tables for plans 3 / 4 / 5 and slot order pins plan 2's.
_PLANS: tuple[tuple[int, int, dict[int, tuple[int, bool]]], ...] = (
    (2, 0, {1: (4, True)}),
    (4, 1, {}),
    (5, 2, {}),
    (5, 3, {0: (2, True)}),
    (5, 3, {2: (2, True), 4: (3, False)}),
)


def _render(steps: int, core: int, overrides: dict[int, tuple[int, bool]]) -> str:
    """Spell one plan out as a pool code."""
    codes = []
    for i in range(steps):
        backs, odd = overrides.get(i, (1, True))
        codes.append(_step(carry=2 if i == core else 1, backs=backs, odd=odd))
    return "".join(codes)


_POOL_CODES = tuple(_render(*plan) for plan in _PLANS)


# The verdict is invariant in the walk out (9..39), so the key omits it.
_PROBE_WALK_OUT = _POOL_WIDTH + 1

#: Cells 0 to ``_POOL_WIDTH - 1``: the window a pool verdict depends on.
_POOL_MASK = (1 << _POOL_WIDTH) - 1
