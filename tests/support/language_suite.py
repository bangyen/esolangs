"""Collect a language's existing cases through a uniform suite entry point."""

from importlib import import_module
from pathlib import Path
from typing import Any, Literal

import pytest

LANGUAGES = Path(__file__).resolve().parents[2] / "src/esolangs/languages"


def register_case_assertions() -> None:
    """Rewrite assertions before cross-suite imports load any case modules."""
    modules = [
        "esolangs.languages."
        + ".".join(path.relative_to(LANGUAGES).with_suffix("").parts)
        for path in sorted(LANGUAGES.glob("*/tests/*_cases.py"))
    ]
    pytest.register_assert_rewrite(*modules)


def load_suite(
    namespace: dict[str, Any], language: str, kind: Literal["interpreter", "generator"]
) -> None:
    """Expose cases and fixtures without changing their defining module."""
    if kind not in {"interpreter", "generator"}:
        raise ValueError(f"unknown suite kind: {kind}")
    cases = import_module(f"esolangs.languages.{language}.tests.{kind}_cases")
    namespace.update(
        (name, value)
        for name, value in vars(cases).items()
        if not name.startswith("__")
    )
