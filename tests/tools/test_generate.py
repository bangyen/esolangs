"""Unit tests for the program generator tool."""

import importlib
import inspect
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest

import esolangs.tools.text as gen
from esolangs.interpreters.grid_based.clockwise import run as clockwise_run
from esolangs.interpreters.grid_based.dig import run as dig_run
from esolangs.interpreters.grid_based.laserfuck import run as laserfuck_run
from esolangs.interpreters.grid_based.streetcode import run as streetcode_run
from esolangs.interpreters.grid_based.wii2d import run as wii2d_run
from esolangs.interpreters.io import IO
from esolangs.interpreters.other.container import run as container_run
from esolangs.interpreters.other.cvnc import run as cvnc_run
from esolangs.interpreters.other.forbin import run as forbin_run
from esolangs.interpreters.other.ztoalc_l import run as ztoalc_run
from esolangs.interpreters.randomness import FirstDraw
from esolangs.interpreters.register_based.between import run as between_run
from esolangs.interpreters.register_based.bio import run as bio_run
from esolangs.interpreters.register_based.myscript import run as myscript_run
from esolangs.interpreters.register_based.nevermind import run as nevermind_run
from esolangs.interpreters.register_based.polynomial import run as polynomial_run
from esolangs.interpreters.register_based.qoibl import run as qoibl_run
from esolangs.interpreters.register_based.sophie import run as sophie_run
from esolangs.interpreters.stack_based.bfstack import run as bfstack_run
from esolangs.interpreters.stack_based.eval import run as eval_run
from esolangs.interpreters.stack_based.forth import run as forth_run
from esolangs.interpreters.stack_based.modulous import run as modulous_run
from esolangs.interpreters.stack_based.three_x import run as three_x_run
from esolangs.interpreters.stack_based.unsquare import run as unsquare_run
from esolangs.interpreters.tape_based.basicfuck import run as basicfuck_run
from esolangs.interpreters.tape_based.brainif import run as brainif_run
from esolangs.interpreters.tape_based.circlefuck import run as circlefuck_run
from esolangs.interpreters.tape_based.factor import run as factor_run
from esolangs.interpreters.tape_based.rotfuck import run as rotfuck_run
from esolangs.interpreters.tape_based.sbleq import run as sbleq_run
from esolangs.interpreters.tape_based.slow_acv_mammalian import run as mammalian_run
from esolangs.interpreters.tape_based.suffolk import run as suffolk_run
from esolangs.interpreters.tape_based.three_d_brainfuck import run as three_d_bf_run
from esolangs.tools.text import other

WIDTH_CONTRACT_TEXT = "Hello, World!"


def roundtrip_language(language: Any, program: str) -> str:
    """Run ``program`` through the interpreter its language registers.

    The width contract is swept from the registry rather than from a list of
    imports, so it needs a runner keyed the same way.  Container exits rather
    than returning, which is deliberate, so ``SystemExit`` is caught here.
    """
    import io
    from contextlib import redirect_stdout

    module = importlib.import_module("esolangs.interpreters." + language.interpreter)
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            module.run(program.splitlines() if language.split else program, io=IO())
    except SystemExit:
        pass
    return buffer.getvalue()


def roundtrip(interpreter: Callable[..., Any], program: str | list[str]) -> str:
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        interpreter(program, io=IO())
    return buffer.getvalue()


def laserfuck_roundtrip(program: str, heading: int) -> str:
    """Run a LaserFuck program from a fixed heading and return its output.

    LaserFuck's initial heading is random by spec, so a test has to pin it;
    the funnel is supposed to bring every heading to the same place, which
    is why the width tests run all four.
    """
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        laserfuck_run(program.splitlines(), IO(), rng=FirstDraw(heading))
    return buffer.getvalue()


_run_123 = importlib.import_module("esolangs.interpreters.tape_based.one_two_three").run
_run_pct = importlib.import_module(
    "esolangs.interpreters.register_based.pct_squared_minus_one"
).run
_run_painfuck = importlib.import_module("esolangs.interpreters.tape_based.painfuck").run
_run_bit_tilde = importlib.import_module(
    "esolangs.interpreters.tape_based.bit_tilde"
).run


class TestGeneratorRoundTrips:
    def test_123(self) -> None:
        """Each character is XOR-encoded into bits and marched to the output."""
        hi = gen.one_two_three("Hi")
        hello = gen.one_two_three("Hello, World!")
        assert roundtrip(_run_123, hi) == "Hi"
        assert roundtrip(_run_123, hello) == "Hello, World!"

    def test_collatz_multiverse(self) -> None:
        """Characters whose byte values need no constant table still round-trip."""
        collatz_run = importlib.import_module(
            "esolangs.interpreters.register_based.collatz_multiverse"
        ).run
        assert roundtrip(collatz_run, gen.collatz_multiverse("\x00")) == "\x00"
        assert roundtrip(collatz_run, gen.collatz_multiverse("Hi")) == "Hi"

    def test_forth(self) -> None:
        """Each character is built from base-15 digits and printed by [.]."""
        assert roundtrip(forth_run, gen.forth("Hi")) == "Hi"
        assert roundtrip(forth_run, gen.forth("Hello, World!")) == "Hello, World!"
        # single-digit values (< 15) and three-digit base-15 values (>= 241)
        assert roundtrip(forth_run, gen.forth("\t\x0b")) == "\t\x0b"
        assert roundtrip(forth_run, gen.forth("\xff\xf1")) == "\xff\xf1"

    def test_cvnc(self) -> None:
        """The accumulator walks between character values inside syllables.

        Each command needs a partner of the other class, so the walk costs
        two characters per unit rather than one: ``ci`` up, ``c\u0259`` down,
        ``fu`` to print.
        """
        assert roundtrip(cvnc_run, gen.cvnc("Hi")) == "Hi"
        assert roundtrip(cvnc_run, gen.cvnc("Hello, World!")) == "Hello, World!"
        # the extremes of the byte range, and a value needing a walk down
        assert roundtrip(cvnc_run, gen.cvnc("\x00\xff")) == "\x00\xff"
        assert roundtrip(cvnc_run, gen.cvnc("ba")) == "ba"

    def test_cvnc_emits_only_valid_syllables(self) -> None:
        """A program the interpreter rejects would not be a program at all."""
        from esolangs.interpreters.other.cvnc import _syllabify, _tokenize

        assert _syllabify(_tokenize(gen.cvnc("Hello, World!")))

    def test_cvnc_empty_text_is_an_empty_program(self) -> None:
        assert gen.cvnc("") == ""

    def test_cvnc_rejects_non_bytes(self) -> None:
        with pytest.raises(ValueError, match="bytes"):
            gen.cvnc("\u0100")

    def test_unsquare(self) -> None:
        """Each byte is built from a parity seed and +/x, printed by Po."""
        assert roundtrip(unsquare_run, gen.unsquare("Hi")) == "Hi"
        assert roundtrip(unsquare_run, gen.unsquare("Hello, World!")) == "Hello, World!"

    @pytest.mark.parametrize(
        "text",
        ["", "\x00", "\xff", "aaaaaaaa", "abcdefgh", "zyxwvu", "aA" * 8, "!!!"],
    )
    def test_unsquare_reuses_the_accumulator(self, text: str) -> None:
        """A repeated byte costs the print alone, and reuse never regresses.

        ``o`` prints without popping and neither ``P`` nor ``o`` touches the
        accumulator, so it still holds the previous character.  Reaching the
        next one from there is taken only when it is shorter than reseeding,
        so no text can grow.
        """
        program = gen.unsquare(text)
        assert roundtrip(unsquare_run, program) == text
        # Reseeding every character is the old strategy; it is the ceiling.
        reseed = 0
        for char in text:
            value = ord(char)
            run, cur = "", value % 2
            while cur != value:
                if value % 2 == 0 and cur and cur * 2 <= value:
                    cur, run = cur * 2, run + "x"
                else:
                    cur, run = cur + 2, run + "+"
            reseed += len(run) + 4  # the seed's two cells plus "Po"
        assert len(program) <= reseed

    def test_unsquare_repeat_costs_only_the_print(self) -> None:
        """The accumulator already holds the byte, so nothing is rebuilt."""
        assert gen.unsquare("aaaa") == gen.unsquare("a") + "Po" * 3

    def test_unsquare_reseeds_when_parity_blocks_the_chain(self) -> None:
        """``x`` cannot make an odd value, so an odd target after an even
        one reloads the seed rather than chaining."""
        program = gen.unsquare("ba")  # 98 then 97: even, then odd
        assert roundtrip(unsquare_run, program) == "ba"
        assert program.count("I") == 1  # the odd seed was reloaded

    def test_three_d_brainfuck(self) -> None:
        """The brainfuck tape moves map to the array's +X axis."""
        assert roundtrip(three_d_bf_run, gen.three_d_brainfuck("Hi")) == "Hi"
        assert (
            roundtrip(three_d_bf_run, gen.three_d_brainfuck("Hello, World!"))
            == "Hello, World!"
        )

    def test_rotfuck(self) -> None:
        assert roundtrip(rotfuck_run, gen.rotfuck("Hi")) == "Hi"
        assert roundtrip(rotfuck_run, gen.rotfuck("Hello, World!")) == "Hello, World!"
        assert roundtrip(rotfuck_run, gen.rotfuck("\t\x0b\xff")) == "\t\x0b\xff"

    def test_forbin(self) -> None:
        assert roundtrip(forbin_run, gen.forbin("Hi")) == "Hi"
        assert roundtrip(forbin_run, gen.forbin("Hello, World!")) == "Hello, World!"
        assert roundtrip(forbin_run, gen.forbin("\x00\x7f\xff")) == "\x00\x7f\xff"

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

    def test_factor(self) -> None:
        """The integer's prime factors encode a brainfuck program."""
        assert roundtrip(factor_run, gen.factor("Hi")) == "Hi"
        assert roundtrip(factor_run, gen.factor("Hello, World!")) == "Hello, World!"

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

    @pytest.mark.slow  # 1.3s
    def test_clockwise_weave_fills_the_interior(self) -> None:
        """The woven grid is nearly all code, unlike the hollow ring.

        A perimeter ring spends its whole interior on nothing, so a long
        text is mostly blank.  The weave serpentines through the interior
        instead, and every lane cell the walk crosses only once still holds
        an instruction, so little but the turns is blank.
        """
        # The turns are a fixed cost, so density climbs with the text; a
        # one-character text is small enough that the ring still wins.
        for text, floor in (
            ("Hello, World!", 0.90),
            ("Clockwise test 123!", 0.94),
            ("The quick brown fox jumps over the lazy dog.", 0.97),
        ):
            program = gen.clockwise(text)
            code = sum(1 for c in program if not c.isspace())
            assert code / len(program) > floor, f"{text!r}: sparse grid"

    def test_clockwise_gives_up_on_a_template_that_does_not_close(self) -> None:
        """A grid whose walk never comes home ends that size's search.

        The slots are the cells the pointer runs exactly once, so a
        template the walk cannot complete has none to offer.  Every
        template the builder actually produces closes -- the geometry is
        fixed -- so the branch is reached by handing it one that does not.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.text.other")
        from esolangs.tools.text.other import _clockwise_weave

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_weave_template", lambda *_a: [[" "]])
            # Nothing weaves, so the caller falls back to the ring rather
            # than looping on a template that can never hold the program.
            assert _clockwise_weave("abc", 12) is None

    def test_clockwise_clamps_a_width_below_the_weave_floor(self) -> None:
        """A width under the floor gets the narrowest weave, not an error.

        Four columns is the narrowest grid the turtle can walk (a home lane,
        the hairpin ladder and two descent lanes), so a smaller width cannot
        be honoured by any layout.  It is clamped rather than refused: a
        width is a preference about layout, and every other width-taking
        generator answers an impossible one the same way.  The program still
        has to run, which is what rules out returning something merely
        narrow-looking.
        """
        for width in (1, 2, 3, 4):
            program = gen.clockwise("Hello", width)
            assert max(len(line) for line in program.split("\n")) == 4
            assert roundtrip(clockwise_run, program.splitlines()) == "Hello"

    @pytest.mark.parametrize("width", [10, 20, 40, 80])
    @pytest.mark.parametrize("text", ["Hi", "Hello, World!", "q" * 30])
    def test_clockwise_honours_a_width(self, text: str, width: int) -> None:
        """``width`` bounds the columns and the program still round-trips.

        Clockwise builds a shape rather than a line, so it cannot be
        reflowed after the fact -- the width has to reach the generator,
        which lays the ring out to fit.  The square is kept when it already
        fits; otherwise the width caps the columns and the height grows.
        """
        program = gen.clockwise(text, width)
        lines = program.split("\n")
        assert max(len(line) for line in lines) <= width
        assert roundtrip(clockwise_run, lines) == text

    @pytest.mark.parametrize("width", [10, 20, 40, 80])
    @pytest.mark.parametrize("text", ["A", "Hi", "Hello, World!"])
    def test_streetcode_honours_a_width(self, text: str, width: int) -> None:
        """The corridor folds into a boustrophedon and still round-trips.

        The car drives to the column limit, turns south through a gap in the
        wall below, and comes back along the next row.  Every fold is a
        plain corridor bend, so none of the ambiguous-turn or lane-merge
        rules come into play.
        """
        program = gen.streetcode(text, width)
        lines = program.split("\n")
        assert max(len(line) for line in lines) <= width
        assert roundtrip(streetcode_run, lines) == text

    @pytest.mark.parametrize(
        "char",
        ["\x00", "\x01", " ", "0", "A", "H", "z", "\xff", "\u03a9"],
    )
    def test_streetcode_ring_builds_any_first_character(self, char: str) -> None:
        """The ring's factors are free, so every code point round-trips.

        Its nine-by-eight is what the hand-written program draws, not a
        minimum: blanking cells shortens a factor and widening the island
        lengthens one, so small values are products too rather than
        needing a floor below which only a walk works.
        """
        assert roundtrip(streetcode_run, gen.streetcode(char).splitlines()) == char

    def test_streetcode_ring_beats_the_straight_walk(self) -> None:
        """A ring is only emitted when it is smaller than walking.

        The walk spends a cell per unit of the code point, so the saving
        grows with the character; the ring costs a fixed block instead.
        """
        for char in ("H", "\u03a9"):
            # The straight street is four rows of the instruction row's
            # width: two walls, the oncoming lane, and the instructions.
            row = len("C" + "^" * ord(char) + "O;") + 2
            assert len(gen.streetcode(char)) < 4 * row

    @pytest.mark.parametrize(
        "text",
        [
            "H",
            "a",
            "!",
            "\x01",
            "Hi",
            "zyA",
            "Hello, World!",
            "Ω",
            # Two wide codepoints, so both the ring and the street are
            # built at full size: 1.7s at one worker, over the fast
            # run's one-second budget.  The rest are milliseconds.
            pytest.param("€Ā", marks=pytest.mark.slow),
        ],
    )
    def test_streetcode_emits_the_shorter_of_ring_and_street(self, text: str) -> None:
        """Whichever shape is smaller is what comes out.

        The generator builds both the ring and the straight street and
        picks by length rather than predicting the winner from the first
        code point, so neither shape can be emitted while the other one
        would have been shorter.
        """
        from esolangs.tools.text.streetcode import (
            _streetcode_instructions,
            _streetcode_ring,
            _streetcode_straight,
        )

        straight = _streetcode_straight(_streetcode_instructions(text))
        ring = _streetcode_ring(text)
        shortest = straight if ring is None else min((ring, straight), key=len)
        assert gen.streetcode(text) == shortest
        assert roundtrip(streetcode_run, gen.streetcode(text).splitlines()) == text

    @pytest.mark.parametrize("width", [5, 6, 10, 20, 40, 80])
    @pytest.mark.parametrize("text", ["A", "Hi", "Hello, World!", "zyA"])
    def test_streetcode_fold_corridor_is_two_wide(self, text: str, width: int) -> None:
        """The descent corridor is a street, so it is two cells wide.

        "Two characters wide" governs every street in the grid, not just
        the horizontal ones.  An earlier fold gapped its dividers by a
        single column, which round-tripped -- the interpreter drives a
        one-wide corridor without complaint -- but drew a corridor
        narrower than the spec allows (``docs/streetcode.md`` records
        that a ``U`` is the only manoeuvre that currently notices).
        Round-tripping is therefore blind to this; assert the geometry
        directly so a refactor cannot quietly narrow it again.
        """
        lines = gen.streetcode(text, width).split("\n")
        # A text short enough to fit one lane pair folds no dividers at
        # all; the geometry claim is about the dividers that do appear.
        # A ring's southern wall also starts with ``+`` and is also gapped,
        # but by the ring's own descent and return -- a different street,
        # asserted by test_streetcode_ring_fold_keeps_the_ring_geometry.
        # A fold divider is the full width of the grid; the ring's wall is
        # the last full-width line, with the block hanging below it.
        # The grid's own southern wall is the last full-width ``+`` line:
        # a ring hangs its block below that, and those rows are narrower.
        # Dropping it leaves the fold dividers, which are the claim here.
        full_width = [
            i for i, ln in enumerate(lines) if ln.startswith("+") and len(ln) == width
        ]
        dividers = [lines[i] for i in full_width[1:-1]]
        for divider in dividers:
            gap = [i for i, ch in enumerate(divider) if ch == " "]
            assert gap == [1, 2], f"corridor gap {gap} is not two wide"

    @pytest.mark.parametrize(
        ("text", "width"),
        [
            ("Hi", 20),
            ("Hi", 40),
            ("Hello, World!", 20),
            ("Hello, World!", 40),
            ("Hello, World!", 80),
            ("Ωmega", 80),
            ("x" * 40, 80),
        ],
    )
    def test_streetcode_ring_survives_the_fold(self, text: str, width: int) -> None:
        """A folded program may still build its first character with a ring.

        Folding packs the first character's unary walk into more rows; it
        does not make it cheaper.  So the ring is built under a width too
        -- the car meets it in the lowest lane and the block hangs below
        the grid's southern wall -- and whichever program is shorter wins.

        The cases here are the ones where the ring is the winner, which
        needs a text long enough to amortize the block's fixed rows and a
        width wide enough to hold the prefix in one lane; a lone ``"A"``
        or a width of 10 keeps the plain fold, covered by the round-trip
        tests above.  ``Hello, World!`` at 80 is what the committed
        ``examples/hello-world/streetcode.txt`` is built at, so the shipped
        example shows a loop.
        """
        from esolangs.tools.text.streetcode import (
            _streetcode_instructions,
            _streetcode_ring_serpentine,
            _streetcode_serpentine,
        )

        plain = _streetcode_serpentine(_streetcode_instructions(text), width)
        ringed = _streetcode_ring_serpentine(text, width)
        assert ringed is not None
        assert len(ringed) < len(plain), "the ring should win these"

        program = gen.streetcode(text, width)
        assert program == ringed
        # ``U`` is the loop's transfer of the wall-hug at the island; it
        # appears in no other shape, so it witnesses that a ring was used.
        assert "U" in program
        lines = program.split("\n")
        assert max(len(line) for line in lines) <= width
        assert roundtrip(streetcode_run, lines) == text

    @pytest.mark.slow  # 2.3s
    def test_streetcode_fold_falls_back_when_a_ring_will_not_fit(self) -> None:
        """A ring too wide for the lane leaves the plain fold standing.

        The plan for a CJK code point wants a remainder of thousands of
        cells, which no lane can hold, so the prefix does not fit and the
        fold is emitted unringed rather than being re-planned to suit the
        width: what a ring costs is what it costs.
        """
        from esolangs.tools.text.streetcode import _streetcode_ring_serpentine

        assert _streetcode_ring_serpentine("中文", 80) is None
        program = gen.streetcode("中文", 80)
        assert "U" not in program
        assert roundtrip(streetcode_run, program.split("\n")) == "中文"

    def test_streetcode_text_opening_on_a_nul_has_no_ring(self) -> None:
        """A first character of zero is already the cell's value.

        The ring exists to multiply the first code point up from zero, so
        a text starting at zero has nothing to count: the plan is refused
        and the straight walk is emitted, which prints it just the same.
        """
        from esolangs.tools.text.streetcode import (
            _plan_ring,
            _streetcode_ring_serpentine,
        )

        assert _plan_ring(0) is None
        assert _streetcode_ring_serpentine("\x00", 80) is None
        program = gen.streetcode("\x00A")
        assert roundtrip(streetcode_run, program.split("\n")) == "\x00A"

    @pytest.mark.parametrize("width", [10, 20, 40, 60, 80])
    @pytest.mark.parametrize("text", ["A", "Hi", "Hello, World!"])
    def test_wii2d_honours_a_width(self, text: str, width: int) -> None:
        """The instruction line folds into a grid and still round-trips.

        Width 60 is included deliberately: an earlier layout put the ``!``
        marker above the first row, which starts the pointer at row ``-1``
        -- wrapping to the *last* row -- and that width was where the
        resulting tail-only run first showed up.
        """
        program = gen.wii2d(text, width)
        lines = program.split("\n")
        assert max(len(line) for line in lines) <= width
        assert roundtrip(wii2d_run, lines) == text

    @pytest.mark.parametrize("width", [5, 6, 8, 12, 20, 40])
    @pytest.mark.parametrize(
        "text",
        ["A", "Hi", "Hello, World!", "abc 123 xyz", "123456", "a b c d e f"],
    )
    def test_dig_honours_a_width(self, text: str, width: int) -> None:
        """The segments fold over row pairs and the mole still prints them.

        The digit texts are the ones that matter: a segment whose character
        is a digit carries a pad cell, so it is one column wider than the
        rest and the turn has to stay clear of it.  The spaced text drives
        the other reader, ``%``, which takes its 0 from the depth row below.
        """
        program = gen.dig(text, width)
        lines = program.split("\n")
        # A padded segment gives every row one more column; nothing else may.
        assert max(len(line) for line in lines) <= width + 1
        assert roundtrip(dig_run, lines) == text

    def test_dig_narrower_widths_are_never_wider(self) -> None:
        """Asking for less never gets more: the shapes agree at the seam."""
        text = "Hello, World!"
        widest = [
            max(len(line) for line in gen.dig(text, w).split("\n"))
            for w in range(1, 41)
        ]
        assert widest == sorted(widest), widest

    @pytest.mark.parametrize(
        "text", ["Hi", "Hello, World!", "abc 123 xyz", "123456", "a b c"]
    )
    def test_dig_stands_the_program_on_end_below_the_fold_floor(
        self, text: str
    ) -> None:
        """A width no fold can turn in gets the vertical form, two wide.

        The mole falls south through the commands in column 0 and reads its
        counts from column 1, since ``_value`` takes a digit from any
        neighbour rather than the cell below.  Two columns is the floor of
        the language itself, so even width 1 is answered with a program.
        """
        for width in (1, 2, 3, 4):
            program = gen.dig(text, width)
            assert max(len(line) for line in program.split("\n")) == 2
            assert roundtrip(dig_run, program.splitlines()) == text

    def test_dig_vertical_needs_no_padding_cell(self) -> None:
        """A leading digit needs no pad standing up: the count is beside it.

        Folded, a segment starting with a digit takes a padding cell so the
        ``$`` does not read that digit as its own count.  Standing up, the
        count sits in the *other* column, so the character below a ``$`` is
        never mistaken for it and the pad is not emitted.
        """
        program = gen.dig("123456", 2)
        assert "  " not in program
        assert roundtrip(dig_run, program.splitlines()) == "123456"

    def test_dig_without_a_width_is_unchanged(self) -> None:
        """No width leaves the one-pair program the generator always built.

        The refactor that added the fold moved the segment building into
        :func:`~esolangs.tools.text.register._dig_segments`, so this pins the
        width-less output the committed examples depend on.
        """
        assert gen.dig("Hello, World!") == (
            ">$H:e:l:l:$o:,:%:W:$o:r:l:d:$!:@\n 8        8    0   8        2"
        )

    def test_wii2d_start_marker_sits_below_the_first_row(self) -> None:
        """The pointer starts *above* the ``!``, so it must not be on top.

        With the marker on row 0 the pointer starts at row ``-1``, which
        wraps to the last row and runs the program's tail instead of its
        head.
        """
        lines = gen.wii2d("Hello, World!", 40).split("\n")
        assert lines[1] == "!"

    @pytest.mark.parametrize("width", [6, 7, 20, 24, 40, 80])
    @pytest.mark.parametrize(
        "text", ["A", "Hi", "Hello", "The quick brown fox", "x" * 20]
    )
    def test_laserfuck_linear_honours_a_width(self, text: str, width: int) -> None:
        r"""The linear form folds into a zigzag and still round-trips.

        The linear program is one straight run of ``+`` and ``>`` -- no
        mirrors, no brackets -- so the beam can be steered down and back to
        a margin without changing what it executes.  It is also the widest
        thing the generator emits: ``"The quick brown fox"`` is 1833
        columns unfolded.

        Six is the floor -- the margin cell that turns the beam right, an
        op, and the turn-down that ends the segment, plus the column the
        fold returns to -- so it is exercised here alongside the roomier
        widths.
        """
        program = gen.laserfuck(text, width)
        assert max(len(line) for line in program.split("\n")) <= width
        for heading in range(4):
            assert laserfuck_roundtrip(program, heading) == text

    @pytest.mark.parametrize(("text", "width"), [("¨", 14), ("¨¨", 14), ("Wü", 30)])
    def test_laserfuck_folds_a_loop_with_no_tail_to_write(
        self, text: str, width: int
    ) -> None:
        r"""A folded loop whose linear remainder is empty still closes.

        The folded path normally carries on with ``fallback`` -- the run of
        tape code the loop passes did not account for -- and puts the beam's
        ``x`` wherever that run ends.  When the passes reduce every value to
        nothing there is no such run, and the ``x`` goes where the fold left
        the beam instead.

        ``¨`` is U+00A8, whose 168 the generator's base divides exactly, so
        the remainder is empty while the program still needs a loop: the
        combination the ASCII samples above never produce.
        """
        program = gen.laserfuck(text, width)
        assert max(len(line) for line in program.split("\n")) <= width
        for heading in range(4):
            assert laserfuck_roundtrip(program, heading) == text

    def test_laserfuck_linear_fold_is_narrower(self) -> None:
        """Folding actually buys columns, rather than only reshaping."""
        # a text whose bytes are spread out enough that neither the multiply
        # passes nor a shared base pays, so the linear run is what folds --
        # three clusters, which one split into two bands cannot cover
        text = "!Q~!Q~!Q~"
        assert max(len(ln) for ln in gen.laserfuck(text).split("\n")) > 200
        assert max(len(ln) for ln in gen.laserfuck(text, 80).split("\n")) <= 80

    def test_laserfuck_clustered_text_uses_a_shared_base(self) -> None:
        """Bytes that cluster are counted up together, not one at a time.

        One loop brings every cell to the base they are all near, and only
        the differences are written afterwards -- which is what keeps a text
        like this off the linear fallback it used to land on.
        """
        wide = gen.laserfuck("The quick brown fox")
        assert max(len(ln) for ln in wide.split("\n")) < 600
        assert "#/)" in wide, "the shared base is set by a ring"

    def test_laserfuck_builds_a_big_base_with_a_second_ring(self) -> None:
        """A base worth more than its frame is multiplied, not counted out.

        Repeated ``~`` sits at 126, and writing that literally is 126
        columns of ``+``.  A ring counts a scratch cell down instead, so the
        grid carries two rings and comes in far under the literal run.
        """
        program = gen.laserfuck("~~~~~")
        assert program.count("#/)") == 2, "a multiply ring and a spread ring"
        assert max(len(ln) for ln in program.split("\n")) < 126

    def test_laserfuck_small_base_skips_the_multiply_ring(self) -> None:
        """A base too small to be worth a frame is still written out.

        The ring costs a ``}``, a return leg and a test; below roughly a
        couple of dozen units that is more than the ``+`` it removes, so the
        form without it has to win on measurement.
        """
        program = gen.laserfuck("\x03\x03\x03")
        assert program.count("#/)") <= 1

    @pytest.mark.parametrize("width", [5, 8, 12, 20, 30])
    def test_laserfuck_snake_ring_refuses_a_width_it_cannot_fit(
        self, width: int
    ) -> None:
        """Too narrow for the ring, the builder answers None, not a bad grid.

        The snake needs a spine to count down and a right margin to turn in,
        and the finished block still has to sit inside the width.  Each of
        those is checked separately and each answers ``None``, which is what
        lets :func:`laserfuck` fall back to a form that does fit rather than
        emitting a ring whose rows overrun.
        """
        from esolangs.tools.text.laserfuck import _laserfuck_snake_ring

        assert _laserfuck_snake_ring("Hi", width) is None

    def test_laserfuck_snake_needs_a_spine_and_a_margin(self) -> None:
        """A spine with no room either side cannot carry a snake."""
        from esolangs.tools.text.laserfuck import _laserfuck_snake

        # right - spine - 1 < 1: no column for the first chunk.
        assert _laserfuck_snake("+++", 1, 2) is None
        # and with the spine past the right edge entirely.
        assert _laserfuck_snake("+++", 5, 6) is None

    def test_laserfuck_base_factor_gives_up_on_a_small_base(self) -> None:
        """Under six there is no split that beats counting the base out.

        The ring costs ``outer + inner`` plus its frame, so a base with no
        factor pair cheaper than itself is left for the caller to write
        literally.
        """
        from esolangs.tools.text.laserfuck import _laserfuck_base_factor

        assert all(_laserfuck_base_factor(base) is None for base in range(6))
        assert _laserfuck_base_factor(6) == (2, 3, 0)

    def test_laserfuck_counts_a_small_base_out_literally(self) -> None:
        """A base too small to factor is written as a run, with no ring.

        ``\\x01`` needs one unit, and no ``outer``/``inner`` split is cheaper
        than the frame a ring would cost, so the stage is a plain ``+`` run.
        """
        program = gen.laserfuck("\x01", 5)
        for heading in range(4):
            assert laserfuck_roundtrip(program, heading) == "\x01"

    def test_laserfuck_falls_back_when_the_loop_grid_overruns(self) -> None:
        """A loop grid wider than the width is re-emitted as the linear form.

        The loop layout is tied to the beam's track, so it cannot be folded
        the way the linear run can; when it does not fit, the whole form is
        swapped rather than squeezed.
        """
        program = gen.laserfuck("aaa", 25)
        assert max(len(line) for line in program.split("\n")) <= 25
        for heading in range(4):
            assert laserfuck_roundtrip(program, heading) == "aaa"

    def test_laserfuck_multiply_ring_leaves_no_stray_cell(self) -> None:
        """The scratch cell the multiply ring spends never reaches the dump.

        It ends at zero and *touched*, which byte mode would otherwise print
        as a NUL between the text and nothing -- so the tail drives it
        negative, where the dump ignores it.
        """
        for text in ("~~~~~", "zzzzzzzzzz", "Hello, World!"):
            for heading in range(4):
                assert laserfuck_roundtrip(gen.laserfuck(text), heading) == text

    def test_laserfuck_two_clusters_get_their_own_bases(self) -> None:
        """Text split between two ranges is counted up in two rings.

        Ordinary text has two clusters and not one -- letters up near a
        hundred, spaces and punctuation down in the thirties -- and one
        shared base leaves every cell a long way from home.  A ring per band
        cuts the residuals of ``Hello, World!`` from 292 units to 96, which
        shows on the grid as a multiply and a spread ring for each band.
        """
        # ``!`` and ``~`` sit at opposite ends of printable ASCII, so a
        # single base leaves every cell about fifty units from home; a band
        # each takes the residuals to nothing.  Without grouping this is
        # 524 columns wide.
        program = gen.laserfuck("!~!~!~!~!~")
        assert max(len(ln) for ln in program.split("\n")) < 200
        for heading in range(4):
            assert laserfuck_roundtrip(program, heading) == "!~!~!~!~!~"

    def test_laserfuck_one_cluster_stays_on_one_base(self) -> None:
        """Bytes already close together are not split into bands.

        A second band costs another frame and another walk of the tape, so
        for text that is all one cluster the ungrouped form has to win on
        measurement.
        """
        program = gen.laserfuck("xxxxxxxxxxxxxxxxxxxx")
        # one band, so one multiply ring and one spread ring
        assert program.count("#/)") == 2

    def test_laserfuck_snakes_a_ring_to_meet_a_width(self) -> None:
        """A ring too wide for the bound is walked across rows instead.

        A ring body cannot be folded -- the return leg re-enters at the
        ``}`` and re-runs the whole body -- so a bounded width used to drop
        the ring forms entirely and fall back to the linear run.  Snaking
        the body keeps the ring: twenty ``x`` at eighty columns was 41 rows
        and is now well under half that.
        """
        text = "x" * 20
        program = gen.laserfuck(text, 80)
        assert max(len(ln) for ln in program.split("\n")) <= 80
        assert program.count("\n") + 1 < 20
        for heading in range(4):
            assert laserfuck_roundtrip(program, heading) == text

    def test_laserfuck_snaked_rings_stack_without_sharing_rows(self) -> None:
        """Each snaked ring is its own block, joined by a drop and a catch.

        This exercises the builder directly rather than through
        :func:`laserfuck`, which would quietly drop a broken snake and fall
        back to another form -- the failure would not show.
        """
        from esolangs.tools.text.laserfuck import _laserfuck_snake_ring

        for text in ("x" * 20, "Hello, World!", "The quick brown fox"):
            for width in (60, 80, 120):
                program = _laserfuck_snake_ring(text, width)
                assert program is not None
                assert max(len(ln) for ln in program.split("\n")) <= width
                for heading in range(4):
                    assert laserfuck_roundtrip(program, heading) == text

    def test_laserfuck_without_a_width_is_unchanged(self) -> None:
        """The default stays exactly what the generator always produced."""
        for text in ("A", "Hi", "Hello, World!", "The quick brown fox"):
            assert gen.laserfuck(text) == gen.laserfuck(text, None)

    def test_laserfuck_loop_form_folds_to_fit_a_width(self) -> None:
        """A loop program too wide for the width is folded, not abandoned.

        The frame cannot be folded between any two cells the way a straight
        run can -- a "]"'s mirror bounces the beam back to cells placed
        relative to its matching "[" -- so it folds between whole bracket
        spans instead.  The point is that the *loop* form survives the
        width: falling back to the linear form would fit too, by emitting
        several times the program.
        """
        text = "Hello, World!"  # takes the loop branch
        loop = gen.laserfuck(text)
        assert max(len(ln) for ln in loop.split("\n")) > 80

        bounded = gen.laserfuck(text, 80)
        assert max(len(ln) for ln in bounded.split("\n")) <= 80
        assert bounded != loop
        # still the loop form -- the bracket mirrors are what say so -- and
        # so no bigger than the unfolded program, unlike the linear fallback
        assert "#^)#^" in bounded
        assert len(bounded) <= len(loop)

    def test_laserfuck_narrow_width_still_falls_back_to_linear(self) -> None:
        """A width no folded span can fit takes the linear form instead."""
        text = "Hello, World!"
        narrow = gen.laserfuck(text, 40)
        assert max(len(ln) for ln in narrow.split("\n")) <= 40
        assert "#^)#^" not in narrow  # the loop geometry is gone

    def test_laserfuck_keeps_the_loop_form_when_it_fits(self) -> None:
        """A width the loop form already satisfies leaves it untouched."""
        text = "Hello, World!"
        loop = gen.laserfuck(text)
        widest = max(len(ln) for ln in loop.split("\n"))
        assert gen.laserfuck(text, widest) == loop
        assert gen.laserfuck(text, widest + 40) == loop

    def test_clockwise_keeps_the_shape_when_it_fits(self) -> None:
        """A width the default grid already satisfies does not distort it."""
        grid = gen.clockwise("Hello, World!")
        widest = max(len(line) for line in grid.split("\n"))
        assert gen.clockwise("Hello, World!", widest) == grid
        assert gen.clockwise("Hello, World!", widest + 40) == grid

    def test_streetcode(self) -> None:
        """A straight walled corridor walks one cell to each character and prints."""
        assert roundtrip(streetcode_run, gen.streetcode("Hi").splitlines()) == "Hi"
        assert (
            roundtrip(streetcode_run, gen.streetcode("Hello, World!").splitlines())
            == "Hello, World!"
        )
        # descending code points use ~, and grid wall characters are printable
        assert roundtrip(streetcode_run, gen.streetcode("zyA").splitlines()) == "zyA"
        assert roundtrip(streetcode_run, gen.streetcode("-|+").splitlines()) == "-|+"
        # cells are unbounded ints, so O is not limited to bytes
        omega = "\u03a9"
        assert roundtrip(streetcode_run, gen.streetcode(omega).splitlines()) == omega
        # 'H' is 72, built as a product by the counting-loop ring rather
        # than walked: nine laps of the island adding eight each.  That is
        # the hand-written program from TestStreetcodeCountingLoop in
        # tests/interpreters/test_streetcode.py, cell for cell -- the
        # generator's ring is that program generalized, so the smallest
        # one it emits is the original.  'i' is then 33 more, walked on
        # the street because a gap that small is cheaper than a ring.
        assert gen.streetcode("H").splitlines() == [
            "+------------+",
            "|            |",
            "|C^        O;|",
            "+--+  ++  +--+",
            "   |      |",
            "   | ^_~ =|",
            "   | ^++= |",
            "   |^^++^U|",
            "   |^^^^^=|",
            "   |^^^^^^|",
            "   +------+",
        ]
        assert gen.streetcode("Hi").splitlines()[2].endswith("O" + "^" * 33 + "O;|")
        # An empty text has nothing to build, so there is no ring at all.
        assert gen.streetcode("") == "+--+\n|  |\n|C;|\n+--+"

    def test_mammalian(self) -> None:
        """A SEED/SPRINT walk reaches the array holding each character."""
        assert roundtrip(mammalian_run, gen.slow_acv_mammalian("Hi")) == "Hi"
        assert (
            roundtrip(mammalian_run, gen.slow_acv_mammalian("Hello, World!"))
            == "Hello, World!"
        )
        assert gen.slow_acv_mammalian("") == ""

    def test_mammalian_unreachable(self) -> None:
        """Report a character when no SEED/SPRINT walk can reach a value."""
        with (
            patch(
                "esolangs.tools.text.tape._mammalian_walk",
                return_value=[{} for _ in range(256)],
            ),
            pytest.raises(ValueError, match="cannot build"),
        ):
            gen.slow_acv_mammalian("H")

    def test_eval(self) -> None:
        """A string literal prints on the dot instruction."""
        assert roundtrip(eval_run, gen.eval("Hello, World!")) == "Hello, World!"
        assert roundtrip(eval_run, gen.eval('say "hi"')) == 'say "hi"'
        assert gen.eval("") == ""

    def test_eval_backtick(self) -> None:
        """Eval cannot output a literal backtick."""
        with pytest.raises(ValueError, match="backtick"):
            gen.eval("a`b")

    def test_nevermind(self) -> None:
        """Print joins its arguments, with no separator or trailing newline."""
        assert roundtrip(nevermind_run, gen.nevermind("Hi").splitlines()) == "Hi"
        assert roundtrip(nevermind_run, gen.nevermind("a,b").splitlines()) == "a,b"
        assert roundtrip(nevermind_run, gen.nevermind("a*44b").splitlines()) == "a*44b"
        assert roundtrip(nevermind_run, gen.nevermind("a²b").splitlines()) == "a²b"
        assert roundtrip(nevermind_run, gen.nevermind("١٢٣").splitlines()) == "١٢٣"

    def test_myscript(self) -> None:
        """The generator escapes the byte string into one say statement."""
        assert roundtrip(myscript_run, gen.myscript("Hi")) == "Hi"
        assert roundtrip(myscript_run, gen.myscript("a\tb\nc")) == "a\tb\nc"
        assert roundtrip(myscript_run, gen.myscript('quote"slash\\')) == 'quote"slash\\'
        # the backslash, form-feed, and NUL escapes take the remaining branches
        assert roundtrip(myscript_run, gen.myscript("a\\b\fc")) == "a\\b\fc"
        assert roundtrip(myscript_run, gen.myscript("a\x00b")) == "a\x00b"

    @pytest.mark.parametrize("width", [1, 4, 10, 12, 40])
    def test_myscript_splits_across_say_statements(self, width: int) -> None:
        """A width cuts the text across several ``say`` lines, never a escape.

        ``say`` writes with no trailing newline, so the statements
        concatenate.  The escapes (``\\n``, ``\\t``) are two characters that
        only mean a byte together, so a line break must fall between whole
        pieces -- which is why the packing is by piece rather than by slice.
        A width too narrow for one piece still gets that piece.
        """
        text = 'a\tb\nc"d\\e'
        program = gen.myscript(text, width)
        assert all(line.startswith('say "') for line in program.split("\n"))
        assert roundtrip(myscript_run, program) == text

    def test_myscript_rejects_a_byte_it_cannot_escape(self) -> None:
        """A byte outside the printable range has no ``say`` escape."""
        with pytest.raises(ValueError, match="representable bytes"):
            gen.myscript("caf\xe9")

    def test_taglate_rejects_a_line_break(self) -> None:
        """The queue is one line, so a break in the text would split it."""
        with pytest.raises(ValueError, match="newline or other line break"):
            gen.taglate("a\nb")

    def test_empty_text_returns_empty(self) -> None:
        """The register generators return an empty program for empty text."""
        assert gen.collatz_multiverse("") == ""
        assert gen.addsubjump("") == ""
        assert gen.decleq("") == ""

    def test_addsubjump_emits_a_nul_byte(self) -> None:
        """A NUL is a legal byte, and its value is the one built by no doubling.

        The generator builds each byte by doubling up from 1, which needs
        the value to have a leading bit; zero has none, so it takes the
        cleared register as it stands.  NUL passes the byte-range check, so
        this is a text a caller can really ask for.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.addsubjump import run

        program = gen.addsubjump("a\0b")
        io_ = ScriptedIO("")
        run(program, io_)
        assert io_.getvalue() == "a\0b"

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

    @pytest.mark.parametrize(
        ("generator", "name"),
        [
            ("clockwise", "Clockwise"),
            ("container", "Container"),
            ("minifuck", "Minifuck"),
        ],
    )
    def test_non_ascii_is_refused(self, generator: str, name: str) -> None:
        """A 7-bit target rejects text it could only emit as the wrong byte.

        These three keep a 7-bit accumulator or parity, so a character above
        127 would wrap silently.  The shared guard names the generator that
        refused, so the message says which one to retarget.
        """
        with pytest.raises(ValueError, match=f"{name} can only output ASCII"):
            getattr(gen, generator)("café")

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
            "esolangs.interpreters.tape_based.six_five"
        ).run
        assert roundtrip(sixfive_run, gen.six_five("Hello, World!")) == "Hello, World!"

    def test_suptiftam(self) -> None:
        """Each character is a term= byte literal followed by a head move."""
        suptiftam_run = importlib.import_module(
            "esolangs.interpreters.other.suptiftam"
        ).run
        assert roundtrip(suptiftam_run, gen.suptiftam("Hi")) == "Hi"
        assert (
            roundtrip(suptiftam_run, gen.suptiftam("Hello, World!")) == "Hello, World!"
        )
        assert roundtrip(suptiftam_run, gen.suptiftam("")) == ""
        assert gen.suptiftam("Hello, World!").splitlines()[:4] == [
            "term='H'",
            "right(:term:)",
            "term='e'",
            "right(:term:)",
        ]

    def test_suptiftam_alphabet_limits(self) -> None:
        """A tab, newline, quote, or non-ASCII char cannot be emitted."""
        for bad in ("a\tb", "a\nb", "a'b", "\x7f", "\x00", "é", "😀"):
            with pytest.raises(ValueError, match="printable non-quote ASCII"):
                gen.suptiftam(bad)
        assert gen.suptiftam("a b")  # a space is fine

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

    def test_pct_squared_minus_one(self) -> None:
        """Each 'path e resets the accumulator, builds the byte, and prints it."""
        assert gen.pct_squared_minus_one("") == ""
        assert gen.pct_squared_minus_one("\x00") == "'e"
        assert (
            gen.pct_squared_minus_one("H") == "'" + other._pct_path(72) + "e"  # noqa: SLF001
        )
        assert roundtrip(_run_pct, gen.pct_squared_minus_one("Hi")) == "Hi"
        assert (
            roundtrip(_run_pct, gen.pct_squared_minus_one("Hello, World!"))
            == "Hello, World!"
        )

    def test_pct_path_formula(self) -> None:
        """_pct_path is a closed form: final p, halve-when-even greedy, bounds."""
        from esolangs.tools.text.other import _pct_path

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
            "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\na += 65;\nwrite <- a ;\n"
        )
        assert roundtrip(basicfuck_run, gen.basicfuck("Hi")) == "Hi"
        assert (
            roundtrip(basicfuck_run, gen.basicfuck("Hello, World!")) == "Hello, World!"
        )

    def test_bit_tilde(self) -> None:
        """Bits are toggled only where they differ; ( prints the 8-bit window."""
        assert gen.bit_tilde("\x00") == ">>>>>>>" + "<" * 7 + "("
        assert gen.bit_tilde("\x00\x00") == (
            ">>>>>>>" + "<" * 7 + "(" + ">>>>>>>" + "<" * 7 + "("
        )
        assert gen.bit_tilde("\xff") == "~>~>~>~>~>~>~>~" + "<" * 7 + "("
        assert roundtrip(_run_bit_tilde, gen.bit_tilde("Hi")) == "Hi"
        assert (
            roundtrip(_run_bit_tilde, gen.bit_tilde("Hello, World!")) == "Hello, World!"
        )

    def test_three_x(self) -> None:
        """A [literal] prints the text up to the closing bracket."""
        assert gen.three_x("Hi") == "[Hi]"
        assert gen.three_x("") == "[]"
        assert roundtrip(three_x_run, gen.three_x("Hi")) == "Hi"
        assert roundtrip(three_x_run, gen.three_x("Hello, World!")) == "Hello, World!"

    def test_three_x_unsupported(self) -> None:
        """A ']' in the text would end the literal early."""
        with pytest.raises(ValueError, match="end the literal"):
            gen.three_x("a]b")

    def test_byte_generators_reject_unicode(self) -> None:
        """Byte-oriented generators reject codepoints above 255 loudly."""
        for _name, fn in (
            ("dimensional", gen.dimensional),
            ("pct_squared_minus_one", gen.pct_squared_minus_one),
            ("basicfuck", gen.basicfuck),
            ("bit_tilde", gen.bit_tilde),
        ):
            with pytest.raises(ValueError, match="only output bytes"):
                fn("😀")
            assert fn("é") != ""  # 233 fits in a byte

    def test_ztoalc(self) -> None:
        """The Collatz trajectory from the chosen start visits each slot once."""
        assert roundtrip(ztoalc_run, gen.ztoalc_l("Hi").splitlines()) == "Hi"
        assert roundtrip(ztoalc_run, gen.ztoalc_l("").splitlines()) == ""

    def test_ztoalc_compact(self) -> None:
        """The program is far smaller than the 2**n power-of-2 scheme."""
        program = gen.ztoalc_l("Hello, World!")
        assert len(program.splitlines()) < 100
        assert roundtrip(ztoalc_run, program.splitlines()) == "Hello, World!"

    def test_ztoalc_uses_record_holder(self) -> None:
        """Longer text uses the best record-holder covering its length."""
        text = "a" * 200
        program = gen.ztoalc_l(text)
        assert int(program.splitlines()[0]) == 2919  # covers n <= 216
        assert len(program.splitlines()) < 300000
        assert roundtrip(ztoalc_run, program.splitlines()) == text

    def test_ztoalc_long_text(self) -> None:
        """The generator scales to longer text without raising."""
        text = "".join(chr(65 + (i % 26)) for i in range(50))
        program = gen.ztoalc_l(text)
        assert roundtrip(ztoalc_run, program.splitlines()) == text

    def test_ztoalc_anchor_lookup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A length rounds up to the first anchor whose interval covers it."""
        monkeypatch.setattr(other, "ANCHORS", [(1, 2), (8, 6), (20, 18)])
        assert other._anchor_for(1) == 2  # noqa: SLF001
        assert other._anchor_for(8) == 6  # noqa: SLF001
        assert other._anchor_for(9) == 18  # noqa: SLF001
        assert other._anchor_for(20) == 18  # noqa: SLF001
        program = gen.ztoalc_l("ab")
        assert program.splitlines() == ["6", "", "print 98", "", "", "print 97"]
        assert roundtrip(ztoalc_run, program.splitlines()) == "ab"

    def test_ztoalc_too_long_rejected(self) -> None:
        """Text longer than the longest known record is rejected."""
        with pytest.raises(ValueError, match="no Collatz start"):
            gen.ztoalc_l("a" * 1133)

    def test_ztoalc_program_structure(self) -> None:
        """The initial pointer is the chosen start and each char sits on its line."""
        lines = gen.ztoalc_l("ab").splitlines()
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


class TestWidthContract:
    """Every width-taking generator answers every width with a program.

    A width below what a generator's layout can fold in is raised to the
    narrowest that folds, never refused and never ignored.  Ignoring it used
    to mean falling back to the unfolded form, which for LaserFuck is the
    widest thing it emits -- so asking for the narrowest program returned one
    twelve times wider than passing no width at all.
    """

    @staticmethod
    def _width_takers() -> list[str]:
        from esolangs.registry import GENERATORS

        return sorted(
            name
            for name, generator in GENERATORS.items()
            if "width" in inspect.signature(generator).parameters
        )

    def test_the_registry_still_has_width_takers(self) -> None:
        """The sweep below is registry-driven, so it must not be empty."""
        assert self._width_takers()

    @pytest.mark.parametrize("width", [1, 2, 3, 4, 5])
    def test_a_width_below_the_floor_is_clamped_not_widened(self, width: int) -> None:
        """A below-floor width never returns more columns than no width does.

        This is the property that failed: the fallback was wider than the
        default, so the narrowest request produced the widest program.
        """
        from esolangs.registry import GENERATORS, LANGUAGES

        for name in self._width_takers():
            generator = GENERATORS[name]
            unbounded = generator(WIDTH_CONTRACT_TEXT)
            bounded = generator(WIDTH_CONTRACT_TEXT, width)
            widest = max(len(line) for line in bounded.split("\n"))
            default = max(len(line) for line in unbounded.split("\n"))
            assert widest <= default, f"{name} at width={width} widened"
            assert roundtrip_language(LANGUAGES[name], bounded) == (
                WIDTH_CONTRACT_TEXT
            ), f"{name} at width={width} stopped printing its text"


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
            gen.one_two_three,
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
            suffolk_run(gen.suffolk("Hi"), io=IO())
        assert buffer.getvalue() == "Hi"

    def test_suffolk_empty(self) -> None:
        assert gen.suffolk("") == ""

    def test_123_empty(self) -> None:
        assert gen.one_two_three("") == "1"

    def test_forth_nul(self) -> None:
        """A NUL is pushed and printed with an explicit dot."""
        assert gen.forth("a\x00b") == "06F*7+.0.6F*8+."

    @pytest.mark.parametrize("text", ['a"b', "a[b", "a]b", "a\x00b"])
    def test_modulous_unsafe_character(self, text: str) -> None:
        """A quote, bracket, or NUL falls back to per-character INT pushes.

        The ``PSH STR`` literal cannot carry these, so the whole string is
        pushed a character at a time instead of as one literal.
        """
        output = gen.modulous(text)
        assert output == "".join(f"[PSH INT {ord(c)}][PRT]" for c in text) + "[END]"
        assert "PSH STR" not in output
        assert roundtrip(modulous_run, output) == text

    def test_modulous_empty(self) -> None:
        """Empty text takes the fallback branch and emits only the END."""
        assert gen.modulous("") == "[END]"

    def test_main_prints_all(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", ["esolangs.tools.text", "Hi"]):
            gen.main()
        out = capsys.readouterr().out
        assert "--- BFStack ---" in out
        assert "--- Between ---" in out
        assert "--- BrainIf ---" in out
        assert "--- Clockwise ---" in out
        assert "--- Container ---" in out
        assert "--- Modulous ---" in out
        assert "--- Qoibl ---" in out
        assert "--- Sophie ---" in out
        assert "--- ZTOALC L ---" in out
        assert "--- 6-5 ---" in out
        assert "--- Dig ---" in out
        assert "--- Eval ---" in out
        assert "--- LaserFuck ---" in out
        assert "--- SLOW ACV MAMMALIAN ---" in out
        assert "--- Minifuck ---" in out
        assert "--- Nevermind ---" in out
        assert "--- Polynomial ---" in out
        assert "--- WII2D ---" in out

    def test_main_usage(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", ["esolangs.tools.text"]), pytest.raises(SystemExit):
            gen.main()
        out = capsys.readouterr().out
        assert "usage: python -m esolangs.tools.text" in out

    @pytest.mark.slow  # 3.2s: every generator over the edge-case corpus
    def test_edge_case_inputs(self) -> None:
        """Generators must not crash on edge-case inputs."""
        generators = [
            gen.pct_squared_minus_one,
            gen.painfuck,
            gen.laserfuck,
            gen.suffolk,
            gen.modulous,
            gen.qoibl,
            gen.sophie,
            gen.bio,
            gen.six_five,
            gen.wii2d,
            gen.clockwise,
            gen.slow_acv_mammalian,
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
        gen.one_two_three("\x00")
        gen.one_two_three("".join(chr(k) for k in range(1, 20)))

    def test_laserfuck_zero_loop(self) -> None:
        """A small value makes laserfuck's loop end with no tail."""
        gen.laserfuck("\x14")

    def test_painfuck_negative_loop(self) -> None:
        """A large negative delta exercises painfuck's subtract loop."""
        gen.painfuck("H$")

    def test_painfuck_roundtrip(self) -> None:
        """Generated programs round-trip through the interpreter."""
        assert roundtrip(_run_painfuck, gen.painfuck("Hi")) == "Hi"
        assert (
            roundtrip(_run_painfuck, gen.painfuck("Hello, World!")) == "Hello, World!"
        )

    def test_module_entry_point(self, capsys: pytest.CaptureFixture[str]) -> None:
        """python -m esolangs.tools.text runs as a script."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "esolangs.tools.text", "Hi"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--- BFStack ---" in result.stdout

        # run in-process via runpy so the entry point's own lines are traced
        import runpy

        with patch.object(sys, "argv", ["esolangs.tools.text", "Hi"]):
            runpy.run_module("esolangs.tools.text", run_name="__main__")
        assert "--- BFStack ---" in capsys.readouterr().out


class TestWeaveInternals:
    """The weave's rejection paths, which the public generator never reaches.

    :func:`~esolangs.tools.text.other.clockwise` clamps its width up to the
    floor before folding, so the "no weave fits" answers below are
    unreachable through it.  They are what keeps a bad template from being
    filled with instructions anyway, so they are exercised directly.
    """

    def test_slots_rejects_a_template_the_walk_leaves(self) -> None:
        """A grid the pointer walks out of is not a closed template.

        With no turns in it the pointer runs east and off the edge, which
        is how a bad ``units``/``body`` pair is refused: the walk raises
        rather than returning a cell list that was never a circuit.
        """
        from esolangs.tools.text.other import _weave_slots

        assert _weave_slots([[" "] * 4 for _ in range(4)]) is None
        # A ring of turns leaves the grid the same way rather than cycling.
        assert _weave_slots([list(row) for row in ("RR", "RR")]) is None

    def test_weave_refuses_a_width_below_the_floor(self) -> None:
        """Under the floor there is no weave to build; the caller clamps."""
        from esolangs.tools.text.other import _clockwise_weave

        assert _clockwise_weave(";", 3) is None

    def test_the_narrowest_weave_still_holds_a_long_program(self) -> None:
        """Four columns keep taking units until the slots fit the program.

        Each unit adds about six slots, so the search always terminates by
        finding a template rather than by outgrowing the program.
        """
        from esolangs.tools.text.other import _clockwise_weave

        assert _clockwise_weave(";" * 400, 4) is not None
