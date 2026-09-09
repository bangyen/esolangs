"""Function x(y) programs the wiki's examples never spell: the rejections."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.function_x_y import (
    _advance,
    _const,
    _Function,
    run,
)


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestParseErrors:
    def test_a_missing_expression_is_refused(self) -> None:
        with pytest.raises(ValueError, match="expression expected"):
            _run("function f()\n-> ")

    def test_a_lone_minus_is_not_a_number(self) -> None:
        with pytest.raises(ValueError, match="expected a number"):
            _run("function f()\n-> -")

    def test_a_var_without_a_colon_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed variable declaration"):
            _run("function f()\nvar x\n-> 0")

    def test_a_var_without_a_name_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed variable declaration"):
            _run("function f()\nvar 1:0\n-> 0")

    def test_a_parameter_that_is_not_a_name_is_refused(self) -> None:
        with pytest.raises(ValueError, match="malformed parameter"):
            _run("function f(1)\n-> 0")


class TestBinaryOperators:
    def test_a_space_that_no_operator_follows_is_not_one(self) -> None:
        """The space is necessary but not sufficient: the word must match.

        Refused as trailing input rather than parsed as an operator, which
        is what keeps ``a < b`` a comparison and ``)<(`` a ternary.
        """
        with pytest.raises(ValueError, match="trailing input"):
            _run("function f(n)\n-> n &1")


class TestUnknownNodeKind:
    def test_a_node_the_parser_never_emits_halts(self) -> None:
        """``_advance``'s dispatch is exhaustive over the parsed kinds.

        No program spells this node; it guards the invariant that every
        kind the parser can build has an arm here.
        """
        function = _Function("f", [], [])
        frame = (0, 0, (), (("bogus",),))
        with pytest.raises(HaltError, match="unknown expression"):
            _advance((frame,), [], [function], {"f": 0})


class TestParameterDefaults:
    def test_a_literal_default_is_taken(self) -> None:
        assert _const(("lit", 7)) == 7

    def test_a_string_default_is_taken(self) -> None:
        assert _const(("lit", "hi")) == "hi"

    def test_a_computed_default_is_refused(self) -> None:
        with pytest.raises(ValueError, match="must be a literal"):
            _const(("var", "n"))
