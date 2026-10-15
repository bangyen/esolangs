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
