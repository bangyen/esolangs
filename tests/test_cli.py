"""Unit tests for the esolangs command-line interface.

The subprocess tests exercise the real ``python -m esolangs.cli`` entry
point; the in-process tests exercise every branch of ``main`` so the CLI is
fully covered by the suite (subprocesses do not contribute to coverage).
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "esolangs.cli", *args],
        capture_output=True,
        text=True,
    )


class _FakeStdin:
    def __init__(self, data: str) -> None:
        self.data = data

    def isatty(self) -> bool:
        return False

    def read(self) -> str:
        return self.data


def call_main(
    args: list[str], capsys: pytest.CaptureFixture[str], stdin: str = ""
) -> str:
    with (
        patch.object(sys, "argv", ["esolangs", *args]),
        patch.object(sys, "stdin", _FakeStdin(stdin)),
    ):
        main()
    return str(capsys.readouterr().out)


class TestSubprocess:
    def test_list(self) -> None:
        result = run_cli("list")
        assert result.returncode == 0
        assert "Sophie" in result.stdout

    def test_generate(self) -> None:
        result = run_cli("generate", "Sophie", "Hi")
        assert result.returncode == 0
        assert esolangs.run("Sophie", result.stdout) == "Hi"

    def test_run(self, tmp_path: Path) -> None:
        program = tmp_path / "prog.soph"
        program.write_text(esolangs.generate("Sophie", "Hi"))
        result = run_cli("run", "Sophie", str(program))
        assert result.returncode == 0
        assert result.stdout == "Hi"

    def test_transpile(self, tmp_path: Path) -> None:
        program = tmp_path / "prog.bf"
        program.write_text(esolangs.generate("brainfuck", "Hi"))
        result = run_cli("transpile", "brainfuck", "Painfuck", str(program))
        assert result.returncode == 0
        assert esolangs.run("Painfuck", result.stdout) == "Hi"


class TestInProcess:
    def test_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = call_main(["list"], capsys)
        assert "Sophie" in out

    def test_generate(self, capsys: pytest.CaptureFixture[str]) -> None:
        out = call_main(["generate", "Sophie", "Hi"], capsys)
        assert esolangs.run("Sophie", out) == "Hi"

    def test_generate_unknown_language(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "NoSuchLanguage", "x"], capsys)
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err

    def test_generate_missing_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "Sophie"], capsys)
        assert exc.value.code == 2

    def test_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        program = tmp_path / "prog.soph"
        program.write_text(esolangs.generate("Sophie", "Hi"))
        out = call_main(["run", "Sophie", str(program)], capsys)
        assert out == "Hi"

    def test_run_feeds_stdin(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from esolangs.tools import boolean

        program = tmp_path / "prog.txt"
        program.write_text(boolean.circlefuck("1101"))
        out = call_main(["run", "Circlefuck", str(program)], capsys, stdin="1\n0\n")
        assert out == "0"

    def test_run_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "Sophie", "/no/such/file"], capsys)
        assert exc.value.code == 2
        assert "cannot read" in capsys.readouterr().err

    def test_run_missing_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "Sophie"], capsys)
        assert exc.value.code == 2

    def test_run_unknown_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        program = tmp_path / "prog.txt"
        program.write_text("anything")
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "NoSuchLanguage", str(program)], capsys)
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err

    def test_transpile(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        program = tmp_path / "prog.bf"
        program.write_text(esolangs.generate("brainfuck", "Hi"))
        out = call_main(["transpile", "brainfuck", "Painfuck", str(program)], capsys)
        assert esolangs.run("Painfuck", out) == "Hi"

    def test_transpile_unsupported_pair(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        program = tmp_path / "prog.bf"
        program.write_text("x")
        with pytest.raises(SystemExit) as exc:
            call_main(["transpile", "brainfuck", "Unsquare", str(program)], capsys)
        assert exc.value.code == 2
        assert "no transpiler" in capsys.readouterr().err

    def test_transpile_missing_args(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["transpile", "brainfuck", "Circlefuck"], capsys)
        assert exc.value.code == 2

    def test_transpile_missing_file(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["transpile", "brainfuck", "Circlefuck", "/no/such/file"], capsys)
        assert exc.value.code == 2
        assert "cannot read" in capsys.readouterr().err

    def test_unknown_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(["no.such.command"], capsys)
        assert exc.value.code == 2
        assert "unknown command" in capsys.readouterr().err

    def test_no_arguments(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main([], capsys)
        assert exc.value.code == 2


class TestPackageEntryPoint:
    """python -m esolangs dispatches to the CLI via esolangs/__main__.py."""

    def test_run_as_main(self, capsys: pytest.CaptureFixture[str]) -> None:
        import runpy

        with patch.object(sys, "argv", ["esolangs", "generate", "Sophie", "Hi"]):
            runpy.run_module("esolangs", run_name="__main__")
        out = capsys.readouterr().out
        assert esolangs.run("Sophie", out) == "Hi"


class TestWidthOption:
    """``--width`` in all the spellings the parser accepts."""

    def test_width_with_a_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``--width N`` bounds the generated program's columns."""
        out = call_main(["generate", "brainfuck", "Hello", "--width", "20"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= 20
        assert esolangs.run("brainfuck", out) == "Hello"

    def test_width_with_an_equals_sign(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width=N`` is the same option written the other way."""
        out = call_main(["generate", "brainfuck", "Hello", "--width=20"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= 20

    def test_bare_width_takes_the_default(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A bare ``--width`` wraps to the conventional default.

        The common case is "wrap this so I can read it", which needs no
        number; the option is only followed by one when the caller wants a
        width other than the default.
        """
        from esolangs.tools.wrap import DEFAULT_WIDTH

        out = call_main(["generate", "brainfuck", "Hello, World!", "--width"], capsys)
        assert max(len(line) for line in out.rstrip("\n").split("\n")) <= DEFAULT_WIDTH
        assert "\n" in out.rstrip("\n")

    def test_bare_width_before_a_non_integer(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A following word is an argument, not a width.

        Reading the language name as a width would silently generate the
        wrong thing, so only an integer is taken as the option's value.
        """
        out = call_main(["generate", "--width", "brainfuck", "Hi"], capsys)
        assert esolangs.run("brainfuck", out) == "Hi"

    def test_width_rejects_a_non_integer_after_equals(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--width=x`` has no integer to parse, so it is refused."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "brainfuck", "Hi", "--width=x"], capsys)
        assert exc.value.code == 2
        assert "must be an integer" in capsys.readouterr().err

    @pytest.mark.parametrize("value", ["0", "-5"])
    def test_width_rejects_a_non_positive_value(
        self, value: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A width of zero or less bounds nothing."""
        with pytest.raises(SystemExit) as exc:
            call_main(["generate", "brainfuck", "Hi", "--width", value], capsys)
        assert exc.value.code == 2
        assert "must be positive" in capsys.readouterr().err
