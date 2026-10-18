"""Scheme-measurement exemptions: per-language facts for the scheme tests.

A language package may carry a ``language.toml`` holding its own data,
one section per dataset; this module reads only its ``[schemes]``
section and skips a package whose file or section is absent.
:func:`folds_without_tree` aggregates the ``folds_without_tree``
markers, keyed by the language's registry display name: the lookup
routes that shrink a degenerate table without branching on it, which
are the structural fold proxy's known blind spots in
``tests/proofs/test_schemes.py``.
"""

from __future__ import annotations

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
TABLE = "schemes"
#: The only marker the section may carry.
_MARKER = "folds_without_tree"


def _section(path: Path) -> dict[str, object] | None:
    """Return ``path``'s schemes section, or None when it has none."""
    table = tomllib.loads(path.read_text(encoding="utf-8")).get(TABLE)
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError(f"{path}: [{TABLE}] must be a table")
    return table


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
#: every fragment.  The result is a frozenset, so callers may share it.
_AggregateKey = tuple[
    Path, tuple[tuple[str, str], ...], tuple[tuple[str, int, int], ...]
]
_AGGREGATES: dict[_AggregateKey, frozenset[str]] = {}


def aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> frozenset[str]:
    """Return the names whose package records the fold exemption.

    ``languages`` is the registry, in registry order; discovery follows
    it, never a second list.  A section in an unregistered package, an
    unknown key, or a marker that is not ``true`` raises ``ValueError``,
    as does a repeated language.
    """
    langs = list(languages)
    key = (
        packages,
        tuple((lang.id, lang.name) for lang in langs),
        _fingerprint(packages),
    )
    if key not in _AGGREGATES:
        _AGGREGATES[key] = _aggregate_fragments(packages, langs)
    return _AGGREGATES[key]


def _aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> frozenset[str]:
    """Collect the fold exemptions, uncached; see :func:`aggregate_fragments`."""
    names: set[str] = set()
    seen: set[str] = set()
    for lang in languages:
        if lang.id in seen:
            raise ValueError(f"duplicate language id: {lang.id}")
        seen.add(lang.id)
        path = packages / lang.id / FRAGMENT
        if not path.is_file():
            continue
        row = _section(path)
        if row is None:
            continue
        unknown = set(row) - {_MARKER}
        if unknown:
            raise ValueError(f"{path}: unknown schemes keys {sorted(unknown)}")
        if _MARKER in row:
            if row[_MARKER] is not True:
                raise ValueError(f"{path}: {_MARKER} must be true when present")
            names.add(lang.name)
    if packages.is_dir():
        for path in packages.glob(f"*/{FRAGMENT}"):
            if path.parent.name not in seen and _section(path) is not None:
                raise ValueError(
                    f"{path}: package {path.parent.name!r} is not registered"
                )
    return frozenset(names)


def _registry() -> tuple[Language, ...]:
    """Return the registered languages, in registry order."""
    from esolangs.registry import LANGUAGES

    return tuple(LANGUAGES.values())


def folds_without_tree() -> frozenset[str]:
    """Return every language whose lookup route folds without a tree route."""
    return aggregate_fragments(PACKAGES, _registry())
