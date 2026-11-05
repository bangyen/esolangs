"""Reusable conventions helpers."""

from __future__ import annotations

from esolangs.generation.examples import BOOLEAN_EXAMPLES, BooleanExample
from esolangs.registry import BY_BOOLEAN


def _embedding() -> dict[str, BooleanExample]:
    """The embedding examples, keyed by the registry display name."""
    names = {lang.runtime.interpreter: lang.name for lang in BY_BOOLEAN.values()}
    return {
        names[example.interpreter]: example
        for example in BOOLEAN_EXAMPLES.values()
        if example.fill is not None
    }


def _tables(n: int) -> tuple[str, str]:
    parity = "".join("1" if (i).bit_count() % 2 else "0" for i in range(2**n))
    dense = "".join("1" if (i * 7 + 3) % 5 < 2 else "0" for i in range(2**n))
    return parity, dense
