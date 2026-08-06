"""Unit tests for the program generator tool."""

import importlib
from unittest.mock import patch

import pytest

import esolangs.tools._ztoalc as zt
import esolangs.tools.generate as gen
from esolangs.interpreters.other.container import run as container_run
from esolangs.interpreters.other.ztoalc import run as ztoalc_run
from esolangs.interpreters.register_based.bio import run as bio_run
from esolangs.interpreters.register_based.dig import run as dig_run
from esolangs.interpreters.register_based.polynomial import run as polynomial_run
from esolangs.interpreters.register_based.qoibl import run as qoibl_run
from esolangs.interpreters.register_based.sophie import run as sophie_run
from esolangs.interpreters.register_based.WII2D import run as wii2d_run
from esolangs.interpreters.stack_based.bfstack import run as bfstack_run
from esolangs.interpreters.stack_based.modulous import run as modulous_run
from esolangs.interpreters.stack_based.temporary import run as temporary_run
from esolangs.interpreters.tape_based.brainif import run as brainif_run
from esolangs.interpreters.tape_based.excon import run as excon_run
from esolangs.interpreters.tape_based.suffolk import run as suffolk_run


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

    def test_modulous_compact(self) -> None:
        """Safe text uses the PSH STR idiom instead of per-character pushes."""
        assert gen.modulous("Hi") == '[PSH STR "Hi"][PRT STR][JMP B 1 NIF 0]'

    def test_qoibl(self) -> None:
        assert roundtrip(qoibl_run, gen.qoibl("Hi").splitlines()) == "Hi"

    def test_sophie(self) -> None:
        """#<char>, sets the accumulator and prints it as a character."""
        assert roundtrip(sophie_run, gen.sophie("Hello, World!")) == "Hello, World!"
        assert roundtrip(sophie_run, gen.sophie("a\nb")) == "a\nb"

    def test_bio(self) -> None:
        """Registers walk to each character value, then 1ix prints it."""
        assert roundtrip(bio_run, gen.bio("Hello, World!")) == "Hello, World!"

    def test_wii2d(self) -> None:
        """The accumulator is built with digits and squares, then ~ prints."""
        assert (
            roundtrip(wii2d_run, gen.wii2d("Hello, World!").splitlines())
            == "Hello, World!"
        )

    def test_dig(self) -> None:
        """$ digs underground and [letter]: pairs print along the path."""
        assert (
            roundtrip(dig_run, gen.dig("Hello, World!").splitlines()) == "Hello, World!"
        )
        assert roundtrip(dig_run, gen.dig("abcd").splitlines()) == "abcd"

    def test_dig_unsupported(self) -> None:
        """Dig can only output letters, digits, spaces and .,!? directly."""
        with pytest.raises(ValueError, match="only output"):
            gen.dig("a~b")

    def test_polynomial(self) -> None:
        """The register walks each character, and roots encode the instructions."""
        assert roundtrip(polynomial_run, gen.polynomial("Hi")) == "Hi"
        assert roundtrip(polynomial_run, gen.polynomial("aa")) == "aa"
        assert roundtrip(polynomial_run, gen.polynomial("ba")) == "ba"
        assert gen.polynomial("").startswith("f(x) = ")

    def test_polynomial_format(self) -> None:
        """Zero coefficients are omitted from the formatted polynomial."""
        assert gen._polynomial_format([1, 0, 2]) == "f(x) = x^2 + 2"

    def test_six_five(self) -> None:
        """±5/±6 walks reach each character value, then A prints it."""
        sixfive_run = importlib.import_module(
            "esolangs.interpreters.tape_based.6-5"
        ).run
        assert roundtrip(sixfive_run, gen.six_five("Hello, World!")) == "Hello, World!"

    def test_ascii_art(self) -> None:
        """A brainfuck program encoded as drawing blocks prints the text."""
        ascii_run = importlib.import_module(
            "esolangs.interpreters.tape_based.ascii-art"
        ).run
        assert roundtrip(ascii_run, gen.ascii_art("Hi")) == "Hi"
        assert roundtrip(ascii_run, gen.ascii_art("")) == ""

    def test_minifuck(self) -> None:
        """Each character is printed by flipping the differing tape bits."""
        minifuck_run = importlib.import_module(
            "esolangs.interpreters.tape_based.minifuck"
        ).run
        assert roundtrip(minifuck_run, gen.minifuck("Hello, World!")) == "Hello, World!"

    def test_minifuck_nul(self) -> None:
        """Minifuck cannot output NUL (a zero tape means input instead)."""
        with pytest.raises(ValueError, match="NUL"):
            gen.minifuck("\x00")

    def test_minifuck_carries_tape(self) -> None:
        """The tape carries between characters; a matching character is a bare dot."""
        assert gen.minifuck("A") == "[x[x<[x[x[x[x[x[x<[x."
        assert gen.minifuck("AA") == "[x[x<[x[x[x[x[x[x<[x.."

    def test_ztoalc(self) -> None:
        """The Collatz trajectory from the chosen start visits each slot once."""
        assert roundtrip(ztoalc_run, gen.ztoalc("Hi").splitlines()) == "Hi"
        assert roundtrip(ztoalc_run, gen.ztoalc("").splitlines()) == ""

    def test_temporary(self) -> None:
        """The Temporary Stack squish prints each character."""
        assert roundtrip(temporary_run, gen.temporary("Hi")) == "Hi"
        assert roundtrip(temporary_run, gen.temporary("")) == ""

    def test_temporary_long_text(self) -> None:
        """Text longer than 13 characters is split across stack resets."""
        text = "".join(chr(33 + (i % 94)) for i in range(30))
        assert roundtrip(temporary_run, gen.temporary(text)) == text

    def test_temporary_control_characters(self) -> None:
        """Characters whose increment is whitespace are pushed with vN."""
        text = "a\tb \n\x00\x7f"
        assert roundtrip(temporary_run, gen.temporary(text)) == text

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
        monkeypatch.setattr(zt, "_ZTOALC_TABLE_LIMIT", 2)
        monkeypatch.setattr(zt, "_ZTOALC_MAX_LIMIT", 100)
        program = gen.ztoalc("ab")
        assert program.splitlines() == ["4", "print 98", "", "print 97"]
        assert roundtrip(ztoalc_run, program.splitlines()) == "ab"

    def test_ztoalc_search_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Text longer than any trajectory in the search range is rejected."""
        monkeypatch.setattr(gen, "STARTS", {1: 2})
        monkeypatch.setattr(zt, "_ZTOALC_TABLE_LIMIT", 2)
        monkeypatch.setattr(zt, "_ZTOALC_MAX_LIMIT", 2)
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

    def test_suffolk(self) -> None:
        """The tape-based Suffolk program prints the text in one cycle."""
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            suffolk_run(gen.suffolk("Hi"), limit=1)
        assert buffer.getvalue() == "Hi"

    def test_suffolk_empty(self) -> None:
        assert gen.suffolk("") == ""

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
        assert "--- Sophie ---" in out
        assert "--- Temporary ---" in out
        assert "--- ZTOALC ---" in out
        assert "--- 6-5 ---" in out
        assert "--- ASCII art ---" in out
        assert "--- Dig ---" in out
        assert "--- Minifuck ---" in out
        assert "--- Polynomial ---" in out
        assert "--- WII2D ---" in out

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
            gen.temporary,
            gen.sophie,
            gen.bio,
            gen.six_five,
            gen.ascii_art,
            gen.wii2d,
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
