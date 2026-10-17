"""Repeated classes admitted by aggregate mask-fold and bank work bounds."""

from __future__ import annotations

from collections import Counter

from esolangs.generation.helpers import _validate_truth_table
from esolangs.languages.circuit_diagram.generator import (
    _circuit_diagram_model,
    _dag,
    _essential_table,
)
from esolangs.languages.circuit_diagram.generator.banks import (
    _POOLED_MASK_INPUTS,
    _assemble_banks,
    _bank_rectangle,
    _chunks,
    _class_gate_cap,
    _gate_count,
    _pool_budget,
)
from esolangs.languages.circuit_diagram.generator.hpool import (
    _atom_inputs,
    _large_pool_layout,
)
from esolangs.languages.circuit_diagram.generator.layout import _Layout


def _folded_class_masks(
    chunks: list[str], classes: list[str], prefix: int, table_size: int
) -> list[tuple[list[int], str]] | None:
    """Return essential class masks within the aggregate quadratic fold budget."""
    masks = []
    work = 0
    for word in classes:
        used, reduced = _essential_table(
            "".join(str(int(chunk == word)) for chunk in chunks), prefix
        )
        # Include original ports in the quadratic fold-work bound.
        work += (len(_dag(reduced, len(used)).ops) + prefix) ** 2
        if work > 4 * table_size:
            return None
        masks.append((used, reduced))
    return masks


def folded_class_bank_candidate(
    table: str, ceiling: int | None = None
) -> _Layout | None:
    """Return a bounded separate bank with folded masks above eight inputs."""
    n = _validate_truth_table(table)
    tail = _atom_inputs(n)
    prefix = n - tail
    if prefix <= _POOLED_MASK_INPUTS:
        return None
    size = 1 << tail
    chunks = _chunks(table, size)
    counts = Counter(chunks)
    classes = [word for word in counts if "1" in word]
    q = len(classes)
    if q < 2 or q * len(chunks) > 4 * len(table):
        return None
    if not any("0" in word and counts[word] > 1 for word in classes):
        return None
    # q <= 2**(tail+2) and prefix >= tail+1 give clock <= 2n+2:
    # parallel folds, one AND, ceil(log2 q) ORs and three I/O ticks.
    budget = _pool_budget(ceiling)
    if budget is None:
        return None
    masks = _folded_class_masks(chunks, classes, prefix, len(table))
    if masks is None:
        return None
    parts = []
    for word, (used, reduced) in zip(classes, masks, strict=True):
        models = [
            (
                _circuit_diagram_model(
                    reduced, None, input_order=used, port_inputs=prefix
                ),
                list(range(prefix)),
            )
        ]
        if "0" in word:
            used, reduced = _essential_table(word, tail)
            model = _large_pool_layout(
                reduced, input_order=used, port_inputs=tail, ceiling=budget
            )
            if model is None:
                return None
            models.append((model, list(range(prefix, n))))
        parts.append(models)
    gates = sum(_gate_count(m) for group in parts for m, order in group)
    if gates + 2 * q - 1 > _class_gate_cap(len(table), n):
        return None
    dimensions = [m.bounds() for group in parts for m, order in group]
    height, width = _bank_rectangle(dimensions, n, prefix, q)
    if height * width > budget:
        return None
    model = _assemble_banks(parts, n, prefix)
    h, w = model.bounds()
    if h > height or w > width:
        raise AssertionError("folded bank exceeds its preflight rectangle")
    return model
