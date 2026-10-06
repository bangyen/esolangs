"""Packlang paths the wiki examples never take."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import (
    _Machine,
    run,
)
from tests.interpreters.runner import run_program


def _run(code: str, stdin: str = "") -> str:
    return run_program(run, code, stdin)


def _wrap(body: str, decls: str = "") -> str:
    return f"Package : IO {{\n  {decls}\n  Integer main {{\n{body}\n    0;\n  }}\n}} p;"


class TestParameterizedTypes:
    """``Integer(...)``, ``Array(...)`` and ``Pointer(...)`` declarations."""

    def test_a_pointer_declares_the_type_it_points_at(self) -> None:
        program = _wrap(
            "    INCR cell;\n    charPut(cell ^ 64);", "Pointer(Integer) cell;"
        )
        assert _run(program) == "A"

    def test_an_array_declares_a_row_of_cells(self) -> None:
        program = _wrap(
            "    INCR row(1);\n    charPut(row(1) ^ 64);", "Array(Integer, 3) row;"
        )
        assert _run(program) == "A"

    def test_an_integer_with_bounds_wraps_at_them(self) -> None:
        program = _wrap(
            "    DECR cell;\n    charPut(cell);", "Integer(0, 65, 65, 0) cell;"
        )
        assert _run(program) == "A"

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
    def test_charget_reads_into_an_array_element(self) -> None:
        program = _wrap(
            "    charGet(row(0));\n    charPut(row(0));", "Array(Char, 2) row;"
        )
        assert _run(program, "A") == "A"

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

    def test_init_resets_a_whole_array(self) -> None:
        program = _wrap(
            "    INCR row(0);\n    INIT row;\n    charPut(row(0) ^ 65);",
            "Array(Integer, 2) row;",
        )
        assert _run(program) == "A"


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


class TestMachineMemory:
    def test_memory_flattens_an_array_into_its_cells(self) -> None:
        program = _wrap("    INCR row(1);\n    0;", "Array(Integer, 3) row;")
        machine = _Machine(program, ScriptedIO(""))
        seen: list[object] = []
        for _ in range(200):
            if machine.halted:
                break
            machine.step()
            if machine.memory:
                seen = machine.memory
        # The row is flattened in place: three cells, the middle one written.
        assert seen == [0, 1, 0]

    def test_memory_is_empty_once_the_frames_are_gone(self) -> None:
        machine = _Machine(_wrap("    0;"), ScriptedIO(""))
        machine.frames.clear()
        assert machine.memory == []
