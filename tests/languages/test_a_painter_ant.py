"""A Painter Ant through the shared API, CLI and machinery."""

import pytest

import esolangs
from esolangs._execution import interpreter_errors
from tests.cli.test_cli import call_main
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
