"""Tests for the Balik interpreter."""

from pathlib import Path

import pytest

from esolangs import ExecutionLimits, Language, ProgramError
from esolangs.languages.balik import interpreter as native
from esolangs.languages.balik.interpreter import run
from esolangs.languages.balik.tests.source_fixtures import _page_loop
from tests.interpreters.runner import native_runner
from tests.support.cli_support import run_cli
from tests.support.prepared_support import check_image_reuse
from tests.support.vm_support import (
    assert_rejected_input_retry,
    assert_rejected_output_retry,
)


@pytest.mark.medium
def test_rejected_input_stays_with_the_failed_step() -> None:
    assert_rejected_input_retry(
        "Balik", ",.", "x1", "1", "1", position=1, reads=1, rejected="x"
    )


_out = native_runner(run)


def test_increment_wraps_at_three() -> None:
    from esolangs.languages.balik.tests.oracle_checks import (
        check_raw_balik,
    )

    check_raw_balik()
    assert _out("+.+.+.") == "120"


def test_tape_moves_and_input_adds(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _out(",>,.<.", "2\n1\n") == "12"
    assert_rejected_output_retry(
        "Balik",
        ",.",
        2,
        "2",
        prefix=1,
        stdin="2x",
        monkeypatch=monkeypatch,
        unchanged_if_unwritten=True,
        following_writes=(),
    )


def test_page_loop_enters_its_body_on_zero() -> None:
    # The body runs 0 -> 1, 2, 0 and leaves once the cell is 0 again.
    assert _out(_page_loop("   ", "+. ", "   ")) == "120"


def test_page_loop_skips_its_body_on_nonzero() -> None:
    assert _out(_page_loop("+  ", "+. ", ".  ")) == "1"


def test_short_lines_are_padded_not_out_of_bounds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # South from the ``*`` through the empty line's padding to the ``.``;
    # ragged bounds would halt on the empty line and print nothing.
    assert _out("  *\n\n  .") == "0"
    api = Language("Balik")
    path = tmp_path / "source"
    limits = ExecutionLimits(max_steps=10)
    for newline in ("\n", "\r\n"):
        source = newline.join(("  *", "", "  .", ""))
        path.write_bytes(source.encode())
        assert api.run(path).unwrap().output == "0"
        bounded = api.run(path, limits=limits).unwrap()
        assert (bounded.output, bounded.steps) == ("0", 6)
        assert api.run(path, limits=limits, isolated=True).unwrap() == bounded
        cli = run_cli("run", api.name, str(path))
        assert (cli.returncode, cli.stdout, cli.stderr) == (0, "0", "")
    with pytest.raises(ProgramError, match="unknown command"):
        api.run("  *\r  .").unwrap()
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
