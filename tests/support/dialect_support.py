"""Dialect choices derived from the surviving registry."""

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.registry import LANGUAGES
from tests.support.reference import REFERENCE


def foreign_settings() -> DialectSettings:
    """Return a registered choice unsupported by the reference language."""
    accepted = esolangs.describe(REFERENCE)["dialect_settings"]
    for name in esolangs.list_languages():
        for key, option in esolangs.describe(name)["dialect_settings"].items():
            if key not in accepted:
                return DialectSettings(**{key: option["default"]})
    pytest.skip("no registered foreign dialect choice")


def integer_setting() -> str:
    """Return a registered integer option, or skip when none remain."""
    for language in LANGUAGES.values():
        for key, choices in (language.dialect_values or {}).items():
            if type(choices[0]) is int:
                return key
    pytest.skip("no registered integer dialect choice")
