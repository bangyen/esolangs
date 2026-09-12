r"""Unit tests for the CV(N)(C) interpreter."""

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
    r"""The page's four example programs, which pin the execution model."""

    def test_hi(self) -> None:
        assert run_program(HI) == "HI"

    def test_cat_echoes_until_its_input_runs_out(self) -> None:
        r"""The cat loops on the character it read, so EOF is how it ends."""
        io = ScriptedIO("H\ni\n!\n")
        with pytest.raises(EOFError):
            run(CAT, io)
        assert io.getvalue() == "Hi!"

    def test_truth_machine_prints_zero_once_and_halts(self) -> None:
        assert run_program(TRUTH_MACHINE, "0\n") == "0"

    def test_truth_machine_loops_forever_on_one(self) -> None:
        r"""A repeated state is a proof of the hang, so no timeout is needed."""
        io = ScriptedIO("1\n")
        assert run_until_halt_or_cycle(_Machine(TRUTH_MACHINE, io)) is False
        assert set(io.getvalue()) == {"1"}

    def test_hello_world_prints_the_wiki_program_s_own_typo(self) -> None:
        r"""The example is off by one character, and provably so."""
        assert HELLO.count("f") == 14
        assert not any(c in HELLO for c in "ɰʋɹj")
        assert run_program(HELLO) == "Hello, worldd!"


class TestSyllables:
    def test_the_page_s_valid_examples_parse(self) -> None:
        for code in ("su", "suŋ", "suŋs", "suŋsu"):
            assert _syllabify(_tokenize(code))

    def test_the_page_s_counterexample_is_rejected(self) -> None:
        r"""``susŋ`` is CVCN, which cannot be cut into CV(N)(C) syllables."""
        with pytest.raises(ValueError, match="consonant") as caught:
            run_program("susŋ")
        assert str(caught.value) == "syllable must start with a consonant: 'ŋ'"

    def test_a_syllable_needs_a_vowel(self) -> None:
        with pytest.raises(ValueError, match="vowel") as caught:
            run_program("s")
        assert str(caught.value) == "syllable must have a vowel after its consonant"

    def test_a_syllable_starts_with_a_consonant(self) -> None:
        with pytest.raises(ValueError, match="consonant") as caught:
            run_program("is")
        assert str(caught.value) == "syllable must start with a consonant: 'i'"

    def test_an_empty_program_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="empty") as caught:
            run_program("")
        assert str(caught.value) == "program is empty"

    def test_a_non_ipa_symbol_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="symbol"):
            run_program("sxi")

    def test_a_stray_combining_ring_is_malformed(self) -> None:
        r"""The ring is only ever part of ``ɰ̊``."""

        with pytest.raises(ValueError, match="symbol"):
            run_program("s̊i")

    def test_a_final_consonant_is_a_coda_only_without_a_following_vowel(self) -> None:
        r"""``fif`` is one syllable; ``fifi`` is two."""
        assert _syllabify(_tokenize("fif")) == [0]
        assert _syllabify(_tokenize("fifi")) == [0, 2]


class TestFricatives:
    def test_print_integer(self) -> None:
        assert run_program("cicθi") == "1"

    def test_print_character(self) -> None:
        assert run_program("ci" * 65 + "fu") == "A"

    def test_character_output_is_modulo_256(self) -> None:
        assert run_program("ci" * 321 + "fu") == "A"  # 321 % 256 == 65.

    def test_input_integer(self) -> None:
        assert run_program("su" + "θi", "7\n") == "7"

    def test_input_character(self) -> None:
        assert run_program("ʒu" + "θi", "A\n") == "65"

    @pytest.mark.parametrize(
        ("char", "expected"),
        [("\u0100", "0"), ("\u0101", "1"), ("\u4e2d", "45")],
        ids=["256", "257", "cjk"],
    )
    def test_a_unicode_input_character_is_taken_modulo_256(
        self, char: str, expected: str
    ) -> None:
        r"""The spec's own "if Unicode, then modulo it by 256"."""
        assert run_program("ʒu" + "θi", char + "\n") == expected

    def test_a_nul_input_character_reads_as_zero(self) -> None:
        r"""A NUL byte is 0, not the fallback for a missing one."""
        assert run_program("ʒu" + "θi", "\x00\n") == "0"

    def test_an_unparseable_input_line_reads_as_zero(self) -> None:
        assert run_program("su" + "θi", "banana\n") == "0"
        assert run_program("su" + "θi", "\n") == "0"

    def test_a_negative_input_floors_at_zero(self) -> None:
        r"""The accumulator is unsigned."""
        assert run_program("su" + "θi", "-5\n") == "0"

    def test_running_out_of_input_raises(self) -> None:
        with pytest.raises(EOFError):
            run_program("su" + "θi", "")


class TestVowels:
    def test_increment_and_decrement(self) -> None:
        r"""Three increments then one decrement leaves 2."""
        assert run_program("cicici" + "cə" + "θi") == "2"

    def test_decrement_floors_at_zero(self) -> None:
        r"""Two decrements from 0 stay at 0 rather than going negative."""
        assert run_program("cəcə" + "θi") == "0"

    def test_square(self) -> None:
        assert run_program("ci" * 5 + "cæ" + "θu") == "25"

    def test_square_root_floors(self) -> None:
        assert run_program("ci" * 10 + "co" + "θu") == "3"


class TestDeque:
    r"""A nasal is the ``N`` of CV(N)(C), so it can never open a syllable."""

    def test_push_front_and_pop_front(self) -> None:
        assert run_program("cicim" + "cəcə" + "coŋ" + "θi") == "2"

    def test_push_back_and_pop_back(self) -> None:
        assert run_program("cicin" + "cəcə" + "coɲ" + "θi") == "2"

    def test_the_two_ends_are_distinct(self) -> None:
        r"""Push 1 to the front and 3 to the back, then pop the back."""
        assert run_program("cim" + "cicin" + "coɲ" + "θi") == "3"

    @pytest.mark.parametrize(
        ("push", "pop", "expected"),
        [
            ("m", "ŋ", "3"),  # front, front: the later push.
            ("m", "ɲ", "1"),  # front, back: the earlier push.
            ("n", "ŋ", "1"),  # back, back-loaded: the.
            ("n", "ɲ", "3"),  # back, back: the later push is.
        ],
        ids=["front-front", "front-back", "back-front", "back-back"],
    )
    def test_each_end_is_addressed_independently(
        self, push: str, pop: str, expected: str
    ) -> None:
        r"""Two *different* values are what separate the four combinations."""
        program = "ci" + push + "cici" + push + "co" + pop + "θi"
        assert run_program(program) == expected

    def test_a_pop_leaves_the_rest_of_the_deque_intact(self) -> None:
        r"""What a pop *removes* needs three values and a second pop."""
        three = "cin" + "cici" + "n" + "cicici" + "n"
        assert run_program(three + "coɲ" + "coɲ" + "θi") == "3"  # 6 then 3.
        assert run_program(three + "coŋ" + "coŋ" + "θi") == "3"  # 1 then 3.

    @pytest.mark.parametrize("program", ["coŋ", "coɲ"], ids=["front", "back"])
    def test_popping_an_empty_deque_halts(self, program: str) -> None:
        with pytest.raises(HaltError) as caught:
            run_program(program)
        assert str(caught.value) == "pop from an empty deque"

    @pytest.mark.parametrize("program", ["pi", "ki"], ids=["front", "back"])
    def test_appending_from_an_empty_deque_halts(self, program: str) -> None:
        with pytest.raises(HaltError) as caught:
            run_program(program)
        assert str(caught.value) == "pop from an empty deque"


class TestFunction:
    r"""The function is built while the accumulator is 0, then applied by."""

    def test_apply_the_identity(self) -> None:
        assert run_program("do" + "su" + "θi", "5\n") == "5"

    def test_multiplication_binds_tighter_than_addition(self) -> None:
        r"""``a + a * a`` at a == 3 is 12, not 18."""
        program = "do" + "bo" + "do" + "ɡo" + "do" + "su" + "θi"
        assert run_program(program, "3\n") == "12"

    def test_parentheses_override_precedence(self) -> None:
        r"""``(a + a) * a`` at a == 3 is 18."""
        program = "ʔo" + "do" + "bo" + "do" + "ʡo" + "ɡo" + "do" + "su" + "θi"
        assert run_program(program, "3\n") == "18"

    def test_division_floors(self) -> None:
        r"""``a / 2`` at a == 7 is 3, with the 2 popped off the deque."""
        program = "cicin" + "do" + "qo" + "po" + "su" + "θi"
        assert run_program(program, "7\n") == "3"

    def test_dividing_by_zero_halts(self) -> None:
        program = "con" + "do" + "qo" + "po" + "su" + "θi"
        with pytest.raises(HaltError) as caught:
            run_program(program, "7\n")
        assert str(caught.value) == "division by zero in the function"

    def test_subtraction_floors_at_zero(self) -> None:
        r"""The accumulator is unsigned, so ``2 - a`` at a == 5 is 0."""
        program = "cicin" + "po" + "to" + "do" + "su" + "θi"
        assert run_program(program, "5\n") == "0"

    def test_subtraction_that_stays_positive_is_ordinary(self) -> None:
        r"""The floor is a floor, not a clamp to zero: ``a - 2`` at 5 is 3."""
        program = "cicin" + "do" + "to" + "po" + "su" + "θi"
        assert run_program(program, "5\n") == "3"

    def test_a_popped_literal_comes_from_the_named_end(self) -> None:
        r"""``p`` takes the front and ``k`` the back, so they differ."""
        stage = "cim" + "cicicin"  # front 1, back 4.
        # a - 1 == 4 taking the front,.
        assert run_program(stage + "do" + "to" + "po" + "su" + "θi", "5\n") == "4"
        assert run_program(stage + "do" + "to" + "ko" + "su" + "θi", "5\n") == "1"

    @pytest.mark.parametrize(
        "build",
        [
            "",  # empty.
            "ʔo",  # a lone open paren, with.
            "ʔo" + "do",  # "(a" -- an operand, but the.
            "ʡo",  # a lone close paren.
            "do" + "bo",  # a trailing operator.
            "do" + "do",  # two adjacent operands.
            "bo",  # a leading operator.
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
        r"""The spec's own "if the function is valid, else do nothing"."""
        assert run_program(build + "su" + "θi", "5\n") == "5"

    def test_reset_clears_the_function(self) -> None:
        r"""``c`` empties it, and an empty function is invalid, so ``u`` is."""
        assert run_program("do" + "ɡo" + "do" + "co" + "su" + "θi", "5\n") == "5"

    @pytest.mark.parametrize(
        ("build", "stage", "stdin", "expected"),
        [
            ("do" + "\u0261o" + "do" + "\u0261o" + "do", "", "2\n", "8"),
            ("do" + "\u0261o" + "do" + "qo" + "po", "cici" + "n", "6\n", "18"),
        ],
        ids=["a*a*a", "a*a/2"],
    )
    def test_a_chain_of_same_precedence_operators_keeps_going(
        self, build: str, stage: str, stdin: str, expected: str
    ) -> None:
        r"""The term loop consumes *every* multiplicative operator, not one."""
        assert run_program(stage + build + "su" + "\u03b8i", stdin) == expected

    def test_the_function_survives_until_it_is_reset(self) -> None:
        r"""It is applied twice, to two different arguments: 3 and then 9."""
        program = "do" + "ɡo" + "do" + "su" + "su" + "θi"
        assert run_program(program, "3\n9\n") == "81"


class TestControlFlow:
    r"""``ɰ̊`` jumps away when the accumulator is *zero*, so it is the."""

    def test_while_nonzero_runs_its_body_until_the_accumulator_empties(self) -> None:
        r"""Print 3, 2, 1 and stop, decrementing once per pass."""
        assert run_program("ci" * 3 + "ɰ̊u" + "θu" + "cə" + "ʋu") == "321"

    def test_while_zero_skips_its_body_when_the_accumulator_is_set(self) -> None:
        assert run_program("ci" * 3 + "ɰu" + "θu" + "ʋu" + "θi") == "3"

    def test_while_zero_enters_its_body_when_the_accumulator_is_clear(self) -> None:
        assert run_program("ɰu" + "ciθu" + "ʋu") == "1"

    @pytest.mark.parametrize(
        ("program", "expected"),
        [
            ("ci" * 3 + "ɰu" + "θu" + "ʋi" + "θi", "4"),
            ("ɰ̊u" + "θu" + "ʋi" + "θi", "1"),
        ],
        ids=["while-zero", "while-nonzero"],
    )
    def test_a_skipped_loop_resumes_on_the_end_marker_s_own_vowel(
        self, program: str, expected: str
    ) -> None:
        r"""The jump clears the ``ʋ`` and lands on the rest of its syllable."""
        assert run_program(program) == expected

    def test_a_loop_end_with_no_start_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no matching start") as caught:
            run_program("ʋi")
        assert str(caught.value) == "loop end with no matching start"

    def test_a_loop_start_with_no_end_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="no matching end") as caught:
            run_program("ɰi")
        assert str(caught.value) == "loop start with no matching end"

    def test_goto_lands_on_the_accumulator_th_character(self) -> None:
        r"""``su`` reads the target without disturbing it, so the jump is to a."""
        program = "su" + "ɹi" + "θi" + "θi"
        # 4 is the first θ: prints 4,.
        assert run_program(program, "4\n") == "45"
        # 6 is the second θ, reached.
        assert run_program(program, "6\n") == "6"

    def test_goto_a_syllable_counts_syllables_not_characters(self) -> None:
        r"""``suјiθiθi`` has four syllables, so 2 is the first ``θi``."""
        program = "su" + "ji" + "θi" + "θi"
        assert run_program(program, "2\n") == "23"
        assert run_program(program, "3\n") == "3"

    def test_a_goto_past_the_end_halts(self) -> None:
        assert run_program("su" + "ɹi" + "θi" + "θi", "99\n") == ""

    def test_a_syllable_goto_past_the_end_halts(self) -> None:
        assert run_program("su" + "ji" + "θi" + "θi", "99\n") == ""

    def test_a_syllable_goto_to_the_count_itself_halts(self) -> None:
        r"""The bound is exclusive, and off by one it indexes past the list."""
        assert run_program("su" + "ji" + "θi" + "θi", "4\n") == ""

    def test_a_goto_to_its_own_offset_is_an_infinite_loop(self) -> None:
        r"""Nothing rescues a self-jump, and the cycle detector proves it."""
        io = ScriptedIO("2\n")
        assert run_until_halt_or_cycle(_Machine("su" + "ɹi" + "θi", io)) is False

    def test_landing_on_a_combining_ring_resumes_at_its_command(self) -> None:
        r"""``ɰ̊`` spans two codepoints, and both name the one command."""
        program = "su" + "ɹi" + "ci" + "ɰ̊u" + "θə" + "ʋu" + "θi"
        assert run_program(program, "6\n") == "6543210"
        assert run_program(program, "7\n") == "76543210"


class TestSpellings:
    def test_the_ascii_g_is_accepted_like_the_script_g(self) -> None:
        r"""The wiki's table says ``ɡ`` and its Hello, world."""

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
        r"""Two machines differing only in memory must not look alike."""
        empty = _Machine("cim", ScriptedIO(""))
        staged = _Machine("cim", ScriptedIO(""))
        while not staged.halted:
            staged.step()
        assert empty.snapshot() != staged.snapshot()

    def test_the_input_cursor_is_in_the_snapshot(self) -> None:
        r"""A loop that keeps reading is not a cycle, so the cursor counts."""
        io = ScriptedIO("1\n1\n")
        machine = _Machine("su" + "θi", io)
        first = machine.snapshot()
        machine.step()
        assert machine.snapshot() != first
