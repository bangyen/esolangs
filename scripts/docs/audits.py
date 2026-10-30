"""Load the one-off audit dates from each language package's ``language.toml``.

``[audits]`` records when a language passed a one-off audit:
``plain_rewrite`` (every bespoke trick priced against the plain
construction), ``blind_reimplementation`` (a clean-room interpreter
from the wiki page, diffed over the generated corpus),
``docstring_reimplementation`` (the same, from the page plus the
interpreter docstring; a spot check, not a round) and ``trick_prototype``
(a generator searched for one admissible size trick, shipped or not).  A
package with no ``[audits]`` section has passed none.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from .fragments import registry, sections

ROOT = Path(__file__).resolve().parents[2]

FIELDS = (
    "plain_rewrite",
    "blind_reimplementation",
    "docstring_reimplementation",
    "trick_prototype",
)


def _validate(path: Path, row: dict[str, Any]) -> dict[str, datetime.date]:
    """Return ``row`` after checking it holds only known keys with dates."""
    unknown = set(row) - set(FIELDS)
    if unknown:
        raise ValueError(f"{path}: unknown audits keys {sorted(unknown)}")
    for key, value in row.items():
        if not isinstance(value, datetime.date):
            raise ValueError(f"{path}: audits.{key} must be a bare TOML date")
    return dict(row)


def rows(root: Path = ROOT) -> dict[str, dict[str, datetime.date]]:
    """Return every audited language's dates, keyed by name, in registry order."""
    return {
        lang.name: _validate(path, row)
        for lang, path, row in sections(
            root / "src/esolangs/languages", registry(), "audits"
        )
    }
