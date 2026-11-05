"""Load formula checks from validated language-owned evidence."""

from __future__ import annotations

from esolangs.registry import LANGUAGES
from scripts.docs.resource_evidence import Formula, resource_bounds

Exact = bool | frozenset[int]


def exact_at(exact: Exact, n: int) -> bool:
    """Whether some table must reach the formula at ``n``."""
    return n in exact if isinstance(exact, frozenset) else exact


def ledger_formulas(column: str) -> dict[str, tuple[Formula, Exact, tuple[int, ...]]]:
    """Return each explicit formula, exactness rule and unchanged probe arities."""
    return {
        name: (bound.formula, bound.exact, bound.arities)
        for name, language in LANGUAGES.items()
        if language.backend is not None
        if (bound := resource_bounds(name).get(column)) is not None
    }
