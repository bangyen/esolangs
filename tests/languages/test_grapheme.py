"""Grapheme through the shared API, CLI and machinery."""

import warnings

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import DialectSettings
from esolangs._evaluate import _evaluate
from esolangs.debugger import make_debugger
from tests.api.test_api_contracts import XOR
from tests.cli.test_cli import call_main
from tests.reference import REFERENCE
from tests.support.cli_support import call_both
from tests.support.stdin_check import _check_stdin
from tests.support.witness_tables import witnesses


@pytest.mark.filterwarnings("ignore::UserWarning")
class TestGraphemeReadsWhatTheDocsNowSay:
    """The stated mechanism was wrong, and so was its stated direction."""

    def test_only_an_a_line_reads_as_one(self) -> None:
        """'0', '1', 'x' and ' ' are all non-empty and all read as 0."""
        program = esolangs.generate("Grapheme", "01")
        answers = {}
        for line in ("A", "%", "0", "1", "x", " "):
            output = esolangs.run("Grapheme", program, stdin=line + "\n", timeout=10)
            answers[line] = esolangs.read_answer("Grapheme", output)
        assert answers == {
            "A": "1",
            "%": "0",
            "0": "0",
            "1": "0",
            "x": "0",
            " ": "0",
        }


def test_conversion_reaches_debugger_and_bound_language():
    settings = DialectSettings(integer_conversion="after_each_letter")
    language = esolangs.Language("Grapheme")
    assert language.run("FAFY", settings=settings) == "10"
    debugger = make_debugger("Grapheme", "FAFY", settings=settings)
    debugger.run(max_steps=10)
    assert debugger.vm.output == "10"


# The dialect is machine-wide; one string call and one Z rewind witness it.
@pytest.mark.parametrize("source", ["EFAFYEG", "FZFHFAFYMHZ"])
def test_called_code_uses_selected_conversion(source):
    assert (
        esolangs.run(
            "Grapheme",
            source,
            settings=DialectSettings(integer_conversion="after_each_letter"),
        )
        == "10"
    )


def test_numeric_and_function_conversion_remain_literal():
    assert (
        esolangs.run(
            "Grapheme",
            "FAFJYHABHJY",
            settings=DialectSettings(integer_conversion="after_each_letter"),
        )
        == "102"
    )


def test_string_skip_count_uses_conversion():
    source = "FZFEAEFZFV" + "P" * 9 + "TY"
    settings = DialectSettings(integer_conversion="after_each_letter")
    assert esolangs.run("Grapheme", source, settings=settings) == "0"
    assert esolangs.run("Grapheme", source) == "1"


@pytest.mark.parametrize(("source", "expected"), [("FAFDY", "1"), ("EABEDY", "AB")])
def test_unset_names_read_as_themselves(source, expected):
    assert esolangs.run("Grapheme", source) == expected


@pytest.mark.medium
def test_generated_corpus():
    settings = DialectSettings(integer_conversion="after_each_letter")
    for n in range(1, 4):
        for table in witnesses(n):
            for balance in (False, True):
                source = esolangs.generate(
                    "Grapheme", table, settings=settings, balance=balance
                )
                assert _evaluate("Grapheme", source, inputs=n) == table


@pytest.mark.medium
def test_prose_conversion_at_six_inputs():
    table = "".join(str(row.bit_count() & 1) for row in range(64))
    source = esolangs.generate(
        "Grapheme",
        table,
        settings=DialectSettings(integer_conversion="after_each_letter"),
    )
    assert _evaluate("Grapheme", source, inputs=6) == table


def test_metadata():
    settings = esolangs.describe("Grapheme")["dialect_settings"]
    assert settings["integer_conversion"]["default"] == "between_letters"
    assert settings["integer_conversion"]["choices"] == (
        "between_letters",
        "after_each_letter",
    )
    assert set(settings) == {"integer_conversion"}


class TestGrapheme:
    def test_stack_exposed(self) -> None:
        vm = debugger_api.make_vm("Grapheme", "FAFY")
        assert (vm.ip, vm.memory, vm.stack) == ((0,), [], [])
        vm.step()  # F starts int mode
        vm.step()  # A accumulates
        vm.step()  # F ends int mode, pushes 1
        assert vm.stack == [1]
        vm.step()  # Y prints
        assert vm.output == "1"
        assert vm.halted
        assert vm.ip == (len("FAFY"),)  # frames are gone once halted
        assert vm.memory == []

    def test_rejects_non_uppercase(self) -> None:
        with pytest.raises(ValueError, match="uppercase"):
            debugger_api.make_vm("Grapheme", "a")

    def test_ip_exposes_the_call_stack(self) -> None:
        # FAF pushes 1, EKE pushes the string "K"; G calls it as a nested
        # frame (K dups the shared stack's top), so ip grows to (caller pc,
        # callee pc) while that frame is active instead of folding it into
        # one cursor.
        vm = debugger_api.make_vm("Grapheme", "FAFEKEG")
        for _ in range(7):
            vm.step()
        assert vm.ip == (7, 0)  # caller's pc past G, callee's pc at its start
        assert vm.stack == [1]
        vm.step()  # the callee's K command runs, then the frame finishes
        assert vm.halted
        assert vm.ip == (7,)  # the callee frame is gone once it returns
        assert vm.stack == [1, 1]


class TestStdinIsCheckedAgainstTheDeclaredAlphabet:
    """`encode` refused these bytes all along; `run` answered them."""

    def test_a_correct_encoding_is_silent_and_right(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Doing it right must stay quiet, or the check is noise."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate(REFERENCE, "0101"))
        out, err = call_both(["run", REFERENCE, str(path)], capsys, stdin="01")
        assert out.strip() == "1"
        assert err == ""

    def test_the_alphabet_check_reads_the_declared_alphabet(self) -> None:
        """Grapheme's own bits are %/A, so 0/1 is what is wrong there."""
        _check_stdin("Grapheme", "%\nA\n")
        # 0/1 is wrong *here*, and the specific message is the one that
        # fires: the general stray-line rule runs last so a language with
        # something better to say keeps saying it.
        with pytest.raises(esolangs.ArgumentError, match="spells its bits"):
            _check_stdin("Grapheme", "0\n1\n")


class TestTheShapeWarningFiresOnlyWhenItShould:
    """The last silent-wrong path: stdin in the shape a reader expects."""

    def test_the_warning_does_not_change_the_answer(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It is advice; the run is exactly what it was."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110"))
        warned = call_main(["run", "Grapheme", str(path)], capsys, stdin="1\n0\n")
        capsys.readouterr()
        stdin = esolangs.encode_inputs("Grapheme", [1, 0])
        right = call_main(["run", "Grapheme", str(path)], capsys, stdin=stdin)
        assert warned == "0"
        assert right == "1"


def test_grapheme_names_its_input_alphabet() -> None:
    """Digits are read as truthy, so 0/1 lines answer the wrong row."""
    assert esolangs.describe("Grapheme")["input_encoding"] == ("%", "A")
    assert esolangs.describe(REFERENCE)["input_encoding"] == ("0", "1")


def test_the_named_alphabet_is_the_one_that_works() -> None:
    """The point of the key: using it reproduces the truth table."""
    zero, one = esolangs.describe("Grapheme")["input_encoding"]  # type: ignore[misc]
    program = esolangs.generate("Grapheme", XOR)
    got = "".join(
        esolangs.run("Grapheme", program, stdin=f"{[zero, one][a]}\n{[zero, one][b]}\n")
        for a in (0, 1)
        for b in (0, 1)
    )
    assert got == XOR


def test_the_wrong_alphabet_is_warned_about() -> None:
    """The same judgement `check_stdin` raises, rendered as advice."""
    program = esolangs.generate("Grapheme", "0110")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        esolangs.run("Grapheme", program, stdin="0\n1\n", timeout=10)


def test_a_zero_line_reads_as_true_so_zero_is_percent():
    assert esolangs.encode_inputs("Grapheme", [1, 0, 1]) == "A\n%\nA\n"
    assert (
        _evaluate("Grapheme", esolangs.generate("Grapheme", "10010110"), inputs=3)
        == "10010110"
    )
