"""Deep proof measurements: per-generator tuning lives with each language.

A language package may carry a ``language.toml`` holding its own data,
one section per dataset; this suite reads only its ``[deep_arities]``
section and skips a package whose file or section is absent.
:func:`deep_arities` aggregates those sections, keyed by the package's
registry id.  A generator left out gets the suite's default.  Section
rationale, formerly the ledger's comments:

- linearity: builds are measured in seconds; each override is the lowest
  arity that still clears ``MIN_RUNGS`` past its last route change.
- execution: loading, not command count, sets the measured ceilings.
- workspace: written state is recounted every step, so a rung costs about
  four times the last; overrides are lowered where a generator's top rung
  passed about three seconds.  FALSE and BFStack keep 9, since their
  ``poly n`` fit (x1.49, x1.48) is steeper lower down.
- workspace_step_exempt: ``poly n`` rows whose dense increments may grow
  past ``STEP_GROWTH`` at the measured arities; values are the reasons.
"""

from __future__ import annotations

import copy
import tomllib
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ROOT / "src" / "esolangs" / "languages"
FRAGMENT = "language.toml"
#: The section of ``language.toml`` this suite aggregates.
TABLE = "deep_arities"

#: Sections whose values are arity ceilings.
ARITY_SECTIONS = ("linearity", "execution", "workspace")
#: Sections whose values are exemption reasons.
REASON_SECTIONS = ("workspace_step_exempt", "linearity_exempt")
SECTIONS = ARITY_SECTIONS + REASON_SECTIONS


def _table(path: Path) -> dict[str, object] | None:
    """Return ``path``'s deep-arities section, or None when it has none."""
    table = tomllib.loads(path.read_text("utf-8")).get(TABLE)
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


#: Aggregates by (packages, registry ids, fragment fingerprint):
#: repeat loads within a process reuse the first parse instead of
#: re-reading every fragment.
_AggregateKey = tuple[Path, tuple[str, ...], tuple[tuple[str, int, int], ...]]
_AGGREGATES: dict[_AggregateKey, dict[str, dict[str, object]]] = {}


def aggregate_fragments(
    packages: Path, language_ids: Iterable[str]
) -> dict[str, dict[str, object]]:
    """Merge every package's deep-arities section into per-section maps.

    ``language_ids`` is the registry's ids; discovery follows it, never a
    second list.  A package with no ``language.toml``, or one whose file
    has no ``[deep_arities]`` section, is skipped; other sections are not
    this suite's business.  A section in a package the registry does not
    name, an unknown key, or a value of the wrong type raises
    ``ValueError``, as does a repeated language id.
    """
    ids = list(language_ids)
    key = (packages, tuple(ids), _fingerprint(packages))
    if key not in _AGGREGATES:
        _AGGREGATES[key] = _aggregate_fragments(packages, ids)
    return copy.deepcopy(_AGGREGATES[key])


def _aggregate_fragments(
    packages: Path, language_ids: Iterable[str]
) -> dict[str, dict[str, object]]:
    """Merge the deep-arities sections, uncached; see :func:`aggregate_fragments`."""
    sections: dict[str, dict[str, object]] = {name: {} for name in SECTIONS}
    seen: set[str] = set()
    for language_id in language_ids:
        if language_id in seen:
            raise ValueError(f"duplicate language id: {language_id}")
        seen.add(language_id)
        path = packages / language_id / FRAGMENT
        if not path.is_file():
            continue
        table = _table(path)
        if table is None:
            continue
        for section, value in table.items():
            if section not in SECTIONS:
                raise ValueError(f"{path}: unknown section {section!r}")
            if section in REASON_SECTIONS:
                if not isinstance(value, str) or not value:
                    raise ValueError(
                        f"{path}: {section} must be a nonempty reason, got {value!r}"
                    )
            elif isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{path}: {section} must be an int, got {value!r}")
            elif value < 1:
                raise ValueError(f"{path}: {section} must be positive")
            sections[section][language_id] = value
    if packages.is_dir():
        for path in packages.glob(f"*/{FRAGMENT}"):
            if path.parent.name not in seen and _table(path) is not None:
                raise ValueError(
                    f"{path}: package {path.parent.name!r} is not registered"
                )
    return sections


def _registry_ids() -> list[str]:
    """Return the registered language ids, in registry order."""
    from esolangs.registry import LANGUAGES

    return [lang.id for lang in LANGUAGES.values()]


def deep_arities(section: str) -> dict[str, object]:
    """Return deep-proof arities for a section, keyed by generator."""
    if section not in SECTIONS:
        raise ValueError(f"unknown deep-arities section: {section!r}")
    return aggregate_fragments(PACKAGES, _registry_ids())[section]
