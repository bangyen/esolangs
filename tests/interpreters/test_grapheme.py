"""Unit tests for the Grapheme interpreter.

Covers the mode system (string/int/function), the arithmetic and stack
commands, variables, function execution, truthiness-driven skips, and the
documented error conventions.
"""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.grapheme import run
from tests.interpreters.contract import CycleContract, EmptyProgramContract


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


class TestModes:
    def test_stringmode(self) -> None:
        # E HELLOWORLD E Y -> the E's terminate the string, dropping one E
        assert run_program("EHLLOWORLDEY") == "HLLOWORLD"

    def test_stringmode_accumulates_to_end(self) -> None:
        # no closing E: the string is flushed at end of program
        assert run_program("EAY") == ""

    def test_intmode(self) -> None:
        # F A F -> 10; F B F -> 20; A adds; Y prints
        assert run_program("FAFFBFAY") == "30"

    def test_intmode_empty_is_zero(self) -> None:
        assert run_program("FFY") == "0"

    def test_funcmode(self) -> None:
        # H Y H makes a function of Y; I runs it on the pushed 10
        assert run_program("FAFHYHIE") == "10"

    def test_an_unterminated_mode_is_flushed_when_its_frame_ends(self) -> None:
        """Each mode still yields its value when the code runs out.

        At the top level the flushed value lands on the stack after the
        last command, where nothing is left to print it -- so the flush
        was only ever checked by the program not raising.  Ending a
        *called* body in a mode puts the value where the caller can print
        it, one per mode.
        """
        assert run_program("HEABHIY") == "AB"  # string
        assert run_program("HFABHIY") == "120"  # int
        assert run_program("EHABEGNY") == "AB"  # function, via N


class TestArithmetic:
    def test_add(self) -> None:
        assert run_program("FAFFBFAY") == "30"

    def test_subtract(self) -> None:
        assert run_program("FAFFBFBY") == "-10"

    def test_multiply(self) -> None:
        assert run_program("FAFFBFSY") == "200"

    def test_floor_divide(self) -> None:
        assert run_program("FCFFBFRY") == "1"

    def test_string_math_uses_ords(self) -> None:
        # "A" (65) + "A" (65) = 130
        assert run_program("EAEEAEAY") == "130"

    def test_divide_by_zero_halts(self) -> None:
        with pytest.raises(HaltError, match="division by zero"):
            run_program("FFFFR")


class TestStack:
    def test_duplicate(self) -> None:
        assert run_program("FAFKYY") == "1010"

    def test_swap(self) -> None:
        assert run_program("FAFFBFLYY") == "1020"

    def test_reverse(self) -> None:
        assert run_program("EABEECDEPYY") == "ABCD"

    def test_pop(self) -> None:
        assert run_program("EAEM") == ""

    def test_truthiness_to_number(self) -> None:
        assert run_program("FAFTY") == "0"  # 10 is truthy -> push 0
        assert run_program("FFTY") == "1"  # 0 is falsy -> push 1


class TestStrings:
    def test_length(self) -> None:
        assert run_program("EAEOY") == "1"

    def test_int_to_string(self) -> None:
        # 10 -> digits 1,0 -> "AJ"
        assert run_program("FAFNY") == "AJ"

    def test_string_to_int(self) -> None:
        # J on "AJ" parses intmode-style: A=1, J=10 -> (0+1)*10=10, (10+10)*10=200
        assert run_program("EAJEJY") == "200"

    def test_function_to_string(self) -> None:
        assert run_program("HABHNY") == "AB"


class TestVariables:
    def test_set_and_get(self) -> None:
        assert run_program("EAEKKCDY") == "A"

    def test_undeclared_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared"):
            run_program("EAED")


class TestFunctions:
    def test_g_executes_string(self) -> None:
        assert run_program("FAFEYEG") == "10"

    def test_g_on_input_with_bad_commands_rejected(self) -> None:
        """A string read from input and executed via G is validated, not asserted on."""
        import pytest

        with pytest.raises(ValueError, match="unhandled command"):
            run_program("WG", "zkg")

    def test_i_runs_function(self) -> None:
        assert run_program("FAFHYHIE") == "10"

    def test_z_runs_while_stack_nonempty(self) -> None:
        assert run_program("FAFHYHZ") == "10"

    def test_z_repeats_until_the_stack_empties(self) -> None:
        # K duplicates the 10, so the Z body runs twice before the stack empties
        assert run_program("FAFKHYHZ") == "1010"

    def test_q_conditional_execution(self) -> None:
        # truthy 10 on the stack, fn Y: Q pops fn and the 10, then Y pops empty
        with pytest.raises(HaltError, match="popped"):
            run_program("FAFHYHQ")


class TestConditionalsThatDoNothing:
    """Each conditional command's other arm: the case where it declines.

    ``Q``, ``V`` and ``Z`` all guard on what they popped, and the suite only
    ever showed them acting.  A command that quietly does nothing is the
    half more likely to go wrong unnoticed, so each is pinned here by what
    it leaves behind.
    """

    def test_q_ignores_a_value_that_is_not_a_function(self) -> None:
        # Q pops two integers rather than a function and a test, so there is
        # no body to run; the third copy is what Y prints.
        assert run_program("FAFKKQY") == "10"

    def test_v_does_not_jump_when_the_test_is_truthy(self) -> None:
        # V pops a truthy value, so the pc is left alone and Y still runs.
        assert run_program("FAFKKVY") == "10"

    def test_z_ignores_a_value_that_is_not_a_function(self) -> None:
        # Z needs a function to loop over; an integer leaves the stack as is.
        assert run_program("FAFKZY") == "10"


class TestSkips:
    def test_u_skips_when_falsy(self) -> None:
        # [10, 0]: U pops 0 (falsy) and skips the K, so Y prints the 10
        assert run_program("FAFFFUKY") == "10"

    def test_u_does_not_skip_when_truthy(self) -> None:
        # [0, 10]: U pops 10 (truthy), K duplicates the 0, Y prints it
        assert run_program("FFFAFUKY") == "0"

    def test_x_skips_next_when_falsy(self) -> None:
        # [10, 0]: X pops 0 (falsy) and skips the K, so Y prints the 10
        assert run_program("FAFFFXKY") == "10"

    def test_x_skips_after_next_when_truthy(self) -> None:
        # [0, 10]: X pops 10 (truthy), Y prints the 0, then the K is skipped
        assert run_program("FFFAFXYK") == "0"

    def test_the_command_u_skips_is_one_that_would_have_printed(self) -> None:
        """Which way ``U`` skips, read from the output rather than the stack.

        The tests above both skip a ``K`` that sits before a ``Y``, and a
        duplicate the ``Y`` never reaches leaves the printed value the
        same either way -- so an inverted skip passes both.  Skipping the
        ``Y`` itself is the difference.
        """
        assert run_program("FAFFFUY") == ""  # falsy: the Y is skipped
        assert run_program("FBFFAFUY") == "20"  # truthy: the Y runs

    def test_x_resumes_two_commands_on(self) -> None:
        """After the one command it lets through, ``X`` skips exactly one.

        The suite's truthy ``X`` puts the skipped command last, where
        skipping it and running it off the end look alike.  Following it
        with more code shows where execution comes back.
        """
        # [10, 20, 30]: X pops the truthy 30, Y prints 20, the K is skipped,
        # and the last Y prints the 10 that is still underneath.
        assert run_program("FAFFBFFCFXYKY") == "2010"

    def test_x_can_open_the_body_it_governs(self) -> None:
        """``X`` works at the very start of a called body.

        The pending skip is remembered as a position, and the first
        position in a frame is the one an offset-based check is most
        likely to mistake for "nothing pending" -- but the main program
        can never put ``X`` there, since it would pop an empty stack.
        """
        # the body is XYK: X pops the 20, Y prints the 10, the K is skipped
        assert run_program("FAFFBFHXYKHI") == "10"


class TestIO:
    def test_input(self) -> None:
        assert run_program("WKY", "hi") == "hi"

    def test_input_running_out_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run("W", ScriptedIO(""))


class TestErrors:
    def test_pop_empty_halts(self) -> None:
        with pytest.raises(HaltError, match="popped"):
            run_program("AB")

    def test_lowercase_rejected(self) -> None:
        with pytest.raises(ValueError, match="uppercase"):
            run_program("hello")

    def test_constructor_builds_a_runnable_machine_and_validates(self) -> None:
        """The constructor is the one way a program becomes a machine.

        ``run`` and the VM adapter both use it.  The tests reach it only
        via ``run``, which hides the recorded end of the top-level frame
        that ``ip`` reports once every frame has popped.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("FAFY", ScriptedIO())
        assert machine.ip == (0,)  # one frame, at its start
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "10"
        # every frame has popped, so ip falls back to where the program ends
        assert machine.ip == (len("FAFY"),)

        with pytest.raises(ValueError, match="uppercase"):
            _Machine("hello", ScriptedIO())


class TestEdgeCases:
    def test_j_on_an_int_is_identity(self) -> None:
        assert run_program("FAFJJY") == "10"

    def test_j_on_a_function_counts_its_commands(self) -> None:
        assert run_program("HABHJY") == "2"

    def test_j_on_a_string_stops_at_an_f(self) -> None:
        assert run_program("EFAEJY") == "0"

    def test_n_on_a_string_is_identity(self) -> None:
        assert run_program("EAENY") == "A"

    def test_n_on_zero_is_j(self) -> None:
        assert run_program("FFNY") == "J"

    def test_math_on_a_function_halts(self) -> None:
        with pytest.raises(HaltError, match="math on a function"):
            run_program("HABHFFA")

    def test_truthiness_of_strings_and_functions(self) -> None:
        assert run_program("EAETY") == "0"  # "A" truthy -> push 0
        assert run_program("EETY") == "1"  # "" falsy -> push 1
        assert run_program("HABHTY") == "0"  # nonempty function truthy
        assert run_program("HHTY") == "1"  # empty function falsy

    def test_recursion_limit_exceeded(self) -> None:
        with pytest.raises(HaltError, match="recursion"):
            run_program("HKGHKG")

    def test_function_cannot_name_a_variable(self) -> None:
        with pytest.raises(HaltError, match="cannot name"):
            run_program("FAFHHC")
        with pytest.raises(HaltError, match="cannot name"):
            run_program("FAFHHD")

    def test_g_needs_a_string_or_function(self) -> None:
        with pytest.raises(HaltError, match="G needs"):
            run_program("FAFG")

    def test_i_pushes_back_a_non_function(self) -> None:
        assert run_program("FAFIY") == "10"

    def test_v_branches_on_a_falsy_value(self) -> None:
        with pytest.raises(HaltError, match="popped"):
            run_program("FFFFVY")

    def test_y_cannot_output_a_function(self) -> None:
        with pytest.raises(HaltError, match="Y cannot"):
            run_program("HABHY")

    def test_unterminated_int_mode(self) -> None:
        assert run_program("F") == ""

    def test_unterminated_func_mode(self) -> None:
        assert run_program("H") == ""

    def test_v_jumps_forward_over_the_commands_it_counts(self) -> None:
        """``V`` moves the cursor on, not back.

        The suite's jumping ``V`` uses an offset large enough to leave the
        program, which ends the frame whichever way it went; a jump of one
        that lands on a later command is what fixes the direction.
        """
        # [20, 1, 0]: V pops the falsy 0 and the offset 1, skipping the M
        # that would otherwise discard the 20 before Y prints it
        assert run_program("FBFFFTFFVMY") == "20"

    def test_a_z_lap_starts_with_nothing_pending(self) -> None:
        """Each pass over a ``Z`` body begins with no skip outstanding.

        The frame is reused rather than rebuilt, so a pending-skip marker
        left pointing at a position the new lap will reach would swallow a
        command partway through it.  The suite's ``Z`` bodies are one or
        two commands long, too short to reach such a position.
        """
        # four values, and a body of four commands: dup, drop, drop, print
        assert run_program("FAFFBFFCFFDFHKMMYHZ") == "3010"

    def test_a_call_does_not_repeat_itself(self) -> None:
        """Only ``Z`` re-runs its body; ``I`` runs it once.

        The looping flag is empty for every other call, and an empty flag
        and a set one part ways only when the stack outlives the body --
        which is exactly what this program leaves behind.
        """
        # 10 and 20 on the stack, the function prints one of them and
        # returns; the 10 is still there, and must not restart the body
        assert run_program("FAFFBFHYHI") == "20"

    def test_the_last_command_leaves_the_machine_halted(self) -> None:
        """A frame finishes on the step that runs its final command.

        Reaching the end is otherwise only visible one step later, when
        the cursor is found past the code -- so a caller stepping exactly
        as many times as there are commands is what tells the two apart.
        """
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("FAFY", ScriptedIO())
        for _ in range(4):
            assert not machine.halted
            machine.step()
        assert machine.halted

    def test_the_recursion_limit_admits_five_hundred_frames(self) -> None:
        """500 nested calls run; 501 is the one that is refused.

        Every other recursion here runs away without bound, so the depth
        the guard compares -- where counting starts, how fast it climbs,
        and which side of 500 is allowed -- was pinned only from very far
        above.  This counts down from an exact depth instead.
        """
        # the body decrements the count, keeps a copy, and calls itself
        # again through Q while the copy is nonzero
        program = "H" + "FFTBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
        assert run_program("FEZF" + program) == ""
        with pytest.raises(HaltError, match="recursion limit"):
            run_program("FEZF" + "FFT" + "A" + program)

    def test_the_error_messages_read_in_full(self) -> None:
        """Each message entire, not the fragment the tests match on.

        ``match=`` is a substring search, so the assertions above pass on
        a message padded or reworded around the phrase they look for.  The
        two "cannot name" sites are separate raises with the same words,
        so each needs its own program.
        """
        import re

        for code, message in (
            ("M", "popped an empty stack"),
            ("FFFFR", "division by zero"),
            ("FAFHHC", "a function cannot name a variable"),
            ("FAFHHD", "a function cannot name a variable"),
            ("FAFG", "G needs a string or a function"),
            ("HABHFFA", "math on a function is undefined"),
            ("HABHY", "Y cannot output a function"),
            ("HKGHKG", "recursion limit exceeded"),
        ):
            with pytest.raises(HaltError, match=re.escape(message)) as caught:
                run_program(code)
            assert str(caught.value) == message

    def test_the_malformed_program_message_reads_in_full(self) -> None:
        """The rejection names its own rule, in the case it uses."""
        import re

        message = "Grapheme programs may only contain uppercase Latin letters"
        with pytest.raises(ValueError, match=re.escape(message)) as caught:
            run_program("abc")
        assert str(caught.value) == message


class TestStepMachine:
    def test_snapshot_includes_the_input_cursor(self) -> None:
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("W", ScriptedIO("hi"))
        before = machine.snapshot()
        machine.step()  # W reads a line, pushing it
        assert machine.snapshot() != before
        assert machine.io.position() == 1
        assert machine.stack == ["hi"]

    def test_a_closed_mode_leaves_the_frame_as_it_found_it(self) -> None:
        """After a mode ends, the frame reads as one that never opened it.

        The cycle detector compares whole snapshots, so a frame left
        holding a spent mode name -- or a buffer emptied to something
        other than a list -- would keep two identical machines apart, or
        break the snapshot outright.  Nothing else reads those fields once
        the mode is over, so only the snapshot can say what is in them.
        """
        from esolangs.interpreters.stack_based.grapheme import _Machine

        for code, value in (("EAEK", "A"), ("FAFK", 10), ("HAHK", ("func", "A"))):
            machine = _Machine(code, ScriptedIO())
            for _ in range(3):
                machine.step()
            assert machine.snapshot() == (
                (value,),
                frozenset(),
                ((code, 0, 3, "", (), -1, ""),),
                0,
            )


class TestNumberEncoding:
    """Letters stand for digits, with Z standing for zero.

    Numbers only ever reach the tests through programs that print their
    result, where the encoding and the arithmetic that follows it cannot be
    told apart.  These read the conversion directly.
    """

    def test_letters_count_from_a(self) -> None:
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("A") == 10
        assert _to_int("B") == 20

    def test_z_is_zero_not_its_place_in_the_alphabet(self) -> None:
        """``Z`` is the one letter that does not stand for its offset."""
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("Z") == 0

    def test_each_letter_shifts_the_ones_before_it(self) -> None:
        """Position matters: AZ and ZA are different numbers."""
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("AZ") == 100
        assert _to_int("ZA") == 10
        assert _to_int("AB") == 120

    def test_an_empty_value_is_zero(self) -> None:
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("") == 0

    def test_intmode_reads_z_as_zero_too(self) -> None:
        """The buffer a closing ``F`` parses follows the same rule as ``J``.

        The two conversions are written out separately, and only the ``J``
        one is read here -- so intmode's own ``Z`` went unchecked, and
        every program that spells a number avoids ``Z`` by writing the
        shorter letter instead.
        """
        from esolangs.interpreters.stack_based.grapheme import _int_from

        assert _int_from(list("Z")) == 0
        assert _int_from(list("A")) == 10
        assert _int_from(list("AZ")) == 100
        assert _int_from(list("ZA")) == 10
        assert run_program("FZFY") == "0"
        assert run_program("FAZFY") == "100"

    def test_an_empty_string_is_worth_nothing_in_arithmetic(self) -> None:
        """``A`` on two empty strings is 0, not the ord of a stand-in.

        A string operand contributes its first character, and the empty
        string has none -- so the value the code substitutes for the
        missing character is what decides the sum, and every other string
        in the suite has a first character of its own.
        """
        assert run_program("EEEEAY") == "0"


def _machine(code: object) -> object:
    """A machine with ``code`` in its first frame."""
    from esolangs.interpreters.stack_based.grapheme import _Machine

    return _Machine(str(code), ScriptedIO())


class TestContract(EmptyProgramContract, CycleContract):
    """The shared shapes. ``Z`` re-runs ``KM`` -- dup then pop -- forever."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    halting_program = "FAFY"
    looping_program = "FAFHKMHZ"
