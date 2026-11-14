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

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.docs.fragments import AggregateKey, aggregate, registry, sections

if TYPE_CHECKING:
    from esolangs.registry import LanguageDeclaration

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "src" / "esolangs" / "languages"
#: The section of ``language.toml`` this module aggregates.
TABLE = "schemes"
#: The only marker the section may carry.
_MARKER = "folds_without_tree"


#: Aggregates by (packages, registry, fragment fingerprint): repeat
#: loads within a process reuse the first parse instead of re-reading
#: every fragment.  The result is a frozenset, so callers may share it.
_AGGREGATES: dict[AggregateKey, frozenset[str]] = {}


def aggregate_fragments(
    packages: Path, languages: Iterable[LanguageDeclaration]
) -> frozenset[str]:
    """Return the names whose package records the fold exemption.

    ``languages`` is the registry, in registry order; discovery follows
    it, never a second list.  A section in an unregistered package, an
    unknown key, or a marker that is not ``true`` raises ``ValueError``,
    as does a repeated language.
    """
    return aggregate(_AGGREGATES, packages, languages, _aggregate_fragments)


def _aggregate_fragments(
    packages: Path, languages: Iterable[LanguageDeclaration]
) -> frozenset[str]:
    """Collect the fold exemptions, uncached; see :func:`aggregate_fragments`."""
    names: set[str] = set()
    for lang, path, row in sections(packages, languages, TABLE):
        unknown = set(row) - {_MARKER}
        if unknown:
            raise ValueError(f"{path}: unknown schemes keys {sorted(unknown)}")
        if _MARKER in row:
            if row[_MARKER] is not True:
                raise ValueError(f"{path}: {_MARKER} must be true when present")
            names.add(lang.name)
    return frozenset(names)


def folds_without_tree() -> frozenset[str]:
    """Return every language whose lookup route folds without a tree route."""
    return aggregate_fragments(PACKAGES, registry())
