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


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 2, 3, 7, 13, 80])
def test_generated_grapheme_programs_run_at_arbitrary_breaks(width: int) -> None:
    from esolangs.tools.grapheme import grapheme
    from esolangs.tools.wrap import wrap_chars

    tables = [f"{value:04b}" for value in range(16)]
    tables += ["00000000", "11111111", "01101001", "01010011"]
    for table in tables:
        n = len(table).bit_length() - 1
        source = grapheme(table)
        wrapped = wrap_chars(source, width)
        assert max(map(len, wrapped.splitlines())) <= width
        for row, expected in enumerate(table):
            inputs = ["A" if bit == "1" else "%" for bit in f"{row:0{n}b}"]
            io = ScriptedIO("\n".join(inputs))
            run(wrapped, io)
            assert io.getvalue() == expected
            assert io.reads == n


class TestVariables:
    def test_undeclared_halts(self) -> None:
        with pytest.raises(HaltError, match="undeclared"):
            run_program("EAED")


class TestFunctions:
    def test_g_on_input_with_bad_commands_rejected(self) -> None:
        """A string read from input and executed via G is validated, not asserted on."""
        import pytest

        with pytest.raises(ValueError, match="unhandled command"):
            run_program("WG", "zkg")


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
        assert machine.io.getvalue() == "1"
        # every frame has popped, so ip falls back to where the program ends
        assert machine.ip == (len("FAFY"),)

        with pytest.raises(ValueError, match="uppercase"):
            _Machine("hello", ScriptedIO())


class TestEdgeCases:
    def test_recursion_is_not_artificially_capped(self) -> None:
        """A 501-deep finite call chain follows the language's unbounded stack."""
        # the body decrements the count, keeps a copy, and calls itself
        # again through Q while the copy is nonzero
        program = "H" + "FFTPBKFAFDQ" + "H" + "FAFC" + "FAFD" + "G"
        assert run_program("FEZZF" + program) == ""
        assert run_program("FEZZF" + "FFT" + "A" + program) == ""

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


class TestNumberEncoding:
    """Letters stand for digits, with Z standing for zero.

    Numbers only ever reach the tests through programs that print their
    result, where the encoding and the arithmetic that follows it cannot be
    told apart.  These read the conversion directly.
    """

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
        """The buffer a closing ``F`` parses follows the same rule as ``J``.

        The two conversions are written out separately, and only the ``J``
        one is read here -- so intmode's own ``Z`` went unchecked, and
        every program that spells a number avoids ``Z`` by writing the
        shorter letter instead.
        """
        from esolangs.interpreters.stack_based.grapheme import _int_from

        assert _int_from(list("Z")) == 0
        assert _int_from(list("A")) == 1
        assert _int_from(list("AZ")) == 10
        assert _int_from(list("ZA")) == 1
        assert run_program("FZFY") == "0"
        assert run_program("FAZFY") == "10"

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
