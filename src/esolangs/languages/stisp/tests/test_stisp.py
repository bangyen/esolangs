"""Tests for the Stisp interpreter."""

from esolangs.languages.stisp.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO


def _result(code: str) -> str:
    io = ScriptedIO()
    run(code, io)
    return io.getvalue()


def test_the_first_matching_equation_wins() -> None:
    assert _result("x -> f[] = FIRST; A -> f[] = SECOND; A -> f[]") == "FIRST"


def test_a_frame_rewrites_to_several_frames_in_order() -> None:
    """``b`` runs before ``c``: the right side's first frame goes on top."""
    machine = _Machine("x -> a[] = x -> b[] -> c[]; A -> a[] -> d[]", ScriptedIO())
    machine.step()
    assert machine.stack == ["A", "b", "c", "d"]


def test_list_sugar_prints_as_a_list() -> None:
    assert _result("x -> id[] = x; (A . (B . ())) -> id[]") == "(A B)"


def test_deep_data_parses_and_prints_without_recursion() -> None:
    deep = "(" * 5000 + "A" + ")" * 5000
    assert _result(deep) == deep
