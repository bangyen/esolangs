r"""Unit tests for the Grapheme interpreter."""

import contextlib

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.grapheme import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    InputCursorContract,
)


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    with contextlib.suppress(EOFError):
        run(code, io)
    return io.getvalue()


class TestModes:
    def test_stringmode(self) -> None:
        # E HELLOWORLD E Y -> the E's.
        assert run_program("EHLLOWORLDEY") == "HLLOWORLD"

    def test_stringmode_accumulates_to_end(self) -> None:
        # no closing E: the string is.
        assert run_program("EAY") == ""

    def test_intmode(self) -> None:
        # F A F -> 10; F B F -> 20; A.
        assert run_program("FAFFBFAY") == "30"

    def test_intmode_empty_is_zero(self) -> None:
        assert run_program("FFY") == "0"

    def test_funcmode(self) -> None:
        # H Y H makes a function of Y;.
        assert run_program("FAFHYHIE") == "10"

    def test_an_unterminated_mode_is_flushed_when_its_frame_ends(self) -> None:
        r"""Each mode still yields its value when the code runs out."""
        assert run_program("HEABHIY") == "AB"  # string.
        assert run_program("HFABHIY") == "120"  # int.
        assert run_program("EHABEGNY") == "AB"  # function, via N.


class TestArithmetic:
    def test_subtract(self) -> None:
        assert run_program("FAFFBFBY") == "-10"

    def test_multiply(self) -> None:
        assert run_program("FAFFBFSY") == "200"

    def test_floor_divide(self) -> None:
        assert run_program("FCFFBFRY") == "1"

    def test_string_math_uses_ords(self) -> None:
        # "A" (65) + "A" (65) = 130.
        assert run_program("EAEEAEAY") == "130"


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
        assert run_program("FAFTY") == "0"  # 10 is truthy -> push 0.
        assert run_program("FFTY") == "1"  # 0 is falsy -> push 1.


class TestStrings:
    def test_length(self) -> None:
        assert run_program("EAEOY") == "1"

    def test_int_to_string(self) -> None:
        # 10 -> digits 1,0 -> "AJ".
        assert run_program("FAFNY") == "AJ"

    def test_string_to_int(self) -> None:
        # J on "AJ" parses.
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
        r"""A string read from input and executed via G is validated, not."""
        import pytest

        with pytest.raises(ValueError, match="unhandled command"):
            run_program("WG", "zkg")

    def test_i_runs_function(self) -> None:
        assert run_program("FAFHYHIE") == "10"

    def test_z_runs_while_stack_nonempty(self) -> None:
        assert run_program("FAFHYHZ") == "10"

    def test_z_repeats_until_the_stack_empties(self) -> None:
        # K duplicates the 10, so the Z.
        assert run_program("FAFKHYHZ") == "1010"

    def test_q_conditional_execution(self) -> None:
        # truthy 10 on the stack, fn Y:.
        with pytest.raises(HaltError, match="popped"):
            run_program("FAFHYHQ")


class TestConditionalsThatDoNothing:
    r"""Each conditional command's other arm: the case where it declines."""

    def test_q_ignores_a_value_that_is_not_a_function(self) -> None:
        # Q pops two integers rather.
        # no body to run; the third.
        assert run_program("FAFKKQY") == "10"

    def test_v_does_not_jump_when_the_test_is_truthy(self) -> None:
        # V pops a truthy value, so the.
        assert run_program("FAFKKVY") == "10"

    def test_z_ignores_a_value_that_is_not_a_function(self) -> None:
        # Z needs a function to loop.
        assert run_program("FAFKZY") == "10"


class TestSkips:
    def test_u_skips_when_falsy(self) -> None:
        # [10, 0]: U pops 0 (falsy) and.
        assert run_program("FAFFFUKY") == "10"

    def test_u_does_not_skip_when_truthy(self) -> None:
        # [0, 10]: U pops 10 (truthy),.
        assert run_program("FFFAFUKY") == "0"

    def test_x_skips_next_when_falsy(self) -> None:
        # [10, 0]: X pops 0 (falsy) and.
        assert run_program("FAFFFXKY") == "10"

    def test_x_skips_after_next_when_truthy(self) -> None:
        # [0, 10]: X pops 10 (truthy),.
        assert run_program("FFFAFXYK") == "0"

    def test_the_command_u_skips_is_one_that_would_have_printed(self) -> None:
        r"""Which way ``U`` skips, read from the output rather than the stack."""
        assert run_program("FAFFFUY") == ""  # falsy: the Y is skipped.
        assert run_program("FBFFAFUY") == "20"  # truthy: the Y runs.

    def test_x_resumes_two_commands_on(self) -> None:
        r"""After the one command it lets through, ``X`` skips exactly one."""
        # [10, 20, 30]: X pops the.
        # and the last Y prints the 10.
        assert run_program("FAFFBFFCFXYKY") == "2010"

    def test_x_can_open_the_body_it_governs(self) -> None:
        r"""``X`` works at the very start of a called body."""
        # the body is XYK: X pops the.
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
        r"""The constructor is the one way a program becomes a machine."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("FAFY", ScriptedIO())
        assert machine.ip == (0,)  # one frame, at its start.
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "10"
        # every frame has popped, so ip.
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

    def test_truthiness_of_strings_and_functions(self) -> None:
        assert run_program("EAETY") == "0"  # "A" truthy -> push 0.
        assert run_program("EETY") == "1"  # "" falsy -> push 1.
        assert run_program("HABHTY") == "0"  # nonempty function truthy.
        assert run_program("HHTY") == "1"  # empty function falsy.

    def test_i_pushes_back_a_non_function(self) -> None:
        assert run_program("FAFIY") == "10"

    def test_v_branches_on_a_falsy_value(self) -> None:
        with pytest.raises(HaltError, match="popped"):
            run_program("FFFFVY")

    def test_unterminated_int_mode(self) -> None:
        assert run_program("F") == ""

    def test_unterminated_func_mode(self) -> None:
        assert run_program("H") == ""

    def test_v_jumps_forward_over_the_commands_it_counts(self) -> None:
        r"""``V`` moves the cursor on, not back."""
        # [20, 1, 0]: V pops the falsy.
        # that would otherwise discard.
        assert run_program("FBFFFTFFVMY") == "20"

    def test_a_z_lap_starts_with_nothing_pending(self) -> None:
        r"""Each pass over a ``Z`` body begins with no skip outstanding."""
        # four values, and a body of.
        assert run_program("FAFFBFFCFFDFHKMMYHZ") == "3010"

    def test_a_call_does_not_repeat_itself(self) -> None:
        r"""Only ``Z`` re-runs its body; ``I`` runs it once."""
        # 10 and 20 on the stack, the.
        # returns; the 10 is still.
        assert run_program("FAFFBFHYHI") == "20"

    def test_the_last_command_leaves_the_machine_halted(self) -> None:
        r"""A frame finishes on the step that runs its final command."""
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("FAFY", ScriptedIO())
        for _ in range(4):
            assert not machine.halted
            machine.step()
        assert machine.halted

    def test_recursion_is_not_artificially_capped(self) -> None:
        r"""A 501-deep finite call chain follows the language's unbounded stack."""
        # the body decrements the.
        # again through Q while the.
        program = "H" + "FFTBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
        assert run_program("FEZF" + program) == ""
        assert run_program("FEZF" + "FFT" + "A" + program) == ""

    def test_the_error_messages_read_in_full(self) -> None:
        r"""Each message entire, not the fragment the tests match on."""
        import re

        for code, message in (
            ("M", "popped an empty stack"),
            ("FFFFR", "division by zero"),
            ("FAFHHC", "a function cannot name a variable"),
            ("FAFHHD", "a function cannot name a variable"),
            ("FAFG", "G needs a string or a function"),
            ("HABHFFA", "math on a function is undefined"),
            ("HABHY", "Y cannot output a function"),
        ):
            with pytest.raises(HaltError, match=re.escape(message)) as caught:
                run_program(code)
            assert str(caught.value) == message

    def test_the_malformed_program_message_reads_in_full(self) -> None:
        r"""The rejection names its own rule, in the case it uses."""
        import re

        message = "Grapheme programs may only contain uppercase Latin letters"
        with pytest.raises(ValueError, match=re.escape(message)) as caught:
            run_program("abc")
        assert str(caught.value) == message


class TestStepMachine:
    def test_the_read_pushes_the_whole_line(self) -> None:
        r"""``W`` pushes the line itself, not a byte of it."""
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("W", ScriptedIO("hi"))
        machine.step()
        assert machine.stack == ["hi"]

    def test_a_closed_mode_leaves_the_frame_as_it_found_it(self) -> None:
        r"""After a mode ends, the frame reads as one that never opened it."""
        from esolangs.interpreters.stack_based.grapheme import _Machine

        for code, value in (("EAEK", "A"), ("FAFK", 10), ("HAHK", ("func", "A"))):
            machine = _Machine(code, ScriptedIO())
            for _ in range(3):
                machine.step()
            assert machine.snapshot() == (
                (value,),
                frozenset(),
                ((code, 3, "", (), -1, ""),),
                0,
            )


class TestNumberEncoding:
    r"""Letters stand for digits, with Z standing for zero."""

    def test_letters_count_from_a(self) -> None:
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("A") == 10
        assert _to_int("B") == 20

    def test_z_is_zero_not_its_place_in_the_alphabet(self) -> None:
        r"""``Z`` is the one letter that does not stand for its offset."""
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("Z") == 0

    def test_each_letter_shifts_the_ones_before_it(self) -> None:
        r"""Position matters: AZ and ZA are different numbers."""
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("AZ") == 100
        assert _to_int("ZA") == 10
        assert _to_int("AB") == 120

    def test_an_empty_value_is_zero(self) -> None:
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("") == 0

    def test_intmode_reads_z_as_zero_too(self) -> None:
        r"""The buffer a closing ``F`` parses follows the same rule as ``J``."""
        from esolangs.interpreters.stack_based.grapheme import _int_from

        assert _int_from(list("Z")) == 0
        assert _int_from(list("A")) == 10
        assert _int_from(list("AZ")) == 100
        assert _int_from(list("ZA")) == 10
        assert run_program("FZFY") == "0"
        assert run_program("FAZFY") == "100"

    def test_an_empty_string_is_worth_nothing_in_arithmetic(self) -> None:
        r"""``A`` on two empty strings is 0, not the ord of a stand-in."""
        assert run_program("EEEEAY") == "0"


def _machine(code: object) -> object:
    r"""A machine with ``code`` in its first frame."""
    from esolangs.interpreters.stack_based.grapheme import _Machine

    return _Machine(str(code), ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.stack_based.grapheme import _Machine

    return _Machine(str(code), ScriptedIO(stdin))


class TestContract(EmptyProgramContract, CycleContract, InputCursorContract):
    r"""The shared shapes."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    reader = staticmethod(_reader)
    reading_program = "W"
    reading_stdin = "hi"
    halting_program = "FAFY"
    looping_program = "FAFHKMHZ"
