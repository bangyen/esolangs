"""What the CLI says when something is wrong, and when it stays quiet."""

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main
from esolangs.cli_io import _write_output
from tests.cli.test_cli import _FakeStdin, _program, call_main
from tests.cli_support import _failure, _refused, call_both
from tests.pick import first, languages

#: A language whose input bits are not spelled 0 and 1.
_SPELLED = next(
    n
    for n in languages(boolean_generator=True)
    if esolangs.describe(n)["input_encoding"] != ("0", "1")
)
_PADDED = first(input_shape="char_stream_padded")


class TestTheHintsStayQuietWhenTheyDoNotApply:
    """Each hint added this round rewrites one message and no others."""

    def test_encode_leaves_an_unrelated_error_alone(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Only the message naming ``instantiate()`` gets rewritten."""
        with pytest.raises(SystemExit) as exc:
            call_main(["encode", "Nonexistent", "10"], capsys)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "unknown language" in err
        assert "generate --bits" not in err


class TestSmallerReportsFromRoundFifteen:
    """Each one was information that was wrong or hard to find."""

    def test_a_bad_truth_table_echoes_the_argument(self) -> None:
        """It printed ``sorted(set(...))``: "nonsense" came back as "enos"."""
        with pytest.raises(esolangs.TruthTableError, match="got 'nonsense'"):
            esolangs.generate("brainfuck", "nonsense")

    def test_it_also_names_the_offending_character(self) -> None:
        """So a long table does not have to be diffed by eye."""
        with pytest.raises(esolangs.TruthTableError, match="at position 2"):
            esolangs.generate("brainfuck", "01x1")

    def test_a_never_written_cell_reports_a_verdict_not_a_wall(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Four hundred Nones with the answer at the far right of the line."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        out = call_main(
            ["debug", "--steps", "40", "--watch-cell", "999", "brainfuck", str(path)],
            capsys,
            stdin="1\n0\n",
        )
        assert "never written in 40 step(s)" in out
        assert "None" not in out

    @pytest.mark.parametrize(
        ("name", "phrase"),
        [
            (first(input_shape="char_stream_cyclic"), "adjacent bit characters"),
            (first(input_shape="row_index"), "one decimal row index"),
            (_PADDED, "padded with a leading"),
            ("brainfuck", "adjacent bit characters"),
        ],
    )
    def test_describe_spells_the_stdin_out(
        self, name: str, phrase: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A reader had two fields to compose; templates got a sentence."""
        out = call_main(["describe", name], capsys)
        assert phrase in out


# 1.8s over 45 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestRoundSixQol:
    """The CLI no longer sends its users to the Python API for basics."""

    def test_encode_prints_the_stdin_a_language_wants(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run --help` used to answer this with a `python -c` incantation."""
        zero, one = esolangs.describe(_SPELLED)["input_encoding"]  # type: ignore[misc]
        assert call_main(["encode", _SPELLED, "10"], capsys) == f"{one}\n{zero}\n"
        assert call_main(["encode", _PADDED, "101"], capsys) == "0101"

    def test_encode_then_run_computes_the_table(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The pipeline the help now recommends, on the awkward language."""
        path = tmp_path / "tg.txt"
        path.write_text(esolangs.generate(_PADDED, "10010110"))
        got = ""
        for row in range(8):
            stdin = call_main(["encode", _PADDED, f"{row:03b}"], capsys)
            got += call_main(["run", _PADDED, str(path)], capsys, stdin=stdin)[-1:]
        assert got == "10010110"

    def test_version_is_accepted_after_a_subcommand(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The top-level help advertises it without saying where it goes."""
        with pytest.raises(SystemExit) as exc:
            call_main(["list", "--version"], capsys)
        assert exc.value.code == 0
        assert esolangs.__version__ in capsys.readouterr().out

    def test_debug_always_prints_its_stopped_field(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It vanished on a raise, the one case a script most wants to read."""
        # Exits 1 now -- a raise is the program's own failure, which is what
        # `run` has always called exit 1 -- but the report is still printed
        # first, which is the property under test.
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "brainfuck", _program(tmp_path, ",.")], capsys)
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "stopped: raised" in out
        assert "raised: InputExhaustedError" in out

    def test_a_program_that_prints_nothing_says_so_on_a_terminal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Silence was indistinguishable from piping to the wrong path."""
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        # Not ``call_main``: it drains the capture buffer to return stdout,
        # and the note under test goes to stderr.
        with (
            patch.object(sys, "argv", ["esolangs", "run", "brainfuck", str(empty)]),
            patch.object(sys, "stdin", _FakeStdin("")),
            patch.object(sys.stdout, "isatty", lambda: True),
        ):
            main()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "printed nothing" in captured.err
        assert "the file is empty" in captured.err

    def test_a_pipe_still_receives_exactly_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The note is for a terminal; piped output stays byte-exact."""
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        assert call_main(["run", "brainfuck", str(empty)], capsys) == ""


class TestTheLastResortPaths:
    """Refusals a reader only meets when something has already gone wrong."""

    def test_an_oversized_program_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A megabyte is far past anything this package generates."""
        path = tmp_path / "huge.bf"
        path.write_text("+" * (1024 * 1024 + 1))
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "brainfuck", str(path)], capsys)
        assert exc.value.code == 2
        assert "larger than" in capsys.readouterr().err

    def test_output_a_terminal_cannot_encode_is_written_as_bytes(self) -> None:
        """A lone surrogate reaches the byte stream rather than raising."""
        written: list[bytes] = []

        class _Narrow(io.StringIO):
            # utf-8, because the fallback re-encodes with ``surrogatepass``
            # and that is only defined for the utf codecs -- an ascii
            # stream would fail there for a different reason than the one
            # under test.
            encoding = "utf-8"
            buffer = type(
                "_Bytes",
                (),
                {
                    "write": lambda _s, data: written.append(data),
                    "flush": lambda _s: None,
                },
            )()

            def write(self, text: str) -> int:
                raise UnicodeEncodeError("ascii", text, 0, 1, "narrow")

        with patch.object(sys, "stdout", _Narrow()):
            _write_output("\ud800")
        assert written, "nothing reached the byte stream"


@pytest.mark.parametrize(
    ("bad", "good", "hint"),
    [
        ("0120", "0110", "without spaces or separators"),
        ("010", "0110", "two inputs need four"),
        ("1", "11", "constant with one input"),
    ],
)
def test_truth_table_hint_and_corrected_cli_program(bad, good, hint, tmp_path, capsys):
    out, err = _failure(["generate", "brainfuck", bad], capsys)
    assert out == ""
    assert err.count("hint:") == 1
    assert hint in err
    program, err = call_both(["generate", "brainfuck", good], capsys)
    assert err == ""
    path = tmp_path / "generated.bf"
    path.write_text(program)
    bits = "01" if len(good) == 4 else "0"
    stdin, err = call_both(["encode", "brainfuck", bits], capsys)
    assert err == ""
    answer, err = call_both(["run", "brainfuck", str(path)], capsys, stdin)
    assert answer.strip() == "1"
    assert err == ""


def test_reader_template_hint_names_cli_encode(capsys):
    _, err = _failure(["generate", "--bits", "01", "brainfuck", "0110"], capsys)
    assert "hint: pipe input from esolangs encode brainfuck <bits>" in err
    assert "stdin=encode_inputs" not in err


def test_timeout_hint_names_cli_flag_and_correction_runs(tmp_path, capsys):
    path = tmp_path / "program.bf"
    path.write_text("+.")
    _, err = _failure(["run", "--timeout", "0", "brainfuck", str(path)], capsys)
    assert err.startswith("--timeout must be positive, got 0.0\n")
    assert "hint: set a timeout in seconds, for example --timeout 5.0" in err
    output, err = call_both(["run", "--timeout", "5.0", "brainfuck", str(path)], capsys)
    assert output == "\x01"
    assert err == ""


def test_cli_note_translation_preserves_multiline_diagnostic_and_api_notes():
    from esolangs.cli_hints import _cli_error_text

    error = esolangs.ArgumentError("bad timeout=5.0\nscale=1")
    error.add_note("hint: set timeout=5.0 or scale=1")
    error.add_note("unrelated context")
    assert _cli_error_text(error) == (
        "bad timeout=5.0\nscale=1\nhint: set --timeout 5.0 or --scale 1"
    )
    assert error.__notes__ == ["hint: set timeout=5.0 or scale=1", "unrelated context"]


def test_text_generator_scale_hint_uses_cli_flag(capsys):
    _, err = _failure(["generate", "--scale", "2", "brainfuck", "0110"], capsys)
    assert "hint: omit --scale for text languages" in err


#: Refused, but these hints must stay quiet.
_QUIET = {
    "an_unknown_language_is_not_called_a_swapped_argument": (
        "generate Nonexistent 0110",
        "looks like a truth table",
    ),
    "a_non_table_run_of_digits_is_not_called_a_swap": (
        "generate 011 brainfuck",
        "looks like a truth table",
    ),
}


@pytest.mark.parametrize("case", _QUIET.values(), ids=list(_QUIET))
def test_a_bad_command_exits_2_without_the_hint(
    case: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command, message, *stdin = case
    assert message not in _refused(command, tmp_path, capsys, *stdin)
