"""How the API refuses, and what it says while refusing."""

from __future__ import annotations

import contextlib
import re
import warnings

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import _check_program
from tests.generator_support import evaluate_generated, verify_generated
from tests.stdin_check import _check_stdin


class TestTheNewChecksRefuseTheirOwnBadInput:
    """The arguments the round's new parameters can be given wrongly."""

    def test_encode_inputs_names_a_non_string_table(self) -> None:
        """It is a table's *type* that is wrong, not the bit count."""
        with pytest.raises(esolangs.TruthTableError, match="got int"):
            esolangs.encode_inputs("brainfuck", [1, 0], truth_table=110)  # type: ignore[arg-type]

    def test_evaluate_names_a_non_string_table(self) -> None:
        """Reported before any generator sees it, for the same reason."""
        with pytest.raises(esolangs.TruthTableError, match="got list"):
            evaluate_generated("brainfuck", [0, 1, 1, 0])  # type: ignore[arg-type]

    def test_machine_traits_refuses_an_unregistered_name(self) -> None:
        """Same contract as ``make_vm``, which is the only other reader."""
        from esolangs.vm import machine_traits

        with pytest.raises(esolangs.UnknownLanguageError):
            machine_traits("Nonexistent")


def _big_table(arity: int = 11) -> str:
    """Return a dense table at ``arity``, past the cap it is used for."""
    import random

    rng = random.Random(7)
    return "".join(rng.choice("01") for _ in range(2**arity))


class TestEveryAuditedCapIsCatchable:
    """The n=11 probe that found the first five was bounded by n=11."""

    def test_the_refusal_is_catchable_at_the_size_it_refuses(self) -> None:
        """A refusal past the sweep's bound, at the first arity that triggers it."""
        with pytest.raises(esolangs.GeneratorCapError, match="cost"):
            esolangs.generate("Polynomial", _big_table(11))

    def test_it_is_catchable_through_evaluate_too(self) -> None:
        """NoComment's leaked through ``evaluate`` identically."""
        with pytest.raises(esolangs.GeneratorCapError):
            evaluate_generated("Polynomial", _big_table(11))

    def test_befunge_grid_refusal_is_catchable(self) -> None:
        with pytest.raises(esolangs.GeneratorCapError, match="80x25"):
            esolangs.generate("Befunge", "0010" * (1 << 12))

    def test_nocomment_builds_at_the_arity_that_escaped(self) -> None:
        """The escape's subject is gone: n=12 is a template, not a refusal."""
        n = 12
        table = "".join(str(bin(r).count("1") % 2) for r in range(2**n))
        template = esolangs.generate("NoComment", table)
        assert template.inputs == 12

    @pytest.mark.slow
    @pytest.mark.weekly
    @pytest.mark.cost_evidence("an unclassified exception from any n=12 generator")
    def test_nothing_escapes_the_contract_at_twelve_inputs(self) -> None:
        """A periodic table, so the generators that blow up stay small."""
        table = "0010" * (1 << 10)
        escaped = []
        for name in esolangs.list_languages():
            try:
                esolangs.generate(name, table)
            except esolangs.EsolangError:
                pass
            except Exception as exc:
                escaped.append(f"{name}: {type(exc).__name__}")
        assert not escaped, escaped


class TestErrorsSurviveAProcessBoundary:
    """The library's commonest error could not come home from a worker."""

    def test_input_exhausted_round_trips(self) -> None:
        """It built its message in ``__init__``, so unpickling passed one arg."""
        import pickle

        program = esolangs.generate("brainfuck", "10010110")
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            esolangs.run("brainfuck", program, stdin="10", timeout=10)
        restored = pickle.loads(pickle.dumps(caught.value))
        assert str(restored) == str(caught.value)
        assert restored.reads == caught.value.reads
        assert restored.supplied == caught.value.supplied

    def test_unknown_language_does_not_grow_its_message(self) -> None:
        """It re-applied its prefix on every hop: "unknown language: " twice."""
        import pickle

        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe("nosuchlang")
        current: BaseException = caught.value
        for _ in range(3):
            current = pickle.loads(pickle.dumps(current))
        assert str(current) == str(caught.value)


class TestAnUnknownNameIsShownReadably:
    """A bare rendering can be a lie, and was for two shapes of input."""

    def test_an_empty_name_is_not_a_hole_in_a_sentence(self) -> None:
        """It read ``unknown language: ; `esolangs list` shows all of them``."""
        with pytest.raises(esolangs.UnknownLanguageError, match="unknown language: ''"):
            esolangs.describe("")

    def test_an_unprintable_name_is_quoted(self) -> None:
        """Otherwise the message renders the control character and lies."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe("brain\x00fuck")
        assert "\\x00" in str(caught.value)

    def test_an_ordinary_miss_stays_unquoted(self) -> None:
        """Quoting every miss to cover the rare one makes the common case worse."""
        with pytest.raises(
            esolangs.UnknownLanguageError, match="unknown language: zzzz"
        ):
            esolangs.describe("zzzz")


class TestATableLengthNamesTheNearestLegalOnes:
    """The rule without the arithmetic, on the likeliest first error."""

    @pytest.mark.parametrize(
        ("table", "expected"),
        [
            ("0" * 3, "3 is between 2 (1 input) and 4 (2 inputs)"),
            ("0" * 100, "100 is between 64 (6 inputs) and 128 (7 inputs)"),
        ],
    )
    def test_the_brackets_are_named(self, table: str, expected: str) -> None:
        """And singular where it should be: "1 input", not "1 inputs"."""
        with pytest.raises(esolangs.TruthTableError, match=re.escape(expected)):
            esolangs.generate("brainfuck", table)

    def test_an_empty_table_gets_no_brackets(self) -> None:
        """``2 ** -1`` is 0.5, so the arithmetic does not apply to nothing."""
        with pytest.raises(esolangs.TruthTableError) as caught:
            esolangs.generate("brainfuck", "")
        assert "is between" not in str(caught.value)

    def test_the_brackets_are_actually_legal_lengths(self) -> None:
        """The message would be worse than none if it named an unusable size."""
        with pytest.raises(esolangs.TruthTableError) as caught:
            esolangs.generate("brainfuck", "0" * 6)
        for length in (4, 8):
            assert f"{length} (" in str(caught.value)
            esolangs.generate("brainfuck", "0" * length)  # so it builds


class TestASurroundingSpaceResolves:
    """Almost every name already tolerated one, and the one that did not."""

    @pytest.mark.parametrize("pad", [" {} ", "\t{}\n"])
    def test_every_language_tolerates_surrounding_space(self, pad: str) -> None:
        """All of them, because the one that failed was not the obvious one."""
        for name in esolangs.list_languages():
            assert esolangs.describe(pad.format(name))["name"] == name

    @pytest.mark.parametrize("name", ["CV(N)(C)"])
    def test_the_override_name_specifically(self, name: str) -> None:
        """Named, so a future override cannot quietly reintroduce the gap."""
        assert esolangs.describe(f" {name} ")["name"] == name

    def test_internal_spacing_is_still_normalized(self) -> None:
        """The strip must not have replaced the rule that was already working."""
        assert esolangs.describe("Home  Row")["name"] == "Home Row"


class TestABadStdinIsAnArgumentFault:
    """Four entry points filed it as a *program* fault, and one did not."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda: esolangs.run("brainfuck", ",.", stdin=["0"]),
            lambda: _check_program("brainfuck", ",.", ["0"]),
            lambda: debugger_api.make_vm("brainfuck", ",.", stdin=["0"]),
            lambda: debugger_api.make_debugger("brainfuck", ",.", stdin=["0"]),
            lambda: _check_stdin("brainfuck", ["0"]),
        ],
    )
    def test_every_entry_point_agrees(self, call: object) -> None:
        """One fault, one class -- ``except ArgumentError`` has to cover all five."""
        with pytest.raises(esolangs.ArgumentError, match="stdin must be a string"):
            call()  # type: ignore[operator]

    def test_a_bad_program_is_still_a_program_error(self) -> None:
        """The change must not blur the distinction the other way."""
        with pytest.raises(esolangs.ProgramError, match="program must be a string"):
            esolangs.run("brainfuck", 42, stdin="")  # type: ignore[arg-type]


class TestBoolsAreRefusedForAStatedReason:
    """ "must be 0 or 1" reads as wrong when you passed True, which is 1."""

    def test_the_message_says_why(self) -> None:
        """The exclusion is deliberate and the reason is a past wrong answer."""
        with pytest.raises(esolangs.ArgumentError, match="True == 1"):
            esolangs.encode_inputs("brainfuck", [True, False])


class TestTheWarningHasItsOwnClass:
    """So a sweep can escalate exactly these to errors."""

    def test_run_raises_it_by_class(self) -> None:
        """Which is what makes ``filterwarnings("error", ...)`` targeted."""
        program = esolangs.generate("brainfuck", "00011011")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            esolangs.run("brainfuck", program, stdin="1\n1\n0\n0\n1\n1\n", timeout=10)


class TestReadAnswerExplainsInWords:
    """The regex was the whole explanation for the two pattern languages."""

    @pytest.mark.parametrize("name", ["A Painter Ant", "RAM0"])
    def test_the_note_leads_and_the_pattern_follows(self, name: str) -> None:
        """Both halves, in that order."""
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.read_answer(name, "garbage")
        message = str(caught.value)
        note = str(esolangs.describe(name)["answer_convention"])
        pattern = str(esolangs.describe(name)["answer_pattern"])
        assert note in message
        # The pattern is rendered with !r, so a backslash in it is doubled.
        assert repr(pattern) in message
        assert message.index(note) < message.index(repr(pattern))

    def test_a_plain_language_is_unchanged(self) -> None:
        """No pattern, no note, and nothing to add -- it was already clear."""
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.read_answer("brainfuck", "garbage")
        assert "as the last character" in str(caught.value)
        assert "matched with" not in str(caught.value)

    def test_every_dump_language_says_something_in_words(self) -> None:
        """The general claim, not the two cases that prompted it."""
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["answer_mode"] != "dump":
                continue
            with pytest.raises(esolangs.ProgramError) as caught:
                esolangs.read_answer(name, "garbage")
            note = facts["answer_convention"]
            assert note is None or str(note) in str(caught.value), name


class TestATimeoutCannotKillTheProcess:
    """The long-running defect, and the second thing it turned into."""

    def test_a_bound_too_short_to_service_is_refused(self) -> None:
        """The floor, which is what makes restoring the disposition safe."""
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            esolangs.run("brainfuck", "+.", stdin="", timeout=0.0001)

    def test_the_caller_gets_their_disposition_back(self) -> None:
        """Including ``SIG_DFL``, which the previous fix kept for itself."""
        import signal

        previous = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        try:
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], truth_table="0110")
            esolangs.run("brainfuck", program, stdin=stdin, timeout=5)
            assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
        finally:
            signal.signal(signal.SIGALRM, previous)

    def test_a_custom_handler_is_given_back_too(self) -> None:
        """The case that always worked, kept so the fix cannot regress it."""
        import signal

        def _mine(_signum: object, _frame: object) -> None:
            """A handler a caller might have installed."""

        previous = signal.signal(signal.SIGALRM, _mine)
        try:
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], truth_table="0110")
            esolangs.run("brainfuck", program, stdin=stdin, timeout=5)
            assert signal.getsignal(signal.SIGALRM) is _mine
        finally:
            signal.signal(signal.SIGALRM, previous)

    def test_the_timer_is_always_disarmed(self) -> None:
        """A timer left armed is the next run's stray alarm."""
        import signal

        program = esolangs.generate("brainfuck", "0110")
        stdin = esolangs.encode_inputs("brainfuck", [0, 1], truth_table="0110")
        for bound in (10, 0.001):
            with contextlib.suppress(esolangs.ExecutionTimeoutError):
                esolangs.run("brainfuck", program, stdin=stdin, timeout=bound)
            assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)

    @pytest.mark.slow
    def test_many_runs_at_the_floor_neither_die_nor_leak(self) -> None:
        """The stress the floor was chosen against, in process."""
        import signal

        program = esolangs.generate("brainfuck", "0110")
        stdin = esolangs.encode_inputs("brainfuck", [0, 1], truth_table="0110")
        previous = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        try:
            for _ in range(400):
                with contextlib.suppress(esolangs.ExecutionTimeoutError):
                    esolangs.run("brainfuck", program, stdin=stdin, timeout=0.001)
                assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
                assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
        finally:
            signal.signal(signal.SIGALRM, previous)


class TestEvaluateCanRunOffTheMainThread:
    """The wall-clock guard is a signal, and there was no way to opt out."""

    @pytest.mark.medium
    def test_an_explicit_none_means_unbounded(self) -> None:
        """As it does in ``run``; here the same word meant "use the default"."""
        import concurrent.futures as cf

        names = ["brainfuck", "Suffolk", "123", "A Painter Ant", "Fargo"]
        with cf.ThreadPoolExecutor(4) as pool:
            got = list(pool.map(lambda n: verify_generated(n, "0110", None), names))
        assert all(got), dict(zip(names, got, strict=True))


class TestDivergenceIsProvenNotWaitedOut:
    """A repeated state settles it exactly, and in milliseconds."""

    @pytest.mark.parametrize("name", ["123", "ArrowQueue"])
    def test_the_proven_answer_is_the_table(self, name: str) -> None:
        """The answers must be the ones the clock used to give, exactly."""
        assert evaluate_generated(name, "00011011") == "00011011"

    def test_it_no_longer_costs_a_timeout_per_row(self) -> None:
        """It was five seconds per 1-row: twenty seconds for this call."""
        import time

        start = time.monotonic()
        evaluate_generated("123", "0110")
        assert time.monotonic() - start < 5.0
