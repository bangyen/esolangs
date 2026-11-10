"""Tests for the Balik interpreter."""

import pytest

from esolangs.languages.balik import interpreter as native
from esolangs.languages.balik.interpreter import run
from esolangs.languages.balik.tests.source_fixtures import _page_loop
from tests.interpreters.runner import native_runner
from tests.support.prepared_support import check_image_reuse

_out = native_runner(run)


def test_increment_wraps_at_three() -> None:
    from esolangs.languages.balik.tests.oracle_checks import (
        check_raw_balik,
    )

    check_raw_balik()
    assert _out("+.+.+.") == "120"


def test_tape_moves_and_input_adds() -> None:
    assert _out(",>,.<.", "2\n1\n") == "12"


def test_page_loop_enters_its_body_on_zero() -> None:
    # The body runs 0 -> 1, 2, 0 and leaves once the cell is 0 again.
    assert _out(_page_loop("   ", "+. ", "   ")) == "120"


def test_page_loop_skips_its_body_on_nonzero() -> None:
    assert _out(_page_loop("+  ", "+. ", ".  ")) == "1"


def test_short_lines_are_padded_not_out_of_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # South from the ``*`` through the empty line's padding to the ``.``;
    # ragged bounds would halt on the empty line and print nothing.
    assert _out("  *\n\n  .") == "0"
    check_image_reuse(
        "Balik",
        "  *\n\n  .",
        native,
        "_prepare_grid",
        monkeypatch,
        cases=(("", "0"),) * 3,
    )


def test_turns_are_clockwise() -> None:
    # East turns south onto the ``.``; anticlockwise would leave north.
    assert _out("+*\n .") == "1"


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown command"):
        _out("+x")
