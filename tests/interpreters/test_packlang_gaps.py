"""Packlang paths the wiki examples never take.

Every case here is a malformed or edge-shaped program run through the
real parser and machine: the error paths, the parameterized datatypes,
and the clamping and array-indexing arms the five examples never reach.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import (
    _evaluate,
    _Function,
    _int,
    _Machine,
    _node,
    _Parser,
    _pending_call,
    _Program,
    _substitute,
    _Type,
    _visible,
    run,
)
from tests.interpreters.runner import run_program


def _run(code: str, stdin: str = "") -> str:
    return run_program(run, code, stdin)


def _wrap(body: str, decls: str = "") -> str:
    return f"Package : IO {{\n  {decls}\n  Integer main {{\n{body}\n    0;\n  }}\n}} p;"


class TestTypeClamp:
    """``_Type.clamp`` folds out-of-range values to the wrap targets."""

    def test_below_low_takes_the_under_value(self) -> None:
        assert _Type(0, 255).clamp(-1) == 255

    def test_above_high_takes_the_over_value(self) -> None:
        assert _Type(0, 255).clamp(256) == 0

    def test_in_range_is_unchanged(self) -> None:
        assert _Type(0, 255).clamp(7) == 7

    def test_explicit_wrap_targets_win(self) -> None:
        kind = _Type(0, 10, under=3, over=4)
        assert kind.clamp(-5) == 3
        assert kind.clamp(99) == 4


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


class TestInternalGuards:
    """Malformed-tree guards, which no source program can trip.

    They defend an internal invariant rather than validate input, so the
    node is built here directly -- the parser never emits one.
    """

    def test_a_non_tuple_child_slot_is_refused(self) -> None:
        with pytest.raises(HaltError, match="malformed expression node"):
            _node(5)

    def test_a_tuple_child_slot_passes_through(self) -> None:
        assert _node(("lit", 1)) == ("lit", 1)

    def test_a_non_integer_scalar_is_refused(self) -> None:
        with pytest.raises(HaltError, match="expected a number"):
            _int("x")

    def test_a_bool_is_not_a_number(self) -> None:
        # ``bool`` is an ``int`` subclass, so it needs its own rejection.
        flag: object = True
        with pytest.raises(HaltError, match="expected a number"):
            _int(flag)

    def test_an_unknown_expression_kind_is_refused(self) -> None:
        with pytest.raises(HaltError, match="cannot evaluate"):
            _evaluate(("bogus", 0), (), _Program(), "p")

    def test_length_of_a_scalar_is_refused(self) -> None:
        with pytest.raises(HaltError, match="is not an array"):
            _evaluate(("length", "cell"), (("cell", 0),), _Program(), "p")

    def test_length_of_an_array_is_its_row_size(self) -> None:
        store = (("row", (0, 0, 0)),)
        assert _evaluate(("length", "row"), store, _Program(), "p") == 3

    def test_an_unresolved_call_is_refused(self) -> None:
        node = ("apply", "nope", (("lit", 0),))
        with pytest.raises(HaltError, match="unresolved call"):
            _evaluate(node, (), _Program(), "p")

    def test_indexing_takes_exactly_one_index(self) -> None:
        node = ("apply", "row", (("lit", 0), ("lit", 1)))
        store = (("row", (0, 0)),)
        with pytest.raises(HaltError, match="takes exactly one index"):
            _evaluate(node, store, _Program(), "p")


class TestParserScanAhead:
    """``is_declaration`` scans ahead and rewinds, swallowing the error."""

    def test_a_bad_type_is_not_a_declaration(self) -> None:
        parser = _Parser(["Widget", "name", ";"])
        assert parser.is_declaration() is False
        # The rewind is what lets the caller re-read the same tokens.
        assert parser.pos == 0

    def test_a_type_without_a_name_is_not_a_declaration(self) -> None:
        parser = _Parser(["Integer", "(", ")"])
        assert parser.is_declaration() is False

    def test_a_type_then_a_name_then_a_semicolon_is_one(self) -> None:
        assert _Parser(["Integer", "cell", ";"]).is_declaration() is True


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


class TestPendingCallAndSubstitute:
    """``not`` and array-index arms of the two expression walkers."""

    def test_not_is_searched_for_a_pending_call(self) -> None:
        node = ("not", ("apply", "f", ()))
        assert _pending_call(node, (), _Program(), "p") == ("apply", "f", ())

    def test_an_array_index_is_not_a_pending_call(self) -> None:
        node = ("apply", "row", (("lit", 0),))
        assert _pending_call(node, (("row", (0, 0)),), _Program(), "p") is None

    def test_a_call_inside_an_index_is_found_first(self) -> None:
        node = ("apply", "row", (("apply", "f", ()),))
        store = (("row", (0, 0)),)
        assert _pending_call(node, store, _Program(), "p") == ("apply", "f", ())

    def test_an_unknown_kind_has_no_pending_call(self) -> None:
        assert _pending_call(("bogus", 0), (), _Program(), "p") is None

    def test_substitute_rewrites_under_not(self) -> None:
        target = ("apply", "f", ())
        assert _substitute(("not", target), target, 7) == ("not", ("done", 7))

    def test_substitute_rewrites_an_index_argument(self) -> None:
        target = ("apply", "f", ())
        node = ("apply", "row", (target,))
        assert _substitute(node, target, 7) == ("apply", "row", (("done", 7),))

    def test_substitute_leaves_an_unknown_kind_alone(self) -> None:
        node = ("bogus", 0)
        assert _substitute(node, ("apply", "f", ()), 7) is node


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
