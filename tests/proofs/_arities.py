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

import copy
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "src" / "esolangs" / "languages"
FRAGMENT = "language.toml"
#: The section of ``language.toml`` this module aggregates.
TABLE = "formula_arities"
#: The formula columns an arity override may name.
COLUMNS = ("execution", "workspace")


def _section(path: Path) -> dict[str, object] | None:
    """Return ``path``'s formula-arities section, or None when it has none."""
    table = tomllib.loads(path.read_text(encoding="utf-8")).get(TABLE)
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError(f"{path}: [{TABLE}] must be a table")
    return table


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


def _fingerprint(packages: Path) -> tuple[tuple[str, int, int], ...]:
    """Return a stamp of the fragment set under ``packages``.

    One (package, mtime, size) entry per ``language.toml``; adding,
    removing, or editing a fragment changes the stamp, so an aggregate
    cached against it cannot go stale in a process that mutates the
    tree, as the scaffold and removal flows do.
    """
    if not packages.is_dir():
        return ()
    return tuple(
        (path.parent.name, path.stat().st_mtime_ns, path.stat().st_size)
        for path in sorted(packages.glob(f"*/{FRAGMENT}"))
    )


#: Aggregates by (packages, registry, fragment fingerprint): repeat
#: loads within a process reuse the first parse instead of re-reading
#: every fragment.
_AggregateKey = tuple[
    Path, tuple[tuple[str, str], ...], tuple[tuple[str, int, int], ...]
]
_AGGREGATES: dict[_AggregateKey, dict[str, dict[str, tuple[int, ...]]]] = {}


def aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, tuple[int, ...]]]:
    """Merge every package's formula-arities section, by column then name.

    ``languages`` is the registry, in registry order; discovery follows
    it, never a second list.  A section in an unregistered package, an
    unknown key, or a value of the wrong type raises ``ValueError``, as
    does a repeated language.
    """
    langs = list(languages)
    key = (
        packages,
        tuple((lang.id, lang.name) for lang in langs),
        _fingerprint(packages),
    )
    if key not in _AGGREGATES:
        _AGGREGATES[key] = _aggregate_fragments(packages, langs)
    return copy.deepcopy(_AGGREGATES[key])


def _aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, tuple[int, ...]]]:
    """Merge the formula-arities sections, uncached; see :func:`aggregate_fragments`."""
    columns: dict[str, dict[str, tuple[int, ...]]] = {name: {} for name in COLUMNS}
    seen: set[str] = set()
    for lang in languages:
        if lang.id in seen:
            raise ValueError(f"duplicate language id: {lang.id}")
        seen.add(lang.id)
        path = packages / lang.id / FRAGMENT
        if not path.is_file():
            continue
        row = _section(path)
        if row is not None:
            for column, arities in _validate(path, row).items():
                columns[column][lang.name] = arities
    if packages.is_dir():
        for path in packages.glob(f"*/{FRAGMENT}"):
            if path.parent.name not in seen and _section(path) is not None:
                raise ValueError(
                    f"{path}: package {path.parent.name!r} is not registered"
                )
    return columns


def _registry() -> tuple[Language, ...]:
    """Return the registered languages, in registry order."""
    from esolangs.registry import LANGUAGES

    return tuple(LANGUAGES.values())


def formula_arities(column: str) -> dict[str, tuple[int, ...]]:
    """Return the arity overrides for one formula column, keyed by name."""
    if column not in COLUMNS:
        raise ValueError(f"unknown formula-arities column: {column!r}")
    return aggregate_fragments(PACKAGES, _registry())[column]
