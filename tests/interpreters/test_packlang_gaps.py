"""Packlang paths the wiki examples never take.

Every case here is a malformed or edge-shaped program run through the
real parser and machine: the error paths, the parameterized datatypes,
and the clamping and array-indexing arms the five examples never reach.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.other.packlang import (
    _Function,
    _Program,
    _visible,
    run,
)
from tests.interpreters.runner import run_program


def _run(code: str, stdin: str = "") -> str:
    return run_program(run, code, stdin)


def _wrap(body: str, decls: str = "") -> str:
    return f"Package : IO {{\n  {decls}\n  Integer main {{\n{body}\n    0;\n  }}\n}} p;"


class TestParameterizedTypes:
    """``Integer(...)``, ``Array(...)`` and ``Pointer(...)`` declarations."""

    def test_a_non_numeric_type_parameter_is_refused(self) -> None:
        with pytest.raises(ValueError, match="expected a number"):
            _run(_wrap("    0;", "Array(Integer, xyz) row;"))

    def test_a_missing_closing_paren_is_refused(self) -> None:
        with pytest.raises(ValueError, match="expected"):
            _run(_wrap("    0;", "Array(Integer, 3 row;"))


class TestMalformedPrograms:
    def test_a_top_level_word_that_is_not_a_package_is_refused(self) -> None:
        with pytest.raises(ValueError, match="expected a Package or Dependency"):
            _run("Widget : IO {\n  Integer main {\n    0;\n  }\n} p;")

    def test_charput_needs_exactly_one_argument(self) -> None:
        with pytest.raises(ValueError, match="charPut takes exactly one"):
            _run(_wrap("    charPut(65, 66);"))

    def test_charget_needs_a_variable(self) -> None:
        with pytest.raises(ValueError, match="charGet takes exactly one variable"):
            _run(_wrap("    charGet(65 ^ 1);"))

    def test_an_assignment_target_must_be_a_name(self) -> None:
        with pytest.raises(ValueError, match="expected a variable name"):
            _run(_wrap("    INCR 5;"))


class TestArrayRuntime:
    def test_an_array_has_no_scalar_value(self) -> None:
        with pytest.raises(HaltError, match="is an array and has no scalar value"):
            _run(_wrap("    charPut(row);", "Array(Integer, 2) row;"))

    def test_indexing_a_scalar_halts(self) -> None:
        with pytest.raises(HaltError, match="is not an array"):
            _run(_wrap("    charPut(cell(0));", "Integer cell;"))

    def test_an_index_outside_the_row_halts(self) -> None:
        with pytest.raises(HaltError, match="is outside"):
            _run(_wrap("    charPut(row(9));", "Array(Integer, 2) row;"))

    def test_writing_a_scalar_with_an_index_halts(self) -> None:
        with pytest.raises(HaltError, match="is not an array"):
            _run(_wrap("    INCR cell(0);", "Integer cell;"))

    def test_writing_an_array_without_an_index_halts(self) -> None:
        with pytest.raises(HaltError, match="needs an index"):
            _run(_wrap("    INCR row;", "Array(Integer, 2) row;"))

    def test_writing_outside_the_row_halts(self) -> None:
        with pytest.raises(HaltError, match="is outside"):
            _run(_wrap("    INCR row(9);", "Array(Integer, 2) row;"))


class TestCallErrors:
    def test_calling_with_the_wrong_arity_halts(self) -> None:
        program = """
Dependency {
  Integer helper : Integer a {
    a;
  }
} lib;
Package : lib, IO {
  Integer main {
    charPut(helper(1, 2));
    0;
  }
} p;
"""
        with pytest.raises(HaltError, match="takes 1 arguments"):
            _run(program)


class TestTransitiveDependencies:
    def test_a_diamond_dependency_is_walked_once(self) -> None:
        """Two paths reach the same package; the second is skipped.

        ``top`` depends on ``left`` and ``right``, both of which depend on
        ``base`` -- so the walk meets ``base`` twice and must not requeue
        it.  The call succeeds, which is what shows the walk terminated.
        """
        program = """
Dependency {
  Integer helper : Integer a {
    a;
  }
} base;
Dependency : base {
  Integer viaLeft : Integer a {
    a;
  }
} left;
Dependency : base {
  Integer viaRight : Integer a {
    a;
  }
} right;
Package : left, right, IO {
  Integer main {
    charPut(helper(65));
    0;
  }
} top;
"""
        assert _run(program) == "A"

    def test_a_package_reached_twice_is_not_rewalked(self) -> None:
        """The diamond's shared arm is dequeued a second time and skipped.

        Built as a graph rather than a program because the walk returns as
        soon as it meets the target: the re-visit only happens on a miss,
        so the target is a package the graph does not reach at all.
        """
        program = _Program()
        program.dependencies = {
            "top": frozenset({"left", "right"}),
            "left": frozenset({"base"}),
            "right": frozenset({"base"}),
            "base": frozenset(),
        }
        func = _Function("f", (), (), "elsewhere", {})
        assert _visible(func, "top", program) is False
