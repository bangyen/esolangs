"""Unit tests for the Grapheme interpreter."""

from functools import partial

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.grapheme import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    InputCursorContract,
)
from tests.interpreters.cursorless_io import PositionlessIO
from tests.interpreters.runner import run_program as _run_program

run_program = partial(_run_program, run)


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


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # E HELLOWORLD E Y -> the E's terminate the string, dropping one E
        pytest.param("EHLLOWORLDEY", "HLLOWORLD", id="stringmode"),
        # no closing E: the string is flushed at end of program
        pytest.param("EAY", "", id="stringmode_accumulates_to_end"),
        # F A F -> 1; F B F -> 2; A adds; Y prints
        pytest.param("FAFFBFAY", "3", id="intmode"),
        pytest.param("FAFFBFBY", "1", id="subtract"),
        pytest.param("FAFFBFSY", "2", id="multiply"),
        pytest.param("FCFFBFRY", "0", id="floor_divide"),
        # "A" (65) + "A" (65) = 130
        pytest.param("EAEEAEAY", "130", id="string_math_uses_ords"),
        pytest.param("FAFKYY", "11", id="duplicate"),
        pytest.param("FAFFBFLYY", "12", id="swap"),
        pytest.param("EABEECDEPYY", "ABCD", id="reverse"),
        pytest.param("EAEM", "", id="pop"),
        pytest.param("EAEOY", "1", id="length"),
        # 1 -> digit 1 -> "A"
        pytest.param("FAFNY", "A", id="int_to_string"),
        # A=1 and J=10: 1*10 + 10 = 20
        pytest.param("EAJEJY", "20", id="string_to_int"),
        pytest.param("HABHNY", "AB", id="function_to_string"),
        pytest.param("EAEKKCDY", "A", id="set_and_get"),
        # D of the never-set VARIABL pushes the name itself
        pytest.param(
            "EVARIABLEEMYVAREKCDY",
            "VARIABL",
            id="the_wiki_variables_example_prints_variabl",
        ),
        pytest.param("EBEEAECEAEDY", "B", id="a_set_variable_shadows_its_name"),
        pytest.param("FAFEYEG", "1", id="g_executes_string"),
        # H Y H makes a function of Y; I runs it on the pushed 1
        pytest.param("FAFHYHIE", "1", id="i_runs_function"),
        pytest.param("FAFHYHZ", "1", id="z_runs_while_stack_nonempty"),
        # K duplicates the 1, so the Z body runs twice before the stack empties
        pytest.param("FAFKHYHZ", "11", id="z_repeats_until_the_stack_empties"),
        # Each conditional's declining arm.  Q pops two integers rather than a
        # function and a test, so there is no body; the third copy is printed.
        pytest.param("FAFKKQY", "1", id="q_ignores_a_value_that_is_not_a_function"),
        # V pops a truthy value, so the pc is left alone and Y still runs.
        pytest.param("FAFKKVY", "1", id="v_does_not_jump_when_the_test_is_truthy"),
        # Z needs a function to loop over; an integer leaves the stack as is.
        pytest.param("FAFKZY", "1", id="z_ignores_a_value_that_is_not_a_function"),
        # [1, 0]: U pops 0 (falsy) and skips the K, so Y prints the 1
        pytest.param("FAFFFUKY", "1", id="u_skips_when_falsy"),
        # [0, 1]: U pops 1 (truthy), K duplicates the 0, Y prints it
        pytest.param("FFFAFUKY", "0", id="u_does_not_skip_when_truthy"),
        # [1, 0]: X pops 0 (falsy) and skips the K, so Y prints the 1
        pytest.param("FAFFFXKY", "1", id="x_skips_next_when_falsy"),
        # [0, 1]: X pops 1 (truthy), Y prints the 0, then the K is skipped
        pytest.param("FFFAFXYK", "0", id="x_skips_after_next_when_truthy"),
        # [1, 2, 3]: X pops the truthy 3, Y prints 2, the K is skipped,
        # and the last Y prints the 1 that is still underneath.
        pytest.param("FAFFBFFCFXYKY", "21", id="x_resumes_two_commands_on"),
        # X opens a called body XYK: X pops the 2, Y prints the 1, K is skipped
        pytest.param("FAFFBFHXYKHI", "1", id="x_can_open_the_body_it_governs"),
        pytest.param("FAFJJY", "1", id="j_on_an_int_is_identity"),
        pytest.param("HABHJY", "2", id="j_on_a_function_counts_its_commands"),
        pytest.param("EFAEJY", "0", id="j_on_a_string_stops_at_an_f"),
        pytest.param("EAENY", "A", id="n_on_a_string_is_identity"),
        pytest.param("FFNY", "J", id="n_on_zero_is_j"),
        pytest.param("FAFIY", "1", id="i_pushes_back_a_non_function"),
        pytest.param("F", "", id="unterminated_int_mode"),
        pytest.param("H", "", id="unterminated_func_mode"),
        # V moves the cursor on, not back.  [2, 1, 0]: V pops the falsy 0 and
        # the offset 1, skipping the M that would discard the 2 before Y
        pytest.param(
            "FBFFFTFFVMY", "2", id="v_jumps_forward_over_the_commands_it_counts"
        ),
        # Each pass over a Z body begins with no skip outstanding: four
        # values, and a body of four commands: dup, drop, drop, print
        pytest.param(
            "FAFFBFFCFFDFHKMMYHZ", "31", id="a_z_lap_starts_with_nothing_pending"
        ),
        # Only Z re-runs its body; I runs it once.  1 and 2 on the stack, the
        # function prints one and returns; the 1 left must not restart it
        pytest.param("FAFFBFHYHI", "2", id="a_call_does_not_repeat_itself"),
        # A on two empty strings is 0, not the ord of a stand-in
        pytest.param(
            "EEEEAY", "0", id="an_empty_string_is_worth_nothing_in_arithmetic"
        ),
        pytest.param(
            "EABFCEJY",
            "12",
            id="string_integer_conversion_stops_before_f_without_a_final_shift",
        ),
    ],
)
def test_prints(code: str, expected: str) -> None:
    assert run_program(code) == expected


@pytest.mark.parametrize(
    ("code", "stdin", "error", "match"),
    [
        # a string read from input and executed via G is validated
        pytest.param(
            "WG",
            "zkg",
            ValueError,
            "unhandled command",
            id="g_on_input_with_bad_commands_rejected",
        ),
        # truthy 1 on the stack, fn Y: Q pops fn and the 1, then Y pops empty
        pytest.param("FAFHYHQ", "", HaltError, "popped", id="q_conditional_execution"),
        pytest.param("AB", "", HaltError, "popped", id="pop_empty_halts"),
        pytest.param("hello", "", ValueError, "uppercase", id="lowercase_rejected"),
        pytest.param(
            "FFFFVY", "", HaltError, "popped", id="v_branches_on_a_falsy_value"
        ),
        # N's A-J digits have no minus sign (wiki: the reverse of intmode); 0 - 1
        pytest.param(
            "FAFFZFBN",
            "",
            HaltError,
            "negative integer",
            id="n_refuses_a_negative_integer",
        ),
    ],
)
def test_refuses(code: str, stdin: str, error: type, match: str) -> None:
    with pytest.raises(error, match=match):
        run_program(code, stdin)


class TestModes:
    def test_an_unterminated_mode_is_flushed_when_its_frame_ends(self) -> None:
        """Each mode still yields its value when the code runs out."""
        assert run_program("HEABHIY") == "AB"  # string
        assert run_program("HFABHIY") == "12"  # int
        assert run_program("EHABEGNY") == "AB"  # function, via N


class TestStack:
    def test_truthiness_to_number(self) -> None:
        assert run_program("FAFTY") == "0"  # 1 is truthy -> push 0
        assert run_program("FFTY") == "1"  # 0 is falsy -> push 1


class TestSkips:
    def test_the_command_u_skips_is_one_that_would_have_printed(self) -> None:
        """Which way ``U`` skips, read from the output rather than the stack."""
        assert run_program("FAFFFUY") == ""  # falsy: the Y is skipped
        assert run_program("FBFFAFUY") == "2"  # truthy: the Y runs


class TestIO:
    def test_input(self) -> None:
        assert run_program("WKY", "hi") == "hi"

    def test_input_running_out_raises_eof(self) -> None:
        with pytest.raises(EOFError):
            run("W", ScriptedIO(""))


class TestErrors:
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
    def test_truthiness_of_strings_and_functions(self) -> None:
        assert run_program("EAETY") == "0"  # "A" truthy -> push 0
        assert run_program("EETY") == "1"  # "" falsy -> push 1
        assert run_program("HABHTY") == "0"  # nonempty function truthy
        assert run_program("HHTY") == "1"  # empty function falsy

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

    def test_v_with_a_negative_count_skips_nothing(self) -> None:
        """ "skip the next B commands" never moves back to re-run ``V``."""
        assert run_program("FAFFZFBFZFVFAFY") == "1"

    def test_a_function_names_a_variable(self) -> None:
        """The map takes "integers/strings/functions" as keys, by body."""
        assert run_program("FBFHAHCHAHDY") == "2"

    def test_the_error_messages_read_in_full(self) -> None:
        """Each message entire, not the fragment the tests match on."""
        import re

        for code, message in (
            ("M", "popped an empty stack"),
            ("FFFFR", "division by zero"),
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


def test_spec_truth_machine_zero_branch():
    assert run_program("HFAFYHWJUZFZFY", "Z") == "0"


def test_spec_truth_machine_one_branch_as_drawn_prints_zero():
    """Z pops the loop body off an empty stack, so the loop never runs."""
    assert run_program("HFAFYHWJUZFZFY", "A") == "0"


def test_spec_cat_echoes_lines_until_eof():
    from esolangs.interpreters.stack_based.grapheme import run

    io = ScriptedIO("ab\ncd\n")
    with pytest.raises(EOFError):
        run("WKYHWYHZ", io)
    assert io.getvalue() == "abcd"


def test_truth_machine_body_repeats_one_with_a_live_stack():
    from esolangs.interpreters.stack_based.grapheme import _Machine

    machine = _Machine("FAFHFAFYHZ", ScriptedIO())
    for _ in range(100):
        machine.step()
        if len(machine.io.getvalue()) >= 5:
            break
    assert machine.io.getvalue() == "11111"
    assert not machine.halted


def test_an_empty_z_body_repeats_while_the_stack_is_live():
    """Z runs its function "while the stack is not empty", empty body or not."""
    from esolangs.interpreters.stack_based.grapheme import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    assert run_until_halt_or_cycle(_Machine("FAFHHZ", ScriptedIO()), limit=100) is False


def test_a_read_loop_on_a_cursorless_port_is_not_a_cycle():
    """A port with no cursor reports position 0; the snapshot counts reads."""
    from esolangs.interpreters.stack_based.grapheme import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    machine = _Machine("FAFHWMHZ", PositionlessIO("a\n" * 10))
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine, limit=100)
