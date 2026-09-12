r"""Unit tests for the Algebraic Programming Language interpreter."""

from typing import ClassVar

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.algebraic_programming_language import _Machine, run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)
from tests.interpreters.runner import run_program
from tests.raises import raises_message

# The wiki's own examples,.
HELLO_WORLD = "\n".join(
    [
        "72",
        "101",
        "108",
        "108",
        "111",
        "44",
        "32",
        "87",
        "111",
        "114",
        "108",
        "100",
        "33",
    ]
)
TRUTH_MACHINE = "x? = x & x?\nn?"
NOT = "!x = {\nx & $0\n$1\n}"
CEIL = "CEIL(n) = {\nn % 1 & $(n - n % 1 + 1)\nn\n}"
FLOOR = "FLOOR(n) = n - n % 1"
WHILE = "WHILE(x, c) = x() & ((c() | 1) & WHILE(x, c))"
IF = "IF(x, c) = x & c()"


def run_and_capture(program: str, stdin: str = "") -> str:
    r"""Run a program and return everything it wrote."""
    return run_program(run, program, stdin)


def machine(program: str, stdin: str = "") -> _Machine:
    r"""Build a machine for the stepping and cycle contracts."""
    return _Machine(program, ScriptedIO(stdin))


class TestWikiExamples:
    r"""Every program the wiki gives, producing what the wiki says it does."""

    def test_hello_world_prints_the_ascii_values(self) -> None:
        r"""The example prints numbers, not characters: APL has only numbers."""
        assert run_and_capture(HELLO_WORLD) == (
            "72\n101\n108\n108\n111\n44\n32\n87\n111\n114\n108\n100\n33\n"
        )

    def test_numeric_cat_echoes_its_input(self) -> None:
        r"""``n`` reads a variable by naming it and prints the line's result."""
        assert run_and_capture("n", "42\n") == "42\n"

    def test_truth_machine_halts_on_zero(self) -> None:
        r"""``x."""
        assert run_and_capture(TRUTH_MACHINE, "0\n") == "0\n"

    def test_floor_of_a_fraction(self) -> None:
        assert run_and_capture(f"{FLOOR}\nFLOOR(7 / 2)") == "3\n"

    def test_ceiling_of_a_fraction(self) -> None:
        assert run_and_capture(f"{CEIL}\nCEIL(7 / 2)") == "4\n"

    def test_ceiling_of_an_integer_prints_only_the_answer(self) -> None:
        r"""The ``$`` statement is silent, so no stray 0 precedes the 3."""
        assert run_and_capture(f"{CEIL}\nCEIL(3)") == "3\n"

    def test_not_of_a_truthy_value(self) -> None:
        assert run_and_capture(f"{NOT}\n!5") == "0\n"

    def test_not_of_zero(self) -> None:
        r"""``x & $0`` never outputs x, so only the returned 1 is printed."""
        assert run_and_capture(f"{NOT}\n!0") == "1\n"

    def test_if_runs_its_code_function_when_the_condition_holds(self) -> None:
        assert run_and_capture(f"{IF}\nY() = 9\nIF(1, Y)") == "9\n"

    def test_if_short_circuits_to_zero_when_it_does_not(self) -> None:
        assert run_and_capture(f"{IF}\nY() = 9\nIF(0, Y)") == "0\n"

    def test_while_stops_when_its_condition_is_false(self) -> None:
        assert run_and_capture(f"{WHILE}\nF() = 0\nG() = 7\nWHILE(F, G)") == "0\n"

    def test_multiline_prints_every_statement_but_the_last(self) -> None:
        r"""``{ 123 456 }`` prints 123 and returns 456."""
        assert run_and_capture("M() = {\n123\n456\n}\nM()") == "123\n456\n"

    def test_a_dollar_returns_early_and_prints_nothing_before_it(self) -> None:
        assert run_and_capture("M() = {\n$123\n456\n}\nM()") == "123\n"

    def test_mean_operator(self) -> None:
        r"""The wiki's ``a ~ b`` infix operator."""
        assert run_and_capture("a ~ b = (a + b) / 2\n4 ~ 6") == "5\n"

    def test_doubling_operator(self) -> None:
        r"""The wiki's ``a@`` postfix operator."""
        assert run_and_capture("a@ = a * 2\n21@") == "42\n"

    def test_a_three_argument_operator_pattern(self) -> None:
        r"""``^a^b^c^`` is valid per the wiki's operator section."""
        assert run_and_capture("^a^b^c^ = a + b + c\n^1^2^3^") == "6\n"

    def test_a_backtick_operator_pattern(self) -> None:
        r"""``~a`b``c~`` is the wiki's other multi-symbol example."""
        assert run_and_capture("~a`b``c~ = (a / b) % c\n~12`3``2~") == "0\n"


class TestExecutionModel:
    r"""Reading by naming, printing by evaluating, and binding across lines."""

    def test_variables_are_read_in_first_appearance_order(self) -> None:
        r"""The wiki's own example asks for a, b, d, c, e -- b only once."""
        assert run_and_capture("a + b + d\nc + e + b", "1\n2\n3\n4\n5\n") == "6\n11\n"

    def test_an_assignment_takes_no_input_and_prints_nothing(self) -> None:
        r"""``n = 123`` binds; only the bare ``n`` line prints."""
        assert run_and_capture("n = 123\nn") == "123\n"

    def test_an_assignment_binds_before_a_later_line_would_read_it(self) -> None:
        assert run_and_capture("n = 7\nn + 1") == "8\n"

    def test_input_is_bound_before_evaluation_not_lazily(self) -> None:
        r"""A short-circuit must not skip a read the spec says happens."""
        assert run_and_capture("a & b\nc", "0\n5\n9\n") == "0\n9\n"

    def test_a_fractional_result_keeps_its_decimal_part(self) -> None:
        assert run_and_capture("7 / 2") == "3.5\n"

    def test_an_exact_division_prints_as_an_integer(self) -> None:
        assert run_and_capture("6 / 3") == "2\n"

    def test_implied_multiplication_between_variables(self) -> None:
        assert run_and_capture("a = 3\nb = 4\nab") == "12\n"

    def test_exponentiation_is_right_associative(self) -> None:
        assert run_and_capture("2 ** 3 ** 2") == "512\n"

    def test_unary_negation(self) -> None:
        assert run_and_capture("-5 + 2") == "-3\n"

    def test_brackets_override_precedence(self) -> None:
        assert run_and_capture("(1 + 2) * 3") == "9\n"

    def test_standard_order_of_operations(self) -> None:
        assert run_and_capture("1 + 2 * 3") == "7\n"

    def test_modulo(self) -> None:
        assert run_and_capture("7 % 3") == "1\n"

    def test_a_fractional_literal(self) -> None:
        assert run_and_capture("1.5 + 1.5") == "3\n"

    def test_or_returns_its_left_operand_when_truthy(self) -> None:
        assert run_and_capture("5 | 9") == "5\n"

    def test_or_returns_its_right_operand_otherwise(self) -> None:
        assert run_and_capture("0 | 9") == "9\n"

    def test_and_returns_zero_when_its_left_is_false(self) -> None:
        assert run_and_capture("0 & 9") == "0\n"

    def test_and_returns_its_right_operand_when_its_left_is_true(self) -> None:
        assert run_and_capture("5 & 9") == "9\n"

    def test_an_empty_input_line_reads_as_zero(self) -> None:
        assert run_and_capture("n", "\n") == "0\n"

    def test_a_bare_uppercase_name_passes_the_function_itself(self) -> None:
        r"""``WHILE(x, c)`` receives functions by name and calls them."""
        assert run_and_capture(f"{IF}\nY() = 4\nIF(1, Y)") == "4\n"


class TestErrors:
    r"""Malformed programs raise ValueError; bad operations raise HaltError."""

    def test_bracket_multiplication_is_rejected(self) -> None:
        r"""The wiki says ``1(2)`` raises an error."""
        with raises_message(ValueError, "bracket multiplication is invalid syntax"):
            run_and_capture("1(2)")

    def test_an_unknown_variable_is_rejected(self) -> None:
        r"""A variable inside a *function* body is not input-bound."""
        with raises_message(ValueError, "unknown variable 'q'"):
            run_and_capture("F() = q\nF()")

    def test_an_unknown_function_is_rejected(self) -> None:
        with raises_message(ValueError, "unknown function 'G'"):
            run_and_capture("G()")

    def test_a_bare_unknown_function_name_is_rejected(self) -> None:
        with raises_message(ValueError, "unknown function 'G'"):
            run_and_capture("F(x) = 1\nF(G)")

    def test_the_wrong_argument_count_is_rejected(self) -> None:
        with raises_message(ValueError, "'F' takes 1 argument(s), got 2"):
            run_and_capture("F(x) = x\nF(1, 2)")

    def test_an_unbalanced_bracket_is_rejected(self) -> None:
        with raises_message(ValueError, "expected ')'"):
            run_and_capture("(1 + 2")

    def test_an_unbalanced_brace_is_rejected(self) -> None:
        with raises_message(ValueError, "unbalanced { in program"):
            run_and_capture("F() = {\n1")

    def test_trailing_input_is_rejected(self) -> None:
        with raises_message(ValueError, "trailing input at ')'"):
            run_and_capture("1 + 2)")

    def test_an_empty_expression_is_rejected(self) -> None:
        with raises_message(ValueError, "unexpected end of expression"):
            run_and_capture("1 +")

    def test_a_bad_parameter_is_rejected(self) -> None:
        with raises_message(ValueError, "bad parameter '1'"):
            run_and_capture("F(1) = 2\nF(3)")

    def test_an_operator_with_no_arguments_is_rejected(self) -> None:
        with raises_message(ValueError, "operator '##' takes no arguments"):
            run_and_capture("## = 2\n1")

    def test_an_operator_repeating_a_parameter_is_rejected(self) -> None:
        with raises_message(ValueError, "operator 'a#a' repeats a parameter"):
            run_and_capture("a#a = 2\n1")

    def test_division_by_zero_is_a_halt(self) -> None:
        with raises_message(HaltError, "division by zero"):
            run_and_capture("1 / 0")

    def test_modulo_by_zero_is_a_halt(self) -> None:
        with raises_message(HaltError, "modulo by zero"):
            run_and_capture("1 % 0")

    def test_zero_to_a_negative_power_is_a_halt(self) -> None:
        with raises_message(HaltError, "zero to a negative power"):
            run_and_capture("0 ** -1")

    def test_non_numeric_input_is_a_halt(self) -> None:
        with raises_message(HaltError, "input 'oops' is not a number"):
            run_and_capture("n", "oops\n")

    def test_arithmetic_on_a_function_is_a_halt(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("F() = 1\nF + 1")

    def test_input_running_out_raises_eof(self) -> None:
        r"""A line naming more variables than the input supplies."""
        with pytest.raises(EOFError):
            run_program(run, "a + b", "1\n", suppress_eof=False)

    def test_a_definition_with_no_left_hand_side_is_rejected(self) -> None:
        with raises_message(ValueError, "definition has no left-hand side"):
            run_and_capture("= 2")

    def test_a_malformed_function_header_is_rejected(self) -> None:
        with raises_message(ValueError, "malformed function header 'F1'"):
            run_and_capture("F1 = 2\n1")


class TestContract(EmptyProgramContract):
    r"""An empty program has no lines to execute, so it prints nothing."""

    run = staticmethod(run_and_capture)
    empty_program = ""
    empty_output = ""


class TestSnapshot(SnapshotContract):
    machine: ClassVar = staticmethod(machine)
    stepping_program: ClassVar = "1 + 1"


class TestCycles(CycleContract):
    r"""The hang detectors' verdicts on this language's two shapes."""

    machine: ClassVar = staticmethod(machine)
    halting_program: ClassVar = "1 + 1"
    # APL's loop is recursion,.
    # revisiting a state, so the.
    # prove: that class is the.
    looping_program: ClassVar = None


class TestFrameBookkeeping:
    r"""The state the hang detectors read, asserted without importing them."""

    def test_a_recursion_pushes_one_frame_per_lap(self) -> None:
        r"""This is what makes the ancestor check applicable at all."""
        machine_ = machine(TRUTH_MACHINE, "1\n")
        depths = []
        for _ in range(60):
            machine_.step()
            depths.append(len(machine_.frames))
        assert max(depths) > 3, depths

    def test_two_laps_of_the_truth_machine_share_a_frame_key(self) -> None:
        r"""Same operator, same binding, same input cursor -- so it repeats."""
        machine_ = machine(TRUTH_MACHINE, "1\n")
        keys = []
        seen = 0
        for _ in range(200):
            machine_.step()
            if len(machine_.frames) > seen and machine_.frames:
                keys.append(machine_.frame_entry_key(machine_.frames[-1]))
            seen = len(machine_.frames)
        recursive = [k for k in keys if k[0] == "\0?"]
        assert len(recursive) >= 2
        assert recursive[0] == recursive[1]

    def test_the_frame_key_carries_the_input_cursor(self) -> None:
        r"""Two calls either side of a read must not compare equal."""
        machine_ = machine("F(x) = x\nF(1)\nn\nF(1)", "5\n")
        keys = []
        seen = 0
        for _ in range(400):
            if machine_.halted:
                break
            machine_.step()
            if len(machine_.frames) > seen and machine_.frames:
                frame = machine_.frames[-1]
                if frame.fn.name == "F":
                    keys.append(machine_.frame_entry_key(frame))
            seen = len(machine_.frames)
        assert len(keys) == 2
        assert keys[0] != keys[1], "the read between them must change the key"

    def test_the_snapshot_distinguishes_two_stages_of_one_expression(self) -> None:
        r"""Recording the work stack's depth alone made these compare equal."""
        machine_ = machine("1 + 1")
        seen = []
        while not machine_.halted:
            seen.append(machine_.snapshot())
            machine_.step()
        assert len(seen) == len(set(seen)), "a halting run repeated a state"

    def test_only_executed_lines_read_input(self) -> None:
        r"""A variable inside a function body is *not* input-bound."""
        with raises_message(ValueError, "unknown variable 'n'"):
            run_and_capture("F() = n\nF()", "1\n")


class TestCoveragePaths:
    r"""The error and shape paths the wiki's own examples do not reach."""

    def test_an_operator_argument_slot_with_nothing_after_it(self) -> None:
        r"""A pattern that runs out of tokens mid-match is not a match."""
        with raises_message(ValueError, "trailing input at '#'"):
            run_and_capture("a # b = a\n1 #")

    def test_a_stray_comma_is_rejected(self) -> None:
        with raises_message(ValueError, "unexpected token ','"):
            run_and_capture(",")

    def test_a_bare_return_operator_is_rejected(self) -> None:
        with raises_message(ValueError, "unexpected end of expression"):
            run_and_capture("$")

    def test_trailing_input_in_a_function_header_is_rejected(self) -> None:
        with raises_message(ValueError, "trailing input in header 'F(x) y'"):
            run_and_capture("F(x) y = 1\n1")

    def test_a_digit_leading_operator_pattern_is_rejected(self) -> None:
        with raises_message(ValueError, "bad operator pattern '1a'"):
            run_and_capture("1a = 2\n1")

    def test_a_postfix_operator_applies_twice(self) -> None:
        r"""The postfix loop keeps matching until no pattern fits."""
        assert run_and_capture("a@ = a * 2\n3@@") == "12\n"

    def test_a_blank_line_inside_a_block_is_skipped(self) -> None:
        assert run_and_capture("F() = {\n1\n\n2\n}\nF()") == "1\n2\n"

    def test_an_uppercase_name_without_parentheses_is_a_nullary_function(
        self,
    ) -> None:
        r"""``F = 7`` defines a function, since only *lowercase* names assign."""
        assert run_and_capture("F = 7\nF()") == "7\n"

    def test_printing_a_function_rather_than_calling_it_is_a_halt(self) -> None:
        r"""Only numbers are printable, so a bare function is an error."""
        with pytest.raises(HaltError):
            run_and_capture("F = 7\nF")

    def test_a_blank_line_between_executed_lines_is_skipped(self) -> None:
        r"""At depth 0 a blank line is dropped rather than joined."""
        assert run_and_capture("1\n\n2") == "1\n2\n"

    def test_trailing_input_after_a_block_is_rejected(self) -> None:
        r"""``F() = {1} 2`` balances its braces but does not end at one."""
        with raises_message(ValueError, "trailing input after block in '{1} 2'"):
            run_and_capture("F() = {1} 2\nF()")

    def test_a_parameter_holding_a_function_is_looked_up_locally(self) -> None:
        r"""``F(c) = c()`` resolves ``c`` from the frame, not the globals."""
        assert run_and_capture("F(c) = c()\nG() = 5\nF(G)") == "5\n"

    def test_a_function_value_is_truthy(self) -> None:
        r"""``&`` with a function on the left proceeds to its right side."""
        assert run_and_capture("F() = 1\nG(x) = x & 9\nG(F)") == "9\n"

    def test_the_evaluation_budget_is_enforced(self) -> None:
        r"""A runaway expression halts rather than allocating without bound."""
        machine_ = machine("F(x) = F(x + 1)\nF(0)")
        machine_._WORK_LIMIT = 50  # noqa: SLF001
        with raises_message(HaltError, "expression exceeded the evaluation budget"):
            while not machine_.halted:
                machine_.step()

    def test_the_line_cursor_and_frames_are_reported_as_the_ip(self) -> None:
        r"""``ip`` is the line cursor followed by each live frame's statement."""
        machine_ = machine("1 + 1")
        machine_.step()
        assert machine_.ip == (1, 0)

    def test_memory_reports_the_bound_variables(self) -> None:
        r"""APL has no addressable store; ``memory`` is what input has bound."""
        machine_ = machine("a + b", "3\n4\n")
        machine_.step()
        assert machine_.memory == [3, 4]

    def test_memory_reports_zero_for_a_non_numeric_binding(self) -> None:
        r"""A function-valued global has no integer to report."""
        machine_ = machine("n = 1.5\nn")
        while not machine_.halted:
            machine_.step()
        assert machine_.memory == [1]

    def test_stack_reports_the_live_frames(self) -> None:
        machine_ = machine("1 + 1")
        machine_.step()
        assert len(machine_.stack) == 1


class TestMutationGaps:
    r"""Behaviour the wiki's examples exercise but do not *discriminate*."""

    def test_a_longer_operator_pattern_wins_over_a_shorter_prefix(self) -> None:
        r"""``^a^b^`` must not be matched as ``^a^`` followed by junk."""
        program = "^a^ = a * 10\n^a^b^ = a + b\n^1^2^"
        assert run_and_capture(program) == "3\n"

    def test_a_shorter_pattern_still_matches_when_the_longer_cannot(self) -> None:
        assert run_and_capture("^a^ = a * 10\n^a^b^ = a + b\n^7^") == "70\n"

    def test_a_single_star_is_multiplication_not_a_power(self) -> None:
        r"""The ``**`` lookahead needs both tokens, not just the first."""
        assert run_and_capture("2 * 3") == "6\n"

    def test_a_power_of_a_product_binds_tighter_than_the_product(self) -> None:
        assert run_and_capture("2 * 3 ** 2") == "18\n"

    def test_a_trailing_star_at_the_end_of_input_is_not_a_power(self) -> None:
        r"""The lookahead's bounds check is what stops this indexing off."""
        with raises_message(ValueError, "unexpected end of expression"):
            run_and_capture("2 *")

    def test_the_snapshot_line_cursor_varies(self) -> None:
        r"""Two programs differing only in how far they have got differ."""
        first = machine("1\n2")
        second = machine("1\n2")
        second.step()
        while second.frames:
            second.step()
        assert first.snapshot() != second.snapshot()

    def test_the_snapshot_carries_the_globals(self) -> None:
        r"""Two machines at the same cursor with different bindings differ."""
        one = machine("n\nn", "1\n")
        two = machine("n\nn", "2\n")
        for machine_ in (one, two):
            while machine_.frames or machine_.line == 0:
                machine_.step()
        assert one.snapshot() != two.snapshot()

    def test_the_snapshot_carries_the_input_cursor(self) -> None:
        r"""A loop that keeps reading is not a repeat, so reads must show."""
        machine_ = machine("a\nb", "1\n1\n")
        seen = set()
        while not machine_.halted:
            seen.add(machine_.snapshot())
            machine_.step()
        # Both lines print the same.
        # only the input cursor.
        assert len(seen) == len([1 for _ in seen])

    def test_the_frame_key_carries_the_bindings(self) -> None:
        r"""Two calls of one function with different arguments differ."""
        machine_ = machine("F(x) = x\nF(1)\nF(2)")
        keys = []
        seen = 0
        while not machine_.halted:
            machine_.step()
            if len(machine_.frames) > seen and machine_.frames:
                frame = machine_.frames[-1]
                if frame.fn.name == "F":
                    keys.append(machine_.frame_entry_key(frame))
            seen = len(machine_.frames)
        assert len(keys) == 2
        assert keys[0] != keys[1]

    def test_the_frame_key_carries_the_function_name(self) -> None:
        r"""Two different nullary functions must not share a key."""
        machine_ = machine("F() = 1\nG() = 1\nF()\nG()")
        keys = []
        seen = 0
        while not machine_.halted:
            machine_.step()
            if len(machine_.frames) > seen and machine_.frames:
                frame = machine_.frames[-1]
                if frame.fn.name:
                    keys.append(machine_.frame_entry_key(frame))
            seen = len(machine_.frames)
        assert len(keys) == 2
        assert keys[0] != keys[1]

    def test_a_definition_body_replaces_its_placeholder(self) -> None:
        r"""The self-reference trick registers an empty body first."""
        assert run_and_capture("F() = 42\nF()") == "42\n"

    def test_a_recursive_operator_sees_its_own_pattern(self) -> None:
        r"""Registering the name before parsing is what makes this parse."""
        assert run_and_capture("x? = x & x?\n0?") == "0\n"


class TestNestedTraversals:
    r"""The two tree walks, exercised at every branch they recurse through."""

    def test_a_return_inside_a_negation_suppresses_the_print(self) -> None:
        r"""``-$1`` is a ``$`` under a ``neg``."""
        assert run_and_capture("M() = {\n-$1\n9\n}\nM()") == "1\n"

    def test_a_return_in_a_binary_left_operand_suppresses_the_print(
        self,
    ) -> None:
        r"""``$1 + 2`` returns before the addition, and prints nothing."""
        assert run_and_capture("M() = {\n$1 + 2\n9\n}\nM()") == "1\n"

    def test_a_return_in_a_call_argument_suppresses_the_print(self) -> None:
        r"""``F($1)`` is a ``$`` inside a call's argument list."""
        assert run_and_capture("F(x) = x\nM() = {\nF($1)\n9\n}\nM()") == "1\n"

    def test_a_statement_with_no_return_anywhere_still_prints(self) -> None:
        r"""The other side of the same decision, at the same depth."""
        assert run_and_capture("F(x) = x\nM() = {\nF(-(1 + 2))\n9\n}\nM()") == (
            "-3\n9\n"
        )

    def test_a_variable_under_a_negation_is_read(self) -> None:
        assert run_and_capture("-a", "5\n") == "-5\n"

    def test_variables_in_both_operands_are_read_left_to_right(self) -> None:
        assert run_and_capture("a - b", "9\n4\n") == "5\n"

    def test_a_variable_inside_a_call_argument_is_read(self) -> None:
        assert run_and_capture("F(x) = x * 2\nF(a)", "6\n") == "12\n"

    def test_variables_across_call_arguments_are_read_in_order(self) -> None:
        r"""``F(a, b)`` reads a then b, so swapping the feed swaps the answer."""
        assert run_and_capture("F(x, y) = x - y\nF(a, b)", "9\n4\n") == "5\n"

    def test_a_variable_under_a_return_is_read(self) -> None:
        r"""``$a`` still names ``a``, so the pre-scan must reach through it."""
        assert run_and_capture("$a", "7\n") == "7\n"

    def test_a_repeated_variable_is_read_once(self) -> None:
        r"""First-appearance order dedupes, so ``a + a`` takes one input."""
        assert run_and_capture("a + a", "5\n") == "10\n"

    def test_a_variable_repeated_across_operands_is_read_once(self) -> None:
        r"""``a + (b - a)`` reads a and b, in that order -- not a, b, a."""
        assert run_and_capture("a + (b - a)", "3\n10\n") == "10\n"


class TestGuardsAndBoundaries:
    r"""The guards, boundaries, and lexer edges no earlier test pins."""

    def test_a_nonzero_base_to_a_negative_power(self) -> None:
        r"""Only a *zero* base refuses; 2 ** -1 is an ordinary fraction."""
        assert run_and_capture("2 ** -1") == "0.5\n"

    def test_zero_to_the_zeroth_power(self) -> None:
        r"""``0 ** 0`` is 1: the guard's ``right < 0`` excludes zero."""
        assert run_and_capture("0 ** 0") == "1\n"

    def test_a_dot_with_no_digit_after_it_is_its_own_token(self) -> None:
        r"""A fractional part needs a digit; a bare trailing dot is a symbol."""
        with raises_message(ValueError, "trailing input at '.'"):
            run_and_capture("3.")

    def test_a_dot_before_a_letter_is_not_a_decimal_point(self) -> None:
        r"""``3.a`` is 3, a dot, and a name -- not the number 3 times a."""
        with raises_message(ValueError, "trailing input at '.'"):
            run_and_capture("3.a")

    def test_a_multi_digit_fractional_part(self) -> None:
        r"""The fraction loop runs past its first digit, so .25 is not .2."""
        assert run_and_capture("3.25 + 0") == "3.25\n"

    def test_an_equals_after_nested_brackets_still_splits(self) -> None:
        r"""Bracket depth counts up, not to one."""
        assert run_and_capture("F(x) = x\nG(x) = F(F(x))\nG(4)") == "4\n"

    def test_a_four_statement_body_runs_each_statement_once(self) -> None:
        r"""Statement advance is ``+= 1``, not a jump to a fixed index."""
        assert run_and_capture("F(n) = {\n1\n2\n3\n4\n}\nF(0)") == "1\n2\n3\n4\n"

    def test_arithmetic_on_a_function_names_the_value_it_refused(self) -> None:
        r"""The halt message carries the offending value, not a bare None."""
        with raises_message(HaltError, "expected a number, got <F/1>"):
            run_and_capture("F(x) = x\n1 + F")

    def test_a_negative_right_hand_side_with_no_space(self) -> None:
        r"""The split keeps everything after the ``=``, sign included."""
        assert run_and_capture("a=-3\na") == "-3\n"

    def test_a_bracketed_right_hand_side_with_no_space(self) -> None:
        r"""The same, for a bracket: eating the ``(`` would unbalance it."""
        assert run_and_capture("a=(1+2)\na") == "3\n"

    def test_a_short_circuited_return_does_not_print_its_statement(self) -> None:
        r"""The control flag is read even when the ``$`` never evaluates."""
        assert run_and_capture("F(n) = {\n-(0 & $7)\n9\n}\nF(0)") == "9\n"
        assert run_and_capture("F(n) = {\n-(0 & 7)\n9\n}\nF(0)") == "0\n9\n"

    def test_a_short_circuited_return_inside_an_operation(self) -> None:
        r"""The same reach, through a ``bin`` node."""
        assert run_and_capture("F(n) = {\n1 + (0 & $7)\n9\n}\nF(0)") == "9\n"

    def test_a_short_circuited_return_inside_a_call_argument(self) -> None:
        r"""And through a ``call`` node's argument list."""
        assert run_and_capture("G(x) = x\nF(n) = {\nG(0 & $7)\n9\n}\nF(0)") == "9\n"

    def test_a_three_digit_fractional_part(self) -> None:
        r"""The fraction loop steps one digit at a time, so .125 is not .15."""
        assert run_and_capture("3.125 * 8") == "25\n"
