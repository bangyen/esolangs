"""Tests for the Sonata interpreter."""

from esolangs.languages.sonata.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO


def _step(code: str, text: str) -> str:
    machine = _Machine(code, ScriptedIO(text))
    machine.step()
    return machine.text


def test_the_page_duplicates_the_first_character() -> None:
    assert _step("^A_B->^A^A_B", "abc") == "aabc"


def test_the_page_binds_the_shortest_substrings() -> None:
    """The page's ``aabb`` gives ``,ab``, not ``a,b``."""
    assert _step("_Aa_Bb->_A,_B", "aabb") == ",ab"


def test_one_trailing_newline_leaves_the_input() -> None:
    io = ScriptedIO("ab\n")
    run("ab->ok", io)
    assert io.getvalue() == "ok"


def test_a_later_arrow_is_literal() -> None:
    io = ScriptedIO("a")
    run("a->b->c", io)
    assert io.getvalue() == "b->c"
