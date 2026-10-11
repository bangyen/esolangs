"""Unit tests for the Grapheme interpreter."""

from functools import partial

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.grapheme import _Machine as Grapheme
from esolangs.interpreters.stack_based.grapheme import run
from esolangs.vm import run_until_halt_or_ancestor
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    InputCursorContract,
)
from tests.interpreters.cursorless_io import PositionlessIO
from tests.interpreters.runner import run_program as _run_program
from tests.support.raises import assert_rejected_with_hint

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
        pytest.param("EHLLOWORLDEY", "HLLOWORLD", id="stringmode"),
        pytest.param("EAY", "", id="stringmode_to_end"),
        pytest.param("FAFFBFAY", "3", id="intmode"),
        pytest.param("FAFFBFBY", "1", id="subtract"),
        pytest.param("FAFFBFSY", "2", id="multiply"),
        pytest.param("FCFFBFRY", "0", id="floor_divide"),
        pytest.param("EAEEAEAY", "130", id="string_math_ords"),
        pytest.param("FAFKYY", "11", id="duplicate"),
        pytest.param("FAFFBFLYY", "12", id="swap"),
        pytest.param("EABEECDEPYY", "ABCD", id="reverse"),
        pytest.param("EAEM", "", id="pop"),
        pytest.param("EAEOY", "1", id="length"),
        pytest.param("FAFNY", "A", id="int_to_string"),
        pytest.param("EAJEJY", "20", id="string_to_int"),
        pytest.param("EAEKKCDY", "A", id="set_and_get"),
        pytest.param("EVARIABLEEMYVAREKCDY", "VARIABL", id="wiki_variables"),
        pytest.param("EBEEAECEAEDY", "B", id="set_variable_shadows_name"),
        pytest.param("FAFEYEG", "1", id="g_executes_string"),
        pytest.param("FAFHYHIE", "1", id="i_runs_function"),
        pytest.param("FAFHYHZ", "1", id="z_runs_while_stack_nonempty"),
        pytest.param("FAFKHYHZ", "11", id="z_repeats"),
        pytest.param("FAFKKQY", "1", id="q_needs_a_function"),
        pytest.param("FAFKKVY", "1", id="v_truthy_no_jump"),
        pytest.param("FAFKZY", "1", id="z_needs_a_function"),
        pytest.param("FFFAFUKY", "0", id="u_truthy_runs"),
        pytest.param("FAFFFXKY", "1", id="x_falsy_skips"),
        pytest.param("FAFFBFFCFXYKY", "21", id="x_resumes_two_on"),
        pytest.param("FAFFBFHXYKHI", "1", id="x_opens_its_body"),
        pytest.param("FAFJJY", "1", id="j_on_int"),
        pytest.param("EFAEJY", "0", id="j_on_string"),
        pytest.param("EAENY", "A", id="n_on_string"),
        pytest.param("FFNY", "J", id="n_on_zero"),
        pytest.param("FAFIY", "1", id="i_pushes_non_function"),
        pytest.param("F", "", id="unterminated_int_mode"),
        pytest.param("H", "", id="unterminated_func_mode"),
        pytest.param("FBFFFTFFVMY", "2", id="v_jumps_forward"),
        pytest.param("FAFFBFFCFFDFHKMMYHZ", "31", id="z_lap_starts_empty"),
        pytest.param("FAFFBFHYHI", "2", id="call_does_not_repeat"),
        pytest.param("EEEEAY", "0", id="empty_string_is_zero"),
        pytest.param("EABFCEJY", "12", id="string_integer_conversion"),
        pytest.param("FAFFZFBFZFVFAFY", "1", id="v_negative_skips_nothing"),
        pytest.param("FBFHAHCHAHDY", "2", id="function_names_a_variable"),
    ],
)
def test_prints(code: str, expected: str) -> None:
    assert run_program(code) == expected


@pytest.mark.parametrize(
    ("code", "stdin", "error", "match"),
    [
        # a string read from input and executed via G is validated
        pytest.param(
            "WG", "zkg", ValueError, "unhandled command", id="g_on_input_rejected"
        ),
        # truthy 1 on the stack, fn Y: Q pops fn and the 1, then Y pops empty
        pytest.param("FAFHYHQ", "", HaltError, "popped", id="q_conditional_execution"),
        pytest.param("AB", "", HaltError, "popped", id="pop_empty_halts"),
        pytest.param("hello", "", ValueError, "uppercase", id="lowercase_rejected"),
        pytest.param("FFFFVY", "", HaltError, "popped", id="v_branches_on_falsy"),
        # N's A-J digits have no minus sign; 0 - 1 refuses
        pytest.param(
            "FAFFZFBN", "", HaltError, "negative integer", id="n_refuses_negative"
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


class TestErrors:
    def test_constructor_builds_a_runnable_machine_and_validates(self) -> None:
        """The constructor is the one way a program becomes a machine."""
        machine = Grapheme("FAFY", ScriptedIO())
        assert machine.ip == (0,)  # one frame, at its start
        while not machine.halted:
            machine.step()
        assert machine.io.getvalue() == "1"
        # every frame has popped, so ip falls back to where the program ends
        assert machine.ip == (len("FAFY"),)

        with pytest.raises(ValueError, match="uppercase"):
            Grapheme("hello", ScriptedIO())


class TestEdgeCases:
    def test_truthiness_of_strings_and_functions(self) -> None:
        assert run_program("EAETY") == "0"  # "A" truthy -> push 0
        assert run_program("EETY") == "1"  # "" falsy -> push 1
        assert run_program("HABHTY") == "0"  # nonempty function truthy
        assert run_program("HHTY") == "1"  # empty function falsy

    def test_the_last_command_leaves_the_machine_halted(self) -> None:
        """A frame finishes on the step that runs its final command."""
        machine = Grapheme("FAFY", ScriptedIO())
        for _ in range(4):
            assert not machine.halted
            machine.step()
        assert machine.halted

    def test_recursion_is_not_artificially_capped(self) -> None:
        """A 501-deep finite call chain follows the language's unbounded stack."""
        # the body decrements the count, keeps a copy, and calls itself again
        program = "H" + "FFTPBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
        assert run_program("FEZZF" + program) == ""
        assert run_program("FEZZF" + "FFT" + "A" + program) == ""

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


class TestStepMachine:
    def test_the_read_pushes_the_whole_line(self) -> None:
        """``W`` pushes the line itself, not a byte of it."""
        machine = Grapheme("W", ScriptedIO("hi"))
        machine.step()
        assert machine.stack == ["hi"]

    def test_a_closed_mode_leaves_the_frame_as_it_found_it(self) -> None:
        """After a mode ends, the frame reads as one that never opened it."""
        for code, value in (("EAEK", "A"), ("FAFK", 1), ("HAHK", ("func", "A"))):
            machine = Grapheme(code, ScriptedIO())
            for _ in range(3):
                machine.step()
            assert machine.snapshot() == (
                (value,),
                frozenset(),
                ((code, 3, "", (), -1, False),),
                0,
                0,  # successful reads, for a port with no cursor (286aa9b8)
            )


def _machine(code: object) -> object:
    """A machine with ``code`` in its first frame."""
    return Grapheme(str(code), ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    return Grapheme(str(code), ScriptedIO(stdin))


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


def test_an_empty_z_body_repeats_while_the_stack_is_live():
    """Z runs its function "while the stack is not empty", empty body or not."""
    from esolangs.vm import run_until_halt_or_cycle

    assert run_until_halt_or_cycle(Grapheme("FAFHHZ", ScriptedIO()), limit=100) is False


def test_a_read_loop_on_a_cursorless_port_is_not_a_cycle():
    """A port with no cursor reports position 0; the snapshot counts reads."""
    from esolangs.vm import run_until_halt_or_cycle

    machine = Grapheme("FAFHWMHZ", PositionlessIO("a\n" * 10))
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine, limit=100)


def test_grapheme_replayed_function_is_detected_as_an_ancestor() -> None:
    # The function invokes itself without changing the shared state.
    machine = Grapheme("HKGHKG", ScriptedIO())
    assert run_until_halt_or_ancestor(machine) is False


def test_grapheme_changing_stack_halts() -> None:
    # The function decrements the count before Q recurs, so each entry
    # has a different shared stack and reaches the zero base case.
    code = "FAF" + "H" + "FFTPBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
    assert run_until_halt_or_ancestor(Grapheme(code, ScriptedIO())) is True


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Grapheme", "abc", "uppercase Latin")
