"""Unit tests for the program generator tool."""

from unittest.mock import patch

import pytest

import esolangs.tools.generate as gen
from esolangs.interpreters.other.container import run as container_run
from esolangs.interpreters.other.ztoalc import run as ztoalc_run
from esolangs.interpreters.register_based.qoibl import run as qoibl_run
from esolangs.interpreters.stack_based.bfstack import run as bfstack_run
from esolangs.interpreters.stack_based.modulous import run as modulous_run
from esolangs.interpreters.tape_based.brainif import run as brainif_run
from esolangs.interpreters.tape_based.excon import run as excon_run


def roundtrip(interpreter, program):
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        interpreter(program)
    return buffer.getvalue()


class TestGeneratorRoundTrips:
    def test_bfstack(self) -> None:
        assert roundtrip(bfstack_run, gen.bfstack("Hi")) == "Hi"

    def test_excon(self) -> None:
        assert roundtrip(excon_run, gen.excon("Hi")) == "Hi"

    def test_modulous(self) -> None:
        assert roundtrip(modulous_run, gen.modulous("Hi")) == "Hi"

    def test_qoibl(self) -> None:
        assert roundtrip(qoibl_run, gen.qoibl("Hi").splitlines()) == "Hi"

    def test_ztoalc(self) -> None:
        """The Collatz trajectory from the chosen start visits each slot once."""
        assert roundtrip(ztoalc_run, gen.ztoalc("Hi").splitlines()) == "Hi"
        assert roundtrip(ztoalc_run, gen.ztoalc("").splitlines()) == ""

    def test_ztoalc_compact(self) -> None:
        """The program is far smaller than the 2**n power-of-2 scheme."""
        program = gen.ztoalc("Hello, World!")
        assert len(program.splitlines()) < 100
        assert roundtrip(ztoalc_run, program.splitlines()) == "Hello, World!"

    def test_ztoalc_extends_search(self) -> None:
        """Longer text uses a precomputed start far beyond the base search limit."""
        text = "a" * 200
        program = gen.ztoalc(text)
        assert int(program.splitlines()[0]) > 20000
        assert len(program.splitlines()) < 100000
        assert roundtrip(ztoalc_run, program.splitlines()) == text

    def test_ztoalc_long_text(self) -> None:
        """The generator scales to longer text without raising."""
        text = "".join(chr(65 + (i % 26)) for i in range(50))
        program = gen.ztoalc(text)
        assert roundtrip(ztoalc_run, program.splitlines()) == text

    def test_ztoalc_searches_beyond_table(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A length missing from the table falls back to a dynamic search."""
        monkeypatch.setattr(gen, "STARTS", {1: 2, 3: 8})
        monkeypatch.setattr(gen, "_ZTOALC_TABLE_LIMIT", 2)
        monkeypatch.setattr(gen, "_ZTOALC_MAX_LIMIT", 100)
        program = gen.ztoalc("ab")
        assert program.splitlines() == ["4", "print 98", "", "print 97"]
        assert roundtrip(ztoalc_run, program.splitlines()) == "ab"

    def test_ztoalc_search_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Text longer than any trajectory in the search range is rejected."""
        monkeypatch.setattr(gen, "STARTS", {1: 2})
        monkeypatch.setattr(gen, "_ZTOALC_TABLE_LIMIT", 2)
        monkeypatch.setattr(gen, "_ZTOALC_MAX_LIMIT", 2)
        with pytest.raises(ValueError, match="no Collatz start"):
            gen.ztoalc("abcde")

    def test_ztoalc_program_structure(self) -> None:
        """The initial pointer is the chosen start and each char sits on its line."""
        lines = gen.ztoalc("ab").splitlines()
        assert lines[0] == "4"
        assert "print 98" in lines
        assert "print 97" in lines

    def test_brainif(self) -> None:
        assert roundtrip(brainif_run, gen.brainif("Hi").splitlines()) == "Hi"

    def test_container(self) -> None:
        import contextlib
        import io

        import pytest

        buffer = io.StringIO()
        with pytest.raises(SystemExit):
            with contextlib.redirect_stdout(buffer):
                container_run(gen.container("Hi").splitlines())
        assert buffer.getvalue() == "Hi"


class TestGeneratorProducesOutput:
    def test_supported_languages(self) -> None:
        """Every generator produces non-empty output for non-empty text."""
        generators = [
            gen.forth,
            gen.laserfuck,
            gen.magnitude,
            gen.painfuck,
            gen.suffolk,
            gen._123,
        ]
        for gen_fn in generators:
            assert gen_fn("Hi"), gen_fn.__name__


class TestGeneratorBranches:
    def test_bfstack_large_drop(self) -> None:
        """A large drop between characters takes the reset branch."""
        output = gen.bfstack("a\x01")
        assert "[-]" in output

    def test_brainif_decreasing(self) -> None:
        """A decreasing character takes the move-right branch."""
        assert "move right" in gen.brainif("ba")

    def test_container_empty(self) -> None:
        assert gen.container("") == "EXIT=1:\n-1 EXIT>=0"

    def test_container_decreasing_char(self) -> None:
        """A character lower than the previous one takes the negative branch."""
        assert "-1 A>=" in gen.container("ba")

    def test_suffolk_empty(self) -> None:
        assert gen.suffolk("") == "\n"

    def test_123_empty(self) -> None:
        assert gen._123("") == "1"

    def test_main_prints_all(self, capsys: pytest.CaptureFixture) -> None:
        with patch("sys.argv", ["esolangs.tools.generate", "Hi"]):
            gen.main()
        out = capsys.readouterr().out
        assert "--- BFStack ---" in out
        assert "--- BrainIf ---" in out
        assert "--- EXCON ---" in out
        assert "--- Modulous ---" in out
        assert "--- Qoibl ---" in out
        assert "--- ZTOALC ---" in out

    def test_main_usage(self, capsys: pytest.CaptureFixture) -> None:
        with patch("sys.argv", ["esolangs.tools.generate"]):
            with pytest.raises(SystemExit):
                gen.main()
        out = capsys.readouterr().out
        assert "usage: python -m esolangs.tools.generate" in out

    def test_edge_case_inputs(self) -> None:
        """Generators must not crash on edge-case inputs."""
        generators = [
            gen.magnitude,
            gen.painfuck,
            gen.laserfuck,
            gen.suffolk,
            gen.excon,
            gen.modulous,
            gen.qoibl,
        ]
        inputs = [
            "\x01",
            "a\x01",
            "za",
            "AB",
            "zZ",
            " \n",
            "\x7f",
            "!@#",
            "aaaa",
            "".join(chr(k) for k in range(33, 127)),
            "".join(chr(k) for k in range(1, 20)),
            "z\x00",
        ]
        for gen_fn in generators:
            for text in inputs:
                gen_fn(text)

    def test_control_character_123(self) -> None:
        """The 123 generator must not crash on control characters."""
        gen._123("\x00")
        gen._123("".join(chr(k) for k in range(1, 20)))

    def test_laserfuck_zero_loop(self) -> None:
        """A small value makes laserfuck's loop end with no tail."""
        gen.laserfuck("\x14")

    def test_painfuck_negative_loop(self) -> None:
        """A large negative delta exercises painfuck's subtract loop."""
        gen.painfuck("H$")

    def test_module_entry_point(self) -> None:
        """python -m esolangs.tools.generate runs as a script."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "esolangs.tools.generate", "Hi"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--- BFStack ---" in result.stdout
