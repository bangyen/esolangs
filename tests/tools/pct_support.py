"""Tuple-state adapters over ``_FoldLedger`` for the %^2^-1 fold tests."""

from esolangs.tools.pct_fold import _FoldState
from esolangs.tools.pct_fold_plan import _FoldLedger, _FoldOp


def _fold_step(state: _FoldState, op: _FoldOp) -> _FoldState | None:
    """Apply one concrete op to a tuple state, or ``None`` where it is refused."""
    ledger = _FoldLedger.from_state(state)
    return ledger.to_state() if ledger.step(op) else None


def _fold_clean_amount(state: _FoldState, kind: str, k: int) -> int | None:
    """:meth:`_FoldLedger.clean_amount` on a tuple state."""
    return _FoldLedger.from_state(state).clean_amount(kind, k)


def _fold_span(state: _FoldState) -> int:
    """Return ``state``'s occupied top-to-bottom extent."""
    return max(point for point, _, _, _ in state) - min(
        point - extent for point, extent, _, _ in state
    )


def _fold_rule_move(state: _FoldState) -> _FoldOp | None:
    """:meth:`_FoldLedger.rule_move` on a tuple state."""
    return _FoldLedger.from_state(state).rule_move()
