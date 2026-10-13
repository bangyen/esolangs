"""Minifuck through the shared API, CLI and machinery."""

import re
from pathlib import Path

import pytest

import esolangs
from esolangs import _check_program
from esolangs.exceptions import TemplateError
from tests.api.test_api_contracts import (
    XOR,
)
from tests.cli.test_cli import call_main
from tests.support.cli_support import _failure, call_both
from tests.support.reference import REFERENCE


def test_describe_template_still_hides_stdin_fields(capsys) -> None:
    output, _error = call_both(["describe", "Minifuck"], capsys)
    assert "input_shape" not in output
    assert "generate --bits" in output


class TestMessagesNameTheThingThatIsWrong:
    """Small, and each one sent a reader to the wrong word."""

    def test_encode_points_at_a_flag_not_a_python_call(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`instantiate()` is not reachable from a shell."""
        with pytest.raises(SystemExit) as exc:
            call_main(["encode", "Minifuck", "10"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "instantiate()" not in err
        assert "esolangs generate --bits" in err


def test_template_hint_names_cli_bits_and_correction_runs(tmp_path, capsys) -> None:
    _, err = _failure(["generate", "--bits", "0", "Minifuck", "0110"], capsys)
    assert "hint: pass exactly 2 0/1 digits to --bits, one per input" in err
    assert "instantiate()" not in err
    program, err = call_both(["generate", "--bits", "01", "Minifuck", "0110"], capsys)
    assert err == ""
    path = tmp_path / "generated.mini"
    path.write_text(program)
    answer, err = call_both(["run", "Minifuck", str(path)], capsys)
    assert answer.strip() == "1"
    assert err == ""


class TestFillingSomethingWithNoSlots:
    """ "0 inputs" is true and answers a question nobody asked."""

    def test_a_plain_program_says_it_is_not_a_template(self) -> None:
        """The mistake is "this is not a template", not a count of zero."""
        with pytest.raises(esolangs.TemplateError, match=re.escape("no run of '$'")):
            esolangs.instantiate("Minifuck", "abc", [1, 0])

    def test_filling_twice_says_the_same_thing(self) -> None:
        """The other way to get here, and it looks identical from inside."""
        template = esolangs.generate("Minifuck", "0110")
        filled = esolangs.instantiate("Minifuck", template, [1, 0])
        with pytest.raises(esolangs.TemplateError, match="already been applied"):
            esolangs.instantiate("Minifuck", filled, [1, 0])

    def test_a_real_slot_mismatch_still_counts(self) -> None:
        """The count is the right answer when there *are* slots."""
        template = esolangs.generate("Minifuck", "0110")
        with pytest.raises(esolangs.TemplateError, match="2 inputs"):
            esolangs.instantiate("Minifuck", template, [1, 0, 1])


def test_template_hint_and_example() -> None:
    template = esolangs.generate("Minifuck", "0110")
    with pytest.raises(esolangs.TemplateError) as caught:
        esolangs.instantiate("Minifuck", template, [0])
    assert "exactly 2 integer bits" in caught.value.__notes__[0]
    program = esolangs.instantiate("Minifuck", template, [0, 1])
    assert esolangs.read_answer("Minifuck", esolangs.run("Minifuck", program)) == "1"


class TestInstantiateValidates:
    """A wrong call is refused where it is made, not one layer downstream."""

    def test_the_bit_count_must_match_the_slots(self) -> None:
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(TemplateError, match="2 inputs, but 1 bit was given"):
            esolangs.instantiate("Minifuck", template, [1])

    def test_a_bit_must_be_a_bit(self) -> None:
        """``2`` was substituted silently into a program that then lied."""
        template = esolangs.generate("Minifuck", XOR)
        with pytest.raises(esolangs.ArgumentError, match="must each be 0 or 1"):
            esolangs.instantiate("Minifuck", template, [2, 0])

    def test_a_non_string_template_is_refused_before_provenance(self) -> None:
        """With a table, ``_is_template_for`` called ``.replace`` on the value."""
        with pytest.raises(TemplateError, match="must be the string"):
            esolangs.instantiate("Minifuck", 5, [1], width=None, truth_table=XOR)


class TestCapabilityListing:
    """`esolangs list` can answer what the README sends a reader to it for."""

    def test_details_marks_generators_templates_and_examples(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The name column is as wide as the longest name, and names hold
        # single spaces only, so two or more end it.
        rows = dict(
            (*re.split(r"\s{2,}", line.strip(), maxsplit=1), "")[:2]
            for line in call_main(["list", "--details"], capsys).splitlines()
        )
        assert rows[REFERENCE] == "gen ex"
        assert rows["Minifuck"] == "gen tmpl ex"


class TestTemplatesAreReachableFromTheCli:
    """Seventeen languages a CLI-only user could not finish."""

    def test_bits_completes_every_row(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The refusal pointed at ``esolangs.instantiate``, a Python call."""
        got = ""
        for a in (0, 1):
            for b in (0, 1):
                program = call_main(
                    ["generate", "--bits", f"{a}{b}", "Minifuck", "0110"], capsys
                )
                path = tmp_path / "m.txt"
                path.write_text(program.rstrip("\n"))
                got += call_main(["run", "Minifuck", str(path)], capsys)
        assert got == "0110"

    def test_bits_rejects_a_non_binary_string(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--bits", "2x", "Minifuck", "0110"], capsys)
        assert exc.value.code == 2
        assert "must be a string of 0s and 1s" in capsys.readouterr().err

    def test_bits_on_a_reader_says_so(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--bits", "01", REFERENCE, "0110"], capsys)
        assert exc.value.code == 2
        assert "reads its inputs" in capsys.readouterr().err


def test_running_one_unfilled_is_refused() -> None:
    """Minifuck ignored its slots and reported a constant as the answer."""
    template = esolangs.generate("Minifuck", XOR)
    with pytest.raises(TemplateError) as exc:
        esolangs.run("Minifuck", template)
    assert "unfilled runs of '$'" in str(exc.value)
    assert "instantiate" in str(exc.value)


def test_instantiating_gives_the_right_answer() -> None:
    """The whole point: all four rows, executed."""
    template = esolangs.generate("Minifuck", XOR)
    got = "".join(
        esolangs.run("Minifuck", esolangs.instantiate("Minifuck", template, [a, b]))
        for a in (0, 1)
        for b in (0, 1)
    )
    assert got == XOR


def test_an_unfilled_template_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """It stepped one to a confident ``output: '0'``, which was wrong."""
    path = tmp_path / "t.txt"
    path.write_text(esolangs.generate("Minifuck", "0110"))
    with pytest.raises(SystemExit) as exc:
        call_main(["debug", "Minifuck", str(path)], capsys)
    assert exc.value.code == 2
    assert "unfilled runs of '$'" in capsys.readouterr().err


class TestPackageSurface:
    """Minifuck follows public source validation."""

    @pytest.mark.parametrize("language", ["Minifuck", REFERENCE])
    def test_check_runnable_refuses_a_non_source(self, language: str) -> None:
        """An int leaked a TypeError for a template language and passed elsewhere."""
        with pytest.raises(esolangs.ProgramError, match="string of source"):
            _check_program(language, 5)
