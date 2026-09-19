"""How the API refuses, and what it says while refusing.

Every deliberate failure derives from EsolangError, every cap names a remedy a
caller can actually reach, and a near miss on a language name is answered with
silence rather than a wrong guess.  The timeout suites are here too: a bound
that cannot kill the process, and a divergence proved rather than waited out.
"""

from __future__ import annotations

import contextlib
import difflib
import re
from typing import ClassVar

import pytest

import esolangs
from esolangs import cli
from esolangs.registry import _BY_ID, SUGGESTION_CUTOFF, canonical_id


class TestTheNewChecksRefuseTheirOwnBadInput:
    """The arguments the round's new parameters can be given wrongly."""

    def test_encode_inputs_names_a_non_string_table(self) -> None:
        """It is a table's *type* that is wrong, not the bit count."""
        with pytest.raises(esolangs.TruthTableError, match="got int"):
            esolangs.encode_inputs("brainfuck", [1, 0], 110)  # type: ignore[arg-type]

    def test_evaluate_names_a_non_string_table(self) -> None:
        """Reported before any generator sees it, for the same reason."""
        with pytest.raises(esolangs.TruthTableError, match="got list"):
            esolangs.evaluate("brainfuck", [0, 1, 1, 0])  # type: ignore[arg-type]

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
    """The package promises it, and the refusals that broke the promise.

    Every generator cap once raised a plain ``ValueError``, so ``except
    EsolangError`` around a registry sweep, the idiom the docs advertise,
    crashed on the first of them.  The caps that remain still have to be
    catchable.
    """

    #: The ones that stop rather than build, and the arity that trips each.
    #: Only these are built here: the rest succeed at n=11 and several take
    #: minutes to do it.  Carried per language rather than as one table:
    #: Factor's cap was on the encoded integer's digits, not on ``n``, and
    #: a shared n=11 quietly stopped testing it at all -- the
    #: ``pytest.raises`` simply saw the program get built.
    _REFUSERS: ClassVar[dict[str, int]] = {
        "Polynomial": 11,
    }

    @pytest.mark.slow
    @pytest.mark.parametrize("name", _REFUSERS)
    def test_the_refusal_is_catchable(self, name: str) -> None:
        """And by the documented base class, not only the specific one."""
        with pytest.raises(esolangs.GeneratorCapError):
            esolangs.generate(name, _big_table(self._REFUSERS[name]))

    @pytest.mark.slow
    @pytest.mark.parametrize("name", _REFUSERS)
    def test_the_documented_idiom_catches_it(self, name: str) -> None:
        """``except EsolangError`` is what the package docstring promises."""
        with pytest.raises(esolangs.EsolangError):
            esolangs.generate(name, _big_table(self._REFUSERS[name]))

    def test_it_is_still_a_value_error(self) -> None:
        """Callers catching ValueError must not be broken by the new class."""
        assert issubclass(esolangs.GeneratorCapError, ValueError)
        assert issubclass(esolangs.GeneratorCapError, esolangs.EsolangError)

    def test_it_is_exported(self) -> None:
        """A refusal nobody can name is a refusal nobody can catch."""
        assert "GeneratorCapError" in esolangs.__all__

    @pytest.mark.slow
    def test_no_private_name_leaks_into_a_message(self) -> None:
        """A cap message renders its constant's value, not its name."""
        with pytest.raises(esolangs.GeneratorCapError) as exc:
            esolangs.generate("Polynomial", _big_table())
        assert "_POLYNOMIAL" not in str(exc.value)


class TestEveryAuditedCapIsCatchable:
    """The n=11 probe that found the first five was bounded by n=11.

    NoComment first refused at n=12, so it escaped that sweep and still
    raised a bare ``ValueError`` -- and a reader following the try/except
    the previous round *added to the docstring* was met with an uncaught
    exception.  The fix for a class of bug cannot be found by widening the
    sweep that missed it, so the remaining sites were audited by reading.

    NoComment no longer refuses at any arity -- its chain runs on six tape
    cells -- so the fast checks here drive the cheapest refusal that
    remains, Polynomial's instruction cap on a dense eleven-input table,
    and NoComment is checked to *build* where it escaped.
    """

    def test_the_refusal_is_catchable_at_the_size_it_refuses(self) -> None:
        """A refusal past the sweep's bound, at the first arity that triggers it."""
        with pytest.raises(esolangs.GeneratorCapError, match="cost"):
            esolangs.generate("Polynomial", _big_table(11))

    def test_it_is_catchable_through_evaluate_too(self) -> None:
        """NoComment's leaked through ``evaluate`` identically."""
        with pytest.raises(esolangs.GeneratorCapError):
            esolangs.evaluate("Polynomial", _big_table(11))

    def test_nocomment_builds_at_the_arity_that_escaped(self) -> None:
        """The escape's subject is gone: n=12 is a template, not a refusal."""
        n = 12
        table = "".join(str(bin(r).count("1") % 2) for r in range(2**n))
        template = esolangs.generate("NoComment", table)
        assert template.inputs == 12

    @pytest.mark.slow
    @pytest.mark.weekly
    def test_nothing_escapes_the_contract_at_twelve_inputs(self) -> None:
        """A periodic table, so the generators that blow up stay small.

        73.6s, the most expensive test in the suite, so it runs weekly
        rather than on every ``test-full``; see the ``weekly`` marker.
        """
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

    def test_the_docstring_states_no_count(self) -> None:
        """It said "Five do" and six do; a tally in prose is a second copy."""
        assert esolangs.generate.__doc__ is not None
        assert "Five do" not in esolangs.generate.__doc__


class TestFactorHasNoDigitBudget:
    """Its refusal named ``max_digits``, a knob the public API never had.

    The knob and the budget are gone together: the integer is arbitrary
    precision on both sides, so the public API builds every table.
    """

    @pytest.mark.slow
    def test_the_arity_that_used_to_refuse_builds(self) -> None:
        """Dense n=13 was the 500000-digit refusal; it is 705048 digits now."""
        import random

        rng = random.Random(7)
        table = "".join(rng.choice("01") for _ in range(2**13))
        program = esolangs.generate("Factor", table)
        assert program.isdigit()
        assert len(program) > 500_000


class TestErrorsSurviveAProcessBoundary:
    """The library's commonest error could not come home from a worker."""

    def test_input_exhausted_round_trips(self) -> None:
        """It built its message in ``__init__``, so unpickling passed one arg.

        A worker raising it died, and the pool broke with
        ``BrokenProcessPool`` and no diagnostic -- for the error 43 of the
        52 stdin languages raise, in the parallel sweep this package is
        for.
        """
        import pickle

        program = esolangs.generate("brainfuck", "10010110")
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            esolangs.run("brainfuck", program, "1\n0\n", 10)
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
            lambda: esolangs.run("brainfuck", "+[]", "", 0.01),
            lambda: esolangs.run(
                "brainfuck", esolangs.generate("brainfuck", "10010110"), "1\n0\n", 10
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
        """It was the one exception in the package that was not ours.

        The package makes exactly one promise about errors -- that every
        deliberate failure derives from ``EsolangError`` -- and a sweep
        written to it crashed here.

        Driven through a stand-in rather than through a real language.  It
        used to be driven by Qoibl on a six-input table, which no longer
        recurses anywhere near the limit, and the alternative was a program
        big enough to still blow the stack -- roughly 90000 characters now
        -- which prices a promise about error *types* at minutes of
        execution.  What is under test is the wrapping.
        """

        def explode(*_args: object, **_kwargs: object) -> None:
            raise RecursionError("maximum recursion depth exceeded")

        monkeypatch.setattr(esolangs, "_run", explode)
        with pytest.raises(esolangs.EsolangError) as caught:
            esolangs.run("brainfuck", "+.", "")
        assert isinstance(caught.value, esolangs.InterpreterLimitError)
        assert "recursed deeper" in str(caught.value)
        assert "setrecursionlimit" in str(caught.value)

    @pytest.mark.slow
    def test_qoibl_no_longer_hits_the_wall(self) -> None:
        """The six-input table this class was built around now computes.

        Qoibl's tokenizer searched tokenizations with one Python frame per
        character -- 1241 of the 1315 frames a 3972-character program
        reached -- so the language was capped near 2800 characters by
        CPython rather than by anything Qoibl says.
        """
        assert esolangs.verify("Qoibl", self._parity(6), timeout=300)

    def test_it_is_a_halt_error(self) -> None:
        """The run ended abnormally, which is what that base means."""
        assert issubclass(esolangs.InterpreterLimitError, esolangs.HaltError)
        assert "InterpreterLimitError" in esolangs.__all__

    def test_it_is_not_a_generator_cap(self) -> None:
        """A cap declines to build; this built and could not be run."""
        assert not issubclass(
            esolangs.InterpreterLimitError, esolangs.GeneratorCapError
        )


class TestASuggestionIsWorthLessThanSilence:
    """0.6 offered ``Sophie`` for ``nope``.

    A wrong guess is worse than none: it sends the reader off to check a
    language they never meant.  0.65 is the lowest cutoff that suggests
    nothing for any of the junk below, and it rescues exactly as many real
    typos as 0.6 did -- 265 of 269 single-edit slips across the 59 names.
    0.7 starts costing rescues.

    The numbers are recomputed below rather than quoted, so the constant
    cannot drift away from the reason it has its value.
    """

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

    _JUNK = ("nope", "zzzz", "xyz", "qqqqqq", "hello", "python", "asdf", "foo")

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
        """The trade, recomputed: 0.6 costs junk and 0.7 costs rescues.

        Without this the constant is a number somebody once measured, and
        the next person to nudge it has nothing to nudge it against.
        """
        shipped = self._score(SUGGESTION_CUTOFF)
        assert shipped[2] == 0, "the shipped cutoff offers a guess for junk"
        # Lower: the same rescues, but junk comes back.  This is the
        # positive control -- without it the cutoff could be doing nothing.
        lower = self._score(0.6)
        assert lower[0] == shipped[0]
        assert lower[2] > 0
        # Higher: no junk either, but it starts costing real rescues.
        assert self._score(0.7)[0] < shipped[0]

    @pytest.mark.parametrize(
        "word", ["nope", "zzzz", "xyz", "qqqqqq", "hello", "python", "asdf", "foo"]
    )
    def test_a_word_that_is_not_close_gets_no_guess(self, word: str) -> None:
        """It gets the command that lists them, which is the honest answer."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe(word)
        assert "did you mean" not in str(caught.value)
        assert "`esolangs list` shows all of them" in str(caught.value)

    @pytest.mark.parametrize(
        ("typo", "wanted"),
        [
            ("Brainfck", "brainfuck"),
            ("brainfuk", "brainfuck"),
            ("Streetcod", "Streetcode"),
            ("Minifuk", "Minifuck"),
            ("Sofie", "Sophie"),
            ("Sufolk", "Suffolk"),
        ],
    )
    def test_a_real_typo_is_still_rescued(self, typo: str, wanted: str) -> None:
        """The half of the trade that raising a cutoff can quietly cost."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe(typo)
        assert wanted in str(caught.value)

    def test_the_cli_shares_the_number(self) -> None:
        """Its docstring promised the same cutoff while keeping its own copy."""
        assert cli._did_you_mean("nope", esolangs.list_languages()) == ""  # noqa: SLF001
        assert "--width" in cli._did_you_mean("--wdith", ["--width", "--bits"])  # noqa: SLF001


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


class TestUnknownLanguageAlwaysOffersANextStep:
    """A near miss suggested; a far one was a dead end."""

    def test_a_far_miss_names_the_listing_command(self) -> None:
        """Someone misremembering a name has nothing to be suggested."""
        with pytest.raises(esolangs.UnknownLanguageError, match="esolangs list"):
            esolangs.describe("Malbolge")

    def test_a_near_miss_still_suggests(self) -> None:
        """The better hint must win where there is one."""
        with pytest.raises(esolangs.UnknownLanguageError, match="did you mean"):
            esolangs.describe("Brainfck")


class TestATableLengthNamesTheNearestLegalOnes:
    """The rule without the arithmetic, on the likeliest first error."""

    @pytest.mark.parametrize(
        ("table", "expected"),
        [
            ("0" * 3, "3 is between 2 (1 input) and 4 (2 inputs)"),
            ("0" * 6, "6 is between 4 (2 inputs) and 8 (3 inputs)"),
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
    """Almost every name already tolerated one, and the one that did not.

    ``canonical_id`` collapses runs of non-alphanumerics and strips the
    result, so a stray space fell out for almost every name.  The override
    table is an exact lookup, though, so a name needing an override
    broke -- ``"CV(N)(C) "`` came back as
    ``did you mean CV(N)(C)?``, an invisible diff with no way forward.
    """

    @pytest.mark.parametrize("pad", [" {}", "{} ", " {} ", "\t{}\n"])
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
    """Four entry points filed it as a *program* fault, and one did not.

    ``ProgramError`` says "a program could not be loaded: it is malformed
    for its language".  The stdin is not the program.  Both derive from
    ``EsolangError`` so a generic handler always worked, but the taxonomy
    is the thing this package sells, and here it disagreed with itself.
    """

    @pytest.mark.parametrize(
        "call",
        [
            lambda: esolangs.run("brainfuck", ",.", b"0\n"),
            lambda: esolangs.check_program("brainfuck", ",.", b"0\n"),
            lambda: esolangs.make_vm("brainfuck", ",.", b"0\n"),
            lambda: esolangs.make_debugger("brainfuck", ",.", b"0\n"),
            lambda: esolangs.check_stdin("brainfuck", b"0\n"),
        ],
    )
    def test_every_entry_point_agrees(self, call: object) -> None:
        """One fault, one class -- ``except ArgumentError`` has to cover all five."""
        with pytest.raises(esolangs.ArgumentError, match="stdin must be a string"):
            call()  # type: ignore[operator]

    def test_a_bad_program_is_still_a_program_error(self) -> None:
        """The change must not blur the distinction the other way."""
        with pytest.raises(esolangs.ProgramError, match="program must be a string"):
            esolangs.run("brainfuck", 42, "")  # type: ignore[arg-type]


class TestBoolsAreRefusedForAStatedReason:
    """ "must be 0 or 1" reads as wrong when you passed True, which is 1."""

    def test_the_message_says_why(self) -> None:
        """The exclusion is deliberate and the reason is a past wrong answer."""
        with pytest.raises(esolangs.ArgumentError, match="True == 1"):
            esolangs.encode_inputs("brainfuck", [True, False])


class TestTheWarningHasItsOwnClass:
    """So a sweep can escalate exactly these to errors."""

    def test_it_is_a_user_warning_subclass(self) -> None:
        """Existing ``UserWarning`` filters must keep working."""
        assert issubclass(esolangs.InputMismatchWarning, UserWarning)
        assert "InputMismatchWarning" in esolangs.__all__

    def test_run_raises_it_by_class(self) -> None:
        """Which is what makes ``filterwarnings("error", ...)`` targeted."""
        program = esolangs.generate("brainfuck", "00011011")
        with pytest.warns(esolangs.InputMismatchWarning):
            esolangs.run("brainfuck", program, "1\n1\n0\n0\n1\n1\n", 10)


class TestAFailedRowSaysWhichRow:
    """``execution exceeded the 0.2-second timeout`` and nothing else.

    On a 1024-row table "row 0 is pathological" and "row 900 is" are
    different problems, and they had the same message.  A note carries the
    row rather than a longer message because the exceptions here do not
    share a constructor -- ``InputExhaustedError`` takes two counts and
    builds its own text -- so re-raising with more words would mean knowing
    every class that can arrive.
    """

    def test_the_note_names_the_row_and_the_inputs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failure forced at a chosen row, since a real one lands on row 0.

        A timeout small enough to bite bites the first row, which is the
        case that never needed the note.
        """
        real_run = esolangs.run

        def fail_on_the_sixth(
            language: str, program: object, stdin: str = "", timeout: object = None
        ) -> str:
            if stdin == "1\n0\n1\n":  # row 5 of an eight-row table
                raise esolangs.ExecutionTimeoutError("execution exceeded the bound")
            return real_run(language, program, stdin, timeout)  # type: ignore[arg-type]

        monkeypatch.setattr(esolangs, "run", fail_on_the_sixth)
        with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
            esolangs.evaluate("brainfuck", "01101001", timeout=10)
        note = "\n".join(getattr(caught.value, "__notes__", []))
        assert "row 5 of 8" in note
        assert "inputs 101" in note
        assert "after 5 rows" in note
        assert "01101" in note  # the answers that did come back

    def test_a_real_timeout_carries_one_too(self) -> None:
        """Not only the stand-in: the path a caller actually hits.

        The bound is set from the measurement, not from what used to be
        slow: a parity n=7 Circuit Diagram row ran for over a second when
        the first bound was chosen, 0.306 when it was cut to a twentieth,
        and now steps inside 0.05 alone, so that bound passed on nothing.
        It times out at 0.02 and below; 0.005 leaves a 4x margin.
        """
        table = "".join(str(bin(r).count("1") & 1) for r in range(128))
        with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
            esolangs.evaluate("Circuit Diagram", table, timeout=0.005)
        note = "\n".join(getattr(caught.value, "__notes__", []))
        assert "row 0 of 128" in note

    def test_a_clean_evaluate_adds_nothing(self) -> None:
        """A note is for a failure; a success must not grow one."""
        assert esolangs.evaluate("brainfuck", "0110") == "0110"

    def test_the_note_survives_the_exception_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reason it is a note: the class and its arguments are untouched.

        ``InputExhaustedError`` builds its message from two counts, so a
        re-raise that rewrote the text would have to reconstruct it.
        """
        real_run = esolangs.run

        def exhaust(
            language: str, program: object, stdin: str = "", timeout: object = None
        ) -> str:
            if stdin == "1\n1\n":
                raise esolangs.InputExhaustedError(2, 2)
            return real_run(language, program, stdin, timeout)  # type: ignore[arg-type]

        monkeypatch.setattr(esolangs, "run", exhaust)
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            esolangs.evaluate("brainfuck", "0110", timeout=10)
        assert caught.value.reads == 2
        assert caught.value.supplied == 2
        assert "read past the end of input" in str(caught.value)
        assert "row 3 of 4" in "\n".join(getattr(caught.value, "__notes__", []))


class TestReadAnswerExplainsInWords:
    """The regex was the whole explanation for the two pattern languages.

    Right for a maintainer, nothing at all for a reader wondering where the
    answer was meant to be -- and the plain-language note already existed on
    ``describe``.  The note leads now and the pattern follows in brackets,
    so neither reader loses.
    """

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
        """The general claim, not the two cases that prompted it.

        Writing this is what caught the narrow first fix: only the two
        *pattern* languages got the note, and Back, Minsky Swap and
        LaserFuck dump their state while being read by last character --
        so they got "as the last character", a true account of the
        mechanism and no account of where the answer lives.
        """
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["answer_mode"] != "dump":
                continue
            with pytest.raises(esolangs.ProgramError) as caught:
                esolangs.read_answer(name, "garbage")
            note = facts["answer_convention"]
            assert note is None or str(note) in str(caught.value), name


class TestATimeoutCannotKillTheProcess:
    """The long-running defect, and the second thing it turned into.

    A sub-millisecond ``timeout`` killed the interpreter outright about one
    run in three: no traceback, no exception, exit 142, which is SIGALRM's
    default disposition doing what it does.  Two attempts to close the race
    that delivers it failed, and the third worked by never restoring
    ``SIG_DFL`` -- a handler that does nothing cannot kill anything.

    That fix was wrong in a quieter way, and a later reader found it: the
    no-op stayed installed, so every alarm the *caller* set afterwards was
    swallowed, and a pending one was cancelled outright.  Taking someone
    else's signals is worse than a rare death at a bound nobody uses.

    So the disposition is restored exactly, the pending alarm is put back,
    and the bound that re-opens the race is refused instead.  Measured, with
    ``SIG_DFL`` genuinely restored: at 100 microseconds 19 of 20 processes
    hammering it died; at 1 millisecond, none in 4000 runs.  The floor is
    that measurement, not a taste.
    """

    def test_a_bound_too_short_to_service_is_refused(self) -> None:
        """The floor, which is what makes restoring the disposition safe."""
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            esolangs.run("brainfuck", "+.", "", 0.0001)

    def test_the_caller_gets_their_disposition_back(self) -> None:
        """Including ``SIG_DFL``, which the previous fix kept for itself."""
        import signal

        previous = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        try:
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
            esolangs.run("brainfuck", program, stdin, 5)
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
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
            esolangs.run("brainfuck", program, stdin, 5)
            assert signal.getsignal(signal.SIGALRM) is _mine
        finally:
            signal.signal(signal.SIGALRM, previous)

    def test_the_timer_is_always_disarmed(self) -> None:
        """A timer left armed is the next run's stray alarm."""
        import signal

        program = esolangs.generate("brainfuck", "0110")
        stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
        for bound in (10, 0.001):
            with contextlib.suppress(esolangs.ExecutionTimeoutError):
                esolangs.run("brainfuck", program, stdin, bound)
            assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)

    @pytest.mark.slow
    def test_many_runs_at_the_floor_neither_die_nor_leak(self) -> None:
        """The stress the floor was chosen against, in process.

        A death here would take the whole test session with it, which is
        exactly the failure being guarded and makes it unmissable.
        """
        import signal

        program = esolangs.generate("brainfuck", "0110")
        stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
        previous = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        try:
            for _ in range(400):
                with contextlib.suppress(esolangs.ExecutionTimeoutError):
                    esolangs.run("brainfuck", program, stdin, 0.001)
                assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
                assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
        finally:
            signal.signal(signal.SIGALRM, previous)


class TestTheCallersSignalsAreTheirOwn:
    """The fix for the death took the caller's SIGALRM hostage."""

    def test_a_pending_alarm_survives_a_timed_run(self) -> None:
        """Arming ours cancelled theirs, and nothing put it back."""
        import signal

        previous = signal.signal(signal.SIGALRM, lambda *_a: None)
        try:
            signal.alarm(30)
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
            esolangs.run("brainfuck", program, stdin, 5)
            remaining = signal.alarm(0)
            assert remaining > 0, "the caller's alarm was cancelled"
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    def test_the_default_disposition_is_restored(self) -> None:
        """It was left as a no-op, which swallowed the caller's later alarms.

        Closing the death by never restoring ``SIG_DFL`` traded one bug for
        a quieter one: every alarm the caller set afterwards was ignored.
        """
        import signal

        previous = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        try:
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
            esolangs.run("brainfuck", program, stdin, 5)
            assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
        finally:
            signal.signal(signal.SIGALRM, previous)

    def test_a_bound_too_short_to_service_is_refused(self) -> None:
        """Measured: at 100us, 19 of 20 processes died; at 1ms, none of 4000."""
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            esolangs.run("brainfuck", "+.", "", 0.0001)

    def test_the_floor_applies_to_evaluate_too(self) -> None:
        """Its termination path never reaches ``run``, so it checked nothing.

        The same bound raised for the languages that halt and was silently
        read as "diverges" for the termination-answer ones, which returned a
        confident ``1111`` for XOR.
        """
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            esolangs.evaluate("123", "0110", 1e-06)


class TestEvaluateCanRunOffTheMainThread:
    """The wall-clock guard is a signal, and there was no way to opt out."""

    def test_an_explicit_none_means_unbounded(self) -> None:
        """As it does in ``run``; here the same word meant "use the default"."""
        import concurrent.futures as cf

        names = ["brainfuck", "Suffolk", "123", "A Painter Ant", "Fargo"]
        with cf.ThreadPoolExecutor(4) as pool:
            got = list(pool.map(lambda n: esolangs.verify(n, "0110", None), names))
        assert all(got), dict(zip(names, got, strict=True))

    def test_omitting_it_still_takes_the_defaults(self) -> None:
        """A sentinel, so adding the escape hatch broke no existing caller."""
        assert esolangs.evaluate("123", "0110") == "0110"


class TestDivergenceIsProvenNotWaitedOut:
    """A repeated state settles it exactly, and in milliseconds."""

    @pytest.mark.parametrize("name", ["123", "ArrowQueue"])
    @pytest.mark.parametrize("table", ["0110", "00011011"])
    def test_the_proven_answer_is_the_table(self, name: str, table: str) -> None:
        """The answers must be the ones the clock used to give, exactly."""
        assert esolangs.evaluate(name, table) == table

    def test_it_no_longer_costs_a_timeout_per_row(self) -> None:
        """It was five seconds per 1-row: twenty seconds for this call.

        Timed rather than asserted about, because "it is faster now" is the
        kind of claim that quietly stops being true.  The bound is loose --
        it is checking that the *clock* is no longer in the loop, not
        holding anything to a schedule.
        """
        import time

        start = time.monotonic()
        esolangs.evaluate("123", "0110")
        assert time.monotonic() - start < 5.0


class TestTheTerminationProofFallsBackToTheClock:
    """A cycle is not the only way to diverge; growth never repeats a state."""

    def test_the_proof_beats_even_a_millisecond_bound(self) -> None:
        """Which is the measurement, and also why the clock arm is untested.

        I expected a one-millisecond bound to force the fallback and assert
        the old "diverges" answer.  It does not: these programs revisit a
        state inside a hundred steps, so the cycle is proven before the
        clock can fire, and the right table comes back anyway.  The
        fallback is real -- unbounded growth never repeats a state -- but
        no table in this suite reaches it.
        """
        assert esolangs.evaluate("123", "0110", 0.001) == "0110"

    def test_the_answers_match_what_the_clock_used_to_give(self) -> None:
        """The proof must not have changed any verdict, only the cost."""
        for name in ("123", "ArrowQueue"):
            assert esolangs.evaluate(name, "0110") == "0110"


class TestEvaluateNoLongerClaimsToPayTheTimeout:
    """Its docstring and ``Debugger.snapshot``'s disagreed about the same thing."""

    def test_a_termination_table_returns_far_inside_the_bound(self) -> None:
        """Five seconds per 1-row would be twenty for this table."""
        import time

        start = time.monotonic()
        assert esolangs.evaluate("123", "0110") == "0110"
        assert time.monotonic() - start < 2.0

    def test_the_docstring_says_the_proof_is_the_mechanism(self) -> None:
        """Prose, checked, because it was prose that had gone stale."""
        doc = esolangs.evaluate.__doc__
        assert doc is not None
        # Not a search for the old phrase: the correction quotes it in
        # order to retract it, so an absence test fails on the fix.  What
        # has to be there is the mechanism and the denial.
        assert "repeated machine state" in doc
        assert "do not pay it" in doc
