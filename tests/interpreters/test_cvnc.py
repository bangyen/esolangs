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
        assert io.getvalue() == "H\ni\n!\n"

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
        """The ring is only ever part of ``ɰ̊``."""
        with pytest.raises(ValueError, match="symbol"):
            run_program("s̊i")

    def test_a_final_consonant_is_a_coda_only_without_a_following_vowel(self) -> None:
        """``fif`` is one syllable; ``fifi`` is two."""
        assert _syllabify(_tokenize("fif")) == [0]
        assert _syllabify(_tokenize("fifi")) == [0, 2]


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

    @pytest.mark.parametrize(
        ("push", "pop", "expected"),
        [
            ("m", "ŋ", "3"),  # front, front: the later push is in front
            ("m", "ɲ", "1"),  # front, back: the earlier push is at the back
            ("n", "ŋ", "1"),  # back, back-loaded: the earlier push is in front
            ("n", "ɲ", "3"),  # back, back: the later push is at the back
        ],
        ids=["front-front", "front-back", "back-front", "back-back"],
    )
    def test_each_end_is_addressed_independently(
        self, push: str, pop: str, expected: str
    ) -> None:
        """Two *different* values are what separate the four combinations.

        With a single element on the deque, pushing to the front and to the
        back leave the same deque and popping either end returns the same
        number, so a test that stages one value cannot tell any of the four
        apart -- it passes just as happily if both ends are the same end.
        Staging 1 and then 3 gives each combination its own answer.
        """
        program = "ci" + push + "cici" + push + "co" + pop + "θi"
        assert run_program(program) == expected

    def test_a_pop_leaves_the_rest_of_the_deque_intact(self) -> None:
        """What a pop *removes* needs three values and a second pop.

        Every test above pops once and reads the value that came off,
        which is the same under any slice that keeps the right end: it is
        the remainder that differs.  Two elements cannot separate them
        either -- dropping the last of two and keeping the first of two
        are the same tuple.  Three pushes stage ``(1, 3, 6)``, the
        accumulator carrying across each, and the second pop reads back
        what the first one left.
        """
        three = "cin" + "cici" + "n" + "cicici" + "n"
        assert run_program(three + "coɲ" + "coɲ" + "θi") == "3"  # 6 then 3
        assert run_program(three + "coŋ" + "coŋ" + "θi") == "3"  # 1 then 3

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
        """The jump clears the ``ʋ`` and lands on the rest of its syllable.

        ``ʋ`` is a consonant, so its syllable carries a vowel that is a
        command in its own right and must still run.  Every other loop test
        here happens to pair ``ʋ`` with a vowel that changes nothing, so
        landing one command further would look identical; giving that
        syllable an ``i`` makes the difference observable -- the increment
        is skipped if the jump overshoots.
        """
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

    def test_a_syllable_goto_to_the_count_itself_halts(self) -> None:
        """The bound is exclusive, and off by one it indexes past the list.

        ``suјiθiθi`` has four syllables, so 4 is the first index with no
        syllable to land on.  Accepting it would read ``starts[4]`` and
        raise ``IndexError`` rather than halting, which is a crash the
        far-past-the-end case never reaches.
        """
        assert run_program("su" + "ji" + "θi" + "θi", "4\n") == ""

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


class TestIgnoredLF:
    @pytest.mark.parametrize(
        ("code", "stdin", "expected"),
        [
            (HI, "", "HI"),
            ("suɹiθiθi", "4\n", "45"),
            ("suɹiθiθi", "6\n", "6"),
            ("sujiθiθi", "2\n", "23"),
            ("sujiθiθi", "3\n", "3"),
            ("suɹiciɰ̊uθəʋuθi", "6\n", "6543210"),
            ("suɹiciɰ̊uθəʋuθi", "7\n", "76543210"),
            (TRUTH_MACHINE, "0\n", "0"),
        ],
    )
    def test_lf_at_every_boundary_preserves_execution(
        self, code: str, stdin: str, expected: str
    ) -> None:
        assert run_program(code, stdin) == expected
        for at in range(len(code) + 1):
            assert run_program(code[:at] + "\n" + code[at:], stdin) == expected
        assert run_program("\n\n" + "\n\n".join(code) + "\n\n", stdin) == expected

    @pytest.mark.parametrize("char", [" ", "\t", "\r"])
    def test_other_whitespace_remains_invalid(self, char: str) -> None:
        with pytest.raises(ValueError, match="not a CV"):
            run_program("θ\n" + char + "\ni")

    def test_lf_does_not_fix_invalid_symbols_or_syllables(self) -> None:
        for code in ("s\nx\ni", "s\n̊\ni", "su\ns\nŋ"):
            with pytest.raises(ValueError, match=r"not a CV|syllable"):
                run_program(code)
        with pytest.raises(ValueError, match="empty"):
            run_program("\n\n")

    def test_lf_split_loop_still_has_the_same_cycle(self) -> None:
        io = ScriptedIO("1\n")
        assert run_until_halt_or_cycle(_Machine("\n".join(TRUTH_MACHINE), io)) is False
        assert set(io.getvalue()) == {"1"}
