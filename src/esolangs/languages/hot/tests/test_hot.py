"""Tests for the Hot interpreter."""

import pytest

from esolangs.languages.hot.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO


def test_a_starved_head_gets_f_appended() -> None:
    """``K`` takes two arguments, so the run starts as ``K F F``."""
    machine = _Machine("K", ScriptedIO())
    assert machine.stack == ["K", "F", "F"]
    machine.step()
    assert machine.stack == ["F", "F"]


def test_an_unmatched_close_is_refused() -> None:
    with pytest.raises(ValueError, match="no matching"):
        run("K)", ScriptedIO())


def test_the_empty_program_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one combinator"):
        run(" \n", ScriptedIO())
