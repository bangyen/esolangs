"""Deep proof measurements: per-generator tuning lives in a fixture."""

import tomllib
from pathlib import Path

_TUNING = Path(__file__).resolve().parents[2] / "fixtures" / "deep_arities.toml"


def deep_arities(section: str) -> dict[str, object]:
    """One section of ``tests/fixtures/deep_arities.toml``, keyed by generator."""
    return tomllib.loads(_TUNING.read_text(encoding="utf-8"))[section]
