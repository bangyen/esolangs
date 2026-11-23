"""Unit tests for the esolangs command-line interface."""

import gzip
import json
import os
import shlex
import subprocess
import sys
from dataclasses import replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import _emit, _generate, main
from esolangs.cli.io import _StdoutEncodingError
from esolangs.registry import LANGUAGES, _table
from esolangs.registry._backend import BooleanBackend
from tests.support.cli_support import (
    _failure,
    _program,
    _refused,
    call_both,
    call_main,
    run_cli,
)
from tests.support.pick import first
from tests.support.reference import REFERENCE

_RASTER = first(source_kind="raster", boolean_generator=True)
_GZIP = next(n for n, lang in LANGUAGES.items() if lang.runtime.compressed_source)

RASTER = first(source_kind="raster", boolean_generator=True)
TEMPLATED = first(parameterized=True)

# A 3-input parity table.  Parity depends on every input, so the program is
# long enough to have something to wrap -- an echo-one-input table folds
# down to a few characters and the width options below would be no-ops.
TABLE3 = "01101001"


def test_generate_reads_a_truth_table_from_stdin(capsys) -> None:
    expected = call_both(["generate", "--width=4", REFERENCE, "0110"], capsys)
    assert (
        call_both(["generate", "--width=4", REFERENCE, "-"], capsys, " \t0110\r\n")
        == expected
    )
    output, error = _failure(["generate", REFERENCE, "-"], capsys, stdin="01\n10")
    assert output == ""
    assert "truth table must contain only" in error


@pytest.mark.parametrize(
    ("options", "language", "error"),
    [
        (["--bits", "10"], REFERENCE, "there is nothing to instantiate"),
        (["--gzip"], _RASTER, "gzip export requires text"),
    ],
)
def test_generate_refuses_impossible_options_before_stdin(
    monkeypatch, capsys, options, language, error
) -> None:
    def unread(*_args, **_kwargs):
        pytest.fail("invalid options reached stdin")

    monkeypatch.setattr("esolangs.cli._read_stdin", unread)
    output, diagnostic = _failure(["generate", *options, language, "-"], capsys)
    assert output == ""
    assert error in diagnostic
    _, invalid_table = _failure(["generate", *options, language, "x"], capsys)
    assert "truth table must contain only" in invalid_table


@pytest.mark.parametrize(
    ("args", "is_terminal", "error"),
    [
        (["--scale", "2", REFERENCE], False, "scale is only supported for raster"),
        ([_RASTER], True, "generates a PNG"),
        (["--gzip", REFERENCE], True, "generates gzip"),
    ],
)
def test_generate_checks_scale_and_terminal_before_stdin(
    monkeypatch, capsys, args, is_terminal, error
) -> None:
    def unread(*_args, **_kwargs):
        pytest.fail("invalid output settings reached stdin")

    monkeypatch.setattr("esolangs.cli._read_stdin", unread)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: is_terminal)
    output, diagnostic = _failure(["generate", *args, "-"], capsys)
    assert output == ""
    assert error in diagnostic


def test_template_fill_hint_replays_the_stdin_table(capsys) -> None:
    language = first(parameterized=True, answer_mode="output")
    args = ["generate", "--width=4", language, "-"]
    _, diagnostic = call_both(args, capsys, "0110\n")
    command, _, reminder = diagnostic.split("fill them with: ", 1)[1].partition("\n")
    assert reminder.strip() == "Supply the same truth table again on stdin."
    argv = shlex.split(command)
    assert argv == ["esolangs", "generate", "--bits", "<bits>", *args[1:]]
    argv[3] = "10"
    assert call_both(argv[1:], capsys, "0110\n") == call_both(
        [*argv[1:-1], "0110"], capsys
    )


def test_bad_large_table_has_a_bounded_diagnostic(capsys) -> None:
    data = "0" * ((1 << 20) - 1) + "x"
    output, error = _failure(["generate", REFERENCE, "-"], capsys, stdin=data)
    assert output == ""
    assert "'x' at position 1048575" in error
    assert "(1048576 characters)" in error
    assert len(error) < 512


@pytest.mark.medium
def test_generate_from_stdin_bypasses_argument_size_limits(tmp_path) -> None:
    inputs = 20
    generated = run_cli("generate", REFERENCE, "-", stdin="0" * (1 << inputs) + "\n")
    assert (generated.returncode, generated.stderr) == (0, "")
    ran = run_cli(
        "run",
        "--max-steps",
        "1000",
        REFERENCE,
        _program(tmp_path, generated.stdout),
        stdin="0" * inputs,
    )
    assert (ran.returncode, ran.stdout, ran.stderr) == (0, "0", "")


class TestInProcess:
    def test_generating_a_raster_writes_png_bytes(
        self, capsysbinary: pytest.CaptureFixture[bytes], tmp_path: Path
    ) -> None:
        """Raster ``generate`` writes the image; ``--plain`` says it did nothing."""
        argv = ["esolangs", "generate", "--plain", _RASTER, "0110"]
        with (
            patch.object(sys, "argv", argv),
            patch.object(sys, "stdin", StringIO("")),
        ):
            main()
        out, err = capsysbinary.readouterr()
        assert err == b"note: --plain has no effect on a raster; it is PNG\n"
        assert out.startswith(b"\x89PNG\r\n\x1a\n")
        path = tmp_path / "generated.png"
        path.write_bytes(out)
        api = esolangs.Language(_RASTER)
        restored = api.from_file(path)
        assert restored.input_arity == 2
        assert api.evaluate(restored, [1, 0]).answer == "1"
        image = esolangs.Raster.from_png(out)
        stdin = esolangs.encode_inputs(_RASTER, [1, 0])
        assert (
            esolangs.read_answer(
                _RASTER, esolangs.run(_RASTER, image, stdin=stdin).output
            )
            == "1"
        )

    def test_an_oversized_scale_is_a_usage_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It rendered outside the error handler: internal error, exit 70."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "--scale", "999999999", _RASTER, "0110"], capsys)
        assert exc.value.code == 2
        assert "pixel limit" in capsys.readouterr().err

    @pytest.mark.medium
    def test_large_scale_reaches_the_pixel_limit(self, tmp_path: Path) -> None:
        language = first(source_kind="raster", state_model="stack")
        cap = sys.int_info.str_digits_check_threshold
        huge = 10 ** (cap + 1) - 1
        api = esolangs.Language(language)

        def generate(scale: str) -> subprocess.CompletedProcess[bytes]:
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "esolangs",
                    "generate",
                    f"--scale={scale}",
                    language,
                    "01",
                ],
                env={**os.environ, "PYTHONINTMAXSTRDIGITS": str(cap)},
                capture_output=True,
                timeout=10,
                check=False,
            )

        with pytest.raises(esolangs.ArgumentError, match="pixel limit"):
            api.generate("01", scale=huge)
        rejected = generate("9" * (cap + 1))
        assert (rejected.returncode, rejected.stdout) == (2, b"")
        assert b"pixel limit; use a smaller scale" in rejected.stderr

        control = generate("2")
        path = tmp_path / "scaled.png"
        api.to_file(api.generate("01", scale=2), path)
        assert (control.returncode, control.stdout, control.stderr) == (
            0,
            path.read_bytes(),
            b"",
        )
        assert api.evaluate(api.from_file(path), [1]).answer == "1"

    def test_raster_scale_hint_names_the_working_cli_flag(
        self, tmp_path, capsys
    ) -> None:
        language = first(source_kind="raster", state_model="stack")
        program = esolangs.generate(language, "01")
        assert isinstance(program.source, esolangs.Raster)
        path = tmp_path / "program.png"
        esolangs.to_file(language, program, path)
        invalid_scale = len(program.source.rows) + 1
        _, error = _failure(
            ["run", "--scale", str(invalid_scale), language, str(path)], capsys
        )
        assert "use --scale 1" in error
        stdin = esolangs.encode_inputs(language, [1])
        output = call_main(["run", "--scale", "1", language, str(path)], capsys, stdin)
        assert esolangs.read_answer(language, output) == "1"

    @pytest.mark.parametrize("closed_streams", ["stdout", "both"])
    def test_a_closed_stdout_object_exits_120(self, closed_streams: str) -> None:
        """A closed stream object exited 70 (or raised, stderr closed too)."""
        import io

        for detached in (False, True):
            closed = io.TextIOWrapper(io.BytesIO())
            if detached:
                closed.detach().close()
            else:
                closed.close()
            with (
                patch.object(sys, "argv", ["esolangs", "list"]),
                patch.object(sys, "stdout", closed),
                patch.object(
                    sys, "stderr", closed if closed_streams == "both" else io.StringIO()
                ),
                pytest.raises(SystemExit) as exc,
            ):
                main()
            assert exc.value.code == 120

        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["esolangs", "encode-inputs", REFERENCE, "1"]),
            patch.object(sys, "stdout", output),
            patch.object(sys, "stderr", closed),
        ):
            main()
        assert output.getvalue() == "1"

    def test_help_for_an_unknown_command_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`help zzz` printed the usage and exited 0."""
        with pytest.raises(SystemExit) as exc:
            call_main(["help", "zzz"], capsys)
        assert exc.value.code == 2
        assert "unknown command: zzz" in capsys.readouterr().err
        bad = "no\x1b[2J\ncommand"
        notice = r"unknown command: no\x1b[2J\ncommand"
        assert _failure(["help", bad], capsys) == ("", notice + "\n")
        out, error = _failure([bad], capsys)
        assert not out
        assert error.startswith(notice + "\n\nusage:")
        assert "\x1b" not in error

    def test_partial_output_on_a_pipe_is_byte_exact(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
    ) -> None:
        """An error can retain the output of an earlier invocation."""
        from esolangs.runtime._execution import interpreter_module

        path = tmp_path / "p.txt"
        path.write_text("+.,")
        command = ["run", REFERENCE, str(path)]
        output, diagnostic = _failure(command, capsys, code=1)
        assert output == "\x01"
        assert diagnostic.startswith("program read past the end of input")

        api = esolangs.Language(REFERENCE)
        first = api.execute(path)
        shared = first.error
        assert isinstance(shared, esolangs.InputExhaustedError)
        assert shared.partial_output == first.observation.output == output
        module = interpreter_module(REFERENCE)
        hook = LANGUAGES[REFERENCE].runtime.completion_entrypoint
        original = getattr(module, hook)

        def reuse_error(program, io, **kwargs):
            try:
                return original(program, io, **kwargs)
            except esolangs.InputExhaustedError:
                raise shared from None

        monkeypatch.setattr(module, hook, reuse_error)
        path.write_text("++.,")
        result = api.execute(path)
        assert result.error is shared
        assert shared.partial_output == "\x01"
        assert result.observation.output == "\x02"
        assert _failure(command, capsys, code=1) == (
            result.observation.output,
            diagnostic,
        )

        class RefusesInput:
            def read(self):
                raise shared

        assert api.execute(path, stdin=RefusesInput()).observation.output == ""
        with (
            patch.object(sys, "argv", ["esolangs", *command]),
            patch.object(sys, "stdin", RefusesInput()),
            pytest.raises(SystemExit) as exited,
        ):
            main()
        assert exited.value.code == 1
        assert capsys.readouterr() == ("", diagnostic)
        assert shared.partial_output == "\x01"

    def test_max_memory_names_the_flag(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = tmp_path / "p.txt"
        path.write_text("+")
        monkeypatch.setattr(sys, "platform", "darwin")
        with pytest.raises(SystemExit):
            call_main(["run", "--max-memory", "1000", REFERENCE, str(path)], capsys)
        assert "--max-memory is supported only on Linux" in capsys.readouterr().err
        name = "No such language"
        limits = esolangs.ExecutionLimits(max_memory=1000)
        expected = esolangs.execute(name, path, limits=limits)
        assert isinstance(expected.error, esolangs.UnknownLanguageError)
        assert _failure(["run", "--max-memory", "1000", name, str(path)], capsys) == (
            "",
            f"{expected.error}\n",
        )
        _, diagnostic = _failure(["run", "--max-memory", "0", name, str(path)], capsys)
        assert diagnostic == "--max-memory must be a positive integer, got 0\n"

    @pytest.mark.medium
    def test_an_output_cap_implies_isolation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--max-output`` alone exited 2 with "requires --isolated"."""
        path = tmp_path / "p.txt"
        path.write_text("+[.]")
        with pytest.raises(SystemExit, match=r"^124$"):
            call_main(["run", "--max-output", "3", REFERENCE, str(path)], capsys)
        captured = capsys.readouterr()
        assert captured.out == "\x01" * 3
        assert "output limit exceeded" in captured.err
        assert "raise --max-output" in captured.err

    def test_spec_json_is_the_spec(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``--spec --json`` printed every fact, ignoring ``--spec``."""
        out = call_main(["describe", "--spec", "--json", REFERENCE], capsys)
        assert json.loads(out) == esolangs.describe(REFERENCE).spec

    def test_run_feeds_stdin(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        program = tmp_path / "prog.txt"
        esolangs.to_file(REFERENCE, esolangs.generate(REFERENCE, "1101"), program)
        stdin = esolangs.encode_inputs(REFERENCE, [1, 0])
        out = call_main(["run", REFERENCE, str(program)], capsys, stdin=stdin)
        assert esolangs.read_answer(REFERENCE, out) == "0"

    def test_run_missing_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["run", REFERENCE], capsys)
        assert exc.value.code == 2

    def test_run_unknown_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        program = tmp_path / "prog.txt"
        program.write_text("anything")
        for command, args in (("run", [str(program)]), ("generate", ["01"])):
            for options in ([], ["--set", "mode=1"], ["--settings", '{"mode":1}']):
                with pytest.raises(SystemExit) as exc:
                    call_main([command, "NoSuchLanguage", *args, *options], capsys)
                assert exc.value.code == 2
                error = capsys.readouterr().err
                assert "unknown language" in error
                assert "internal error" not in error

    def test_no_arguments(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main([], capsys)
        assert exc.value.code == 2


@pytest.mark.parametrize(
    ("args", "limit", "runs"),
    [
        # ``--width N`` bounds the generated program's columns.
        pytest.param([REFERENCE, TABLE3, "--width", "20"], 20, True, id="value"),
        # The guard rejects zero and below, not one.
        pytest.param([REFERENCE, "0110", "--width", "1"], None, False, id="one"),
        # ``--width N`` consumes two arguments, not three.
        pytest.param(["--width", "20", REFERENCE, TABLE3], 20, True, id="first"),
        pytest.param([REFERENCE, TABLE3, "--width=20"], 20, False, id="equals"),
        # A bare ``--width`` wraps to the conventional default.
        pytest.param([REFERENCE, TABLE3, "--width"], "default", False, id="bare"),
        # A following word is an argument, not a width.
        pytest.param(["--width", REFERENCE, TABLE3], None, True, id="bare_first"),
    ],
)
def test_width_option(
    args: list[str],
    limit: int | str | None,
    capsys: pytest.CaptureFixture[str],
    *,
    runs: bool,
) -> None:
    """``--width`` in all the spellings the parser accepts."""
    from esolangs.generation.wrap import DEFAULT_WIDTH

    out = call_main(["generate", *args], capsys)
    assert out.strip()
    if limit is not None:
        limit = DEFAULT_WIDTH if limit == "default" else limit
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= limit
        assert "\n" in out.rstrip("\n")
    if runs:
        assert esolangs.run(REFERENCE, out, stdin="011").output == "0"


class TestHelp:
    """Every command documents itself, because `--help` is what gets typed."""

    @pytest.mark.parametrize("flag", ["--help", "-h", "help"])
    def test_the_top_level_flag_is_not_an_unknown_command(
        self, flag: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It used to exit 2 with ``unknown command: --help``."""
        with pytest.raises(SystemExit) as exc:
            call_main([flag], capsys)
        assert exc.value.code == 0
        assert "usage: esolangs <command>" in capsys.readouterr().out

    @pytest.mark.parametrize("command", ["list", "generate", "run"])
    def test_each_command_expands_its_own_options(
        self, command: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A ``--help`` used to print its usage line and stop there."""
        with pytest.raises(SystemExit) as exc:
            call_main([command, "--help"], capsys)
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert f"usage: esolangs {command}" in out
        assert len(out.splitlines()) > 3, "a usage line alone is not help"


# Each case generates a program and runs it through a real subprocess --
# 22.3s over nine tests, the fast band's single largest class.
@pytest.mark.medium
class TestProgramFailuresAreReported:
    """An interpreter's failure is a message and an exit code, not a stack."""

    def test_reading_past_the_input_is_a_clean_message(self, tmp_path: Path) -> None:
        """The traceback leaked src/ paths and an empty EOFError message."""
        result = run_cli("run", REFERENCE, str(_program(tmp_path, ",.")), stdin="")
        assert result.returncode == 1
        assert "Traceback" not in result.stderr
        assert "read past the end of input" in result.stderr

    def test_native_source_is_not_guessed_from_template_characters(
        self, tmp_path: Path
    ) -> None:
        path = _program(tmp_path, "$+.")
        result = run_cli("run", REFERENCE, str(path))
        assert result.returncode == 0
        assert result.stdout == "\x01"
        assert result.stderr == ""
        # Generation knows the bindings. Running the file sees literal source.
        template = run_cli("generate", TEMPLATED, "0110")
        assert template.returncode == 0
        assert (
            "input slots; fill them with: esolangs generate --bits" in template.stderr
        )
        path = _program(tmp_path, template.stdout)
        result = run_cli("run", TEMPLATED, str(path), stdin="")
        assert result.returncode == 0
        assert result.stderr == ""


class TestOutputAndAbridging:
    """The two output conventions: byte-exact when piped, readable when not."""

    def test_gzip_export(self, capsysbinary, monkeypatch) -> None:
        _generate([REFERENCE, "01", "--gzip"])
        data = capsysbinary.readouterr().out
        expected = esolangs.generate(REFERENCE, "01").source + "\n"
        assert gzip.decompress(data).decode() == expected
        assert esolangs.run(REFERENCE, data, stdin="1").output == "1"

        declaration = LANGUAGES[REFERENCE]
        source = ",."
        backend = BooleanBackend(entrypoint=lambda _request: source)
        scope = esolangs.Catalog([replace(declaration, backend=backend)])
        monkeypatch.setattr(_table, "CATALOG", scope)
        for flags in ([], ["--gzip"]):
            args = ["esolangs", "generate", *flags, REFERENCE, "01"]
            monkeypatch.setattr(sys, "argv", args)
            main()
            rendered, diagnostic = capsysbinary.readouterr()
            assert not diagnostic
            assert esolangs.run(REFERENCE, rendered, stdin="1").output == "1"

        source += "\ud800"
        artifact = scope.bind(REFERENCE).generate("01")
        assert scope.bind(REFERENCE).run(artifact, stdin="1").output == "1"
        for flags in ([], ["--gzip"]):
            monkeypatch.setattr(
                sys, "argv", ["esolangs", "generate", *flags, REFERENCE, "01"]
            )
            with pytest.raises(SystemExit) as exited:
                main()
            assert exited.value.code == 1
            assert capsysbinary.readouterr() == (
                b"",
                b"output contains a surrogate at character 2 "
                b"and cannot be encoded as UTF-8\n",
            )

        with pytest.raises(_StdoutEncodingError) as caught:
            _emit(artifact, plain=False, gzip=True, catalog=scope)
        compression_error = caught.value.__cause__
        assert isinstance(compression_error, esolangs.ArgumentError)
        assert isinstance(compression_error.__cause__, UnicodeEncodeError)
        assert compression_error.__cause__.object.startswith(source)

        for error in (
            esolangs.ArgumentError("invalid compressor options"),
            esolangs.GeneratorCapError("compressed size bound"),
        ):

            def refuse(*_args, failure=error):
                raise failure

            with monkeypatch.context() as active:
                active.setattr(esolangs.CompressedText, "from_chunks", refuse)
                with pytest.raises(type(error)) as untouched:
                    _emit(artifact, plain=False, gzip=True, catalog=scope)
                assert untouched.value is error

    @pytest.mark.medium
    def test_raster_bits_refusal_points_to_a_working_input_pipeline(
        self, capsysbinary, tmp_path: Path
    ) -> None:
        refused = run_cli("generate", "--bits", "1", _RASTER, "01")
        assert (refused.returncode, refused.stdout) == (2, "")
        hint = f"hint: pipe input from esolangs encode-inputs {shlex.quote(_RASTER)}"
        assert hint in refused.stderr

        with pytest.raises(SystemExit) as swapped:
            _generate(["--scale", "2", "01", _RASTER])
        assert swapped.value.code == 2
        captured = capsysbinary.readouterr()
        assert not captured.out
        repaired = shlex.split(captured.err.decode().split("first: ", 1)[1])
        assert repaired == ["esolangs", "generate", "--scale=2", _RASTER, "01"]
        _generate(repaired[2:])
        path = tmp_path / "program.png"
        path.write_bytes(capsysbinary.readouterr().out)
        assert esolangs.from_file(_RASTER, path).scale == 2
        encoded = run_cli("encode-inputs", _RASTER, "1")
        assert encoded.returncode == 0, encoded.stderr
        execution = run_cli("run", _RASTER, str(path), stdin=encoded.stdout)
        assert execution.returncode == 0, execution.stderr
        assert esolangs.read_answer(_RASTER, execution.stdout) == "1"

    @pytest.mark.medium
    def test_template_fill_hint_keeps_export_flags(
        self, capsysbinary, tmp_path, monkeypatch
    ) -> None:
        language = first(parameterized=True, answer_mode="output")
        original = ["--gzip", "--width=3", language, "01"]
        _generate(original)
        stderr = capsysbinary.readouterr().err.decode()
        command = shlex.split(stderr.split("fill them with: ", 1)[1])
        assert command == ["esolangs", "generate", "--bits", "<bits>", *original]
        path = tmp_path / "program.gz"
        for bit in "01":
            command[3] = bit
            _generate(command[2:])
            data = capsysbinary.readouterr().out
            assert data.startswith(b"\x1f\x8b")
            with pytest.raises(SystemExit) as swapped:
                _generate(["--bits", bit, *original[:-2], "01", language])
            assert swapped.value.code == 2
            captured = capsysbinary.readouterr()
            assert not captured.out
            repaired = shlex.split(captured.err.decode().split("first: ", 1)[1])
            assert repaired[:2] == ["esolangs", "generate"]
            _generate(repaired[2:])
            corrected = capsysbinary.readouterr().out
            assert corrected == data
            path.write_bytes(corrected)
            result = run_cli("run", language, str(path))
            assert result.returncode == 0, result.stderr
            assert esolangs.read_answer(language, result.stdout) == bit

        _check_dialect_repair(language, capsysbinary, monkeypatch)

    def test_a_trailing_newline_is_added_only_for_a_terminal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Piped output is compared and diffed, so it stays byte-exact."""
        program = _program(tmp_path, "+.")
        with patch.object(sys.stdout, "isatty", lambda: True):
            assert call_main(["run", REFERENCE, str(program)], capsys) == "\x01\n"
        assert call_main(["run", REFERENCE, str(program)], capsys) == "\x01"

    def test_binary_programs_refuse_a_terminal(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """PNG and gzip bytes went to the terminal unannounced."""
        with patch.object(sys.stdout, "isatty", lambda: True):
            for args, alternative in (
                (["generate", _RASTER, "0110"], ""),
                (["generate", _GZIP, "01"], " or pass --plain"),
                (
                    ["generate", REFERENCE, "01", "--gzip"],
                    " or replace --gzip with --plain",
                ),
            ):
                with pytest.raises(SystemExit) as exit_:
                    call_main(args, capsys)
                assert exit_.value.code == 2
                output = capsys.readouterr()
                assert not output.out
                assert output.err.rstrip().endswith(
                    f"redirect stdout to a file{alternative}"
                )

        label = "clear\x1b[2J\nlabel"
        shown = r"clear\x1b[2J\nlabel"
        raster = LANGUAGES[_RASTER]
        scope = esolangs.Catalog([replace(raster, name=label)])
        with (
            patch.object(_table, "CATALOG", scope),
            patch.object(sys.stdout, "isatty", lambda: True),
        ):
            assert _failure(["generate", raster.id, "01"], capsys) == (
                "",
                f"{shown} generates a PNG; redirect stdout to a file\n",
            )
        bound = scope.bind(raster.id)
        assert bound.evaluate(bound.generate("01"), [1]).answer == "1"

        text = LANGUAGES[
            first(
                source_kind="text",
                boolean_generator=True,
                parameterized=False,
                answer_mode="output",
                width_effect="none",
            )
        ]
        scope = esolangs.Catalog([replace(text, name=label)])
        with patch.object(_table, "CATALOG", scope):
            source, error = call_both(["generate", "--width=3", text.id, "01"], capsys)
        assert error == (
            f"note: --width has no effect on {shown} -- "
            "the generator retains its original layout\n"
        )
        bound = scope.bind(text.id)
        result = bound.run(source, stdin=bound.encode_inputs([1]))
        assert bound.read_answer(result.output) == "1"


def _check_dialect_repair(language, capsysbinary, monkeypatch) -> None:
    original = esolangs.Language(language)
    declaration = original.catalog.languages[language]
    schema = esolangs.DialectSchema(
        language,
        {"mode": ("plain", "é", "été"), "radix": (1, 2)},
        {"mode": "plain", "radix": 1},
    )
    observed = []

    def validate(**choices):
        observed.append(choices)

    runtime = replace(declaration.runtime, dialect_schema=schema, dialect=validate)
    scope = esolangs.Catalog([replace(declaration, runtime=runtime)])
    monkeypatch.setattr(_table, "CATALOG", scope)

    class Diagnostic(StringIO):
        def __init__(self, codec, declared):
            super().__init__()
            self.codec = codec
            self.declared = declared

        @property
        def encoding(self):
            return self.declared

        def write(self, data):
            data.encode(self.codec)
            return super().write(data)

    for codec, declared in (("ascii", "ascii"), ("ascii", None), ("utf-8", "utf-8")):
        for values, expected in (
            (["--settings", '{"mode":"é"}'], {"mode": "é", "radix": 1}),
            (
                [
                    "--settings",
                    '{"mode":"plain"}',
                    "--set",
                    "mode=é",
                    "--set",
                    "radix=0x2",
                    "--set",
                    "mode=été",
                ],
                {"mode": "été", "radix": 2},
            ),
        ):
            for swapped in (False, True):
                stderr = Diagnostic(codec, declared)
                with monkeypatch.context() as active:
                    active.setattr(sys, "stderr", stderr)
                    if swapped:
                        with pytest.raises(SystemExit) as exited:
                            _generate(["--bits", "1", *values, "01", language])
                        assert exited.value.code == 2
                        prefix = "first: "
                    else:
                        _generate([*values, language, "01"])
                        prefix = "fill them with: "
                capsysbinary.readouterr()
                advice = stderr.getvalue().split(prefix, 1)[1]
                repaired = [
                    "1" if arg == "<bits>" else arg for arg in shlex.split(advice)
                ]
                assert repaired[:2] == ["esolangs", "generate"]
                if codec == "ascii":
                    assert advice.isascii()
                observed.clear()
                _generate(repaired[2:])
                assert observed[-1] == expected
                source = capsysbinary.readouterr().out
                assert original.read_answer(original.run(source).output) == "1"

    with monkeypatch.context() as active:
        stderr = Diagnostic("ascii", None)
        active.setattr(sys, "stderr", stderr)
        with pytest.raises(SystemExit) as exited:
            _generate(["--scale", "\u0661", "01", language])
        assert exited.value.code == 2
        assert "first: esolangs generate" not in stderr.getvalue()
        assert ascii("--scale=\u0661") in stderr.getvalue()


class TestGenerateArgumentTypes:
    """``generate``'s own arguments are checked before a generator runs."""

    def test_a_non_integer_width_from_the_api_is_refused(self) -> None:
        """The CLI parses its width; a Python caller can pass anything."""
        with pytest.raises(ValueError, match="width must be an integer"):
            esolangs.generate(REFERENCE, "0110", width="80")


#: Commands refused with exit code 2, and what stderr must say.
#: ``prog:SRC`` is a file holding SRC; a third item is stdin.
_REFUSALS = {
    "gzip_plain": (f"generate {REFERENCE} 01 --gzip --plain", "mutually exclusive"),
    "gzip_raster": (f"generate {RASTER} 01 --gzip", "rasters use PNG"),
    "generate_bits_refuses_a_raster": (
        f"generate {RASTER} 0110 --bits 01",
        "raster programs read bits",
    ),
    "generate_unknown_language": ("generate NoSuchLanguage 01", "unknown language"),
    "run_missing_file": ("run brainfuck /no/such/file", "cannot read"),
    "unknown_command": ("no.such.command", "unknown command"),
    "width_rejects_a_non_integer_after_equals": (
        f"generate brainfuck {TABLE3} --width=x",
        "must be an integer",
    ),
    "width_rejects_a_non_positive_value-0": (
        f"generate brainfuck {TABLE3} --width 0",
        "must be positive",
    ),
    "unknown_language": ("run NoSuchLanguage prog:+", "unknown language"),
    "missing_args": ("run brainfuck", "usage: esolangs run"),
    "an_option_with_no_value_is_refused": (
        "run brainfuck prog.b --execution-timeout",
        "--execution-timeout needs a value",
    ),
    "removed_debug_is_refused": ("debug brainfuck prog:+", "unknown command"),
    "an_unknown_option_is_named": (
        "run --frobnicate brainfuck prog:+",
        "unknown option: --frobnicate",
    ),
    "an_extra_argument_is_refused": (
        f"generate brainfuck {TABLE3} extra",
        "unexpected argument: 'extra'",
    ),
    "a_repeated_width_quotes_its_value": (
        "generate --width 77 --width 33 brainfuck 0110",
        "first was '77'",
    ),
    "a_missing_argument_is_named": ("generate brainfuck", "missing <truth-table>"),
    "swapped_arguments_are_recognized_as_swapped": (
        "generate 0110 brainfuck",
        "looks like a truth table",
    ),
    "a_misspelled_option_is_suggested": (
        "generate --wdith 40 brainfuck 0110",
        "did you mean --width",
    ),
    "read_answer_reports_an_unknown_language": (
        "read-answer Nonexistent",
        "unknown language",
        "1",
    ),
    "a_genuine_extra_argument_still_says_so": (
        "describe brainfuck zzz",
        "unexpected argument",
    ),
    "an_unknown_subcommand_is_suggested": ("lst", "did you mean list"),
    "encode_refuses_a_language_that_reads_nothing": (
        f"encode-inputs {TEMPLATED!r} 01",
        "reads no stdin",
    ),
    "a_repeated_option_is_refused": (
        f"generate --bits 10 --bits 01 {TEMPLATED!r} 0110",
        "more than once",
    ),
    "encode_refuses_a_non_binary_bit_string": (
        "encode-inputs brainfuck 2x",
        "0s and 1s",
    ),
    "a_swallowed_table_is_named": ("generate brainfuck --width 0110", "--width"),
}


def test_option_passes_cannot_steal_another_options_value(capsys, tmp_path) -> None:
    for options in (["--settings", "--set"], ["--settings=--set"], ["-s", "--set"]):
        _, error = _failure(["generate", *options, REFERENCE, "01"], capsys)
        assert "--settings is not valid JSON" in error

    for command, operands in (
        ("list", []),
        ("describe", [REFERENCE]),
        ("encode-inputs", [REFERENCE, "01"]),
        ("read-answer", [REFERENCE]),
    ):
        for args in (["-s", "{}"], ["-s={}"]):
            assert _failure([command, *args, *operands], capsys) == (
                "",
                f"unknown option: {args[0]}\n",
            )
    assert _failure(["help", "-s"], capsys) == ("", "unknown command: -s\n")
    bad_option = "--oops\x1b[2J\nfield"
    assert _failure(["run", bad_option, REFERENCE, "prog.txt"], capsys) == (
        "",
        r"unknown option: --oops\x1b[2J\nfield" + "\n",
    )

    path = _program(tmp_path, ",.")
    for args in (["--settings", "{}"], ["-s", "{}"], ["-s={}"]):
        program = call_main(["generate", *args, REFERENCE, "01"], capsys)
        assert esolangs.run(REFERENCE, program, stdin="1").output == "1"
        assert call_main(["run", *args, REFERENCE, path], capsys, stdin="Q") == "Q"


@pytest.mark.parametrize(("command", "operand"), [("generate", "01"), ("run", "p.txt")])
@pytest.mark.parametrize(
    ("option", "message"),
    [
        ("--settings", "--settings is not valid JSON"),
        ("-s", "--settings is not valid JSON"),
        ("--set", "--set needs KEY=VALUE"),
    ],
)
def test_settings_operand_error_precedes_arity(
    capsys: pytest.CaptureFixture[str],
    command: str,
    operand: str,
    option: str,
    message: str,
) -> None:
    stdout, error = _failure([command, option, REFERENCE, operand], capsys)
    assert stdout == ""
    assert error.startswith(message)


def test_deep_settings_document_is_a_usage_error() -> None:
    document = '{"setting":' + "[" * 10_000 + "0" + "]" * 10_000 + "}"
    result = run_cli("generate", "--settings", document, REFERENCE, "01")
    assert result.returncode == 2
    assert (
        "--settings is not valid JSON" in result.stderr
        or "dialect setting" in result.stderr
    )


@pytest.mark.parametrize(
    ("command", "flag", "arguments"),
    [
        ("generate", "--plain", [REFERENCE, "01"]),
        ("describe", "--spec", [REFERENCE]),
        ("describe", "--json", [REFERENCE]),
        ("list", "--details", []),
        ("list", "--generator", []),
    ],
)
def test_bare_flags_refuse_repeats(capsys, command, flag, arguments) -> None:
    _, error = _failure([command, flag, flag, *arguments], capsys)
    assert f"{flag} given more than once" in error


@pytest.mark.parametrize("option", [["--plain"], ["--settings", "{}"]])
def test_bare_width_does_not_consume_a_table_past_another_option(
    capsys, option: list[str]
) -> None:
    default = call_main(["generate", "--width", REFERENCE, TABLE3], capsys)
    assert (
        call_main(["generate", REFERENCE, "--width", *option, TABLE3], capsys)
        == default
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--bits", "0", TEMPLATED, "0110"], "pass exactly 2 0/1 digits to --bits"),
        (
            ["--bits", "1", REFERENCE, "01"],
            "hint: pipe input from esolangs encode-inputs",
        ),
        (["--gzip", _RASTER, "01"], "gzip export requires text; rasters use PNG"),
        (["--bits", "1", _RASTER, "01"], "raster programs read bits from stdin"),
        (["--bits", "1", TEMPLATED, "10x"], "truth table must contain"),
    ],
)
def test_incompatible_generation_options_fail_before_building(
    capsys, monkeypatch, args, message
) -> None:
    from esolangs.operations import generation

    def unused(*_args, **_kwargs):
        pytest.fail("incompatible generation options started synthesis")

    monkeypatch.setattr(generation, "_generate_checked", unused)
    output, error = _failure(["generate", *args], capsys)
    assert not output
    assert message in error


def test_template_flags_preserve_width_and_operand_separator(capsys, tmp_path) -> None:
    language = first(parameterized=True, answer_mode="output")
    default = call_main(["generate", language, "01", "--width=7", "--bits=1"], capsys)
    framed = call_main(
        ["generate", "--bits", "1", "--width", "7", "--", language, "01"], capsys
    )
    assert framed == default
    path = tmp_path / "program.txt"
    path.write_text(framed, encoding="utf-8")
    output = call_main(["run", language, str(path)], capsys)
    assert esolangs.read_answer(language, output) == "1"
    _, error = _failure(["generate", "--", "--bits", "01"], capsys)
    assert "unknown language: --bits" in error


def test_read_answer_treats_empty_output_as_a_program_failure(capsys) -> None:
    stdout, error = _failure(["read-answer", REFERENCE], capsys, code=1)
    assert stdout == ""
    assert "nothing on stdin" in error


@pytest.mark.parametrize("case", _REFUSALS.values(), ids=list(_REFUSALS))
def test_a_bad_command_exits_2_and_says_why(
    case: tuple[str, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    command, message, *stdin = case
    for output in stdin or [""]:
        assert message in _refused(command, tmp_path, capsys, output)
