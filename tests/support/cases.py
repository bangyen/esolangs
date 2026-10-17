"""A language's ``tests/cases.toml``: wiki examples and spec/generator triggers.

One file per language, so its cases leave with it.  Keys: ``language`` and
``oldid`` (the cited wiki revision) with ``[[examples]]``; ``[[spec_triggers]]``
and ``[spec_untriggerable]`` for the interpreter's ``Errors:``;
``[[generator_triggers]]`` and ``[generator_untriggerable]`` for the
generator's ``Raises:``.  A ``*_file`` value is relative to ``tests/``.
"""

import tomllib
from pathlib import Path
from typing import Any

LANGUAGES_DIR = Path(__file__).resolve().parents[2] / "src/esolangs/languages"


def cases_path(language_id: str) -> Path:
    """Return the language's cases file, present or not."""
    return LANGUAGES_DIR / language_id / "tests" / "cases.toml"


def cases(language_id: str) -> dict[str, Any]:
    """Return the language's cases, or an empty table."""
    path = cases_path(language_id)
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
