"""The ``[audits]`` dates the roadmap's progress lines are generated from."""

import datetime
from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES
from scripts.docs.audits import _validate, rows


def test_every_recorded_audit_parses() -> None:
    assert rows()


def test_a_plain_rewrite_audit_names_a_generator() -> None:
    stray = [
        name
        for name, row in rows().items()
        if "plain_rewrite" in row and LANGUAGES[name].boolean is None
    ]
    assert stray == []


@pytest.mark.parametrize(
    "row",
    [{"plain_rewite": datetime.date(2026, 10, 27)}, {"plain_rewrite": "2026-10-27"}],
)
def test_a_misspelled_key_or_quoted_date_is_refused(row: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="audits"):
        _validate(Path("language.toml"), row)
