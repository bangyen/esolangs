"""A Painter Ant through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs
from esolangs._execution import interpreter_errors
from tests.cli.test_cli import _program, call_main
from tests.cli_support import call_both
from tests.generator_support import evaluate_generated


class TestAMultiWordNameSuggestsQuoting:
    """`describe A Painter Ant` blamed the third word."""

    def test_the_joined_positionals_are_suggested(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The suggester can already resolve it; it was never asked."""
        with pytest.raises(SystemExit) as exc:
            call_main(["describe", "A", "Painter", "Ant"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "quote" in err.lower()
        assert "A Painter Ant" in err


def test_template_rewording_keeps_notes_and_quotes_language():
    from esolangs.cli_hints import _template_hint

    error = esolangs.TemplateError(
        "unfilled slots; fill them with esolangs.instantiate("
    )
    error.add_note("hint: keep the original template")
    assert _template_hint(error, "A Painter Ant") == (
        "unfilled slots; fill them with: esolangs generate --bits <bits> "
        '"A Painter Ant" <table>\nhint: keep the original template'
    )


@pytest.mark.parametrize(
    ("message", "hint"),
    [
        ("could not convert string to float: 'x'", "decimal number"),
        ("bytes must be in range(0, 256)", "between 0 and 255"),
        ("malformed operand", "describe --spec 'A Painter Ant'"),
    ],
)
def test_unannotated_value_error_keeps_its_diagnostic(message, hint):
    with (
        pytest.raises(esolangs.ProgramError, match=r".+") as caught,
        interpreter_errors("recursion", language="A Painter Ant"),
    ):
        raise ValueError(message)
    assert str(caught.value) == message
    assert hint in caught.value.__notes__[0]


class TestAPaintersMarkMustBeInAGrid:
    """Its pattern was ``([o@])``, so any stray ``o`` read as a zero."""

    def test_garbage_is_refused(self) -> None:
        """It was the one language that read a crash message as an answer."""
        with pytest.raises(esolangs.ProgramError):
            esolangs.read_answer("A Painter Ant", "hello world")

    def test_a_real_grid_still_reads(self) -> None:
        """The check is worth nothing if it costs the actual answers."""
        assert evaluate_generated("A Painter Ant", "0110") == "0110"


class TestPrintedCommandsCanBePasted:
    """The tool emitted commands it cannot itself parse."""

    SPACED = "A Painter Ant"

    def test_the_spec_line_is_quoted(self, capsys: pytest.CaptureFixture[str]) -> None:
        """And unspaced names stay unquoted, since quoting them is noise."""
        out, _err = call_both(["describe", self.SPACED], capsys)
        assert f'--spec "{self.SPACED}"' in out
        plain, _err = call_both(["describe", "brainfuck"], capsys)
        assert "--spec brainfuck" in plain

    def test_the_quoted_command_actually_runs(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The point of quoting it, and the thing a test can check."""
        out, _err = call_both(["describe", "--spec", self.SPACED], capsys)
        assert out.startswith("Interpreter for A Painter Ant")

    def test_the_template_hint_is_quoted(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``encode`` on a template language points at ``generate --bits``."""
        with pytest.raises(SystemExit):
            call_main(["encode", self.SPACED, "10"], capsys)
        assert f'"{self.SPACED}"' in capsys.readouterr().err

    def test_every_spaced_name_is_quoted_in_its_describe(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every name, since one unquoted survivor is the whole bug again."""
        spaced = [n for n in esolangs.list_languages() if " " in n]
        assert len(spaced) == 10
        for name in spaced:
            out, _err = call_both(["describe", name], capsys)
            assert f'--spec "{name}"' in out, name


def test_a_painter_ant_is_the_one_that_cannot_be_stepped() -> None:
    """Stated as data: three million steps leave it with no output."""
    unsteppable = [
        n
        for n in esolangs.list_languages()
        if not esolangs.describe(n)["steppable_to_answer"]
    ]
    assert unsteppable == ["A Painter Ant"]


def test_describe_prints_the_traits_that_decide_how_to_drive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A Painter Ant cannot be stepped to its answer; it says so."""
    out = call_main(["describe", "A Painter Ant"], capsys)
    assert "steppable_to_answer" in out
    assert "False" in out


def test_run_read_answer_prints_the_bit_for_a_dump(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Painter Ant's grid, reduced through the separate answer reader."""
    program = esolangs.instantiate(
        "A Painter Ant", esolangs.generate("A Painter Ant", "0110"), [0, 1]
    )
    out = call_main(["run", "A Painter Ant", _program(tmp_path, program)], capsys)
    assert esolangs.read_answer("A Painter Ant", out).strip() == "1"
