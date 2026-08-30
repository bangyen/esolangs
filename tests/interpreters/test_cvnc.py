"""Unit tests for the CV(N)(C) interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.cvnc import (
    _Machine,
    _syllabify,
    _tokenize,
    run,
)
from esolangs.vm import run_until_halt_or_cycle

TRUTH_MACHINE = "soθɰ̊oθʋi"
CAT = "ʒuɰ̊fuʒʋu"
HI = "didididædədædidididididididifif"
HELLO = (
    "cicidigæducədəcədəcədəcədəcəfodigiducificiʔiciʔicidifufiʡiʡifocədəgəduqəʔə"
    "cədəgəfoduʡəʡəʡəcəfodogiducidigædəbəfodubifiditifoducədəfogæfodufoboʔidiʡu"
    "ʔiʔicif"
)


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestWikiExamples:
    """The page's four example programs, which pin the execution model."""

    def test_hi(self) -> None:
        assert run_program(HI) == "HI"

    def test_cat_echoes_until_its_input_runs_out(self) -> None:
        """The cat loops on the character it read, so EOF is how it ends."""
        io = ScriptedIO("H\ni\n!\n")
        with pytest.raises(EOFError):
            run(CAT, io)
        assert io.getvalue() == "Hi!"

    def test_truth_machine_prints_zero_once_and_halts(self) -> None:
        assert run_program(TRUTH_MACHINE, "0\n") == "0"

    def test_truth_machine_loops_forever_on_one(self) -> None:
        """A repeated state is a proof of the hang, so no timeout is needed."""
        io = ScriptedIO("1\n")
        assert run_until_halt_or_cycle(_Machine(TRUTH_MACHINE, io)) is False
        assert set(io.getvalue()) == {"1"}

    def test_hello_world_prints_the_wiki_program_s_own_typo(self) -> None:
        """The example is off by one character, and provably so.

        It contains fourteen ``f`` prints and not a single loop or goto, so
        it emits exactly fourteen characters under *any* reading of the
        spec -- while "Hello, world!" is thirteen.  The doubled ``d`` is a
        bug in the wiki's program, not in this interpreter, and asserting
        the real output is the only honest thing to pin.
        """
        assert HELLO.count("f") == 14
        assert not any(c in HELLO for c in "ɰʋɹj")
        assert run_program(HELLO) == "Hello, worldd!"


class TestSyllables:
    def test_the_page_s_valid_examples_parse(self) -> None:
        for code in ("su", "suŋ", "suŋs", "suŋsu"):
            assert _syllabify(_tokenize(code))

    def test_the_page_s_counterexample_is_rejected(self) -> None:
        """``susŋ`` is CVCN, which cannot be cut into CV(N)(C) syllables.

        The ``s`` is taken as the coda of ``sus`` because no vowel follows
        it, which strands the nasal with no syllable of its own to be the
        ``N`` of -- and a nasal can never be an onset.
        """
        with pytest.raises(ValueError, match="consonant"):
            run_program("susŋ")

    def test_a_syllable_needs_a_vowel(self) -> None:
        with pytest.raises(ValueError, match="vowel"):
            run_program("s")

    def test_a_syllable_starts_with_a_consonant(self) -> None:
        with pytest.raises(ValueError, match="consonant"):
            run_program("is")

    def test_an_empty_program_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            run_program("")

    def test_a_non_ipa_symbol_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="symbol"):
            run_program("sxi")

    def test_a_stray_combining_ring_is_malformed(self) -> None:
        """The ring is only ever part of ``ɰ̊``."""
        with pytest.raises(ValueError, match="symbol"):
            run_program("s̊i")

    def test_a_final_consonant_is_a_coda_only_without_a_following_vowel(self) -> None:
        """``fif`` is one syllable; ``fifi`` is two."""
        assert _syllabify(_tokenize("fif")) == [0]
        assert _syllabify(_tokenize("fifi")) == [0, 2]


class TestFricatives:
    def test_print_integer(self) -> None:
        assert run_program("cicθi") == "1"

    def test_print_character(self) -> None:
        assert run_program("ci" * 65 + "fu") == "A"

    def test_character_output_is_modulo_256(self) -> None:
        assert run_program("ci" * 321 + "fu") == "A"  # 321 % 256 == 65

    def test_input_integer(self) -> None:
        assert run_program("su" + "θi", "7\n") == "7"

    def test_input_character(self) -> None:
        assert run_program("ʒu" + "θi", "A\n") == "65"

    def test_an_unparseable_input_line_reads_as_zero(self) -> None:
        assert run_program("su" + "θi", "banana\n") == "0"
        assert run_program("su" + "θi", "\n") == "0"

    def test_a_negative_input_floors_at_zero(self) -> None:
        """The accumulator is unsigned."""
        assert run_program("su" + "θi", "-5\n") == "0"

    def test_running_out_of_input_raises(self) -> None:
        with pytest.raises(EOFError):
            run_program("su" + "θi", "")


class TestVowels:
    def test_increment_and_decrement(self) -> None:
        """Three increments then one decrement leaves 2."""
        assert run_program("cicici" + "cə" + "θi") == "2"

    def test_decrement_floors_at_zero(self) -> None:
        """Two decrements from 0 stay at 0 rather than going negative."""
        assert run_program("cəcə" + "θi") == "0"

    def test_square(self) -> None:
        assert run_program("ci" * 5 + "cæ" + "θu") == "25"

    def test_square_root_floors(self) -> None:
        assert run_program("ci" * 10 + "co" + "θu") == "3"


class TestDeque:
    """A nasal is the ``N`` of CV(N)(C), so it can never open a syllable.

    That places every deque command in third position: ``cim`` pushes and
    ``coŋ`` pops, and the vowel between is chosen to leave the value alone.
    """

    def test_push_front_and_pop_front(self) -> None:
        assert run_program("cicim" + "cəcə" + "coŋ" + "θi") == "2"

    def test_push_back_and_pop_back(self) -> None:
        assert run_program("cicin" + "cəcə" + "coɲ" + "θi") == "2"

    def test_the_two_ends_are_distinct(self) -> None:
        """Push 1 to the front and 3 to the back, then pop the back."""
        assert run_program("cim" + "cicin" + "coɲ" + "θi") == "3"

    @pytest.mark.parametrize("program", ["coŋ", "coɲ"], ids=["front", "back"])
    def test_popping_an_empty_deque_halts(self, program: str) -> None:
        with pytest.raises(HaltError, match="empty deque"):
            run_program(program)

    @pytest.mark.parametrize("program", ["pi", "ki"], ids=["front", "back"])
    def test_appending_from_an_empty_deque_halts(self, program: str) -> None:
        with pytest.raises(HaltError, match="empty deque"):
            run_program(program)


class TestFunction:
    """The function is built while the accumulator is 0, then applied by ``su``.

    Every plosive appends to the function, and ``c`` -- the one consonant
    that does not -- *resets* it, so there is no way to climb the
    accumulator with a run of ``ci`` once a function is live.  The idiom
    instead is to build first, when the accumulator is still 0 and the
    ``o`` partnering each build token is the identity, and then let ``su``
    read the argument and apply the function in a single syllable.
    """

    def test_apply_the_identity(self) -> None:
        assert run_program("do" + "su" + "θi", "5\n") == "5"

    def test_multiplication_binds_tighter_than_addition(self) -> None:
        """``a + a * a`` at a == 3 is 12, not 18."""
        program = "do" + "bo" + "do" + "ɡo" + "do" + "su" + "θi"
        assert run_program(program, "3\n") == "12"

    def test_parentheses_override_precedence(self) -> None:
        """``(a + a) * a`` at a == 3 is 18."""
        program = "ʔo" + "do" + "bo" + "do" + "ʡo" + "ɡo" + "do" + "su" + "θi"
        assert run_program(program, "3\n") == "18"

    def test_division_floors(self) -> None:
        """``a / 2`` at a == 7 is 3, with the 2 popped off the deque."""
        program = "cicin" + "do" + "qo" + "po" + "su" + "θi"
        assert run_program(program, "7\n") == "3"

    def test_dividing_by_zero_halts(self) -> None:
        program = "con" + "do" + "qo" + "po" + "su" + "θi"
        with pytest.raises(HaltError, match="division by zero"):
            run_program(program, "7\n")

    def test_subtraction_floors_at_zero(self) -> None:
        """The accumulator is unsigned, so ``2 - a`` at a == 5 is 0."""
        program = "cicin" + "po" + "to" + "do" + "su" + "θi"
        assert run_program(program, "5\n") == "0"

    def test_subtraction_that_stays_positive_is_ordinary(self) -> None:
        """The floor is a floor, not a clamp to zero: ``a - 2`` at 5 is 3."""
        program = "cicin" + "do" + "to" + "po" + "su" + "θi"
        assert run_program(program, "5\n") == "3"

    def test_a_popped_literal_comes_from_the_named_end(self) -> None:
        """``p`` takes the front and ``k`` the back, so they differ."""
        stage = "cim" + "cicicin"  # front 1, back 4
        # a - 1 == 4 taking the front, a - 4 == 1 taking the back
        assert run_program(stage + "do" + "to" + "po" + "su" + "θi", "5\n") == "4"
        assert run_program(stage + "do" + "to" + "ko" + "su" + "θi", "5\n") == "1"

    @pytest.mark.parametrize(
        "build",
        [
            "",  # empty
            "ʔo",  # a lone open paren, with nothing to open
            "ʔo" + "do",  # "(a" -- an operand, but the paren never closes
            "ʡo",  # a lone close paren
            "do" + "bo",  # a trailing operator
            "do" + "do",  # two adjacent operands
            "bo",  # a leading operator
        ],
        ids=[
            "empty",
            "open",
            "unclosed",
            "close",
            "trailing",
            "adjacent",
            "leading",
        ],
    )
    def test_an_invalid_function_does_nothing(self, build: str) -> None:
        """The spec's own "if the function is valid, else do nothing"."""
        assert run_program(build + "su" + "θi", "5\n") == "5"

    def test_reset_clears_the_function(self) -> None:
        """``c`` empties it, and an empty function is invalid, so ``u`` is
        inert -- which is what makes ``ci``/``fu`` a safe no-op pairing."""
        assert run_program("do" + "ɡo" + "do" + "co" + "su" + "θi", "5\n") == "5"

    def test_the_function_survives_until_it_is_reset(self) -> None:
        """It is applied twice, to two different arguments: 3 and then 9."""
        program = "do" + "ɡo" + "do" + "su" + "su" + "θi"
        assert run_program(program, "3\n9\n") == "81"


class TestControlFlow:
    """``ɰ̊`` jumps away when the accumulator is *zero*, so it is the opener
    of a while-nonzero loop; ``ɰ`` jumps away when nonzero and opens the
    while-zero one.  The wiki's truth machine turns on exactly that: its
    ``ɰ̊`` falls through on 1 and repeats forever.
    """

    def test_while_nonzero_runs_its_body_until_the_accumulator_empties(self) -> None:
        """Print 3, 2, 1 and stop, decrementing once per pass."""
        assert run_program("ci" * 3 + "ɰ̊u" + "θu" + "cə" + "ʋu") == "321"

    def test_while_zero_skips_its_body_when_the_accumulator_is_set(self) -> None:
        assert run_program("ci" * 3 + "ɰu" + "θu" + "ʋu" + "θi") == "3"

    def test_while_zero_enters_its_body_when_the_accumulator_is_clear(self) -> None:
        assert run_program("ɰu" + "ciθu" + "ʋu") == "1"

    def test_a_loop_end_with_no_start_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no matching start"):
            run_program("ʋi")

    def test_a_loop_start_with_no_end_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no matching end"):
            run_program("ɰi")

    def test_goto_lands_on_the_accumulator_th_character(self) -> None:
        """``su`` reads the target without disturbing it, so the jump is
        to a value the test chooses.  The offsets of ``suɹiθiθi`` are
        ``s`` 0, ``u`` 1, ``ɹ`` 2, ``i`` 3, ``θ`` 4, ``i`` 5, ``θ`` 6.
        """
        program = "su" + "ɹi" + "θi" + "θi"
        # 4 is the first θ: prints 4, the i makes it 5, the second θ prints 5
        assert run_program(program, "4\n") == "45"
        # 6 is the second θ, reached directly
        assert run_program(program, "6\n") == "6"

    def test_goto_a_syllable_counts_syllables_not_characters(self) -> None:
        """``suјiθiθi`` has four syllables, so 2 is the first ``θi``.

        The same index means different things to the two gotos, which is
        what distinguishes them: here syllable 3 is the *second* ``θi``
        while character 3 would be a bare ``i``.
        """
        program = "su" + "ji" + "θi" + "θi"
        assert run_program(program, "2\n") == "23"
        assert run_program(program, "3\n") == "3"

    def test_a_goto_past_the_end_halts(self) -> None:
        assert run_program("su" + "ɹi" + "θi" + "θi", "99\n") == ""

    def test_a_syllable_goto_past_the_end_halts(self) -> None:
        assert run_program("su" + "ji" + "θi" + "θi", "99\n") == ""

    def test_a_goto_to_its_own_offset_is_an_infinite_loop(self) -> None:
        """Nothing rescues a self-jump, and the cycle detector proves it."""
        io = ScriptedIO("2\n")
        assert run_until_halt_or_cycle(_Machine("su" + "ɹi" + "θi", io)) is False

    def test_landing_on_a_combining_ring_resumes_at_its_command(self) -> None:
        """``ɰ̊`` spans two codepoints, and both name the one command.

        In this program the ``ɰ̊`` sits at offset 6 and its ring at 7, and
        the countdown that follows prints every value from the accumulator
        down to 0.  Jumping to either offset runs the same ``ɰ̊``, so the
        two runs differ only by the accumulator they carried in -- there is
        no offset that lands "inside" the command and skips it.
        """
        program = "su" + "ɹi" + "ci" + "ɰ̊u" + "θə" + "ʋu" + "θi"
        assert run_program(program, "6\n") == "6543210"
        assert run_program(program, "7\n") == "76543210"


class TestSpellings:
    def test_the_ascii_g_is_accepted_like_the_script_g(self) -> None:
        """The wiki's table says ``ɡ`` and its Hello, world! writes ``g``."""
        ascii_g = "do" + "go" + "do" + "su" + "θi"
        script_g = ascii_g.replace("g", "ɡ")
        assert run_program(ascii_g, "3\n") == run_program(script_g, "3\n") == "9"

    def test_the_two_spellings_tokenize_the_same(self) -> None:
        assert _tokenize("ɡo") == _tokenize("go")


class TestMachine:
    def test_stepping_a_halted_machine_does_nothing(self) -> None:
        io = ScriptedIO("")
        machine = _Machine("ci", io)
        while not machine.halted:
            machine.step()
        before = machine.snapshot()
        machine.step()
        assert machine.snapshot() == before

    def test_the_snapshot_carries_the_deque_and_the_function(self) -> None:
        """Two machines differing only in memory must not look alike."""
        empty = _Machine("cim", ScriptedIO(""))
        staged = _Machine("cim", ScriptedIO(""))
        while not staged.halted:
            staged.step()
        assert empty.snapshot() != staged.snapshot()

    def test_the_input_cursor_is_in_the_snapshot(self) -> None:
        """A loop that keeps reading is not a cycle, so the cursor counts."""
        io = ScriptedIO("1\n1\n")
        machine = _Machine("su" + "θi", io)
        first = machine.snapshot()
        machine.step()
        assert machine.snapshot() != first
