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

    def test_setting_one_bit_leaves_the_others_alone(self) -> None:
        """Each ``%`` adds to the number rather than replacing it.

        Every case above sets a single bit, where writing the number
        outright and folding the bit into it give the same answer.  Two
        bits tell them apart: 1 and 2 together read 3, where an assignment
        would leave only whichever was set last.
        """
        assert run_program("% 0 1\n% 1 1\n$") == "3"
        assert run_program("% 1 1\n% 0 1\n$") == "3"

    def test_clearing_a_bit_leaves_the_others_alone(self) -> None:
        """Clearing picks out its own bit, which bit 0 cannot show.

        The mask that clears bit ``n`` is built by shifting, and at bit 0
        a shift either way gives the same mask -- so the existing case
        passes whichever direction it shifts.  Clearing bit 1 out of 3
        leaves 1; a mask built by shifting the wrong way clears nothing
        and leaves 3.
        """
        assert run_program("% 0 1\n% 1 1\n% 1 0\n$") == "1"

    def test_shifts(self) -> None:
        assert run_program("% 0 > 1\n$") == "0"  # 1 << 1 = 2, bit 0 is 0
        assert run_program("% 0 < 10\n$") == "1"  # 2 >> 1 = 1

    def test_shifts_move_exactly_one_place(self) -> None:
        """Pin the distance, which ``%`` alone cannot see.

        ``%`` writes only the *low bit* of its value, so ``1 << 1`` and
        ``1 << 2`` both leave bit 0 clear and look alike.  Indexing an
        array by the shifted number reads the whole value instead: this
        array answers 1 at index 2 and 0 at index 4, so a one-place shift
        and a two-place shift give different output.
        """
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
        """Each operand must come from its own position.

        A binary operator that read one argument twice would still agree
        on every *symmetric* case, so these are the asymmetric ones: for
        AND and OR the two orders of ``1``/``0`` must agree with each
        other and disagree with the doubled operand.
        """
        assert run_program("% 0 & 0 1\n$") == "0"
        assert run_program("% 0 & 1 0\n$") == "0"
        assert run_program("% 0 | 1 0\n$") == "1"
        assert run_program("% 0 | 0 1\n$") == "1"
        # `+[] x y` concatenates in order, so index 0 comes from the left.
        assert run_program("% 0 [?] +[] [] 1 [] 0 0\n$") == "1"
        assert run_program("% 0 [?] +[] [] 1 [] 0 1\n$") == "0"

    def test_writes_and_prints_evaluate_to_zero(self) -> None:
        """``%`` and ``$`` return 0, which is what keeps output write-only.

        The recursion check omits the output number from a frame's key on
        exactly this basis, so a nonzero return here would quietly make
        that unsound.  ``|`` exposes the value ``%`` hands back.
        """
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

    def test_arrays(self) -> None:
        assert run_program("% 0 [?] [] 1 0\n$") == "1"
        assert run_program("% 0 [?] +[] [] 0 [] 1 1\n$") == "1"

    def test_conditional_runs_its_body_when_the_guard_is_nonzero(self) -> None:
        assert run_program("setter % 0 1\n: 1 setter\n$") == "1"

    def test_conditional_skips_its_body_when_the_guard_is_zero(self) -> None:
        assert run_program("setter % 0 1\n: 0 setter\n$") == "0"

    def test_conditional_returns_a_plain_value_unevaluated(self) -> None:
        assert run_program("% 0 : 1 1\n$") == "1"

    def test_conditional_nested_in_a_call_yields_its_body_s_value(self) -> None:
        """``:`` becomes the call it runs, so its value is that call's.

        Only visible when the ``:`` sits *inside* another call: at the top
        level a spare value has nowhere to go, but here ``%`` is waiting
        for it and would otherwise fire on a stray 0 before ``g`` ran.
        """
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

    def test_a_second_hash_stays_inside_the_comment(self) -> None:
        """Only the first ``#`` divides code from comment."""
        assert run_program("% 0 1 # a # b # c\n$") == "1"

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

    def test_a_bare_colon_is_the_builtin_not_a_parameter(self) -> None:
        """``:`` names the conditional, so it starts the code.

        Only ``:name`` marks a raw function; stripping the mark from a
        bare ``:`` would leave nothing and make the language's only
        conditional parse as an ordinary parameter name.
        """
        defs, _ = _parse_program("count n : n count < n\n$\n")
        assert defs["count"].params == ("n",)
        assert defs["count"].code == (":", "n", "count", "<", "n")

    def test_a_parameter_can_hold_a_raw_function_and_be_called(self) -> None:
        assert run_program("apply c : 1 c\nsetter % 0 1\napply :setter\n$") == "1"

    def test_a_bound_zero_arity_function_runs_in_argument_position(self) -> None:
        """Outside a raw slot, a bound function is called, not passed on.

        ``c`` holds ``setter``, and ``|`` wants a value, so ``c`` runs and
        its side effect lands before the ``$``.
        """
        assert run_program("use c | c 0\nsetter % 0 1\nuse :setter\n$") == "1"

    def test_a_self_call_takes_its_own_arity(self) -> None:
        """A recursive name is sized from the definition being parsed.

        It is not in ``self.defs`` yet while its own body is checked, so
        the one-outer-call count has to reach for the parameters it is in
        the middle of gathering.
        """
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

    def test_a_body_still_owing_arguments_is_malformed(self) -> None:
        # ``&`` wants two and the body supplies one.
        with pytest.raises(ValueError, match="no outer call"):
            run_program("f x & x\n$\n")

    def test_an_undefined_name_in_a_body_supplies_a_value(self) -> None:
        """It cannot be a call, so the count treats it as one value.

        Whether it *resolves* is a runtime question -- here it completes
        ``&``'s arguments, so the definition is well-formed and only a
        call to ``f`` would raise.
        """
        run_program("f x & x nope\n$\n")

    def test_redefinition_is_unreachable_rather_than_rejected(self) -> None:
        """The wiki calls it an error; the grammar makes it unwritable.

        A line whose first token is already defined parses as a *call*, so
        the second ``f`` here calls the first rather than redefining it --
        there is no way to express the error the spec names.
        """
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
        """Each field is load-bearing, so a run's states are all distinct.

        The cycle detector's soundness rests on the snapshot being
        *complete*: a field it drops is a difference two runs can hide
        behind.  These three pairs differ only in a frame's bindings, its
        pending arguments, and its result respectively -- the parts that
        are captured through ``repr()`` and so are easiest to hollow out
        without any output changing.
        """
        assert self._states("f x | x 0\nf 1\n$\n") != self._states(
            "f x | x 0\nf 0\n$\n"
        ), "bindings do not reach the snapshot"
        assert self._states("% 0 | 1 0\n$\n") != self._states("% 0 | 0 0\n$\n"), (
            "pending arguments do not reach the snapshot"
        )
        assert self._states("g | 1 0\n% 0 : 1 g\n$\n") != self._states(
            "g | 0 0\n% 0 : 1 g\n$\n"
        ), "a frame's result does not reach the snapshot"

    def test_every_step_of_a_run_has_its_own_state(self) -> None:
        """No two steps collide, so nothing is a spurious cycle."""
        seen = self._states("f x | x 0\nf 1\n$\n")
        assert len(set(seen)) == len(seen)

    def test_frame_entry_key_separates_differing_bindings(self) -> None:
        """Two calls of one function with different arguments differ.

        The ancestor check calls a frame a replay when its key matches an
        ancestor's, so bindings dropped from the key would make an
        ordinary recursion look like a hang.
        """
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
