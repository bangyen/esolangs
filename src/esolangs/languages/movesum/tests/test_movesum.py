"""Tests for the Movesum interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.movesum.interpreter import run
from tests.interpreters.runner import native_runner

out = native_runner(run)


def test_unchanged_compares_values_not_keys() -> None:
    from esolangs.languages.movesum.tests.oracle_checks import check_raw_movesum

    check_raw_movesum()
    """Writing 0 to a fresh cell is no change: the truth machine halts on 0."""
    assert out("0=0\nmove 0 -1\nmove 0 7") == "0"
    assert out("0=42\nmove 0 -1\nmove 0 1\nmove 2 1", "0\n") == "0"


def test_a_change_resets_the_count() -> None:
    """Two quiet commands halt; a changing one between them keeps it going."""
    assert out("0=1\nmove 0 -1\nmove 0 2\nmove 0 -1\nmove 0 0") == "1 1"


def test_sum_adds_cells_one_to_four() -> None:
    code = "0=9 1=1 2=2 3=3 4=4 5=100\nsum\nmove 0 -1\nmove 0 0"
    assert out(code) == "10"


def test_both_negative_is_a_quiet_command() -> None:
    assert out("0=5\nmove -1 -1\nmove -2 -3\nmove 0 -1") == ""


def test_42_as_key_reads_before_the_value(monkeypatch) -> None:
    assert out("42=42\nmove 5 -1\nmove 0 0", "5\n7\n") == "7"
    from esolangs.languages.movesum import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Movesum",
        "42=42\nmove 5 -1\nmove 0 0",
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("5\n7\n", "7"), ("5\n8\n", "8"), ("5\n9\n", "9")),
    )


def test_eof_reads_zero() -> None:
    assert out("1=42\nmove 1 -1\nmove 0 0") == "0"
    assert out("0=9\nmove -1 0\nmove 0 -1\nmove 0 0") == "0"


def test_no_separator_trails_and_blank_lines_are_skipped() -> None:
    assert out("0=1 1=2\n\nmove 0 -1\n\nmove 1 -1\nmove 0 0\n") == "1 2"


def test_the_array_is_unbounded_to_the_right() -> None:
    assert out("0=3\nmove 0 100000\nmove 100000 -1\nmove 0 0") == "3"


def test_a_negative_input_is_refused() -> None:
    with pytest.raises(HaltError, match="negative"):
        out("0=0\nmove -1 1\nmove 1 -1", "-1\n")
