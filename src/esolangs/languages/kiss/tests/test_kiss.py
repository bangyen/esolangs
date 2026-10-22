"""Tests for the Kiss interpreter."""

import pytest

from esolangs.languages.kiss.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO


def test_k_exits_zero_and_s_exits_nonzero() -> None:
    assert run("K", ScriptedIO()) == 0
    assert run("S", ScriptedIO()) == 1


def test_the_cat_exits_zero_after_echoing() -> None:
    io = ScriptedIO("1")
    assert run("S (K K) (S K)", io) == 0
    assert io.getvalue() == "1"


def test_only_the_head_is_rewritten() -> None:
    """The argument ``K K K`` stays unreduced while the head outputs."""
    machine = _Machine("K (K K K)", ScriptedIO())
    machine.step()
    assert machine.stack == ["K", "K", "K"]


def test_a_newline_ends_the_input() -> None:
    with pytest.raises(EOFError):
        run("S (K K) (S (K K) (S K))", ScriptedIO("1\n1"))


def test_the_empty_program_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one combinator"):
        run(" \n", ScriptedIO())
