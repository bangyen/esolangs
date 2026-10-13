"""Fixed four-root forests with folded masks and left carry rails."""

from __future__ import annotations

from esolangs.generation.helpers import _validate_truth_table
from esolangs.languages.circuit_diagram.generator import _circuit_diagram_model, hpool
from esolangs.languages.circuit_diagram.generator.banks import (
    _assemble_banks,
    _online_bank_area_floor,
)
from esolangs.languages.circuit_diagram.generator.folded_banks import (
    _folded_class_masks,
)
from esolangs.languages.circuit_diagram.generator.forest import _suffix_forest
from esolangs.languages.circuit_diagram.generator.layout import _Layout


def bundled_class_bank_candidate(
    table: str, ceiling: int | None = None
) -> _Layout | None:
    """Return bounded four-root banks, retaining one outer transport stage."""
    n = _validate_truth_table(table)
    tail = 7 if n % 2 else 8
    prefix = n - tail
    if prefix < 2 or len(set(table)) == 1:
        return None
    size = 1 << tail
    chunks = [table[i : i + size] for i in range(0, len(table), size)]
    classes = [word for word in dict.fromkeys(chunks) if "1" in word]
    q = len(classes)
    if q * len(chunks) > 4 * len(table):
        return None
    budget = hpool._h_pool_area_floor(n, n)  # noqa: SLF001
    if ceiling is not None:
        budget = min(budget, ceiling)
    if budget <= 0:
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
        gates += (
            sum(sum(char in "ao~xX" for char in m.glyphs.values()) for m in bands)
            + ands
            + len(words)
            - 1
        )
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
            share_prefix_complements=False,
            shared_suffix=forest,
            online_returns=True,
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
        share_prefix_complements=False,
        online_returns=True,
        left_returns=True,
    )
    h, w = model.bounds()
    return model if h * w <= budget else None
