"""Parse a generator's module docstring into its template sections.

The shape is the ``_GENERATOR`` stub in ``scripts/new_language.py``.
"""

import random
import re

from tests.interpreters.spec_sections import section

#: The sections, in the order a docstring gives them; ``Size:`` is required.
SECTIONS = ("Size", "Raises", "Decisions")

#: What ``esolangs.generate`` raises beyond the shared table check.
PUBLIC_ERRORS = frozenset({"GeneratorCapError", "ArgumentError"})

#: ``n=8 parity: 1,186 chars`` -- a size ``esolangs.generate`` must reproduce.
ANCHOR = re.compile(
    r"n=(\d+) (parity|and|or|majority|zero|random \d+): ([\d,]+) (chars|codels)"
)

_ENTRY = re.compile(r"^    (\w+):")

#: A measured figure: a percentage, a decimal, or an integer of 3+ digits.
#: Shorter integers (``n=10``, ``2**n``) recur legitimately.
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
    return figures(ANCHOR.sub("", told)) - {"10%"}


def named_table(n: int, name: str) -> str:
    """Return the ``2**n``-row table an anchor names, MSB-first rows."""
    if name.startswith("random "):
        rng = random.Random(int(name.split()[1]))
        return format(rng.getrandbits(1 << n), f"0{1 << n}b")
    rule = {
        "parity": lambda ones: ones % 2,
        "and": lambda ones: ones == n,
        "or": lambda ones: ones > 0,
        "majority": lambda ones: 2 * ones > n,
        "zero": lambda _: 0,
    }[name]
    return "".join(str(int(rule(row.bit_count()))) for row in range(1 << n))


def anchors(doc: str) -> list[tuple[int, str, int, str]]:
    """Return ``(n, table name, size, unit)`` for each anchor ``Size:`` gives."""
    return [
        (int(m[1]), m[2], int(m[3].replace(",", "")), m[4])
        for m in ANCHOR.finditer(
            " ".join(line.strip() for line in section(doc, "Size"))
        )
    ]


def raises_entries(doc: str) -> set[str]:
    """Return the exception names ``Raises:`` lists."""
    return {m[1] for line in section(doc, "Raises") if (m := _ENTRY.match(line))}
