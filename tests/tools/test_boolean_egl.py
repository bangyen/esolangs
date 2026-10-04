"""Execution tests for the EGL boolean generator."""

from esolangs import tools


def test_the_walk_is_branch_free() -> None:
    """One guard an input, and no other loop: the table is not a tree."""
    program = tools.egl("01101001")
    assert program.count("(") == 3


def test_size_is_table_content_only() -> None:
    """Two tables of one arity and one popcount render to the same length."""
    assert len(tools.egl("01101001")) == len(tools.egl("00001111"))


def test_wrapped_width_budget() -> None:
    table = "10010110"
    for width in (5, 20, 80):
        program = tools.egl(table, width)
        assert max(map(len, program.split("\n"))) <= max(width, len("8,2:"))
