r"""Unit tests for the 3x interpreter."""

from fractions import Fraction

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.three_x import run
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)
from tests.raises import raises_message


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class Test3x:
    def test_literal(self) -> None:
        assert run_program("[Hi]") == "Hi"
        assert run_program("[Hello, World!]") == "Hello, World!"

    def test_literal_skips_past_bracket(self) -> None:
        # the literal ends at the first.
        assert run_program("[A]333x!") == "A0"

    def test_push_three(self) -> None:
        assert run_program("3!") == "3"

    def test_x_operation(self) -> None:
        # (3-3)/3 = 0, (3-0)/3 = 1.
        assert run_program("333x!") == "0"
        assert run_program("3333x3x!") == "1"

    def test_fraction_output(self) -> None:
        # (1-3)/3 = -2/3, printed as a.
        assert run_program("3333333x3xx!") == "-2/3"

    def test_swap(self) -> None:
        assert run_program("333x3!") == "3"
        assert run_program("333x3#!") == "0"  # swapped.

    def test_printing_pops_one_value_at_a_time(self) -> None:
        r"""``!`` removes the top and leaves everything under it."""
        assert run_program("???!!!", "1\n2\n3\n") == "321"
        assert run_program("????!!!", "1\n2\n3\n4\n") == "432"

    def test_read(self) -> None:
        assert run_program("33?x!", "6\n") == "1"  # (6-3)/3.
        assert run_program("?3^!", "6\n") == "3"  # unassigned variable -> 3.

    def test_store_and_recall(self) -> None:
        assert run_program("3^!") == "3"  # default value for an.
        assert run_program("3333xv3^!") == "0"  # store 0 under 3, recall it.

    def test_storing_a_second_key_keeps_the_first(self) -> None:
        r"""A binding replaces only its own key, not the whole variable store."""
        # Store 0 under 3, then 3 under.
        # first binding survived the.
        assert run_program("3333xv3333x3v3^!") == "0"

    def test_loop(self) -> None:
        # push 1, loop prints 0 then.
        assert run_program("3333x3x(33x)!") == "0"
        # push 0, the loop skips.
        assert run_program("333x(3)!") == "0"

    def test_loop_repeats(self) -> None:
        # push 3, loop: 33x -> 0, exit;.
        # (3-?)/3 .
        assert run_program("3(33x)!") == "0"

    def test_error_empty_stack(self) -> None:
        with pytest.raises(HaltError):
            run_program("x")
        with pytest.raises(HaltError):
            run_program("!")
        with pytest.raises(HaltError):
            run_program("#")
        with pytest.raises(HaltError):
            run_program("(")
        with pytest.raises(HaltError):
            run_program(")")

    def test_every_error_message_is_exact(self) -> None:
        r"""All four messages are pinned whole, from each place they are raised."""
        for code, stdin, message in (
            ("!", "", "empty stack"),  # through _pop.
            ("x", "", "empty stack"),  # the arithmetic's first pop.
            ("(", "", "empty stack"),  # the loop head's own guard.
            (")", "", "empty stack"),  # and the loop tail's.
            ("333x33x!", "", "division by zero"),
            ("333x(", "", "unmatched ("),
            ("3)", "", "unmatched )"),
        ):
            with pytest.raises(HaltError) as caught:
                run_program(code, stdin)
            assert str(caught.value) == message, code

        for code, stdin in (("?", "abc"), ("?", "1/0")):
            with raises_message(ValueError, "input must be an integer or a fraction"):
                run_program(code, stdin)

    def test_loop_jumps_back_on_nonzero_top(self) -> None:
        # pass 1 ends with a 3 on top.
        assert run_program("333(33x#)!") == "0"

    def test_skipped_loop_counts_nested_brackets(self) -> None:
        # 333x leaves 0 on top, so the.
        # () inside must be counted so.
        # not the inner one, leaving.
        assert run_program("333x(3()3)3!") == "3"
        assert run_program("333x(())3!") == "3"

    def test_unmatched_print_bracket_prints_nothing(self) -> None:
        assert run_program("[") == ""

    def test_error_unmatched_bracket(self) -> None:
        with pytest.raises(HaltError):
            run_program("333x(")
        with pytest.raises(HaltError):
            run_program("33)")

    def test_empty_program(self) -> None:
        assert run_program("") == ""


class TestStepMachine:
    def test_stack_commands_replace_or_consume_their_operands(self) -> None:
        r"""Arithmetic, output, and swap do not leave stale operands behind."""
        from esolangs.interpreters.stack_based.three_x import _advance

        three = Fraction(3)
        zero = Fraction(0)
        assert _advance((0, (three, three, three), (), ()), "x") == (
            1,
            (zero,),
            (),
            (),
        )
        assert _advance((0, (three, zero), (), ()), "!") == (1, (three,), (), ())
        assert _advance((0, (three, zero), (), ()), "#") == (1, (zero, three), (), ())

    def test_an_open_paren_on_zero_skips_only_when_it_has_a_target(self) -> None:
        r"""``(`` on a zero jumps past the loop, or advances with no target."""
        from esolangs.interpreters.stack_based.three_x import _advance

        zero = Fraction(0)
        assert _advance((0, (zero,), (), ()), "(") == (1, (zero,), (), ())
        assert _advance((0, (zero,), (), ()), "(", None, 9) == (10, (zero,), (), ())

    def test_a_close_paren_with_no_open_loop(self) -> None:
        r"""``)`` on a zero falls out of a loop it was never inside."""
        from esolangs.exceptions import HaltError
        from esolangs.interpreters.stack_based.three_x import _Machine

        machine = _Machine("?)", ScriptedIO("0\n"))
        while not machine.halted:
            machine.step()
        assert machine.stack == (0,), "the zero is still there, unlooped"
        assert machine.jumps == ()

        def drain(machine: _Machine) -> None:
            while not machine.halted:
                machine.step()

        with pytest.raises(HaltError, match="unmatched"):
            drain(_Machine("?)", ScriptedIO("1\n")))

    def test_an_unterminated_literal_prints_nothing(self) -> None:
        r"""``[`` with no closing ``]`` prints the empty string, not the rest."""
        from esolangs.interpreters.stack_based.three_x import _Machine

        machine = _Machine("[abc", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == ""

    def test_a_literal_ends_at_its_own_closer(self) -> None:
        r"""Each ``[`` takes the *nearest* following ``]``, and may be empty."""
        assert run_program("[a]b[c]") == "ac"
        assert run_program("[hi][yo]") == "hiyo"
        assert run_program("[]") == ""
        # An empty literal alone prints.
        # or missed, so it needs a real.
        # a character late runs past.
        assert run_program("[][a]") == "a"

    def test_printing_uses_the_fraction_form_only_when_it_has_to(self) -> None:
        r"""A whole number prints bare; anything else prints as a fraction."""
        assert run_program("?!", "1/2") == "1/2"
        assert run_program("?!", "4/2") == "2"

    def test_a_closed_literal_prints_its_contents(self) -> None:
        r"""The companion to the unterminated case: a closed ``[`` prints."""
        from esolangs.interpreters.stack_based.three_x import _Machine

        closed = _Machine("[abc]", ScriptedIO())
        while not closed.halted:
            closed.step()
        assert closed.io.getvalue() == "abc"

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.stack_based.three_x import _Machine

        machine = _Machine("", ScriptedIO())
        assert machine.halted
        machine.step()  # stepping a halted machine is.
        assert machine.stack == ()


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.three_x import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    r"""The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "3"
    halting_program = "3!"
    looping_program = "3()"
    state_views = ("ind", "variables", "ip", "memory")
    # Assigns a variable, so.
    # for every program in this.
    viewing_program = "3333xv3^!"
    constant_views = frozenset({"memory"})


class TestStateViewValues:
    r"""The named views read the slots they claim, not one another."""

    def test_variables_is_the_variable_map(self) -> None:
        r"""The assignment lands in ``variables``, and ``memory`` stays empty."""
        machine = _machine("3333xv3^!")
        while not machine.halted:
            machine.step()
        assert machine.variables == {Fraction(3): Fraction(0)}
        assert machine.memory == []
