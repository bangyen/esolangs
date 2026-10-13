"""Occurrence-mask banks with charged work and native resource guards.

Mask folds charge visits and quadratic layout work to 4T. Fixed seven/eight
input bodies cost O(T); the retained-band rectangle bounds copying and
rendering. With q classes, 2*max(prefix,tail)+ceil(log2 q)+5 bounds ticks;
counted gates retain the existing written-state bound.
With G gates, n+G wire bits, at most 2G+1 latch bits and halt give
3G+n+2 <= 6T+25n+335 <= 7T+2n-9 for n>=17, independently of q.
"""

from __future__ import annotations

from esolangs.generation.helpers import _validate_truth_table
from esolangs.languages.circuit_diagram.generator import hpool
from esolangs.languages.circuit_diagram.generator.banks import (
    _assemble_banks,
    _online_bank_area_floor,
)
from esolangs.languages.circuit_diagram.generator.hpool import _large_pool_layout
from esolangs.languages.circuit_diagram.generator.layout import _Layout
from esolangs.languages.circuit_diagram.generator.sparse_masks import (
    _SparseWork,
    sparse_mask_model,
)


def sparse_class_bank_candidate(
    table: str, ceiling: int | None = None
) -> _Layout | None:
    """Admit repeated classes by mask work, ticks, gates and retained area."""
    n = _validate_truth_table(table)
    tail = 7 if n % 2 else 8
    prefix = n - tail
    if prefix <= 8 or len(set(table)) == 1:
        return None
    size = 1 << tail
    positions: dict[str, list[int]] = {}
    for start in range(0, len(table), size):
        word = table[start : start + size]
        if "1" in word:
            positions.setdefault(word, []).append(start // size)
    q = len(positions)
    if q < 2 or not any(
        "0" in word and len(rows) > 1 for word, rows in positions.items()
    ):
        return None
    depth = (q - 1).bit_length()
    if 2 * max(prefix, tail) + depth + 5 > 2 * n + 2:
        return None
    budget = hpool._h_pool_area_floor(n, n)  # noqa: SLF001
    if ceiling is not None:
        budget = min(budget, ceiling)
    if budget <= 0:
        return None
    work = _SparseWork(4 * len(table))
    parts: list[list[tuple[_Layout, list[int]]]] = []
    dimensions: list[tuple[int, int]] = []
    ands = sum("0" in word for word in positions)
    gates = 2 * q - 1
    for word, rows in positions.items():
        mask = sparse_mask_model(rows, prefix, work=work)
        if mask is None:
            return None
        models = [(mask, list(range(prefix)))]
        if "0" in word:
            body = _large_pool_layout(word, port_inputs=tail, ceiling=budget)
            if body is None:
                return None
            models.append((body, list(range(prefix, n))))
        for model, _order in models:
            dimensions.append(model.bounds())
            gates += sum(char in "ao~xX" for char in model.glyphs.values())
        if gates > 2 * len(table) + 8 * n + 111:
            return None
        if _online_bank_area_floor(dimensions, n, prefix, q, ands) > budget:
            return None
        parts.append(models)
    height = 2 * n + 8 + 4 * prefix + sum(h + 8 for h, _w in dimensions) + 32 * q + 5
    width = max(w for _h, w in dimensions) + 2 * n + 40 + 2 * (depth + 1)
    if height * width > budget:
        return None
    model = _assemble_banks(
        parts, n, prefix, share_prefix_complements=False, online_returns=True
    )
    h, w = model.bounds()
    if h > height or w > width:
        raise AssertionError("sparse bank exceeds its preflight rectangle")
    return model
