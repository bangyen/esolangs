"""Unit tests for the 3x interpreter."""

from fractions import Fraction
from functools import partial

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.three_x import run
from tests.interpreters import runner
from tests.interpreters.contract import (
    CycleContract,
    SnapshotContract,
    StateViewContract,
)

run_program = partial(runner.run_program, run, suppress_eof=False)


class Test3x:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            # The literal ends at the first ], so trailing commands still run.
            pytest.param("[A]333x!", "A0", id="literal_skips_past_bracket"),
            pytest.param("3!", "3", id="push_three"),
            # (1-3)/3 = -2/3, printed as a fraction.
            pytest.param("3333333x3xx!", "-2/3", id="fraction_output"),
            # Store 0 under 3, then 3 under 0: the final lookup proves the first
            # binding survived the second, so a binding replaces only its key.
            pytest.param(
                "3333xv3333x3v3^!", "0", id="storing_a_second_key_keeps_the_first"
            ),
            # The loop body runs while the top is nonzero.
            pytest.param("3(33x)!", "0", id="loop_repeats"),
            # Pass 1 ends with a 3 on top (jump back), pass 2 with a 0 (exit).
            pytest.param("333(33x#)!", "0", id="loop_jumps_back_on_nonzero_top"),
            pytest.param("[", "", id="unmatched_print_bracket_prints_nothing"),
        ],
    )
    def test_output(self, code: str, expected: str) -> None:
        assert run_program(code) == expected

    def test_x_operation(self) -> None:
        # (3-3)/3 = 0, (3-0)/3 = 1
        assert run_program("333x!") == "0"
        assert run_program("3333x3x!") == "1"

    def test_swap(self) -> None:
        assert run_program("333x3!") == "3"
        assert run_program("333x3#!") == "0"  # swapped

    def test_printing_pops_one_value_at_a_time(self) -> None:
        """``!`` removes the top and leaves everything under it."""
        assert run_program("???!!!", "1\n2\n3\n") == "321"
        assert run_program("????!!!", "1\n2\n3\n4\n") == "432"

    def test_read(self) -> None:
        assert run_program("33?x!", "6\n") == "1"  # (6-3)/3
        assert run_program("?3^!", "6\n") == "3"  # unassigned variable -> 3

    def test_store_and_recall(self) -> None:
        assert run_program("3^!") == "3"  # default value for an unassigned key
        assert run_program("3333xv3^!") == "0"  # store 0 under 3, recall it

    def test_loop(self) -> None:
        # push 1, loop prints 0 then exits on the 0
        assert run_program("3333x3x(33x)!") == "0"
        # push 0, the loop skips
        assert run_program("333x(3)!") == "0"

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

    def test_division_by_a_zero_third_item_halts(self) -> None:
        with pytest.raises(HaltError, match="division by zero"):
            run_program("?33x", "0\n")

    def test_a_fraction_input_with_a_zero_denominator_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="integer or a fraction"):
            run_program("?", "1/0\n")

    def test_skipped_loop_counts_nested_brackets(self) -> None:
        # 333x leaves 0 on top, so the outer ( skips its body; the nested
        # () inside must be counted so the skip stops at the *matching* ),
        # not the inner one, leaving the trailing 3 to be printed
        assert run_program("333x(3()3)3!") == "3"
        assert run_program("333x(())3!") == "3"

    def test_error_unmatched_bracket(self) -> None:
        with pytest.raises(HaltError):
            run_program("333x(")
        with pytest.raises(HaltError):
            run_program("3(")
        with pytest.raises(HaltError):
            run_program("33)")


class TestStepMachine:
    def test_stack_commands_replace_or_consume_their_operands(self) -> None:
        """Arithmetic, output, and swap do not leave stale operands behind."""
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
        """``(`` on a zero jumps past the loop, or advances with no target."""
        from esolangs.interpreters.stack_based.three_x import _advance

        zero = Fraction(0)
        assert _advance((0, (zero,), (), ()), "(") == (1, (zero,), (), ())
        assert _advance((0, (zero,), (), ()), "(", None, 9) == (10, (zero,), (), ())

    def test_a_close_paren_with_no_open_loop(self) -> None:
        """``)`` on a zero falls out of a loop it was never inside."""
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
        """``[`` with no closing ``]`` prints the empty string, not the rest."""
        from esolangs.interpreters.stack_based.three_x import _Machine

        machine = _Machine("[abc", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == ""

    def test_a_literal_ends_at_its_own_closer(self) -> None:
        """Each ``[`` takes the *nearest* following ``]``, and may be empty."""
        assert run_program("[a]b[c]") == "ac"
        assert run_program("[hi][yo]") == "hiyo"
        assert run_program("[]") == ""
        # An empty literal alone prints nothing whether its closer is found
        # or missed, so it needs a real literal behind it: a search starting
        # a character late runs past this closer into the next pair.
        assert run_program("[][a]") == "a"

    def test_printing_uses_the_fraction_form_only_when_it_has_to(self) -> None:
        """A whole number prints bare; anything else prints as a fraction."""
        assert run_program("?!", "1/2") == "1/2"
        assert run_program("?!", "4/2") == "2"

    def test_a_closed_literal_prints_its_contents(self) -> None:
        """The companion to the unterminated case: a closed ``[`` prints."""
        from esolangs.interpreters.stack_based.three_x import _Machine

        closed = _Machine("[abc]", ScriptedIO())
        while not closed.halted:
            closed.step()
        assert closed.io.getvalue() == "abc"

    def test_step_after_halt_is_a_noop(self) -> None:
        from esolangs.interpreters.stack_based.three_x import _Machine

        machine = _Machine("", ScriptedIO())
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.stack == ()

    def test_a_loop_that_reads_is_not_a_cycle(self) -> None:
        """The snapshot holds the input cursor (214c4f77)."""
        from esolangs.interpreters.stack_based.three_x import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        io = ScriptedIO("1 1 0")
        assert run_until_halt_or_cycle(_Machine("?(!?)!", io), limit=100)
        assert io.getvalue() == "110"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.three_x import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract, StateViewContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "3"
    halting_program = "3!"
    looping_program = "3()"
    state_views = ("ind", "variables", "ip")
    # Assigns a variable, so `variables` moves.
    viewing_program = "3333xv3^!"


class TestStateViewValues:
    """The named views read the slots they claim, not one another."""

    def test_variables_is_the_variable_map(self) -> None:
        """The assignment lands in ``variables``, and ``memory`` stays empty."""
        machine = _machine("3333xv3^!")
        while not machine.halted:
            machine.step()
        assert machine.variables == {Fraction(3): Fraction(0)}
        assert not hasattr(machine, "memory")
