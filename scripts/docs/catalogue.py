"""Load generator catalogue rows from each package's ``language.toml``.

Generators whose mechanism is not a canonical helper, and why.  The rows
live in the packages so the tests enforcing them name no language: the
tests read this aggregate, as they read the ledger before it.

``sharing`` covers tree-shaped generators whose sharing is a
language-local mechanism, or which share nothing; every tree generator
not exempt must shrink a repeated table, measured by
``tests/generators/test_boolean_sharing_catalogue.py``.  ``folding``
covers mechanisms not expressed by the canonical span or residual
helpers: local entries name reachable native constructors, exemptions
state the construction's limit, and ``ignored_read`` entries fold an
ignored input's branch but keep a read that costs over half a real
input at n=8; enforced by ``test_boolean_canonical_catalogue.py``.
A package with no file or no ``[catalogue]`` section is skipped.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .fragments import AggregateKey, aggregate, registry, sections

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).resolve().parents[2]

#: The section's flat keys, in order, and the (section, group) each feeds.
_GROUPS = {
    "sharing_local": ("sharing", "local"),
    "sharing_exempt": ("sharing", "exempt"),
    "folding_ignored": ("folding", "ignored"),
    "folding_constant": ("folding", "constant"),
    "folding_ignored_read": ("folding", "ignored_read"),
    "folding_ignored_local": ("folding", "ignored_local"),
    "folding_constant_local": ("folding", "constant_local"),
}

#: Key pairs one fragment may not hold together: a mechanism is either a
#: named local helper or an exemption with a reason, never both.  The
#: ignored piece has three homes — plain exemption, costly-read
#: exemption, and local helper — which likewise exclude each other.
_CONTRADICTIONS = (
    ("sharing_local", "sharing_exempt"),
    ("folding_ignored", "folding_ignored_local"),
    ("folding_ignored", "folding_ignored_read"),
    ("folding_ignored_read", "folding_ignored_local"),
    ("folding_constant", "folding_constant_local"),
)


def _validate(path: Path, row: dict[str, Any]) -> dict[str, str]:
    """Return ``row`` after checking its keys, values, and exclusions."""
    unknown = set(row) - set(_GROUPS)
    if unknown:
        raise ValueError(f"{path}: unknown catalogue keys {sorted(unknown)}")
    for key, value in row.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}: catalogue {key} must be a nonempty string")
    for held, excluded in _CONTRADICTIONS:
        if held in row and excluded in row:
            raise ValueError(f"{path}: catalogue holds both {held} and {excluded}")
    return dict(row)


#: Aggregates by (packages, registry, fragment fingerprint): repeat
#: loads within a process reuse the first parse instead of re-reading
#: every fragment.
_AGGREGATES: dict[AggregateKey, dict[str, dict[str, dict[str, str]]]] = {}


def aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, dict[str, str]]]:
    """Merge every package's catalogue section, grouped as the ledger was.

    ``languages`` is the registry, in registry order; discovery follows
    it, never a second list.  Every group is present, empty when no
    package declares it, and each group's rows are keyed by language
    name.  A section in an unregistered package, an unknown key, a
    blank or non-string value, or two keys that exclude each other
    raises ``ValueError``, as does a repeated language.
    """
    return aggregate(_AGGREGATES, packages, languages, _aggregate_fragments)


def _aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, dict[str, str]]]:
    """Merge the catalogue sections, uncached; see :func:`aggregate_fragments`."""
    groups: dict[str, dict[str, dict[str, str]]] = {}
    for section, group in _GROUPS.values():
        groups.setdefault(section, {})[group] = {}
    for lang, path, row in sections(packages, languages, "catalogue"):
        for key, value in _validate(path, row).items():
            section, group = _GROUPS[key]
            rows = groups[section][group]
            if lang.name in rows:
                raise ValueError(f"duplicate language name: {lang.name}")
            rows[lang.name] = value
    return groups


def load(root: Path = ROOT) -> dict[str, dict[str, dict[str, str]]]:
    """Return every catalogue group, keyed by section, group, and name."""
    return aggregate_fragments(root / "src/esolangs/languages", registry())
