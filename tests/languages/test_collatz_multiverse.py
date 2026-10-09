"""Collatz Multiverse through the shared API, CLI and machinery."""

import pytest

from esolangs.interpreters.register_based.collatz_multiverse import (
    suggest_corrections as _collatz_corrections,
)
from tests.cli_support import assert_repair_runs, repaired


def test_collatz_repair_executes(tmp_path, capsys):
    assert_repair_runs(
        "Collatz Multiverse", "a = b x + c, do PRNIT.", "\x00", tmp_path, capsys
    )


def test_collatz_identifiers_are_untouched():
    source = "print = do x + not, do PRNIT."
    result = repaired(source, _collatz_corrections(source))
    assert result == "print = do x + not, DO PRINT."


@pytest.mark.parametrize(
    "source",
    [
        "a = 3 x + 1, do PRINT.",
        "do PRNIT.",
        "a = b x + c, DO PRINT.",
        "a = b x + c, DOT PRINT.",  # an ambiguous keyword
    ],
)
def test_collatz_invalid_prefix_or_valid_source_has_no_edits(source):
    assert not _collatz_corrections(source)
