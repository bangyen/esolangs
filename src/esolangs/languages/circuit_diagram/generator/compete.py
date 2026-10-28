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
)
from esolangs.languages.circuit_diagram.generator.layout import _Layout, _layout_area


class _Target(NamedTuple):
    table: str
    inputs: int
    used: list[int]  # essential inputs
    projected: str  # the table over ``used``


# A candidate returns a model or None; ``ceiling`` is the best area so far
# (None before any model), and a candidate may skip work it can bound above it.
_Candidate = Callable[[_Target, "int | None"], "_Layout | None"]


def _pool(target: _Target, ceiling: int | None) -> _Layout | None:
    """Large pool; the H term and pool layouts never win, so they do not race.

    Up to eight essential inputs the folds beat them on area; from nine the
    pool's geometry is table-independent and its area is 0.80-0.85 of the
    smaller H floor.
    """
    from esolangs.languages.circuit_diagram.generator.hpool import _large_pool_layout

    _, inputs, used, projected = target
    return _large_pool_layout(
        projected, input_order=used, port_inputs=inputs, ceiling=ceiling
    )


# Leave-one-out: bundled saves 40.7% / 60.7% of area on random tables at
# n=12 / 14.  Order breaks equal-area ties.
_CANDIDATES: tuple[_Candidate, ...] = (
    _pool,
    lambda t, ceiling: bundled_banks.bundled_class_bank_candidate(t.table, ceiling),
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
