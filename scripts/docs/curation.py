"""Load curation rows from each language package's ``language.toml``.

The census dates live in the root ``snapshot.json``'s ``collected``
block: they describe the census, not any one language.  A package with
no file or no ``[curation]`` section is skipped.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .fragments import AggregateKey, aggregate

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "src" / "esolangs" / "languages"
FRAGMENT = "language.toml"

_FIELDS = frozenset(
    {"backlinks", "bf_derivative", "bf_derivative_predates", "unassessed"}
)
_COLLECTED = {"checked": "curation", "bf_derivatives_checked": "bf_derivatives"}


def _section(path: Path) -> dict[str, Any] | None:
    """Return ``path``'s curation section, or None when it has none."""
    table = tomllib.loads(path.read_text(encoding="utf-8")).get("curation")
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError(f"{path}: [curation] must be a table")
    return table


def _validate(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    """Return ``row`` after checking its keys and value types."""
    unknown = set(row) - _FIELDS
    if unknown:
        raise ValueError(f"{path}: unknown curation keys {sorted(unknown)}")
    if "unassessed" in row:
        if row != {"unassessed": True}:
            raise ValueError(f"{path}: an unassessed row carries no other curation")
    elif "backlinks" not in row:
        raise ValueError(f"{path}: a curation row needs backlinks or unassessed")
    if "backlinks" in row:
        value = row["backlinks"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{path}: backlinks must be a nonnegative int")
    for key in ("bf_derivative", "bf_derivative_predates", "unassessed"):
        if key in row and not isinstance(row[key], bool):
            raise ValueError(f"{path}: {key} must be a bool")
    if row.get("bf_derivative_predates") and not row.get("bf_derivative"):
        raise ValueError(
            f"{path}: bf_derivative_predates records a Brainfuck derivative "
            "admitted before the 2026-10-15 exclusion, so bf_derivative "
            "must be true"
        )
    return dict(row)


#: Aggregates by (packages, registry, fragment fingerprint).  Callers
#: that loop over the whole registry -- the new-language check above
#: all -- would otherwise re-parse every fragment on every call.
_AGGREGATES: dict[AggregateKey, dict[str, dict[str, Any]]] = {}


def aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, Any]]:
    """Merge every package's curation section, keyed by language name.

    ``languages`` is the registry, in registry order; discovery follows
    it, never a second list.  A section in an unregistered package, an
    unknown key, or a value of the wrong type raises ``ValueError``, as
    does a repeated language.
    """
    return aggregate(_AGGREGATES, packages, languages, _aggregate_fragments)


def _aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, Any]]:
    """Merge the curation sections, uncached; see :func:`aggregate_fragments`."""
    rows: dict[str, dict[str, Any]] = {}
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
            rows[lang.name] = _validate(path, row)
    if packages.is_dir():
        for path in packages.glob(f"*/{FRAGMENT}"):
            if path.parent.name not in seen and _section(path) is not None:
                raise ValueError(
                    f"{path}: package {path.parent.name!r} is not registered"
                )
    return rows


def fragment_row(path: Path) -> dict[str, Any]:
    """Return one package fragment's validated curation row, or {}."""
    if not path.is_file():
        return {}
    row = _section(path)
    return {} if row is None else _validate(path, row)


def _registry() -> tuple[Language, ...]:
    """Return the registered languages, in registry order."""
    from esolangs.registry import LANGUAGES

    return tuple(LANGUAGES.values())


def rows(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    """Return every language's curation row, keyed by name."""
    return aggregate_fragments(root / "src/esolangs/languages", _registry())


def dates(root: Path = ROOT) -> dict[str, str]:
    """Return the census dates from the snapshot's ``collected`` block."""
    data = json.loads((root / "snapshot.json").read_text(encoding="utf-8"))
    collected = data.get("collected") if isinstance(data, dict) else None
    if not isinstance(collected, dict):
        raise ValueError("snapshot holds no collected block")
    unknown = set(collected) - {"durations", *_COLLECTED.values()}
    if unknown:
        raise ValueError(f"snapshot collected holds unknown keys {sorted(unknown)}")
    out = {}
    for key, source in _COLLECTED.items():
        value = collected.get(source)
        if not isinstance(value, str) or not value:
            raise ValueError(f"snapshot collected: {source} must be a nonempty date")
        out[key] = value
    return out


def load(root: Path = ROOT) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    """Return the census dates and every language's curation row."""
    return dates(root), rows(root)
