"""Unit tests for the Fargo interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fargo import _Machine, _parse_program, run
from esolangs.vm import run_until_halt_or_ancestor, run_until_halt_or_cycle

# The wiki's truth machine, verbatim apart from the zero-width spaces it
# renders inside the first two lines (kept in TestWikiExamples below).
TRUTH_MACHINE = "one ^ $ one\n% 0 @ 0\n: @ 0 one\n$\n"


def run_program(code: str, stdin: str = "0\n") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestBuiltins:
    def test_output_number_starts_at_zero(self) -> None:
        assert run_program("$") == "0"

    def test_set_and_print_a_bit(self) -> None:
        assert run_program("% 0 1\n$") == "1"
        assert run_program("% 11 1\n$") == "8"

    def test_setting_a_bit_to_zero_clears_it(self) -> None:
        assert run_program("% 0 1\n% 0 0\n$") == "0"

    def test_shifts(self) -> None:
        assert run_program("% 0 > 1\n$") == "0"  # 1 << 1 = 2, bit 0 is 0
        assert run_program("% 0 < 10\n$") == "1"  # 2 >> 1 = 1

    def test_bitwise_operators(self) -> None:
        assert run_program("% 0 & 1 1\n$") == "1"
        assert run_program("% 0 & 1 0\n$") == "0"
        assert run_program("% 0 | 0 1\n$") == "1"
        assert run_program("% 0 ^ 1 1\n$") == "0"
        assert run_program("% 0 ^ 1 0\n$") == "1"

    def test_input_bits_are_lsb_first(self) -> None:
        # 6 is 0b110: bit 0 is 0, bits 1 and 2 are 1.
        assert run_program("% 0 @ 0\n$", "6\n") == "0"
        assert run_program("% 0 @ 1\n$", "6\n") == "1"
        assert run_program("% 0 @ 10\n$", "6\n") == "1"

    def test_literals_are_binary(self) -> None:
        # 101 is 5, so bit 0 of the output becomes bit 0 of the input 5.
        assert run_program("% 0 @ 0\n$", "5\n") == "1"
        assert run_program("% 101 1\n$") == "32"

    def test_arrays(self) -> None:
        assert run_program("% 0 [?] [] 1 0\n$") == "1"
        assert run_program("% 0 [?] +[] [] 0 [] 1 1\n$") == "1"

    def test_conditional_runs_its_body_when_the_guard_is_nonzero(self) -> None:
        assert run_program("setter % 0 1\n: 1 setter\n$") == "1"

    def test_conditional_skips_its_body_when_the_guard_is_zero(self) -> None:
        assert run_program("setter % 0 1\n: 0 setter\n$") == "0"

    def test_conditional_returns_a_plain_value_unevaluated(self) -> None:
        assert run_program("% 0 : 1 1\n$") == "1"


class TestSyntax:
    def test_comments_and_blank_lines_are_ignored(self) -> None:
        assert run_program("# a comment\n\n% 0 1 # trailing\n$") == "1"

    def test_zero_width_spaces_are_stripped(self) -> None:
        assert run_program("​% 0 1\n$") == "1"

    def test_definition_splits_arguments_from_code(self) -> None:
        # ``^`` is a builtin, so it starts the code and ``one`` takes no
        # arguments; ``dbl x > x`` takes one, since ``>`` is the first
        # defined name after it.
        defs, calls = _parse_program("dbl x > x\n% 1 dbl 1\n$\n")
        assert defs["dbl"].params == ("x",)
        assert defs["dbl"].code == (">", "x")
        assert calls == [("%", "1", "dbl", "1"), ("$",)]

    def test_a_function_can_take_no_arguments(self) -> None:
        defs, _ = _parse_program(TRUTH_MACHINE)
        assert defs["one"].params == ()
        assert defs["one"].code == ("^", "$", "one")

    def test_user_function_is_called_with_its_arguments(self) -> None:
        # The parameters must precede the first defined name: ``pick & x y``
        # would declare *none*, since the builtin ``&`` starts the code.
        assert run_program("pick x y & x y\n% 0 pick 1 1\n$") == "1"
        assert run_program("pick x y & x y\n% 0 pick 1 0\n$") == "0"

    def test_a_builtin_first_leaves_no_parameters(self) -> None:
        defs, _ = _parse_program("pick & x y\n$\n")
        assert defs["pick"].params == ()
        assert defs["pick"].code == ("&", "x", "y")

    def test_raw_function_argument(self) -> None:
        assert run_program("setter % 0 1\n: 1 :setter\n$") == "1"

    def test_a_repeated_parameter_name_starts_the_code(self) -> None:
        # ``x`` is already a defined name by its second appearance, so it
        # begins the code rather than declaring a second parameter.
        defs, _ = _parse_program("f x x\n$\n")
        assert defs["f"].params == ("x",)
        assert defs["f"].code == ("x",)


class TestWikiExamples:
    """The page's truth machine, including its zero-width spaces."""

    WIKI = "one ​^ $ one\n​% 0 @ 0\n: @ 0 one\n$\n"

    def test_truth_machine_on_zero_prints_zero_once(self) -> None:
        assert run_program(self.WIKI, "0\n") == "0"

    def test_truth_machine_on_one_loops(self) -> None:
        machine = _Machine(self.WIKI, ScriptedIO("1\n"))
        assert run_until_halt_or_ancestor(machine) is False

    def test_legal_definition_has_one_outer_call(self) -> None:
        prelude = "otherFn a b & a b\nthirdFn c d & c d\n"
        run_program(prelude + "myFn x y z otherFn x thirdFn y z\n$\n")

    def test_two_outer_calls_are_malformed(self) -> None:
        prelude = "otherFn a b & a b\nanotherFn e < e\n"
        with pytest.raises(ValueError, match="more than one outer call"):
            run_program(prelude + "myFn x y z otherFn x y z anotherFn x\n")

    def test_a_bare_name_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no outer call"):
            run_program("myFn\n")


class TestErrors:
    def test_undefined_function(self) -> None:
        with pytest.raises(HaltError, match="undefined function"):
            run_program("% 0 nope 1\n")

    def test_array_index_out_of_range(self) -> None:
        with pytest.raises(HaltError, match="out of range"):
            run_program("% 0 [?] [] 1 1\n")

    def test_number_expected(self) -> None:
        with pytest.raises(HaltError, match="expected a number"):
            run_program("% 0 < [] 1\n")

    def test_array_expected(self) -> None:
        with pytest.raises(HaltError, match="expected an array"):
            run_program("% 0 [?] 1 0\n")


class TestInput:
    def test_input_is_read_once_before_the_program_begins(self) -> None:
        # No ``@`` anywhere, yet the input line is still consumed.
        io = ScriptedIO("3\n")
        run("% 0 1\n$\n", io)
        assert io.position() == 1

    def test_empty_input_is_zero(self) -> None:
        assert run_program("% 0 @ 0\n$", "") == "0"

    def test_non_numeric_input_is_zero(self) -> None:
        assert run_program("% 0 @ 0\n$", "banana\n") == "0"

    def test_a_negative_input_number_indexes_as_two_s_complement(self) -> None:
        # -3 is ...11101, so bit 0 is 1 and bit 1 is 0.  The index itself
        # can never be negative, which is why neither is guarded.
        assert run_program("% 0 @ 0\n$", "-3\n") == "1"
        assert run_program("% 0 @ 1\n$", "-3\n") == "0"


class TestMachine:
    def test_empty_program_halts(self) -> None:
        machine = _Machine("", ScriptedIO(""))
        assert machine.halted
        assert run_until_halt_or_cycle(machine) is True

    def test_snapshot_tracks_the_output_number(self) -> None:
        machine = _Machine("% 0 1\n$\n", ScriptedIO("0\n"))
        before = machine.snapshot()
        while not machine.halted:
            machine.step()
        assert machine.snapshot() != before
        assert machine.output == 1

    def test_step_after_halting_is_a_no_op(self) -> None:
        machine = _Machine("$\n", ScriptedIO("0\n"))
        while not machine.halted:
            machine.step()
        state = machine.snapshot()
        machine.step()
        assert machine.snapshot() == state

    def test_frame_entry_key_ignores_the_output_number(self) -> None:
        # The output number is write-only, so two frames that differ only
        # in what they have printed are correctly seen as replays.
        machine = _Machine(TRUTH_MACHINE, ScriptedIO("1\n"))
        keys = []
        while len(keys) < 2:
            machine.step()
            if machine.frames:
                keys.append(machine.frame_entry_key(machine.frames[-1]))
        assert keys[0] == keys[1]
