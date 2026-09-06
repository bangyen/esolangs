"""Shared fold-state geometry for the %^2^-1 interleaved route scripts.

``verify_pct_interleaved_ten.py`` rebuilds the seed-31 route from scratch and
``verify_pct_interleaved_portability.py`` replays the recorded moves on other
tables.  Both walk the same fold state, so both need the same reading of it:
what a state's span is, what identifies it, and how the one awkward tightening
step is spelled.

That tightening step is the reason this module exists.  A cmin contraction at
span 3004 collides, and the only legal way through is a two-step form: widen
the endpoint to exactly 3003 at cmax, then contract that same endpoint from
the opposite side at cmin.  Getting either half wrong yields a state that
still looks plausible, so the spelling is written once here rather than
copied.

The callers keep their own acceptance rules.  ``_ten`` additionally demands
that a candidate preserve the live-point count; ``_portability`` does not.
That difference is deliberate, so this module enumerates candidates and lets
each caller filter.
"""

# ruff: noqa: SLF001
# mypy: disable-error-code="no-untyped-call,no-untyped-def"

from __future__ import annotations

import importlib

pct = importlib.import_module("esolangs.tools.boolean.pct_squared_minus_one")


def signature(state):
    """Keep exact geometry and cofactor strings, including their remaining depth."""
    return tuple((point, point_span, cls) for point, point_span, cls, _rows in state)


def span(state):
    """Measure the state's footprint, from its highest point to its lowest edge."""
    return max(p for p, _s, _c, _r in state) - min(p - s for p, s, _c, _r in state)


def collision_candidates(current, seen):
    """Yield ``(span, (widen, contract), next)`` for each legal two-step cmin.

    A direct cmin contraction collides at span 3004.  Widening the endpoint to
    exactly 3003 at cmax first makes the same contraction legal, so each
    direction contributes at most one candidate: the pair of moves, and the
    state they land on.
    """
    for kind, opposite in (("d", "u"), ("u", "d")):
        frame = pct._fold_wipe_frame(current, kind, 1)
        if frame is None:
            continue
        q1, _tops = frame
        widen = pct._fold_op(current, kind, 1, pct._LIMIT + q1)
        widened = pct._fold_step(current, widen)
        if widened is None or span(widened) != pct._LIMIT:
            continue
        amount = pct._fold_clean_amount(widened, opposite, 1)
        if amount is None:
            continue
        contract = pct._fold_op(widened, opposite, 1, amount)
        nxt = pct._fold_step(widened, contract)
        if nxt is None or span(nxt) > pct._LIMIT or signature(nxt) in seen:
            continue
        yield span(nxt), (widen, contract), nxt
