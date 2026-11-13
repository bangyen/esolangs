"""Grapheme through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import run
from esolangs.debugger import make_debugger
from tests.support.cli_support import call_both, call_main
from tests.support.evaluation import _evaluate
from tests.support.reference import REFERENCE
from tests.support.witness_tables import XOR, witnesses


class TestGraphemeReadsWhatTheDocsNowSay:
    """The stated mechanism was wrong, and so was its stated direction."""

    def test_only_an_a_line_reads_as_one(self) -> None:
        """'0', '1', 'x' and ' ' are all non-empty and all read as 0."""
        program = esolangs.generate("Grapheme", "01")
        answers = {}
        for line in ("A", "%", "0", "1", "x", " "):
            output = run(
                "Grapheme",
                program,
                stdin=line + "\n",
                limits=esolangs.ExecutionLimits(execution_timeout=10),
            ).output
            answers[line] = esolangs.read_answer("Grapheme", output)
        assert answers == {
            "A": "1",
            "%": "0",
            "0": "0",
            "1": "0",
            "x": "0",
            " ": "0",
        }


def test_conversion_reaches_debugger_and_bound_language(monkeypatch) -> None:
    settings = esolangs.Language("Grapheme").settings(
        integer_conversion="after_each_letter"
    )
    language = esolangs.Language("Grapheme")
    assert language.run("FAFY", settings=settings).output == "10"
    debugger = make_debugger("Grapheme", "FAFY", settings=settings)
    debugger.run(max_steps=10)
    assert debugger.vm.output == "10"

    from esolangs.languages.grapheme import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Grapheme",
        "WKY\nFAFY",
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("A", "A10"), ("Z", "Z10"), ("Q", "Q10")),
        settings=settings,
    )


# The dialect is machine-wide; one string call and one Z rewind witness it.
@pytest.mark.parametrize("source", ["EFAFYEG", "FZFHFAFYMHZ"])
def test_called_code_uses_selected_conversion(source) -> None:
    assert (
        run(
            "Grapheme",
            source,
            settings=esolangs.Language("Grapheme").settings(
                integer_conversion="after_each_letter"
            ),
        ).output
        == "10"
    )


def test_numeric_and_function_conversion_remain_literal() -> None:
    assert (
        run(
            "Grapheme",
            "FAFJYHABHJY",
            settings=esolangs.Language("Grapheme").settings(
                integer_conversion="after_each_letter"
            ),
        ).output
        == "102"
    )


def test_string_skip_count_uses_conversion() -> None:
    source = "FZFEAEFZFV" + "P" * 9 + "TY"
    settings = esolangs.Language("Grapheme").settings(
        integer_conversion="after_each_letter"
    )
    assert run("Grapheme", source, settings=settings).output == "0"
    assert run("Grapheme", source).output == "1"


@pytest.mark.parametrize(("source", "expected"), [("FAFDY", "1"), ("EABEDY", "AB")])
def test_unset_names_read_as_themselves(source, expected) -> None:
    assert run("Grapheme", source).output == expected


@pytest.mark.medium
def test_generated_corpus() -> None:
    settings = esolangs.Language("Grapheme").settings(
        integer_conversion="after_each_letter"
    )
    for n in range(1, 4):
        for table in witnesses(n):
            for balance in (False, True):
                source = esolangs.generate(
                    "Grapheme", table, settings=settings, balance=balance
                )
                assert _evaluate("Grapheme", source, inputs=n) == table


@pytest.mark.medium
def test_prose_conversion_at_six_inputs() -> None:
    table = "".join(str(row.bit_count() & 1) for row in range(64))
    source = esolangs.generate(
        "Grapheme",
        table,
        settings=esolangs.Language("Grapheme").settings(
            integer_conversion="after_each_letter"
        ),
    )
    assert _evaluate("Grapheme", source, inputs=6) == table


def test_metadata() -> None:
    settings = esolangs.describe("Grapheme").dialect_settings
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


class TestInputUsesTheDeclaredAlphabet:
    """`encode` refused these bytes all along; `run` answered them."""

    def test_a_correct_encoding_is_silent_and_right(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Doing it right must stay quiet, or the check is noise."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate(REFERENCE, "0101").source)
        out, err = call_both(["run", REFERENCE, str(path)], capsys, stdin="01")
        assert out.strip() == "1"
        assert err == ""

    def test_the_alphabet_check_reads_the_declared_alphabet(self) -> None:
        """Grapheme's own bits are %/A, so 0/1 is what is wrong there."""
        assert esolangs.encode_inputs("Grapheme", [0, 1]) == "%\nA\n"
        source = esolangs.generate("Grapheme", "0101")
        assert run("Grapheme", source, stdin="%\nA\n").output == "1"
        assert run("Grapheme", source, stdin="0\n1\n").output == "0"


class TestRawInputKeepsItsNativeMeaning:
    def test_the_cli_reads_the_supplied_alphabet(
        self, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110").source)
        raw = call_main(["run", "Grapheme", str(path)], capsys, stdin="1\n0\n")
        capsys.readouterr()
        stdin = esolangs.encode_inputs("Grapheme", [1, 0])
        right = call_main(["run", "Grapheme", str(path)], capsys, stdin=stdin)
        assert raw == "0"
        assert right == "1"


def test_grapheme_names_its_input_alphabet() -> None:
    """Digits are read as truthy, so 0/1 lines answer the wrong row."""
    assert esolangs.describe("Grapheme").input_encoding == ("%", "A")
    assert esolangs.describe(REFERENCE).input_encoding == ("0", "1")


def test_the_named_alphabet_is_the_one_that_works() -> None:
    """The point of the key: using it reproduces the truth table."""
    zero, one = esolangs.describe("Grapheme").input_encoding
    program = esolangs.generate("Grapheme", XOR)
    got = "".join(
        run("Grapheme", program, stdin=f"{[zero, one][a]}\n{[zero, one][b]}\n").output
        for a in (0, 1)
        for b in (0, 1)
    )
    assert got == XOR


def test_digit_lines_are_read_as_zero() -> None:
    program = esolangs.generate("Grapheme", "0110")
    assert (
        run(
            "Grapheme",
            program,
            stdin="0\n1\n",
            limits=esolangs.ExecutionLimits(execution_timeout=10),
        ).output
        == "0"
    )


def test_a_zero_line_reads_as_true_so_zero_is_percent() -> None:
    assert esolangs.encode_inputs("Grapheme", [1, 0, 1]) == "A\n%\nA\n"
    assert (
        _evaluate("Grapheme", esolangs.generate("Grapheme", "10010110"), inputs=3)
        == "10010110"
    )
