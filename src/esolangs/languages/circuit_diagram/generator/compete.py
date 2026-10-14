"""Model selection for n>=8: every candidate layout races on area.

Lives apart from ``__init__`` because the candidates import it back (a real
cycle), so ``__init__`` imports this module lazily, once.  Every name tests
monkeypatch is looked up at call time, through its module or a local import:
bound here, a patch made after the first import would never reach it, and a
first import under a patch would keep it (a zero pool floor made every later
build route the H pool, 2.3 s -> 6.2 s).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from esolangs.languages.circuit_diagram.generator import (
    _essential_table,
    bundled_banks,
    folded_banks,
    sparse_banks,
)
from esolangs.languages.circuit_diagram.generator.hlayout import _h_term_layout
from esolangs.languages.circuit_diagram.generator.hpool import _H_POOL_MIN_INPUTS
from esolangs.languages.circuit_diagram.generator.layout import _Layout, _layout_area


class _Target(NamedTuple):
    table: str
    inputs: int
    used: list[int]  # essential inputs
    projected: str  # the table over ``used``


# A candidate returns a model or None; ``ceiling`` is the best area so far
# (None before any model), and a candidate may skip work it can bound above it.
_Candidate = Callable[[_Target, "int | None"], "_Layout | None"]


def _h_fallback(target: _Target, large_area: int | None) -> _Layout | None:
    """Return the smaller H layout, skipping one the large pool already beats.

    Only skips an older layout when it is strictly larger, preserving its
    area ties: the mandatory term glyphs prove these floors.
    """
    from esolangs.languages.circuit_diagram.generator.hlayout import (
        _h_term_area_floor,
    )
    from esolangs.languages.circuit_diagram.generator.hpool import (
        _h_pool_area_floor,
        _h_pool_layout,
    )

    _, inputs, used, projected = target
    selected: _Layout | None = None
    if large_area is None or large_area >= _h_term_area_floor(len(used), inputs):
        selected = _h_term_layout(projected, input_order=used, port_inputs=inputs)
    if len(used) >= _H_POOL_MIN_INPUTS and (
        large_area is None or large_area >= _h_pool_area_floor(len(used), inputs)
    ):
        pooled = _h_pool_layout(projected, input_order=used, port_inputs=inputs)
        if selected is None or _layout_area(pooled) < _layout_area(selected):
            selected = pooled
    return selected


def _pool(target: _Target, ceiling: int | None) -> _Layout | None:
    """Large pool; with no model yet, the H layouts too (the pool wins strict only)."""
    from esolangs.languages.circuit_diagram.generator.hpool import _large_pool_layout

    _, inputs, used, projected = target
    large = _large_pool_layout(
        projected, input_order=used, port_inputs=inputs, ceiling=ceiling
    )
    if ceiling is not None:
        return large
    fallback = _h_fallback(target, _layout_area(large) if large is not None else None)
    if large is not None and (
        fallback is None or _layout_area(large) < _layout_area(fallback)
    ):
        return large
    return fallback


def _residual(target: _Target, ceiling: int | None) -> _Layout | None:
    from esolangs.languages.circuit_diagram.generator.banks import (
        _residual_class_bank_candidate,
    )

    return _residual_class_bank_candidate(target.table, ceiling)


# Order is the tie-break: an earlier candidate keeps an equal-area win.  The
# interval models count characters before rendering, so a node cap cannot
# hide a smaller complete fold.
_CANDIDATES: tuple[_Candidate, ...] = (
    lambda t, ceiling: folded_banks.folded_class_bank_candidate(t.table, ceiling),
    lambda t, ceiling: sparse_banks.sparse_class_bank_candidate(t.table, ceiling),
    _pool,
    lambda t, ceiling: bundled_banks.bundled_class_bank_candidate(t.table, ceiling),
    _residual,
)


def select_competing_model(truth_table: str, inputs: int) -> _Layout:
    """Return the smallest-area model over every n>=8 candidate layout.

    Each candidate is bounded by the best area so far and replaces it only
    when strictly smaller.  Raises AssertionError when none builds, which the
    constructions rule out.
    """
    used, projected = _essential_table(truth_table, inputs)
    target = _Target(truth_table, inputs, used, projected)
    best: _Layout | None = None
    area: int | None = None
    for candidate in _CANDIDATES:
        model = candidate(target, area)
        if model is not None and (area is None or _layout_area(model) < area):
            best, area = model, _layout_area(model)
    if best is None:
        raise AssertionError("missing Circuit Diagram layout")
    return best
