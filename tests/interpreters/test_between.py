"""Unit tests for the Between interpreter.

Between is a goto-based language: each line is ``<arg1><operation><arg2>``
over string, integer, variable, condition, and none values.  The tests cover
the value types, the operations, the goto control flow, and the documented
spec-gap decisions (0-indexed addresses, doubled-apostrophe strings, comment
lines, integer-zero variable initialization).
"""

from typing import ClassVar

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.between import run
from tests.interpreters.contract import SnapshotContract
from tests.interpreters.runner import run_program


def run_and_capture(code: str, inputs: list[str] | None = None) -> str:
    """Run a Between program, which this file writes as one string."""
    return run_program(
        run,
        code.splitlines(),
        "".join(f"{line}\n" for line in inputs or []),
    )


class TestBasics:
    def test_print_string(self) -> None:
        assert run_and_capture("'Hello, World!'p.\n.x.") == "Hello, World!"

    def test_print_integer(self) -> None:
        assert run_and_capture("|65|p.") == "65"

    def test_print_variable(self) -> None:
        assert run_and_capture("'x'v.\n[x]s|7|\n[x]p.") == "7"

    def test_empty_program(self) -> None:
        assert run_and_capture("") == ""
        assert run_and_capture("\n\n") == ""

    def test_comments_and_blank_lines_skipped(self) -> None:
        code = "# a comment\n\n'x'v.\n[x]s|5|\n[x]p.\n# done"
        assert run_and_capture(code) == "5"

    def test_fall_off_end_halts(self) -> None:
        assert run_and_capture("'ok'p.") == "ok"

    def test_exit_stops_mid_program(self) -> None:
        assert run_and_capture("'a'p.\n.x.\n'b'p.") == "a"

    def test_whitespace_between_tokens(self) -> None:
        assert run_and_capture("'x' v .\n[x] s |3|\n[x] p .") == "3"


class TestOperations:
    def test_set_and_use_variable(self) -> None:
        assert run_and_capture("'a'v.\n[a]s|5|\n[a]p.") == "5"

    def test_variable_defaults_to_integer_zero(self) -> None:
        assert run_and_capture("'a'v.\n[a]p.") == "0"

    def test_set_from_variable(self) -> None:
        assert run_and_capture("'a'v.\n'b'v.\n[a]s|3|\n[b]s[a]\n[b]p.") == "3"

    def test_add_integers(self) -> None:
        assert run_and_capture("||1|+|2||p.") == "3"

    def test_add_variables(self) -> None:
        code = "'a'v.\n'b'v.\n[a]s|2|\n[b]s|3|\n|[a]+[b]|p."
        assert run_and_capture(code) == "5"

    def test_concatenate_strings(self) -> None:
        assert run_and_capture("'foo'+'bar'") == ""

    def test_add_mixed_types_halts(self) -> None:
        with pytest.raises(HaltError, match="two integers"):
            run_and_capture("|1|+'a'")

    def test_multiply(self) -> None:
        assert run_and_capture("||3|*|4||p.") == "12"

    def test_operands_on_both_sides_may_be_variables(self) -> None:
        """Either side of an operation can be a name needing resolution.

        Elsewhere at least one operand is a literal, so the lookup that
        turns a name into a value was never exercised on both sides of the
        same operation -- and an operand left unresolved is not a value of
        any usable type.  Each operation is driven with variables in both
        slots.
        """
        decl = "'x'v.\n[x]s|3|\n'y'v.\n[y]s|2|\n"
        assert run_and_capture(decl + "|[x]*[y]|p.") == "6"
        assert run_and_capture(decl + "|[x]+[y]|p.") == "5"
        assert run_and_capture(decl + "|6|f([x]=[y])\n'no'p.\n'yes'p.") == "noyes"
        assert run_and_capture(decl + "|6|f([x]>[y])\n'no'p.\n'yes'p.") == "yes"

    def test_multiply_non_integer_halts(self) -> None:
        with pytest.raises(HaltError, match="two integers"):
            run_and_capture("'a'*|2|")

    def test_convert_integer_to_string(self) -> None:
        """c on an integer yields a string, usable only as a discarded value."""
        assert run_and_capture("'v'v.\n[v]s|12|\n[v]c.") == ""

    def test_convert_string_to_integer(self) -> None:
        code = "'v'v.\n[v]s'12'\n[v]s|[v]c.|\n[v]p."
        assert run_and_capture(code) == "12"

    def test_convert_non_numeric_halts(self) -> None:
        with pytest.raises(HaltError, match="numerals"):
            run_and_capture("'abc'c.")

    def test_equal_true(self) -> None:
        assert run_and_capture("|3|f(|1|=|1|)\n'eq'p.") == ""

    def test_equal_false_falls_through(self) -> None:
        assert run_and_capture("|9|f(|1|=|2|)\n'eq'p.") == "eq"

    def test_greater(self) -> None:
        assert run_and_capture("|9|f(|3|>|2|)\n'no'p.") == ""

    def test_greater_non_integer_halts(self) -> None:
        with pytest.raises(HaltError, match="two integers"):
            run_and_capture("|1|>'a'")

    def test_or_condition(self) -> None:
        code = "'x'v.\n[x]s|8|\n|9|f(([x]=|7|)r([x]=|8|))\n'no'p."
        assert run_and_capture(code) == ""

    def test_or_non_condition_halts(self) -> None:
        with pytest.raises(HaltError, match="two conditions"):
            run_and_capture("|1|r|2|")

    def test_negate_condition(self) -> None:
        code = "'x'v.\n[x]s|8|\n|3|f(([x]=|7|)n.)\n'yes'p."
        assert run_and_capture(code) == "yes"

    def test_negate_non_condition_halts(self) -> None:
        with pytest.raises(HaltError, match="needs a condition"):
            run_and_capture("|1|n.")


class TestInput:
    def test_read_input(self) -> None:
        code = "'in'v.\n[in]i.\n[in]p."
        assert run_and_capture(code, inputs=["hi"]) == "hi"

    def test_input_arithmetic(self) -> None:
        code = "'n'v.\n[n]i.\n[n]s|[n]c.|\n|[n]+|2||p."
        assert run_and_capture(code, inputs=["5"]) == "7"

    def test_cat(self) -> None:
        code = "'in'v.\n[in]i.\n[in]p.\n.x."
        assert run_and_capture(code, inputs=["hello"]) == "hello"

    def test_input_needs_variable(self) -> None:
        with pytest.raises(HaltError, match="variable"):
            run_and_capture("|1|i.")


class TestControlFlow:
    def test_truth_machine_zero(self) -> None:
        code = "'in'v.\n[in]i.\n|5|f([in]='1')\n|0|p.\n.x.\n|1|p.\n|5|f."
        assert run_and_capture(code, inputs=["0"]) == "0"

    def test_conditional_goto_taken(self) -> None:
        code = "'x'v.\n[x]s|7|\n|9|f([x]=|7|)\n'no'p."
        assert run_and_capture(code) == ""

    def test_conditional_goto_not_taken(self) -> None:
        code = "'x'v.\n[x]s|8|\n|9|f([x]=|7|)\n'yes'p."
        assert run_and_capture(code) == "yes"

    def test_goto_out_of_range_halts(self) -> None:
        assert run_and_capture("'a'p.\n|99|f.") == "a"

    def test_goto_target_from_variable(self) -> None:
        code = "'t'v.\n[t]s|4|\n[t]f.\n'no'p.\n'yes'p."
        assert run_and_capture(code) == "yes"

    def test_goto_target_must_be_integer(self) -> None:
        with pytest.raises(HaltError, match="integer"):
            run_and_capture("'a'f.")

    def test_goto_condition_must_be_condition(self) -> None:
        with pytest.raises(HaltError, match="condition"):
            run_and_capture("|1|f|2|")

    def test_0_indexed_addresses(self) -> None:
        """Line 2 is the third instruction, so goto 2 prints 'two'."""
        code = "'one'p.\n|3|f.\n'two'p.\n'three'p."
        assert run_and_capture(code) == "onethree"


class TestParsing:
    def test_apostrophe_escape(self) -> None:
        assert run_and_capture("'can''t'p.") == "can't"

    def test_a_string_that_is_only_an_escaped_apostrophe(self) -> None:
        """``''''`` is one apostrophe, and the tightest case for the scan.

        ``'can''t'`` has letters on both sides of the pair, so the scan
        reaches it already inside the literal and leaves it with more to
        read.  Here the pair is the whole content: the scan meets it
        immediately after the opening quote, and mistaking either half for
        the terminator ends the string early.
        """
        assert run_and_capture("''''p.") == "'"
        assert run_and_capture("''p.") == ""

    def test_nested_pipe_expression(self) -> None:
        code = "'v'v.\n[v]s|[v]+|1||\n[v]p."
        assert run_and_capture(code) == "1"

    def test_condition_expression_with_pipe(self) -> None:
        code = "'v'v.\n[v]s|1|\n|4|f(|[v]+|2||=|5|)\n'yes'p."
        assert run_and_capture(code) == "yes"

    def test_condition_literal_true(self) -> None:
        assert run_and_capture("|9|f(True)\n'no'p.") == ""

    def test_condition_literal_false(self) -> None:
        assert run_and_capture("|9|f(False)\n'no'p.") == "no"

    def test_malformed_missing_argument(self) -> None:
        with pytest.raises(ValueError, match="missing argument"):
            run_and_capture("'a'p")

    def test_malformed_missing_operation(self) -> None:
        with pytest.raises(ValueError, match="missing operation"):
            run_and_capture("|1|")

    def test_malformed_unknown_operation(self) -> None:
        with pytest.raises(ValueError, match="unknown operation"):
            run_and_capture("|1|q|2|")

    def test_malformed_invalid_argument(self) -> None:
        with pytest.raises(ValueError, match="invalid argument"):
            run_and_capture("a|1|")

    def test_malformed_unbalanced_bracket(self) -> None:
        with pytest.raises(ValueError, match="unbalanced"):
            run_and_capture("|[a]+[b|p.")

    def test_malformed_unbalanced_group(self) -> None:
        """A group whose inner expression ends on the wrong closer."""
        with pytest.raises(ValueError, match="unbalanced"):
            run_and_capture("(|1|=|1|]")

    def test_malformed_unterminated_string(self) -> None:
        with pytest.raises(ValueError, match="unterminated"):
            run_and_capture("'abc")

    @pytest.mark.parametrize("code", ["|.+.", "(.+.", "|.=.", "(.=."])
    def test_malformed_group_running_to_end_of_line(self, code: str) -> None:
        """A group whose expression ends the line has no closer left to read.

        The inner expression consumes the whole line, so the index of the
        closer is one past the end -- the bound has to be checked before
        the character is, or the miss reads off the string and comes back
        as an ``IndexError`` instead of a rejection.
        """
        with pytest.raises(ValueError, match="unbalanced"):
            run_and_capture(code)

    def test_malformed_trailing_characters(self) -> None:
        with pytest.raises(ValueError, match="trailing"):
            run_and_capture("|1|p.x")

    def test_malformed_second_argument(self) -> None:
        with pytest.raises(ValueError, match="no second argument"):
            run_and_capture("|1|p|2|")


class TestErrors:
    def test_print_condition_halts(self) -> None:
        with pytest.raises(HaltError, match="cannot print"):
            run_and_capture("(True)p.")

    def test_print_none_halts(self) -> None:
        with pytest.raises(HaltError, match="cannot print"):
            run_and_capture(".p.")

    def test_undeclared_variable_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared"):
            run_and_capture("[nope]p.")

    def test_declare_variable_name_not_string(self) -> None:
        with pytest.raises(HaltError, match="must be a string"):
            run_and_capture("|1|v.")

    def test_set_needs_variable(self) -> None:
        with pytest.raises(HaltError, match="variable"):
            run_and_capture("|1|s|2|")

    def test_int_expression_produces_non_integer(self) -> None:
        with pytest.raises(HaltError, match="integer expression"):
            run_and_capture("'x'v.\n[x]s|1|\n|[x]=|1||p.")

    def test_condition_expression_produces_non_condition(self) -> None:
        with pytest.raises(HaltError, match="condition expression"):
            run_and_capture("'x'v.\n[x]s'5'\n([x]c.)p.")

    def test_unknown_operation_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown operation"):
            run_and_capture("|1|q.")

    # Every rejection the interpreter can raise, paired with the program
    # that raises it.  The assertions elsewhere in this file use
    # ``pytest.raises(match=...)``, which is a *substring* search and so
    # passes on any message the real one contains -- these compare the
    # whole string, which is what pins the wording down.
    MESSAGES: ClassVar[list[tuple[str, str]]] = [
        ("(True)p.", "p cannot print this value"),
        ("|1|v.", "variable name must be a string"),
        ("|1|s|2|", "s needs a variable on the left"),
        ("'abc'c.", "c needs a string of numerals or an integer"),
        ("|1|+'a'", "+ needs two integers or two strings"),
        ("'a'*|2|", "* needs two integers"),
        ("|1|>'a'", "> needs two integers"),
        ("|1|r|2|", "r needs two conditions"),
        ("|1|n.", "n needs a condition"),
        ("'a'f.", "goto target must be an integer"),
        ("|1|f|2|", "goto condition must be a condition"),
        ("|1|i.", "i needs a variable on the left"),
        ("[nope]p.", "undeclared variable 'nope'"),
        ("'x'v.\n[x]s|1|\n|[x]=|1||p.", "expected an integer expression"),
        ("'x'v.\n[x]s'5'\n([x]c.)p.", "expected a condition expression"),
        ("'a'p", "missing argument"),
        ("|1|", "missing operation"),
        ("|1|q|2|", "unknown operation 'q'"),
        ("a|1|", "invalid argument 'a'"),
        ("|[a]+[b|p.", "unbalanced '['"),
        ("'abc", "unterminated string literal"),
        ("|1|p.x", "trailing characters"),
        ("|1|p|2|", "operation 'p' takes no second argument"),
    ]

    @pytest.mark.parametrize(("code", "message"), MESSAGES)
    def test_rejection_message_is_exact(self, code: str, message: str) -> None:
        """Each rejection says exactly what it says, start to end."""
        with pytest.raises((HaltError, ValueError)) as caught:
            run_and_capture(code)
        assert str(caught.value) == message


def test_a_whole_program_runs_end_to_end() -> None:
    """The shortest program that prints: one string, one ``p``, and a fall-off."""
    assert run_and_capture("'Hi'p.") == "Hi"


class TestStepMachine:
    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.register_based.between import _Machine

        machine = _Machine([], IO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.halted


def _machine(code: object) -> object:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.register_based.between import _Machine

    return _Machine(code, IO())


class TestContract(SnapshotContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program: ClassVar[list[str]] = ["'x'v.", "[x]s|7|"]
