"""Fixed four-root forests with folded masks and left carry rails."""

from __future__ import annotations

from esolangs.generation.helpers import _validate_truth_table
from esolangs.languages.circuit_diagram.generator import _circuit_diagram_model
from esolangs.languages.circuit_diagram.generator.banks import (
    _assemble_banks,
    _chunks,
    _gate_count,
    _online_bank_area_floor,
    _pool_budget,
)
from esolangs.languages.circuit_diagram.generator.folded_banks import (
    _folded_class_masks,
)
from esolangs.languages.circuit_diagram.generator.forest import _suffix_forest
from esolangs.languages.circuit_diagram.generator.hpool import _atom_inputs
from esolangs.languages.circuit_diagram.generator.layout import _Layout, _layout_area


def bundled_class_bank_candidate(
    table: str, ceiling: int | None = None
) -> _Layout | None:
    """Return bounded four-root banks, retaining one outer transport stage."""
    n = _validate_truth_table(table)
    tail = _atom_inputs(n)
    prefix = n - tail
    if prefix < 2 or len(set(table)) == 1:
        return None
    size = 1 << tail
    chunks = _chunks(table, size)
    classes = [word for word in dict.fromkeys(chunks) if "1" in word]
    q = len(classes)
    if q * len(chunks) > 4 * len(table):
        return None
    budget = _pool_budget(n, ceiling)
    if budget is None:
        return None
    masks = _folded_class_masks(chunks, classes, prefix, len(table))
    if masks is None:
        return None
    parts = []
    dimensions = []
    groups = (q + 3) // 4
    gates = groups - 1
    for start in range(0, q, 4):
        words = classes[start : start + 4]
        forest = (
            _suffix_forest(words, tail) if any("0" in word for word in words) else None
        )
        inner_parts = []
        for index in range(start, start + len(words)):
            used, reduced = masks[index]
            models = []
            if "0" in reduced:
                model = _circuit_diagram_model(
                    reduced, None, input_order=used, port_inputs=prefix
                )
                models.append((model, list(range(prefix))))
            inner_parts.append(models)
        bands = [m for models in inner_parts for m, _ports in models]
        if forest is not None:
            bands.append(forest[0])
        ands = sum("0" in word for word in words) if forest is not None else 0
        gates += sum(_gate_count(m) for m in bands) + ands + len(words) - 1
        if gates > len(table) + n:
            return None
        inner_dimensions = [m.bounds() for m in bands]
        if any(h * w > budget for h, w in inner_dimensions) or (
            _online_bank_area_floor(inner_dimensions, n, prefix, len(words), ands)
            > budget
        ):
            return None
        model = _assemble_banks(
            inner_parts,
            n,
            prefix,
            shared_suffix=forest,
            left_returns=True,
        )
        # G <= T+n implies the written-state bound; q <= 2**min(prefix,tail+2)
        # bounds the combined inner/outer OR depth by ceil(log2 q).
        h, w = model.bounds()
        if h * w > budget:
            return None
        dimensions.append((h, w))
        if _online_bank_area_floor(dimensions, n, 0, groups, 0) > budget:
            return None
        parts.append([(model, list(range(n)))])
    # Uniform nesting retains the transport stage even for one group;
    # removing it breaks the dense 8/10/12 emitted-text growth control.
    model = _assemble_banks(
        parts,
        n,
        0,
        left_returns=True,
    )
    return model if _layout_area(model) <= budget else None
