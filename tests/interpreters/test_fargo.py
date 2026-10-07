"""Unit tests for the Fargo interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fargo import (
    _is_literal,
    _Machine,
    _parse_program,
    run,
)
from esolangs.vm import run_until_halt_or_ancestor

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

    def test_setting_one_bit_leaves_the_others_alone(self) -> None:
        """Each ``%`` adds to the number rather than replacing it."""
        assert run_program("% 0 1\n% 1 1\n$") == "3"
        assert run_program("% 1 1\n% 0 1\n$") == "3"

    def test_shifts_move_exactly_one_place(self) -> None:
        """Pin the distance, which ``%`` alone cannot see."""
        # elements, by index: 0 0 1 0 0
        arr = "+[] +[] +[] +[] [] 0 [] 0 [] 1 [] 0 [] 0"
        assert run_program(f"% 0 [?] {arr} > 1\n$") == "1"  # 1 << 1 == 2
        assert run_program(f"% 0 [?] {arr} < 100\n$") == "1"  # 4 >> 1 == 2
        # and the shift really moves: unshifted, index 1 answers 0
        assert run_program(f"% 0 [?] {arr} 1\n$") == "0"

    def test_bitwise_operators(self) -> None:
        assert run_program("% 0 & 1 1\n$") == "1"
        assert run_program("% 0 & 1 0\n$") == "0"
        assert run_program("% 0 | 0 1\n$") == "1"
        assert run_program("% 0 ^ 1 1\n$") == "0"
        assert run_program("% 0 ^ 1 0\n$") == "1"

    def test_binary_operators_read_both_arguments(self) -> None:
        """Each operand must come from its own position."""
        assert run_program("% 0 & 0 1\n$") == "0"
        assert run_program("% 0 & 1 0\n$") == "0"
        assert run_program("% 0 | 1 0\n$") == "1"
        assert run_program("% 0 | 0 1\n$") == "1"
        # `+[] x y` concatenates in order, so index 0 comes from the left.
        assert run_program("% 0 [?] +[] [] 1 [] 0 0\n$") == "1"
        assert run_program("% 0 [?] +[] [] 1 [] 0 1\n$") == "0"

    def test_writes_and_prints_evaluate_to_zero(self) -> None:
        """``%`` and ``$`` return 0, which is what keeps output write-only."""
        assert run_program("% 0 | 0 % 1 1\n$") == "2"
        assert run_program("% 0 | 0 $\n$") == "00"

    def test_input_bits_are_lsb_first(self) -> None:
        # 6 is 0b110: bit 0 is 0, bits 1 and 2 are 1.
        assert run_program("% 0 @ 0\n$", "6\n") == "0"
        assert run_program("% 0 @ 1\n$", "6\n") == "1"
        assert run_program("% 0 @ 10\n$", "6\n") == "1"

    def test_literals_are_binary(self) -> None:
        # 101 is 5, so bit 0 of the output becomes bit 0 of the input 5.
        assert run_program("% 0 @ 0\n$", "5\n") == "1"
        assert run_program("% 101 1\n$") == "32"

    def test_conditional_returns_a_plain_value_unevaluated(self) -> None:
        assert run_program("% 0 : 1 1\n$") == "1"

    def test_conditional_nested_in_a_call_yields_its_body_s_value(self) -> None:
        """``:`` becomes the call it runs, so its value is that call's."""
        assert run_program("g | 1 0\n% 0 : 1 g\n$") == "1"
        assert run_program("g | 1 0\n% 0 : 0 g\n$") == "0"

    def test_conditional_with_a_builtin_body(self) -> None:
        # ``$`` is zero-arity, so it is a legal body and prints when run.
        assert run_program("% 0 1\n: 1 $\n") == "1"
        assert run_program("% 0 1\n: 0 $\n") == ""


class TestSyntax:
    def test_comments_and_blank_lines_are_ignored(self) -> None:
        assert run_program("# a comment\n\n% 0 1 # trailing\n$") == "1"

    def test_zero_width_spaces_are_stripped(self) -> None:
        assert run_program("​% 0 1\n$") == "1"

    def test_a_token_may_end_in_a_colon(self) -> None:
        """The raw mark is a *prefix*; a trailing colon is part of the name."""
        defs, _ = _parse_program("f: x | x 0\nf: 1\n$\n")
        assert list(defs) == ["f:"]
        assert run_program("f: x | x 0\n% 0 f: 1\n$") == "1"

    def test_only_zero_and_one_are_literal_digits(self) -> None:
        """``2`` is a name, not a number, so it is never a literal."""
        assert not _is_literal("2")
        assert not _is_literal("")
        assert _is_literal("101")
        # a definition named ``2`` therefore parses as a definition
        defs, _ = _parse_program("2 x | x 0\n$\n")
        assert list(defs) == ["2"]

    def test_definition_splits_arguments_from_code(self) -> None:
        # ``^`` is a builtin, so it starts the code and ``one`` takes no
        # arguments; ``dbl x > x`` takes one, since ``>`` is the first
        # defined name after it.
        defs, calls = _parse_program("dbl x > x\n% 1 dbl 1\n$\n")
        assert defs["dbl"].params == ("x",)
        assert defs["dbl"].code == (">", "x")
        assert calls == [("%", "1", "dbl", "1"), ("$",)]

    def test_user_function_is_called_with_its_arguments(self) -> None:
        # The parameters must precede the first defined name: ``pick & x y``
        # would declare *none*, since the builtin ``&`` starts the code.
        assert run_program("pick x y & x y\n% 0 pick 1 1\n$") == "1"
        assert run_program("pick x y & x y\n% 0 pick 1 0\n$") == "0"

    def test_a_builtin_first_leaves_no_parameters(self) -> None:
        defs, _ = _parse_program("pick & x y\n$\n")
        assert defs["pick"].params == ()
        assert defs["pick"].code == ("&", "x", "y")

    def test_a_raw_parameter_is_called_by_its_bare_name(self) -> None:
        """Wiki: ``:g`` marks an argument raw; ``g`` then calls it with ``y``."""
        program = "id x | x 0\napply :g y g y\n% 0 apply :id {}\n$\n"
        assert run_program(program.format(1)) == "1"
        assert run_program(program.format(0)) == "0"

    def test_a_bare_colon_is_the_builtin_not_a_parameter(self) -> None:
        """``:`` names the conditional, so it starts the code."""
        defs, _ = _parse_program("count n : n count < n\n$\n")
        assert defs["count"].params == ("n",)
        assert defs["count"].code == (":", "n", "count", "<", "n")

    def test_a_one_character_name_still_takes_the_raw_mark(self) -> None:
        """``:s`` is the shortest raw reference there is."""
        assert run_program("s % 0 1\n: 1 :s\n$") == "1"
        assert run_program("apply c : 1 c\ns % 0 1\napply :s\n$") == "1"

    def test_a_bound_zero_arity_function_runs_in_argument_position(self) -> None:
        """Outside a raw slot, a bound function is called, not passed on."""
        assert run_program("use c | c 0\nsetter % 0 1\nuse :setter\n$") == "1"

    def test_a_self_call_takes_its_own_arity(self) -> None:
        """A recursive name is sized from the definition being parsed."""
        defs, _ = _parse_program("loop n | n loop n\n$\n")
        assert defs["loop"].params == ("n",)
        # Accepted: ``|`` owes 2, ``n`` and the self-call supply them.
        run_program("loop n | n loop n\n$\n")

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

    @pytest.mark.parametrize("line", ["f0 101", "f x x", "f :x :x"])
    def test_a_body_with_no_call_is_malformed(self, line: str) -> None:
        """A literal or value argument is no call, like the wiki's ``myFn``."""
        with pytest.raises(ValueError, match="no outer call"):
            run_program(line + "\n$\n")

    def test_a_body_still_owing_arguments_is_malformed(self) -> None:
        # ``&`` wants two and the body supplies one.
        with pytest.raises(ValueError, match="no outer call"):
            run_program("f x & x\n$\n")

    def test_an_undefined_name_in_a_body_supplies_a_value(self) -> None:
        """It cannot be a call, so the count treats it as one value."""
        run_program("f x & x nope\n$\n")

    def test_redefinition_is_unreachable_rather_than_rejected(self) -> None:
        """The wiki calls it an error; the grammar makes it unwritable."""
        defs, calls = _parse_program("f | 1 0\nf | 0 0\n$\n")
        assert list(defs) == ["f"]
        assert calls == [("f", "|", "0", "0"), ("$",)]

    def test_one_outer_call_binds_definitions_not_call_lines(self) -> None:
        """A top-level line may hold several complete calls."""
        assert run_program("% 0 1\n$ $\n") == "11"


class TestErrors:
    def test_undefined_function(self) -> None:
        with pytest.raises(HaltError, match="undefined function"):
            run_program("% 0 nope 1\n")

    def test_a_call_left_wanting_arguments(self) -> None:
        # ``%`` takes two and the line supplies one.  ``match=`` is a
        # substring search, so the whole message is compared too.
        with pytest.raises(ValueError, match="wants more args") as caught:
            run_program("% 0\n$\n")
        assert str(caught.value) == "call wants more args"

    def test_calling_a_parameter_bound_to_a_plain_value(self) -> None:
        # ``c`` sits in ``:``'s body slot but was given the number 1.
        with pytest.raises(HaltError, match="non-function argument"):
            run_program("apply c : 1 c\napply 1\n$\n")

    def test_conditional_body_taking_arguments(self) -> None:
        # ``<`` needs an argument and ``:`` has none to give it.
        with pytest.raises(HaltError, match="takes 1 argument"):
            run_program("% 0 : 1 <\n$\n")

    def test_array_index_out_of_range(self) -> None:
        with pytest.raises(HaltError, match="out of range"):
            run_program("% 0 [?] [] 1 1\n")

    def test_shifting_an_array_or_concatenating_numbers_halts(self) -> None:
        with pytest.raises(HaltError, match="expected a number"):
            run_program("% 0 < [] 1\n")
        with pytest.raises(HaltError, match="expected an array"):
            run_program("% 0 +[] 1 1\n")


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
    def test_step_after_halting_is_a_no_op(self) -> None:
        machine = _Machine("$\n", ScriptedIO("0\n"))
        while not machine.halted:
            machine.step()
        state = machine.snapshot()
        machine.step()
        assert machine.snapshot() == state

    @staticmethod
    def _states(code: str, stdin: str = "0\n") -> list[object]:
        """Every snapshot one run passes through, halt included."""
        machine = _Machine(code, ScriptedIO(stdin))
        seen: list[object] = []
        for _ in range(200):
            seen.append(machine.snapshot())
            if machine.halted:
                break
            machine.step()
        return seen

    def test_snapshot_separates_the_state_it_claims_to_carry(self) -> None:
        """Each field matters, so a run's states are all distinct."""
        assert self._states("f x | x 0\nf 1\n$\n") != self._states(
            "f x | x 0\nf 0\n$\n"
        ), "bindings do not reach the snapshot"
        assert self._states("% 0 | 1 0\n$\n") != self._states("% 0 | 0 0\n$\n"), (
            "pending arguments do not reach the snapshot"
        )
        assert self._states("g | 1 0\n% 0 : 1 g\n$\n") != self._states(
            "g | 0 0\n% 0 : 1 g\n$\n"
        ), "a frame's result does not reach the snapshot"

    def test_frame_entry_key_separates_differing_bindings(self) -> None:
        """Two calls of one function with different arguments differ."""
        machine = _Machine("f x | x 0\nf 1\n$\n", ScriptedIO("0\n"))
        keys = []
        while not machine.halted:
            machine.step()
            if machine.frames:
                keys.append(machine.frame_entry_key(machine.frames[-1]))
        other = _Machine("f x | x 0\nf 0\n$\n", ScriptedIO("0\n"))
        others = []
        while not other.halted:
            other.step()
            if other.frames:
                others.append(other.frame_entry_key(other.frames[-1]))
        assert keys != others
