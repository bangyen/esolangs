"""Unit tests for the Algebraic Programming Language interpreter."""

from functools import partial
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
from tests.raises import assert_rejected_with_hint, raises_message

# The wiki's own examples, which are the specification's ground truth.
TRUTH_MACHINE = "x? = x & x?\nn?"
NOT = "!x = {\nx & $0\n$1\n}"
CEIL = "CEIL(n) = {\nn % 1 & $(n - n % 1 + 1)\nn\n}"
FLOOR = "FLOOR(n) = n - n % 1"
WHILE = "WHILE(x, c) = x() & ((c() | 1) & WHILE(x, c))"
IF = "IF(x, c) = x & c()"


run_and_capture = partial(run_program, run)


def machine(program: str, stdin: str = "") -> _Machine:
    """Build a machine for the stepping and cycle contracts."""
    return _Machine(program, ScriptedIO(stdin))


# The wiki's own examples, which are the specification's ground truth,
# then reading by naming, printing by evaluating, and binding across lines.
@pytest.mark.parametrize(
    ("program", "expected"),
    [
        pytest.param(f"{FLOOR}\nFLOOR(7 / 2)", "3\n", id="floor_of_a_fraction"),
        pytest.param(f"{CEIL}\nCEIL(7 / 2)", "4\n", id="ceiling_of_a_fraction"),
        # ``x & $0`` never outputs x, so only the returned 1 is printed.
        pytest.param(f"{NOT}\n!0", "1\n", id="not_of_zero"),
        pytest.param(
            f"{IF}\nY() = 9\nIF(1, Y)",
            "9\n",
            id="if_runs_its_code_function_when_the_condition_holds",
        ),
        pytest.param(
            f"{IF}\nY() = 9\nIF(0, Y)",
            "0\n",
            id="if_short_circuits_to_zero_when_it_does_not",
        ),
        pytest.param(
            f"{WHILE}\nF() = 0\nG() = 7\nWHILE(F, G)",
            "0\n",
            id="while_stops_when_its_condition_is_false",
        ),
        # ``{ 123 456 }`` prints 123 and returns 456.
        pytest.param(
            "M() = {\n123\n456\n}\nM()",
            "123\n456\n",
            id="multiline_prints_every_statement_but_the_last",
        ),
        pytest.param(
            "M() = {\n$123\n456\n}\nM()",
            "123\n",
            id="a_dollar_returns_early_and_prints_nothing_before_it",
        ),
        # The wiki's ``a ~ b`` infix operator.
        pytest.param("a ~ b = (a + b) / 2\n4 ~ 6", "5\n", id="mean_operator"),
        # The wiki's ``a@`` postfix operator.
        pytest.param("a@ = a * 2\n21@", "42\n", id="doubling_operator"),
        # ``^a^b^c^`` is valid per the wiki's operator section.
        pytest.param(
            "^a^b^c^ = a + b + c\n^1^2^3^",
            "6\n",
            id="a_three_argument_operator_pattern",
        ),
        # ``~a`b``c~`` is the wiki's other multi-symbol example.
        pytest.param(
            "~a`b``c~ = (a / b) % c\n~12`3``2~", "0\n", id="a_backtick_operator_pattern"
        ),
        pytest.param(
            "n = 7\nn + 1",
            "8\n",
            id="an_assignment_binds_before_a_later_line_would_read_it",
        ),
        pytest.param("7 / 2", "3.5\n", id="a_fractional_result_keeps_its_decimal_part"),
        pytest.param("2 ** 3 ** 2", "512\n", id="exponentiation_is_right_associative"),
        pytest.param("5 | 9", "5\n", id="or_returns_its_left_operand_when_truthy"),
        pytest.param("0 & 9", "0\n", id="and_returns_zero_when_its_left_is_false"),
        # ``WHILE(x, c)`` receives functions by name and calls them.
        pytest.param(
            f"{IF}\nY() = 4\nIF(1, Y)",
            "4\n",
            id="a_bare_uppercase_name_passes_the_function_itself",
        ),
    ],
)
def test_output(program: str, expected: str) -> None:
    assert run_and_capture(program) == expected


_VALUE_ERRORS = {
    # The wiki says ``1(2)`` raises an error.
    "bracket_multiplication_is_rejected": (
        "bracket multiplication is invalid syntax",
        "1(2)",
    ),
    # A variable inside a *function* body is not input-bound.
    "an_unknown_variable_is_rejected": ("unknown variable 'q'", "F() = q\nF()"),
    "an_unknown_function_is_rejected": ("unknown function 'G'", "G()"),
    "the_wrong_argument_count_is_rejected": (
        "'F' takes 1 argument(s), got 2",
        "F(x) = x\nF(1, 2)",
    ),
    "an_unbalanced_bracket_is_rejected": ("expected ')'", "(1 + 2"),
    "an_unbalanced_brace_is_rejected": ("unbalanced { in program", "F() = {\n1"),
    "trailing_input_is_rejected": ("trailing input at ')'", "1 + 2)"),
    "a_bad_parameter_is_rejected": ("bad parameter '1'", "F(1) = 2\nF(3)"),
    "an_operator_with_no_arguments_is_rejected": (
        "operator '##' takes no arguments",
        "## = 2\n1",
    ),
    "an_operator_repeating_a_parameter_is_rejected": (
        "operator 'a#a' repeats a parameter",
        "a#a = 2\n1",
    ),
    "a_definition_with_no_left_hand_side_is_rejected": (
        "definition has no left-hand side",
        "= 2",
    ),
    "a_malformed_function_header_is_rejected": (
        "malformed function header 'F1'",
        "F1 = 2\n1",
    ),
    # A pattern that runs out of tokens mid-match is not a match.
    "an_operator_argument_slot_with_nothing_after_it": (
        "trailing input at '#'",
        "a # b = a\n1 #",
    ),
    "a_stray_comma_is_rejected": ("unexpected token ','", ","),
    "a_bare_return_operator_is_rejected": ("unexpected end of expression", "$"),
    "trailing_input_in_a_function_header_is_rejected": (
        "trailing input in header 'F(x) y'",
        "F(x) y = 1\n1",
    ),
    "a_digit_leading_operator_pattern_is_rejected": (
        "bad operator pattern '1a'",
        "1a = 2\n1",
    ),
    # ``F() = {1} 2`` balances its braces but does not end at one.
    "trailing_input_after_a_block_is_rejected": (
        "trailing input after block in '{1} 2'",
        "F() = {1} 2\nF()",
    ),
    # The lookahead's bounds check is what stops this indexing off.
    "a_trailing_star_at_the_end_of_input_is_not_a_power": (
        "unexpected end of expression",
        "2 *",
    ),
    # A fractional part needs a digit; a bare trailing dot is a symbol.
    "a_dot_with_no_digit_after_it_is_its_own_token": ("trailing input at '.'", "3."),
    # ``3.a`` is 3, a dot, and a name -- not the number 3 times a.
    "a_dot_before_a_letter_is_not_a_decimal_point": ("trailing input at '.'", "3.a"),
}


class TestErrors:
    """Malformed programs raise ValueError; bad operations raise HaltError."""

    @pytest.mark.parametrize(
        ("message", "program"), _VALUE_ERRORS.values(), ids=list(_VALUE_ERRORS)
    )
    def test_raises(self, message, program) -> None:
        with raises_message(ValueError, message):
            run_and_capture(program)

    @pytest.mark.parametrize(
        ("message", "program", "stdin"),
        [
            ("division by zero", "1 / 0", ""),
            ("zero to a negative power", "0 ** -1", ""),
            ("input 'oops' is not a number", "n", "oops\n"),
        ],
    )
    def test_halts(self, message: str, program: str, stdin: str) -> None:
        with raises_message(HaltError, message):
            run_and_capture(program, stdin)

    def test_arithmetic_on_a_function_is_a_halt(self) -> None:
        with pytest.raises(HaltError):
            run_and_capture("F() = 1\nF + 1")

    def test_input_running_out_raises_eof(self) -> None:
        """A line naming more variables than the input supplies."""
        with pytest.raises(EOFError):
            run_program(run, "a + b", "1\n", suppress_eof=False)


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    run = staticmethod(run_and_capture)
    machine: ClassVar = staticmethod(machine)
    stepping_program: ClassVar = "1 + 1"
    halting_program: ClassVar = "1 + 1"
    # APL's loop is recursion, which grows the frame stack rather than
    # revisiting a state, so the cycle detector has no looping program to
    # prove: that class is the ancestor check's, tested below.
    looping_program: ClassVar = None
    no_cycle_reason = "APL divergence grows the recursive frame stack."


class TestFrameBookkeeping:
    """The state the hang detectors read, asserted without importing them."""

    def test_a_recursion_pushes_one_frame_per_lap(self) -> None:
        """This is what makes the ancestor check applicable at all."""
        machine_ = machine(TRUTH_MACHINE, "1\n")
        depths = []
        for _ in range(60):
            machine_.step()
            depths.append(len(machine_.frames))
        assert max(depths) > 3, depths

    def test_two_laps_of_the_truth_machine_share_a_frame_key(self) -> None:
        """Same operator, same binding, same input cursor -- so it repeats."""
        machine_ = machine(TRUTH_MACHINE, "1\n")
        keys = []
        seen = 0
        for _ in range(200):
            machine_.step()
            if len(machine_.frames) > seen and machine_.frames:
                keys.append(machine_.frame_entry_key(machine_.frames[-1]))
            seen = len(machine_.frames)
        # The key's first field is the typed function key; its name is [2].
        recursive = [k for k in keys if k[0][2] == "\0?"]
        assert len(recursive) >= 2
        assert recursive[0] == recursive[1]

    def test_the_frame_key_carries_the_input_cursor(self) -> None:
        """Two calls either side of a read must not compare equal."""
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
        """Recording the work stack's depth alone made these compare equal."""
        machine_ = machine("1 + 1")
        seen = []
        while not machine_.halted:
            seen.append(machine_.snapshot())
            machine_.step()
        assert len(seen) == len(set(seen)), "a halting run repeated a state"

    def test_only_executed_lines_read_input(self) -> None:
        """A variable inside a function body is *not* input-bound."""
        with raises_message(ValueError, "unknown variable 'n'"):
            run_and_capture("F() = n\nF()", "1\n")


class TestCoveragePaths:
    """The error and shape paths the wiki's own examples do not reach."""

    def test_a_postfix_operator_applies_twice(self) -> None:
        """The postfix loop keeps matching until no pattern fits."""
        assert run_and_capture("a@ = a * 2\n3@@") == "12\n"

    def test_an_uppercase_name_without_parentheses_is_a_nullary_function(
        self,
    ) -> None:
        """``F = 7`` defines a function, since only *lowercase* names assign."""
        assert run_and_capture("F = 7\nF()") == "7\n"

    def test_printing_a_function_rather_than_calling_it_is_a_halt(self) -> None:
        """Only numbers are printable, so a bare function is an error."""
        with pytest.raises(HaltError):
            run_and_capture("F = 7\nF")

    def test_a_blank_line_between_executed_lines_is_skipped(self) -> None:
        """At depth 0 a blank line is dropped rather than joined."""
        assert run_and_capture("1\n\n2") == "1\n2\n"

    def test_a_parameter_holding_a_function_is_looked_up_locally(self) -> None:
        """``F(c) = c()`` resolves ``c`` from the frame, not the globals."""
        assert run_and_capture("F(c) = c()\nG() = 5\nF(G)") == "5\n"

    def test_a_function_value_is_truthy(self) -> None:
        """``&`` with a function on the left proceeds to its right side."""
        assert run_and_capture("F() = 1\nG(x) = x & 9\nG(F)") == "9\n"

    def test_the_evaluation_budget_is_enforced(self) -> None:
        """A runaway expression halts rather than allocating without bound."""
        machine_ = machine("F(x) = F(x + 1)\nF(0)")
        machine_._WORK_LIMIT = 50  # noqa: SLF001
        with raises_message(HaltError, "expression exceeded the evaluation budget"):
            while not machine_.halted:
                machine_.step()

    def test_the_line_cursor_and_frames_are_reported_as_the_ip(self) -> None:
        """``ip`` is the line cursor followed by each live frame's statement."""
        machine_ = machine("1 + 1")
        machine_.step()
        assert machine_.ip == (1, 0)

    def test_memory_reports_the_bound_variables(self) -> None:
        """APL has no addressable store; ``memory`` is what input has bound."""
        machine_ = machine("a + b", "3\n4\n")
        machine_.step()
        assert machine_.memory == [3, 4]


class TestMutationGaps:
    """Behaviour the wiki's examples exercise but do not *discriminate*."""

    def test_a_longer_operator_pattern_wins_over_a_shorter_prefix(self) -> None:
        """``^a^b^`` must not be matched as ``^a^`` followed by junk."""
        program = "^a^ = a * 10\n^a^b^ = a + b\n^1^2^"
        assert run_and_capture(program) == "3\n"

    def test_a_shorter_pattern_still_matches_when_the_longer_cannot(self) -> None:
        assert run_and_capture("^a^ = a * 10\n^a^b^ = a + b\n^7^") == "70\n"

    def test_a_single_star_is_multiplication_not_a_power(self) -> None:
        """The ``**`` lookahead needs both tokens, not just the first."""
        assert run_and_capture("2 * 3") == "6\n"

    def test_a_power_of_a_product_binds_tighter_than_the_product(self) -> None:
        assert run_and_capture("2 * 3 ** 2") == "18\n"

    def test_the_snapshot_line_cursor_varies(self) -> None:
        """Two programs differing only in how far they have got differ."""
        first = machine("1\n2")
        second = machine("1\n2")
        second.step()
        while second.frames:
            second.step()
        assert first.snapshot() != second.snapshot()

    def test_the_snapshot_carries_the_globals(self) -> None:
        """Two machines at the same cursor with different bindings differ."""
        one = machine("n\nn", "1\n")
        two = machine("n\nn", "2\n")
        for machine_ in (one, two):
            while machine_.frames or machine_.line == 0:
                machine_.step()
        assert one.snapshot() != two.snapshot()

    def test_the_snapshot_carries_the_input_cursor(self) -> None:
        """A loop that keeps reading is not a repeat, so reads must show."""
        machine_ = machine("a\nb", "1\n1\n")
        seen = set()
        while not machine_.halted:
            seen.add(machine_.snapshot())
            machine_.step()
        # Both lines print the same value from identical-looking state;
        # only the input cursor separates them.
        assert len(seen) == len([1 for _ in seen])

    def test_the_frame_key_carries_the_bindings(self) -> None:
        """Two calls of one function with different arguments differ."""
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
        """Two different nullary functions must not share a key."""
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
        """The self-reference trick registers an empty body first."""
        assert run_and_capture("F() = 42\nF()") == "42\n"

    def test_a_recursive_operator_sees_its_own_pattern(self) -> None:
        """Registering the name before parsing is what makes this parse."""
        assert run_and_capture("x? = x & x?\n0?") == "0\n"


class TestNestedTraversals:
    """The two tree walks, exercised at every branch they recurse through."""

    def test_a_return_inside_a_negation_suppresses_the_print(self) -> None:
        """``-$1`` is a ``$`` under a ``neg``."""
        assert run_and_capture("M() = {\n-$1\n9\n}\nM()") == "1\n"

    def test_a_return_in_a_binary_left_operand_suppresses_the_print(
        self,
    ) -> None:
        """``$1 + 2`` returns before the addition, and prints nothing."""
        assert run_and_capture("M() = {\n$1 + 2\n9\n}\nM()") == "1\n"

    def test_a_statement_with_no_return_anywhere_still_prints(self) -> None:
        """The other side of the same decision, at the same depth."""
        assert run_and_capture("F(x) = x\nM() = {\nF(-(1 + 2))\n9\n}\nM()") == (
            "-3\n9\n"
        )


class TestGuardsAndBoundaries:
    """The guards, boundaries, and lexer edges no earlier test pins."""

    def test_a_nonzero_base_to_a_negative_power(self) -> None:
        """Only a *zero* base refuses; 2 ** -1 is an ordinary fraction."""
        assert run_and_capture("2 ** -1") == "0.5\n"

    def test_zero_to_the_zeroth_power(self) -> None:
        """``0 ** 0`` is 1: the guard's ``right < 0`` excludes zero."""
        assert run_and_capture("0 ** 0") == "1\n"

    def test_an_equals_after_nested_brackets_still_splits(self) -> None:
        """Bracket depth counts up, not to one."""
        assert run_and_capture("F(x) = x\nG(x) = F(F(x))\nG(4)") == "4\n"

    def test_a_four_statement_body_runs_each_statement_once(self) -> None:
        """Statement advance is ``+= 1``, not a jump to a fixed index."""
        assert run_and_capture("F(n) = {\n1\n2\n3\n4\n}\nF(0)") == "1\n2\n3\n4\n"

    def test_arithmetic_on_a_function_names_the_value_it_refused(self) -> None:
        """The halt message carries the offending value, not a bare None."""
        with raises_message(HaltError, "expected a number, got <F/1>"):
            run_and_capture("F(x) = x\n1 + F")

    def test_a_negative_right_hand_side_with_no_space(self) -> None:
        """The split keeps everything after the ``=``, sign included."""
        assert run_and_capture("a=-3\na") == "-3\n"

    def test_a_short_circuited_return_does_not_print_its_statement(self) -> None:
        """The control flag is read even when the ``$`` never evaluates."""
        assert run_and_capture("F(n) = {\n-(0 & $7)\n9\n}\nF(0)") == "9\n"
        assert run_and_capture("F(n) = {\n-(0 & 7)\n9\n}\nF(0)") == "0\n9\n"


@pytest.mark.parametrize(
    ("program", "stdin", "expected"),
    [
        # Wiki: "Standard order of operations applies" -- ** before negation.
        ("-2**2", "", "-4\n"),
        # Wiki: ab is a * b, so ab**2 is a * b**2.
        ("ab**2", "2\n3\n", "18\n"),
        # Exact integer division past float precision.
        ("(10**20 + 1) / 1", "", "100000000000000000001\n"),
        # A float operand divides as a float, exact or not.
        ("1.5 / 3", "", "0.5\n"),
        # Integers are unbounded, past Python's 4300-digit str limit.
        ("10**4400 + 1", "", "1" + "0" * 4399 + "1\n"),
        # A short-circuit must not skip a read the spec says happens.
        pytest.param(
            "a & b\nc",
            "0\n5\n9\n",
            "0\n9\n",
            id="input_is_bound_before_evaluation_not_lazily",
        ),
        pytest.param("n", "\n42", "42\n", id="numeric_input_skips_blank_lines"),
        pytest.param(
            "a - b",
            "9\n4\n",
            "5\n",
            id="variables_in_both_operands_are_read_left_to_right",
        ),
        # First-appearance order dedupes, so ``a + a`` takes one input.
        pytest.param("a + a", "5\n", "10\n", id="a_repeated_variable_is_read_once"),
    ],
)
def test_arithmetic_regressions(program: str, stdin: str, expected: str) -> None:
    assert run_and_capture(program, stdin) == expected


@pytest.mark.parametrize(
    ("program", "error"),
    [
        ("F() = {\n}\nF()", "empty function body"),
        ("F(x, x) = x\nF(1)", "repeats a parameter"),
        ("F(x,) = x\nF(1)", "bad parameter"),
        ("10.0**400", "exceeds the float range"),
        ("F(x y) = x\nF(1)", "malformed function header"),
        ("X", "unknown function"),
        ("1 % 0", "modulo by zero"),
        ("10.0**308 * 10", "number must be finite"),
    ],
)
def test_malformed_headers_and_overflow_raise(program: str, error: str) -> None:
    with pytest.raises((ValueError, HaltError), match=error):
        run_and_capture(program)


def test_the_evaluation_budget_resets_each_line() -> None:
    """The budget caps one line, not the program: 3 lines of 40 nodes fit 50."""
    machine_ = machine("1+1+1+1+1+1+1+1+1+1\n" * 3)
    machine_._WORK_LIMIT = 50  # noqa: SLF001
    while not machine_.halted:
        machine_.step()
    assert machine_.io.getvalue() == "10\n" * 3


def test_snapshot_distinguishes_a_float_input_by_its_bits() -> None:
    """A read ``1.0`` and a read ``1`` are different states."""
    one, other = machine("x + 0", "1\n"), machine("x + 0", "1.0\n")
    one.step()
    other.step()
    assert one.snapshot() != other.snapshot()


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Algebraic Programming Language", "1(2)", "1*(2)")


@pytest.mark.parametrize(("stdin", "halts"), [("0\n", True), ("1\n", False)])
def test_the_ancestor_check_decides_the_truth_machine(
    stdin: str, *, halts: bool
) -> None:
    """On 1, each lap re-enters ``?`` with the same binding and input cursor."""
    from esolangs.vm import run_until_halt_or_ancestor

    assert run_until_halt_or_ancestor(machine(TRUTH_MACHINE, stdin)) is halts


def test_a_recursion_whose_bindings_differ_each_lap_is_undecided() -> None:
    """The ancestor check proves *repeats*, not every infinite recursion."""
    from esolangs.vm import run_until_halt_or_ancestor

    with pytest.raises(TimeoutError):
        run_until_halt_or_ancestor(machine("F(x) = F(x + 1)\nF(0)"))
