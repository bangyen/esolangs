"""Parse a generator's module docstring into its template sections.

The shape is the ``_GENERATOR`` stub in ``scripts/new_language.py``.
"""

import re

from scripts.docs.evidence import SOURCE_ANCHOR, TableWitness
from tests.interpreters.spec_sections import section

#: The sections, in the order a docstring gives them; ``Size:`` is required.
SECTIONS = ("Size", "Raises", "Decisions")

#: Short integers such as n=10 are parameters, not measured figures.
FIGURE = re.compile(r"\d+(?:\.\d+)?%|\d+\.\d+|\d{1,3}(?:,\d{3})+|\d{3,}")


def figures(text: str) -> set[str]:
    """Return the measured figures in ``text``, thousands separators removed."""
    return {m.replace(",", "") for m in FIGURE.findall(text)}


def measured(doc: str) -> set[str]:
    """Return the figures ``Size:`` and ``Decisions:`` report.

    Anchors are regenerated, not restated, and ``10%`` is CONTRIBUTING's bar;
    a constant in the prose (``59049``, a cap) is code, named beside its use.
    """
    told = " ".join(
        line.strip() for name in ("Size", "Decisions") for line in section(doc, name)
    )
    return figures(SOURCE_ANCHOR.sub("", told)) - {"10%"}


def named_table(n: int, name: str) -> str:
    """Return the ``2**n``-row table an anchor names, MSB-first rows."""
    rule, separator, seed = name.partition(" ")
    return TableWitness(n, rule, int(seed) if separator else None).table()


def anchors(doc: str) -> list[tuple[int, str, int, str]]:
    """Return ``(n, table name, size, unit)`` for each anchor ``Size:`` gives."""
    return [
        (int(m[1]), " ".join(m[2].split()), int(m[3].replace(",", "")), m[4])
        for m in SOURCE_ANCHOR.finditer(
            " ".join(line.strip() for line in section(doc, "Size"))
        )
    ]
