"""Unit tests for the Grapheme interpreter."""

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


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("EABCEY", "ABC"),
        ("FABFY", "12"),
        ("FAFHYHI", "1"),
        ("HABHJY", "2"),
        ("HABHNY", "AB"),
        ("FAFFFUKY", "1"),
        ("FFFAFXYK", "0"),
        ("FBFFAFFAFLRFFVKY", "2"),
    ],
)
def test_lf_is_removed_before_literals_functions_and_command_positions(
    code: str, expected: str
) -> None:
    from esolangs.interpreters.stack_based.grapheme import _Machine

    plain = _Machine(code, ScriptedIO(""))
    wrapped = _Machine("\n" + "\n".join(code) + "\n", ScriptedIO(""))
    while not plain.halted:
        assert plain.snapshot() == wrapped.snapshot()
        plain.step()
        wrapped.step()
    assert wrapped.halted
    assert plain.snapshot() == wrapped.snapshot()
    assert wrapped.ip == (len(code),)
    assert wrapped.io.getvalue() == plain.io.getvalue() == expected


@pytest.mark.parametrize("char", [" ", "\t", "\r", "a"])
def test_loading_ignores_only_lf(char: str) -> None:
    with pytest.raises(ValueError, match="uppercase"):
        run("\nEA" + char + "EY\n", ScriptedIO(""))


class TestModes:
    def test_stringmode(self) -> None:
        # E HELLOWORLD E Y -> the E's terminate the string, dropping one E
        assert run_program("EHLLOWORLDEY") == "HLLOWORLD"

    def test_stringmode_accumulates_to_end(self) -> None:
        # no closing E: the string is flushed at end of program
        assert run_program("EAY") == ""

    def test_intmode(self) -> None:
        # F A F -> 1; F B F -> 2; A adds; Y prints
        assert run_program("FAFFBFAY") == "3"

    def test_intmode_empty_is_zero(self) -> None:
        assert run_program("FFY") == "0"

    def test_funcmode(self) -> None:
        # H Y H makes a function of Y; I runs it on the pushed 1
        assert run_program("FAFHYHIE") == "1"

    def test_an_unterminated_mode_is_flushed_when_its_frame_ends(self) -> None:
        """Each mode still yields its value when the code runs out."""
        assert run_program("HEABHIY") == "AB"  # string
        assert run_program("HFABHIY") == "12"  # int
        assert run_program("EHABEGNY") == "AB"  # function, via N


class TestArithmetic:
    def test_subtract(self) -> None:
        assert run_program("FAFFBFBY") == "1"

    def test_multiply(self) -> None:
        assert run_program("FAFFBFSY") == "2"

    def test_floor_divide(self) -> None:
        assert run_program("FCFFBFRY") == "0"

    def test_string_math_uses_ords(self) -> None:
        # "A" (65) + "A" (65) = 130
        assert run_program("EAEEAEAY") == "130"


class TestStack:
    def test_duplicate(self) -> None:
        assert run_program("FAFKYY") == "11"

    def test_swap(self) -> None:
        assert run_program("FAFFBFLYY") == "12"

    def test_reverse(self) -> None:
        assert run_program("EABEECDEPYY") == "ABCD"

    def test_pop(self) -> None:
        assert run_program("EAEM") == ""

    def test_truthiness_to_number(self) -> None:
        assert run_program("FAFTY") == "0"  # 1 is truthy -> push 0
        assert run_program("FFTY") == "1"  # 0 is falsy -> push 1


class TestStrings:
    def test_length(self) -> None:
        assert run_program("EAEOY") == "1"

    def test_int_to_string(self) -> None:
        # 1 -> digit 1 -> "A"
        assert run_program("FAFNY") == "A"

    def test_string_to_int(self) -> None:
        # A=1 and J=10: 1*10 + 10 = 20
        assert run_program("EAJEJY") == "20"

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
        assert run_program("FAFEYEG") == "1"

    def test_g_on_input_with_bad_commands_rejected(self) -> None:
        """A string read from input and executed via G is validated, not asserted on."""
        import pytest

        with pytest.raises(ValueError, match="unhandled command"):
            run_program("WG", "zkg")

    def test_i_runs_function(self) -> None:
        assert run_program("FAFHYHIE") == "1"

    def test_z_runs_while_stack_nonempty(self) -> None:
        assert run_program("FAFHYHZ") == "1"

    def test_z_repeats_until_the_stack_empties(self) -> None:
        # K duplicates the 1, so the Z body runs twice before the stack empties
        assert run_program("FAFKHYHZ") == "11"

    def test_q_conditional_execution(self) -> None:
        # truthy 1 on the stack, fn Y: Q pops fn and the 1, then Y pops empty
        with pytest.raises(HaltError, match="popped"):
            run_program("FAFHYHQ")


class TestConditionalsThatDoNothing:
    """Each conditional command's other arm: the case where it declines."""

    def test_q_ignores_a_value_that_is_not_a_function(self) -> None:
        # Q pops two integers rather than a function and a test, so there is
        # no body to run; the third copy is what Y prints.
        assert run_program("FAFKKQY") == "1"

    def test_v_does_not_jump_when_the_test_is_truthy(self) -> None:
        # V pops a truthy value, so the pc is left alone and Y still runs.
        assert run_program("FAFKKVY") == "1"

    def test_z_ignores_a_value_that_is_not_a_function(self) -> None:
        # Z needs a function to loop over; an integer leaves the stack as is.
        assert run_program("FAFKZY") == "1"


class TestSkips:
    def test_u_skips_when_falsy(self) -> None:
        # [1, 0]: U pops 0 (falsy) and skips the K, so Y prints the 1
        assert run_program("FAFFFUKY") == "1"

    def test_u_does_not_skip_when_truthy(self) -> None:
        # [0, 1]: U pops 1 (truthy), K duplicates the 0, Y prints it
        assert run_program("FFFAFUKY") == "0"

    def test_x_skips_next_when_falsy(self) -> None:
        # [1, 0]: X pops 0 (falsy) and skips the K, so Y prints the 1
        assert run_program("FAFFFXKY") == "1"

    def test_x_skips_after_next_when_truthy(self) -> None:
        # [0, 1]: X pops 1 (truthy), Y prints the 0, then the K is skipped
        assert run_program("FFFAFXYK") == "0"

    def test_the_command_u_skips_is_one_that_would_have_printed(self) -> None:
        """Which way ``U`` skips, read from the output rather than the stack."""
        assert run_program("FAFFFUY") == ""  # falsy: the Y is skipped
        assert run_program("FBFFAFUY") == "2"  # truthy: the Y runs

    def test_x_resumes_two_commands_on(self) -> None:
        """After the one command it lets through, ``X`` skips exactly one."""
        # [1, 2, 3]: X pops the truthy 3, Y prints 2, the K is skipped,
        # and the last Y prints the 1 that is still underneath.
        assert run_program("FAFFBFFCFXYKY") == "21"

    def test_x_can_open_the_body_it_governs(self) -> None:
        """``X`` works at the very start of a called body."""
        # the body is XYK: X pops the 2, Y prints the 1, the K is skipped
        assert run_program("FAFFBFHXYKHI") == "1"


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
        """The constructor is the one way a program becomes a machine."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("FAFY", ScriptedIO())
        assert machine.ip == (0,)  # one frame, at its start
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "1"
        # every frame has popped, so ip falls back to where the program ends
        assert machine.ip == (len("FAFY"),)

        with pytest.raises(ValueError, match="uppercase"):
            _Machine("hello", ScriptedIO())


class TestEdgeCases:
    def test_j_on_an_int_is_identity(self) -> None:
        assert run_program("FAFJJY") == "1"

    def test_j_on_a_function_counts_its_commands(self) -> None:
        assert run_program("HABHJY") == "2"

    def test_j_on_a_string_stops_at_an_f(self) -> None:
        assert run_program("EFAEJY") == "0"

    def test_n_on_a_string_is_identity(self) -> None:
        assert run_program("EAENY") == "A"

    def test_n_on_zero_is_j(self) -> None:
        assert run_program("FFNY") == "J"

    def test_truthiness_of_strings_and_functions(self) -> None:
        assert run_program("EAETY") == "0"  # "A" truthy -> push 0
        assert run_program("EETY") == "1"  # "" falsy -> push 1
        assert run_program("HABHTY") == "0"  # nonempty function truthy
        assert run_program("HHTY") == "1"  # empty function falsy

    def test_i_pushes_back_a_non_function(self) -> None:
        assert run_program("FAFIY") == "1"

    def test_v_branches_on_a_falsy_value(self) -> None:
        with pytest.raises(HaltError, match="popped"):
            run_program("FFFFVY")

    def test_unterminated_int_mode(self) -> None:
        assert run_program("F") == ""

    def test_unterminated_func_mode(self) -> None:
        assert run_program("H") == ""

    def test_v_jumps_forward_over_the_commands_it_counts(self) -> None:
        """``V`` moves the cursor on, not back."""
        # [2, 1, 0]: V pops the falsy 0 and the offset 1, skipping the M
        # that would otherwise discard the 2 before Y prints it
        assert run_program("FBFFFTFFVMY") == "2"

    def test_a_z_lap_starts_with_nothing_pending(self) -> None:
        """Each pass over a ``Z`` body begins with no skip outstanding."""
        # four values, and a body of four commands: dup, drop, drop, print
        assert run_program("FAFFBFFCFFDFHKMMYHZ") == "31"

    def test_a_call_does_not_repeat_itself(self) -> None:
        """Only ``Z`` re-runs its body; ``I`` runs it once."""
        # 1 and 2 on the stack, the function prints one of them and
        # returns; the 1 is still there, and must not restart the body
        assert run_program("FAFFBFHYHI") == "2"

    def test_the_last_command_leaves_the_machine_halted(self) -> None:
        """A frame finishes on the step that runs its final command."""
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("FAFY", ScriptedIO())
        for _ in range(4):
            assert not machine.halted
            machine.step()
        assert machine.halted

    def test_recursion_is_not_artificially_capped(self) -> None:
        """A 501-deep finite call chain follows the language's unbounded stack."""
        # the body decrements the count, keeps a copy, and calls itself
        # again through Q while the copy is nonzero
        program = "H" + "FFTPBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
        assert run_program("FEZZF" + program) == ""
        assert run_program("FEZZF" + "FFT" + "A" + program) == ""

    def test_the_error_messages_read_in_full(self) -> None:
        """Each message entire, not the fragment the tests match on."""
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
        """The rejection names its own rule, in the case it uses."""
        import re

        message = "Grapheme programs may only contain uppercase Latin letters"
        with pytest.raises(ValueError, match=re.escape(message)) as caught:
            run_program("abc")
        assert str(caught.value) == message


class TestStepMachine:
    def test_the_read_pushes_the_whole_line(self) -> None:
        """``W`` pushes the line itself, not a byte of it."""
        from esolangs.interpreters.stack_based.grapheme import _Machine

        machine = _Machine("W", ScriptedIO("hi"))
        machine.step()
        assert machine.stack == ["hi"]

    def test_a_closed_mode_leaves_the_frame_as_it_found_it(self) -> None:
        """After a mode ends, the frame reads as one that never opened it."""
        from esolangs.interpreters.stack_based.grapheme import _Machine

        for code, value in (("EAEK", "A"), ("FAFK", 1), ("HAHK", ("func", "A"))):
            machine = _Machine(code, ScriptedIO())
            for _ in range(3):
                machine.step()
            assert machine.snapshot() == (
                (value,),
                frozenset(),
                ((code, 3, "", (), -1, False),),
                0,
                0,  # successful reads, for a port with no cursor (286aa9b8)
            )


class TestNumberEncoding:
    """Letters stand for digits, with Z standing for zero."""

    def test_letters_count_from_a(self) -> None:
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("A") == 1
        assert _to_int("B") == 2

    def test_z_is_zero_not_its_place_in_the_alphabet(self) -> None:
        """``Z`` is the one letter that does not stand for its offset."""
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("Z") == 0

    def test_each_letter_shifts_the_ones_before_it(self) -> None:
        """Position matters: AZ and ZA are different numbers."""
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("AZ") == 10
        assert _to_int("ZA") == 1
        assert _to_int("AB") == 12

    def test_an_empty_value_is_zero(self) -> None:
        from esolangs.interpreters.stack_based.grapheme import _to_int

        assert _to_int("") == 0

    def test_intmode_reads_z_as_zero_too(self) -> None:
        """The buffer a closing ``F`` parses follows the same rule as ``J``."""
        from esolangs.interpreters.stack_based.grapheme import _int_from

        assert _int_from(list("Z")) == 0
        assert _int_from(list("A")) == 1
        assert _int_from(list("AZ")) == 10
        assert _int_from(list("ZA")) == 1
        assert run_program("FZFY") == "0"
        assert run_program("FAZFY") == "10"

    def test_an_empty_string_is_worth_nothing_in_arithmetic(self) -> None:
        """``A`` on two empty strings is 0, not the ord of a stand-in."""
        assert run_program("EEEEAY") == "0"


def _machine(code: object) -> object:
    """A machine with ``code`` in its first frame."""
    from esolangs.interpreters.stack_based.grapheme import _Machine

    return _Machine(str(code), ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.stack_based.grapheme import _Machine

    return _Machine(str(code), ScriptedIO(stdin))


class TestContract(EmptyProgramContract, CycleContract, InputCursorContract):
    """The shared shapes. ``Z`` re-runs ``KM`` -- dup then pop -- forever."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    reader = staticmethod(_reader)
    reading_program = "W"
    reading_stdin = "hi"
    position_after_read = 2
    halting_program = "FAFY"
    looping_program = "FAFHKMHZ"


@pytest.mark.parametrize(
    ("letters", "value"),
    [("", 0), ("A", 1), ("AB", 12), ("ABC", 123), ("AZ", 10), ("ZA", 1), ("Y", 25)],
)
def test_integer_conversion_shifts_only_between_letters(letters, value):
    assert run_program("F" + letters + "FY") == str(value)
    assert run_program("E" + letters + "EJY") == str(value)


def test_string_integer_conversion_stops_before_f_without_a_final_shift():
    assert run_program("EABFCEJY") == "12"


def test_spec_truth_machine_zero_branch():
    assert run_program("HFAFYHWJUZFZFY", "Z") == "0"


def test_truth_machine_body_repeats_one_with_a_live_stack():
    from esolangs.interpreters.stack_based.grapheme import _Machine

    machine = _Machine("FAFHFAFYHZ", ScriptedIO())
    for _ in range(100):
        machine.step()
        if len(machine.io.getvalue()) >= 5:
            break
    assert machine.io.getvalue() == "11111"
    assert not machine.halted


def test_n_refuses_a_negative_integer():
    """N's A-J digits have no minus sign (wiki: the reverse of intmode)."""
    with pytest.raises(HaltError, match="negative integer"):
        run_program("FAFFZFBN")  # 0 - 1


def test_an_empty_z_body_repeats_while_the_stack_is_live():
    """Z runs its function "while the stack is not empty", empty body or not."""
    from esolangs.interpreters.stack_based.grapheme import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    assert run_until_halt_or_cycle(_Machine("FAFHHZ", ScriptedIO()), limit=100) is False


def test_a_read_loop_on_a_cursorless_port_is_not_a_cycle():
    """A port with no cursor reports position 0; the snapshot counts reads."""
    from esolangs.interpreters.stack_based.grapheme import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    class _Cursorless(ScriptedIO):
        def position(self) -> int:
            return 0

    machine = _Machine("FAFHWMHZ", _Cursorless("a\n" * 10))
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine, limit=100)
