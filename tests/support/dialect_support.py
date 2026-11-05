"""Dialect choices derived from the surviving registry."""

from io import StringIO

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.registry import LANGUAGES
from tests.support.pick import languages
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
        for key, choices in (language.runtime.dialect_values or {}).items():
            if type(choices[0]) is int:
                return key
    pytest.skip("no registered integer dialect choice")


def _chosen(name: str) -> DialectSettings:
    """Every setting off its default, where the generator targets that."""
    schema = esolangs.describe(name)["dialect_settings"]
    off = {
        k: next(c for c in i["choices"] if c != i["default"]) for k, i in schema.items()
    }
    try:
        esolangs.generate(name, "01", settings=DialectSettings(**off))
    except esolangs.ArgumentError:
        return DialectSettings(**{k: i["default"] for k, i in schema.items()})
    return DialectSettings(**off)


CASES = [
    (name, _chosen(name))
    for name in languages()
    if esolangs.describe(name)["dialect_settings"]
]


class Unreadable(StringIO):
    """Fail if argument validation consumes the source or input."""

    def read(self, *_args, **_kwargs):
        raise AssertionError("read before dialect validation")
