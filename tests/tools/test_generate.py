"""Unit tests for the program generator tool."""

import importlib
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest

import esolangs.tools.generate as gen
from esolangs.interpreters.io import IO
from esolangs.interpreters.other.between import run as between_run
from esolangs.interpreters.other.clockwise import run as clockwise_run
from esolangs.interpreters.other.container import run as container_run
from esolangs.interpreters.other.nevermind import run as nevermind_run
from esolangs.interpreters.other.ztoalc import run as ztoalc_run
from esolangs.interpreters.register_based.bio import run as bio_run
from esolangs.interpreters.register_based.dig import run as dig_run
from esolangs.interpreters.register_based.dotlang import run as dotlang_run
from esolangs.interpreters.register_based.huf import run as huf_run
from esolangs.interpreters.register_based.polynomial import run as polynomial_run
from esolangs.interpreters.register_based.qoibl import run as qoibl_run
from esolangs.interpreters.register_based.sophie import run as sophie_run
from esolangs.interpreters.register_based.WII2D import run as wii2d_run
from esolangs.interpreters.stack_based.bfstack import run as bfstack_run
from esolangs.interpreters.stack_based.eval import run as eval_run
from esolangs.interpreters.stack_based.modulous import run as modulous_run
from esolangs.interpreters.stack_based.temporary import run as temporary_run
from esolangs.interpreters.tape_based.brainif import run as brainif_run
from esolangs.interpreters.tape_based.circlefuck import run as circlefuck_run
from esolangs.interpreters.tape_based.excon import run as excon_run
from esolangs.interpreters.tape_based.mammalian import run as mammalian_run
from esolangs.interpreters.tape_based.sbleq import run as sbleq_run
from esolangs.interpreters.tape_based.suffolk import run as suffolk_run
from esolangs.tools.generators import other


def roundtrip(interpreter: Callable[..., Any], program: str | list[str]) -> str:
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        interpreter(program, io=IO())
    return buffer.getvalue()


class TestGeneratorRoundTrips:
    def test_between(self) -> None:
        """p prints the whole text; apostrophes are doubled inside literals."""
        assert roundtrip(between_run, gen.between("Hi").splitlines()) == "Hi"
        assert (
            roundtrip(between_run, gen.between("Hello, World!").splitlines())
            == "Hello, World!"
        )
        assert roundtrip(between_run, gen.between("a'b").splitlines()) == "a'b"

    def test_between_rejects_newline(self) -> None:
        with pytest.raises(ValueError, match="newline"):
            gen.between("a\nb")

    def test_bfstack(self) -> None:
        assert roundtrip(bfstack_run, gen.bfstack("Hi")) == "Hi"

    def test_excon(self) -> None:
        assert roundtrip(excon_run, gen.excon("Hi")) == "Hi"

    def test_sbleq(self) -> None:
        """Each character is embedded as data and output via -3."""
        assert roundtrip(sbleq_run, gen.sbleq("Hi")) == "Hi"
        assert roundtrip(sbleq_run, gen.sbleq("a\nb")) == "a\nb"
        assert roundtrip(sbleq_run, gen.sbleq("\x00\x7f\xff")) == "\x00\x7f\xff"

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
        assert roundtrip(sophie_run, gen.sophie("a$b")) == "a$b"

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
        assert roundtrip(dig_run, gen.dig("0E").splitlines()) == "0E"

    def test_clockwise(self) -> None:
        """The 1D parity program wraps around a square ring's perimeter."""
        assert roundtrip(clockwise_run, gen.clockwise("Hi").splitlines()) == "Hi"
        assert (
            roundtrip(clockwise_run, gen.clockwise("Hello, World!").splitlines())
            == "Hello, World!"
        )
        assert gen.clockwise("") == ""

    def test_mammalian(self) -> None:
        """A SEED/SPRINT walk reaches the array holding each character."""
        assert roundtrip(mammalian_run, gen.mammalian("Hi")) == "Hi"
        assert (
            roundtrip(mammalian_run, gen.mammalian("Hello, World!")) == "Hello, World!"
        )
        assert gen.mammalian("") == ""

    def test_mammalian_unreachable(self) -> None:
        """Report a character when no SEED/SPRINT walk can reach a value."""
        with (
            patch(
                "esolangs.tools.generators.tape._mammalian_walk",
                return_value=[{} for _ in range(256)],
            ),
            pytest.raises(ValueError, match="cannot build"),
        ):
            gen.mammalian("H")

    def test_huf(self) -> None:
        """Each # + inc >@ segment prints one character."""
        assert roundtrip(huf_run, gen.huf("Hi")) == "Hi"
        assert roundtrip(huf_run, gen.huf("Hello, World!")) == "Hello, World!"
        assert roundtrip(huf_run, gen.huf("a\nb\x00")) == "a\nb\x00"
        assert gen.huf("") == ""

    def test_eval(self) -> None:
        """A string literal prints on the dot instruction."""
        assert roundtrip(eval_run, gen.eval("Hello, World!")) == "Hello, World!"
        assert roundtrip(eval_run, gen.eval('say "hi"')) == 'say "hi"'
        assert gen.eval("") == ""

    def test_eval_backtick(self) -> None:
        """Eval cannot output a literal backtick."""
        with pytest.raises(ValueError, match="backtick"):
            gen.eval("a`b")

    def test_dotlang(self) -> None:
        """A single dot prints one backtick-wrapped string literal."""
        assert (
            roundtrip(dotlang_run, gen.dotlang("Hello, World!").splitlines())
            == "Hello, World!"
        )
        assert roundtrip(dotlang_run, gen.dotlang("123").splitlines()) == "123"
        assert roundtrip(dotlang_run, gen.dotlang("").splitlines()) == ""

    def test_dotlang_multiline(self) -> None:
        """A newline would split the program into a second grid row."""
        with pytest.raises(ValueError, match="single line"):
            gen.dotlang("a\nb")
        with pytest.raises(ValueError, match="single line"):
            gen.dotlang("a`b")

    def test_nevermind(self) -> None:
        """Print joins its arguments; nevermind always adds a trailing newline."""
        assert roundtrip(nevermind_run, gen.nevermind("Hi").splitlines()) == "Hi\n"
        assert roundtrip(nevermind_run, gen.nevermind("a,b").splitlines()) == "a,b\n"
        assert (
            roundtrip(nevermind_run, gen.nevermind("a*44b").splitlines()) == "a*44b\n"
        )
        assert roundtrip(nevermind_run, gen.nevermind("a²b").splitlines()) == "a²b\n"
        assert roundtrip(nevermind_run, gen.nevermind("١٢٣").splitlines()) == "١٢٣\n"

    def test_nevermind_unsupported(self) -> None:
        """Nevermind cannot print multiline text or a leading $."""
        with pytest.raises(ValueError, match="single line"):
            gen.nevermind("a\nb")
        with pytest.raises(ValueError, match="single line"):
            gen.nevermind("a\x0bb")
        with pytest.raises(ValueError, match="single line"):
            gen.nevermind("$abc")

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

    def test_polynomial_byte_range(self) -> None:
        """Codepoints up to 255 round-trip within a reasonable text length."""
        text = "".join(chr(n) for n in range(0, 256, 16))
        assert roundtrip(polynomial_run, gen.polynomial(text)) == text

    def test_polynomial_precision_limit(self) -> None:
        """Large codepoint deltas round-trip despite float64 root limits.

        float64 root-finding cannot recover the instruction roots when
        consecutive characters differ by thousands (the integer coefficients
        exceed float64's exact range).  The interpreter factors the integer
        polynomial instead, so even wide codepoint spans round-trip.
        """
        assert roundtrip(polynomial_run, gen.polynomial("a日a日")) == "a日a日"

    def test_polynomial_format(self) -> None:
        """Zero coefficients are omitted from the formatted polynomial."""
        from esolangs.tools._polynomial import format_coeffs

        assert format_coeffs([1, 0, 2]) == "f(x) = x^2 + 2"

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

    def test_circlefuck(self) -> None:
        """The tape doubles as the program, so cells start at their own codes."""
        assert roundtrip(circlefuck_run, gen.circlefuck("Hi")) == "Hi"
        assert (
            roundtrip(circlefuck_run, gen.circlefuck("Hello, World!"))
            == "Hello, World!"
        )
        assert roundtrip(circlefuck_run, gen.circlefuck("+~")) == "+~"
        assert roundtrip(circlefuck_run, gen.circlefuck("+-")) == "+-"
        assert roundtrip(circlefuck_run, gen.circlefuck("")) == ""

    def test_home_row_nul(self) -> None:
        """NUL uses an as (net zero) prefix so adjacent ks do not collapse."""
        assert gen.home_row("\x00") == "ask;"
        assert gen.home_row("a\x00b").count("ask") == 1

    def test_minifuck_carries_tape(self) -> None:
        """The tape carries between characters; a matching character is a bare dot."""
        assert gen.minifuck("A") == "[x[x<[x[x[x[x[x[x<[x."
        assert gen.minifuck("AA") == "[x[x<[x[x[x[x[x[x<[x.."

    def test_dimensional(self) -> None:
        """Each =HEX. segment sets the current cell and prints it as a byte."""
        assert gen.dimensional("Hi") == "=48.=69."
        assert gen.dimensional("\x00\x7f\xff") == "=00.=7f.=ff."

    def test_two_d_fish(self) -> None:
        """i/d walk the accumulator to each byte and a prints it."""
        assert gen.two_d_fish("A") == "/" + "i" * 65 + "a@"
        assert gen.two_d_fish("AA") == "/" + "i" * 65 + "a" + "a@"
        assert gen.two_d_fish("A\x00") == "/" + "i" * 65 + "a" + "d" * 65 + "a@"

    def test_pct_squared_minus_one(self) -> None:
        """Each 'path e resets the accumulator, builds the byte, and prints it."""
        assert gen.pct_squared_minus_one("") == ""
        assert gen.pct_squared_minus_one("\x00") == "'e"
        assert (
            gen.pct_squared_minus_one("H")
            == "'" + other._pct_path(72) + "e"  # noqa: SLF001
        )

    def test_pct_path_formula(self) -> None:
        """_pct_path is a closed form: final p, halve-when-even greedy, bounds."""
        from esolangs.tools.generators.other import _pct_path

        assert _pct_path(0) == ""
        assert _pct_path(1) == "ips"
        assert _pct_path(8) == "ssmp"
        for byte in range(256):
            path = _pct_path(byte)
            acc = 0
            for op in path:
                if op == "s":
                    acc -= 2
                elif op == "i":
                    acc -= 3
                elif op == "m":
                    acc *= 2
                elif op == "p":
                    acc = -acc
                assert abs(acc) <= 3003  # within the interpreter's reset
            assert acc == byte

    def test_basicfuck(self) -> None:
        """A variable walks to each byte with +=/-= and write prints it."""
        assert gen.basicfuck("A") == (
            "#basicfuck t=1 r=0~255 o=nearest\n"
            "#allocate a\n"
            "a += 65;\n"
            "write <- a ;\n"
        )

    def test_bit_tilde(self) -> None:
        """Bits are toggled only where they differ; ( prints the 8-bit window."""
        assert gen.bit_tilde("\x00") == ">>>>>>>" + "<" * 7 + "("
        assert gen.bit_tilde("\x00\x00") == (
            ">>>>>>>" + "<" * 7 + "(" + ">>>>>>>" + "<" * 7 + "("
        )
        assert gen.bit_tilde("\xff") == "~>~>~>~>~>~>~>~" + "<" * 7 + "("

    def test_three_x(self) -> None:
        """A [literal] prints the text up to the closing bracket."""
        assert gen.three_x("Hi") == "[Hi]"
        assert gen.three_x("") == "[]"

    def test_three_x_unsupported(self) -> None:
        """'?' or ']' in the text would be read as input or end the literal."""
        with pytest.raises(ValueError, match="re-executes"):
            gen.three_x("a]b")
        with pytest.raises(ValueError, match="re-executes"):
            gen.three_x("a?b")

    def test_byte_generators_reject_unicode(self) -> None:
        """Byte-oriented generators reject codepoints above 255 loudly."""
        for _name, fn in (
            ("dimensional", gen.dimensional),
            ("two_d_fish", gen.two_d_fish),
            ("pct_squared_minus_one", gen.pct_squared_minus_one),
            ("basicfuck", gen.basicfuck),
            ("bit_tilde", gen.bit_tilde),
        ):
            with pytest.raises(ValueError, match="only output bytes"):
                fn("😀")
            assert fn("é") != ""  # 233 fits in a byte

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

    def test_ztoalc_uses_record_holder(self) -> None:
        """Longer text uses the best record-holder covering its length."""
        text = "a" * 200
        program = gen.ztoalc(text)
        assert int(program.splitlines()[0]) == 2919  # covers n <= 216
        assert len(program.splitlines()) < 300000
        assert roundtrip(ztoalc_run, program.splitlines()) == text

    def test_ztoalc_long_text(self) -> None:
        """The generator scales to longer text without raising."""
        text = "".join(chr(65 + (i % 26)) for i in range(50))
        program = gen.ztoalc(text)
        assert roundtrip(ztoalc_run, program.splitlines()) == text

    def test_ztoalc_anchor_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A length rounds up to the first anchor whose interval covers it."""
        monkeypatch.setattr(other, "ANCHORS", [(1, 2), (8, 6), (20, 18)])
        assert other._anchor_for(1) == 2  # noqa: SLF001
        assert other._anchor_for(8) == 6  # noqa: SLF001
        assert other._anchor_for(9) == 18  # noqa: SLF001
        assert other._anchor_for(20) == 18  # noqa: SLF001
        program = gen.ztoalc("ab")
        assert program.splitlines() == ["6", "", "print 98", "", "", "print 97"]
        assert roundtrip(ztoalc_run, program.splitlines()) == "ab"

    def test_ztoalc_too_long_rejected(self) -> None:
        """Text longer than the longest known record is rejected."""
        with pytest.raises(ValueError, match="no Collatz start"):
            gen.ztoalc("a" * 1133)

    def test_ztoalc_program_structure(self) -> None:
        """The initial pointer is the chosen start and each char sits on its line."""
        lines = gen.ztoalc("ab").splitlines()
        assert lines[0] == "6"
        assert "print 98" in lines
        assert "print 97" in lines

    def test_brainif(self) -> None:
        assert roundtrip(brainif_run, gen.brainif("Hi").splitlines()) == "Hi"

    def test_container(self) -> None:
        import contextlib
        import io

        import pytest

        buffer = io.StringIO()
        with pytest.raises(SystemExit), contextlib.redirect_stdout(buffer):
            container_run(gen.container("Hi").splitlines(), io=IO())
        assert buffer.getvalue() == "Hi"


class TestGeneratorProducesOutput:
    def test_supported_languages(self) -> None:
        """Every generator produces non-empty output for non-empty text."""
        generators = [
            gen.between,
            gen.forth,
            gen.laserfuck,
            gen.pct_squared_minus_one,
            gen.painfuck,
            gen.suffolk,
            gen._123,  # noqa: SLF001 - public generator
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
            suffolk_run(gen.suffolk("Hi"), limit=1, io=IO())
        assert buffer.getvalue() == "Hi"

    def test_suffolk_empty(self) -> None:
        assert gen.suffolk("") == ""

    def test_123_empty(self) -> None:
        assert gen._123("") == "1"  # noqa: SLF001 - public generator

    def test_forth_nul(self) -> None:
        """A NUL is pushed and printed with an explicit dot."""
        assert gen.forth("a\x00b") == "0F6*7+.0.F6*8+."

    def test_main_prints_all(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", ["esolangs.tools.generate", "Hi"]):
            gen.main()
        out = capsys.readouterr().out
        assert "--- BFStack ---" in out
        assert "--- Between ---" in out
        assert "--- BrainIf ---" in out
        assert "--- Clockwise ---" in out
        assert "--- Container ---" in out
        assert "--- EXCON ---" in out
        assert "--- Modulous ---" in out
        assert "--- Qoibl ---" in out
        assert "--- Sophie ---" in out
        assert "--- Temporary ---" in out
        assert "--- ZTOALC ---" in out
        assert "--- 6-5 ---" in out
        assert "--- ASCII art ---" in out
        assert "--- Dig ---" in out
        assert "--- Dotlang ---" in out
        assert "--- Eval ---" in out
        assert "--- huf ---" in out
        assert "--- LaserFuck ---" in out
        assert "--- MAMMALIAN ---" in out
        assert "--- Minifuck ---" in out
        assert "--- Nevermind ---" in out
        assert "--- Polynomial ---" in out
        assert "--- WII2D ---" in out

    def test_main_usage(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", ["esolangs.tools.generate"]), pytest.raises(SystemExit):
            gen.main()
        out = capsys.readouterr().out
        assert "usage: python -m esolangs.tools.generate" in out

    def test_edge_case_inputs(self) -> None:
        """Generators must not crash on edge-case inputs."""
        generators = [
            gen.pct_squared_minus_one,
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
            gen.clockwise,
            gen.mammalian,
            gen.huf,
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
        gen._123("\x00")  # noqa: SLF001 - public generator
        gen._123("".join(chr(k) for k in range(1, 20)))  # noqa: SLF001

    def test_laserfuck_zero_loop(self) -> None:
        """A small value makes laserfuck's loop end with no tail."""
        gen.laserfuck("\x14")

    def test_painfuck_negative_loop(self) -> None:
        """A large negative delta exercises painfuck's subtract loop."""
        gen.painfuck("H$")

    def test_module_entry_point(self) -> None:
        """Python -m esolangs.tools.generate runs as a script."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "esolangs.tools.generate", "Hi"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--- BFStack ---" in result.stdout
