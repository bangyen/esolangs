"""How the API refuses, and what it says while refusing."""

from __future__ import annotations

import contextlib
import difflib
import re
import warnings

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import _check_program
from esolangs.cli_hints import _did_you_mean
from esolangs.registry import _BY_ID, SUGGESTION_CUTOFF, canonical_id
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


class TestADeliberateRefusalIsAnEsolangError:
    """The package promises it, and the refusals that broke the promise."""

    def test_it_is_still_a_value_error(self) -> None:
        """Callers catching ValueError must not be broken by the new class."""
        assert issubclass(esolangs.GeneratorCapError, ValueError)
        assert issubclass(esolangs.GeneratorCapError, esolangs.EsolangError)

    @pytest.mark.slow
    def test_no_private_name_leaks_into_a_message(self) -> None:
        """A cap message renders its constant's value, not its name."""
        with pytest.raises(esolangs.GeneratorCapError) as exc:
            esolangs.generate("Polynomial", _big_table())
        assert "_POLYNOMIAL" not in str(exc.value)


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


class TestFactorHasNoDigitBudget:
    """Its refusal named ``max_digits``, a knob the public API never had."""

    @pytest.mark.slow
    def test_the_arity_that_used_to_refuse_builds(self) -> None:
        """Dense n=13 was the 500000-digit refusal; this table is 708448 digits now."""
        import random

        rng = random.Random(7)
        table = "".join(rng.choice("01") for _ in range(2**13))
        program = esolangs.generate("Factor", table)
        assert program.isdigit()
        assert len(program) > 500_000


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

    def test_every_error_class_round_trips(self) -> None:
        """The two above were found one at a time; this is the class."""
        import pickle

        raisers = [
            lambda: esolangs.describe("nosuchlang"),
            lambda: esolangs.generate("brainfuck", "011"),
            lambda: esolangs.encode_inputs("brainfuck", [2, 0]),
            lambda: esolangs.instantiate("brainfuck", "x", [0]),
            lambda: esolangs.run("brainfuck", None),  # type: ignore[arg-type]
            lambda: esolangs.run("brainfuck", "+[]", stdin="", timeout=0.01),
            lambda: esolangs.run(
                "brainfuck",
                esolangs.generate("brainfuck", "10010110"),
                stdin="10",
                timeout=10,
            ),
        ]
        for raise_it in raisers:
            with pytest.raises(esolangs.EsolangError) as caught:
                raise_it()
            restored = pickle.loads(pickle.dumps(caught.value))
            assert str(restored) == str(caught.value), type(caught.value).__name__


class TestAnInterpreterLimitIsStillAnEsolangError:
    """Qoibl's interpreter recurses, and Python's stack is finite."""

    @staticmethod
    def _parity(n: int) -> str:
        """Return the parity table of arity ``n`` -- reliably a hard one."""
        return "".join(str(bin(i).count("1") % 2) for i in range(2**n))

    def test_a_recursion_error_does_not_escape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """It was the one exception in the package that was not ours."""

        def explode(*_args: object, **_kwargs: object) -> None:
            raise RecursionError("maximum recursion depth exceeded")

        monkeypatch.setattr(esolangs, "_run", explode)
        with pytest.raises(esolangs.EsolangError) as caught:
            esolangs.run("brainfuck", "+.", stdin="")
        assert isinstance(caught.value, esolangs.InterpreterLimitError)
        assert "recursed deeper" in str(caught.value)
        assert "setrecursionlimit" in str(caught.value)

    def test_a_memory_error_does_not_escape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In process, Underload's string doubling reached it raw."""

        def explode(*_args: object, **_kwargs: object) -> None:
            raise MemoryError

        monkeypatch.setattr(esolangs, "_run", explode)
        with pytest.raises(esolangs.InterpreterLimitError, match="out of memory"):
            esolangs.run("brainfuck", "+.", stdin="")

    @pytest.mark.slow
    def test_qoibl_no_longer_hits_the_wall(self) -> None:
        """The six-input table this class was built around now computes."""
        assert verify_generated("Qoibl", self._parity(6), timeout=300)


class TestASuggestionIsWorthLessThanSilence:
    """0.6 offers ``Nope.`` for ``snorey``."""

    #: Single-edit slips of a real name, as a person makes them.
    @staticmethod
    def _typos(name: str) -> list[str]:
        """Dropped and transposed characters, keeping only real misses."""
        out = [name[:-1], name[0] + name[2:], name[1:]]
        if len(name) > 4:
            out.append(name[:2] + name[3:])
            out.append(name[:2] + name[3] + name[2] + name[4:])
        return [
            typo
            for typo in dict.fromkeys(out)
            if typo and canonical_id(typo) not in _BY_ID
        ]

    _JUNK = ("snorey", "zzzz", "xyz", "qqqqqq", "hello", "python", "asdf", "foo")

    def _score(self, cutoff: float) -> tuple[int, int, int]:
        """Return (typos rescued, typos tried, junk words given a guess)."""
        rescued = tried = 0
        for name in esolangs.list_languages():
            for typo in self._typos(name):
                tried += 1
                close = difflib.get_close_matches(
                    canonical_id(typo), _BY_ID, n=2, cutoff=cutoff
                )
                rescued += name in [_BY_ID[c] for c in close]
        junk = sum(
            bool(difflib.get_close_matches(canonical_id(w), _BY_ID, n=2, cutoff=cutoff))
            for w in self._JUNK
        )
        return rescued, tried, junk

    def test_the_cutoff_is_the_best_available_number(self) -> None:
        """The trade, recomputed: 0.6 costs junk and 0.7 costs rescues."""
        shipped = self._score(SUGGESTION_CUTOFF)
        assert shipped[2] == 0, "the shipped cutoff offers a guess for junk"
        # Lower: the same rescues, but junk comes back.  This is the
        # positive control -- without it the cutoff could be doing nothing.
        lower = self._score(0.6)
        assert lower[0] == shipped[0]
        assert lower[2] > 0
        # Higher: no junk either, but it starts costing real rescues.
        assert self._score(0.7)[0] < shipped[0]

    def test_a_word_that_is_not_close_gets_no_guess(self) -> None:
        """It gets the command that lists them, which is the honest answer."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe("snorey")
        assert "did you mean" not in str(caught.value)
        assert "`esolangs list` shows all of them" in str(caught.value)

    @pytest.mark.parametrize(
        ("typo", "wanted"),
        [
            ("Brainfck", "brainfuck"),
            ("Sofie", "Sophie"),
        ],
    )
    def test_a_real_typo_is_still_rescued(self, typo: str, wanted: str) -> None:
        """The half of the trade that raising a cutoff can quietly cost."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe(typo)
        assert wanted in str(caught.value)

    def test_the_cli_shares_the_number(self) -> None:
        """Its docstring promised the same cutoff while keeping its own copy."""
        assert _did_you_mean("snorey", esolangs.list_languages()) == ""
        assert "--width" in _did_you_mean("--wdith", ["--width", "--bits"])


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


class TestAFailedRowSaysWhichRow:
    """``execution exceeded the 0.2-second timeout`` and nothing else."""

    def test_the_note_names_the_row_and_the_inputs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failure forced at a chosen row, since a real one lands on row 0."""
        real_run = esolangs.run

        def fail_on_the_sixth(
            language: str, program: object, stdin: str = "", timeout: object = None
        ) -> str:
            if stdin == "101":  # row 5 of an eight-row table
                raise esolangs.ExecutionTimeoutError("execution exceeded the bound")
            return real_run(language, program, stdin=stdin, timeout=timeout)  # type: ignore[arg-type]

        monkeypatch.setattr(esolangs, "run", fail_on_the_sixth)
        with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
            evaluate_generated("brainfuck", "01101001", timeout=10)
        note = "\n".join(getattr(caught.value, "__notes__", []))
        assert "row 5 of 8" in note
        assert "inputs 101" in note
        assert "after 5 rows" in note
        assert "01101" in note  # the answers that did come back

    def test_a_real_timeout_carries_one_too(self) -> None:
        """Not only the stand-in: the path a caller actually hits."""
        from esolangs.interpreters.grid_based import circuit_diagram

        table = "".join(str(bin(r).count("1") & 1) for r in range(128))
        # A warm compile cache (another test, same worker) beats 5 ms a row.
        circuit_diagram._compile.cache_clear()  # noqa: SLF001
        with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
            evaluate_generated("Circuit Diagram", table, timeout=0.005)
        note = "\n".join(getattr(caught.value, "__notes__", []))
        assert "row 0 of 128" in note


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


class TestTheCallersSignalsAreTheirOwn:
    """The fix for the death took the caller's SIGALRM hostage."""

    @pytest.mark.parametrize("program", ["+", ","])
    def test_a_periodic_alarm_survives_a_timed_run(self, program: str) -> None:
        import signal

        previous = signal.signal(signal.SIGALRM, lambda *_a: None)
        timer = signal.setitimer(signal.ITIMER_REAL, 30, 5)
        try:
            with contextlib.suppress(esolangs.EsolangError):
                esolangs.run("brainfuck", program, timeout=1)
            remaining, interval = signal.getitimer(signal.ITIMER_REAL)
            assert remaining > 0
            assert interval == 5
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
            signal.setitimer(signal.ITIMER_REAL, *timer)

    def test_a_pending_alarm_survives_a_timed_run(self) -> None:
        """Arming ours cancelled theirs, and nothing put it back."""
        import signal

        previous = signal.signal(signal.SIGALRM, lambda *_a: None)
        try:
            signal.alarm(30)
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], truth_table="0110")
            esolangs.run("brainfuck", program, stdin=stdin, timeout=5)
            remaining = signal.alarm(0)
            assert remaining > 0, "the caller's alarm was cancelled"
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    def test_the_floor_applies_to_evaluate_too(self) -> None:
        """Its termination path never reaches ``run``, so it checked nothing."""
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            evaluate_generated("123", "0110", 1e-06)


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


class TestTheTerminationProofFallsBackToTheClock:
    """A cycle is not the only way to diverge; growth never repeats a state."""

    def test_the_proof_needs_no_clock_at_all(self) -> None:
        """Which is the measurement, and also why the clock arm is untested."""
        assert evaluate_generated("123", "0110", None) == "0110"


class TestTerminationTimeoutIsUndecided:
    def test_timeout_propagates_with_row_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def expired(*_args: object) -> None:
            raise esolangs.ExecutionTimeoutError("forced timeout")

        monkeypatch.setattr(esolangs, "_run", expired)
        with pytest.raises(
            esolangs.ExecutionTimeoutError, match="forced timeout"
        ) as exc:
            verify_generated("123", "01")
        assert any("while evaluating row 0" in note for note in exc.value.__notes__)

    @pytest.mark.medium
    def test_vm_construction_is_timed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import time

        from esolangs import _evaluate

        def slow_machine(*_args: object, **_kwargs: object) -> None:
            time.sleep(1)
            pytest.fail("construction escaped the timeout")

        monkeypatch.setattr(_evaluate, "make_vm", slow_machine)
        with pytest.raises(esolangs.ExecutionTimeoutError):
            evaluate_generated("123", "01", timeout=0.02)
