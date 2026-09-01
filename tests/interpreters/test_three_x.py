"""Unit tests for the 3x interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.three_x import run
from tests.interpreters.contract import CycleContract, SnapshotContract
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
        # the literal ends at the first ], so trailing commands still run
        assert run_program("[A]333x!") == "A0"

    def test_push_three(self) -> None:
        assert run_program("3!") == "3"

    def test_x_operation(self) -> None:
        # (3-3)/3 = 0, (3-0)/3 = 1
        assert run_program("333x!") == "0"
        assert run_program("3333x3x!") == "1"

    def test_fraction_output(self) -> None:
        # (1-3)/3 = -2/3, printed as a fraction
        assert run_program("3333333x3xx!") == "-2/3"

    def test_swap(self) -> None:
        assert run_program("333x3!") == "3"
        assert run_program("333x3#!") == "0"  # swapped

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

    def test_loop_repeats(self) -> None:
        # push 3, loop: 33x -> 0, exit; but with a counter... use input: ? reads n
        # (3-?)/3 ... instead verify the loop body runs while top nonzero
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

    def test_error_division_by_zero(self) -> None:
        with pytest.raises(HaltError):
            run_program("333x33x!")

    def test_error_bad_input(self) -> None:
        with pytest.raises(ValueError, match="integer or a fraction"):
            run_program("?", "abc")
        with pytest.raises(ValueError, match="integer or a fraction"):
            run_program("?", "1/0")

    def test_every_error_message_is_exact(self) -> None:
        """All four messages are pinned whole, from each place they are raised.

        The suite either checks the exception type alone or matches a
        fragment of the text, and ``match=`` is a substring search -- so
        the wording was free to change, and a message could be dropped
        entirely without a test noticing.  ``empty stack`` is raised from
        four separate places and the two bracket errors from one each, so
        this walks a program to every one of them.
        """
        for code, stdin, message in (
            ("!", "", "empty stack"),  # through _pop
            ("x", "", "empty stack"),  # the arithmetic's first pop
            ("(", "", "empty stack"),  # the loop head's own guard
            (")", "", "empty stack"),  # and the loop tail's
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
        # pass 1 ends with a 3 on top (jump back), pass 2 with a 0 (exit)
        assert run_program("333(33x#)!") == "0"

    def test_skipped_loop_counts_nested_brackets(self) -> None:
        # 333x leaves 0 on top, so the outer ( skips its body; the nested
        # () inside must be counted so the skip stops at the *matching* ),
        # not the inner one, leaving the trailing 3 to be printed
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
    def test_a_close_paren_with_no_open_loop(self) -> None:
        """``)`` on a zero falls out of a loop it was never inside.

        The two readings differ by what is on the stack: a nonzero top
        means "jump back", which needs an open loop and halts without one,
        while a zero means "leave", and leaving a loop that was never
        entered is simply the end of it.
        """
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
        """``[`` with no closing ``]`` prints the empty string, not the rest.

        The literal is whatever sits between the brackets, so a bracket
        that never closes delimits nothing -- printing the remainder of the
        program instead would leak its own source into the output.
        """
        from esolangs.interpreters.stack_based.three_x import _Machine

        machine = _Machine("[abc", ScriptedIO())
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == ""

    def test_a_literal_ends_at_its_own_closer(self) -> None:
        """Each ``[`` takes the *nearest* following ``]``, and may be empty.

        One literal in a program cannot show which closer is chosen, and a
        non-empty one cannot show where the search starts.  Two literals
        settle the first: taking the last ``]`` instead would swallow the
        text between them.  An empty one settles the second, since a search
        beginning a character later steps straight over its closer and
        finds nothing.
        """
        assert run_program("[a]b[c]") == "ac"
        assert run_program("[hi][yo]") == "hiyo"
        assert run_program("[]") == ""
        # An empty literal alone prints nothing whether its closer is found
        # or missed, so it needs a real literal behind it: a search starting
        # a character late runs past this closer into the next pair.
        assert run_program("[][a]") == "a"

    def test_printing_uses_the_fraction_form_only_when_it_has_to(self) -> None:
        """A whole number prints bare; anything else prints as a fraction.

        Every printing test uses a value that is already whole, so the
        branch deciding between the two forms was only ever taken one way.
        A half prints as ``1/2``, and 4/2 reduces to a whole 2 -- which
        pins the test on the reduced denominator rather than the input's.
        """
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


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.three_x import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes, with this language's own programs."""

    machine = staticmethod(_machine)
    stepping_program = "3"
    halting_program = "3!"
    looping_program = "3()"
