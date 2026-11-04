"""Formula-check arities: per-language tuning for the ledger formula tests.

A language package may carry a ``language.toml`` holding its own data,
one section per dataset; this module reads only its ``[formula_arities]``
section and skips a package whose file or section is absent.
:func:`formula_arities` aggregates those sections, keyed by the
language's registry display name: the arities at which the formula tests
check that language's ledger clause, where the default span (see
``tests/proofs/_formula.py``) is too slow or too shallow for the
construction.  A generator left out gets the default span.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.docs.fragments import AggregateKey, aggregate, registry, sections

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "src" / "esolangs" / "languages"
#: The section of ``language.toml`` this module aggregates.
TABLE = "formula_arities"
#: The formula columns an arity override may name.
COLUMNS = ("execution", "workspace")


def _validate(path: Path, row: dict[str, object]) -> dict[str, tuple[int, ...]]:
    """Return ``row`` as arity tuples after checking keys and values."""
    unknown = set(row) - set(COLUMNS)
    if unknown:
        raise ValueError(f"{path}: unknown formula-arities keys {sorted(unknown)}")
    out: dict[str, tuple[int, ...]] = {}
    for column, value in row.items():
        if not isinstance(value, list) or not value:
            raise ValueError(f"{path}: {column} must be a nonempty list of arities")
        arities: list[int] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int):
                raise ValueError(f"{path}: {column} arities must be ints")
            if item < 1:
                raise ValueError(f"{path}: {column} arities must be positive")
            arities.append(item)
        if len(set(arities)) != len(arities):
            raise ValueError(f"{path}: {column} arities repeat a value")
        out[column] = tuple(arities)
    return out


#: Aggregates by (packages, registry, fragment fingerprint): repeat
#: loads within a process reuse the first parse instead of re-reading
#: every fragment.
_AGGREGATES: dict[AggregateKey, dict[str, dict[str, tuple[int, ...]]]] = {}


def aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, tuple[int, ...]]]:
    """Merge every package's formula-arities section, by column then name.

    ``languages`` is the registry, in registry order; discovery follows
    it, never a second list.  A section in an unregistered package, an
    unknown key, or a value of the wrong type raises ``ValueError``, as
    does a repeated language.
    """
    return aggregate(_AGGREGATES, packages, languages, _aggregate_fragments)


def _aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, tuple[int, ...]]]:
    """Merge the formula-arities sections, uncached; see :func:`aggregate_fragments`."""
    columns: dict[str, dict[str, tuple[int, ...]]] = {name: {} for name in COLUMNS}
    for lang, path, row in sections(packages, languages, TABLE):
        for column, arities in _validate(path, row).items():
            columns[column][lang.name] = arities
    return columns


def formula_arities(column: str) -> dict[str, tuple[int, ...]]:
    """Return the arity overrides for one formula column, keyed by name."""
    if column not in COLUMNS:
        raise ValueError(f"unknown formula-arities column: {column!r}")
    return aggregate_fragments(PACKAGES, registry())[column]
