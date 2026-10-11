"""Validation and warnings for stdin passed through the public API."""

import warnings

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from tests.api.test_language_coupling import REFERENCE
from tests.support.pick import first, languages, one, one_where
from tests.support.stdin_check import _check_stdin

#: A line-per-bit reader whose bits are not spelled ``0`` and ``1``, if any.
_SPELLED = one_where(
    lambda d: d["input_encoding"] != ("0", "1"),
    reads_input=True,
    input_shape="line_per_bit",
)

#: ``_check_stdin`` arguments it refuses, and what the refusal says.
_REFUSED = {
    # 0/1 lines into a language spelling its bits otherwise: the sharpest edge.
    **dict.fromkeys(
        ["it_catches_the_wrong_alphabet"] * len(_SPELLED),
        ((*_SPELLED, "0\n1\n"), "spells its bits"),
    ),
    # Six lines into a three-input program answered the first three.
    "it_catches_a_surplus_line": (
        (REFERENCE, "110011", "00010111"),
        "reads 3 characters",
    ),
    "it_catches_a_missing_line": (
        (REFERENCE, "10", "00010111"),
        "reads 3 characters",
    ),
    **{
        key: case
        for row_index in one(input_shape="row_index")
        for key, case in {
            # What `run` could not check, because it does not know the arity.
            "it_catches_an_out_of_range_row_index": (
                (row_index, "8\n", "00010111"),
                "out of range",
            ),
            # ``"\u00b2".isdigit()`` is true, but ``int`` rejects it.
            "a_superscript_digit_is_refused_not_int_parsed": (
                (row_index, "\u00b2", "01"),
                "decimal row index",
            ),
        }.items()
    },
    # brainfuck reads the space as a character, so it stays refused.
    "whitespace_still_counts_for_a_reader_that_reads_it": (
        (REFERENCE, "0 1", "0110"),
        "unexpected character",
    ),
    # A template language reads none, so there is nothing to judge.
    "it_refuses_a_language_with_no_stdin": (
        (first(reads_input=False), "1\n0\n"),
        "reads no stdin",
    ),
}


class TestTheStdinJudgeIsReachableFromPython:
    """The one place the API was weaker than the command line."""

    def test_it_accepts_what_encode_inputs_builds(self) -> None:
        """The check must never fire on this package's own encoding."""
        wrong = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["reads_input"]:
                continue
            for table, bits in (("0110", [1, 0]), ("00010111", [1, 0, 1])):
                stdin = esolangs.encode_inputs(name, bits, truth_table=table)
                try:
                    _check_stdin(name, stdin, table)
                except esolangs.EsolangError as exc:
                    wrong.append(f"{name} n={len(bits)}: {exc}")
        assert not wrong, "\n".join(wrong)

    @pytest.mark.parametrize("case", _REFUSED.values(), ids=list(_REFUSED))
    def test_it_refuses(self, case: tuple[tuple[str, ...], str]) -> None:
        args, match = case
        with pytest.raises(esolangs.ArgumentError, match=match):
            _check_stdin(*args)


class TestRunSaysWhenStdinLooksWrong:
    """Silence was indistinguishable from correctness, from Python."""

    def test_a_surplus_line_is_warned_about(self) -> None:
        """Six lines into a three-input program answered the first three."""
        program = esolangs.generate(REFERENCE, "00010111")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            answer = esolangs.run(REFERENCE, program, stdin="110011", timeout=10)
        # A warning, not a refusal: the run still happened and still answered.
        assert answer == "1"

    def test_a_program_that_reads_nothing_is_not_warned_about(self) -> None:
        """Reading none of what it was given is not an arity mistake."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            esolangs.run(REFERENCE, "+.", stdin="1\n0\n", timeout=10)
        assert not [c for c in caught if "lines supplied" in str(c.message)]

    def test_taking_a_value_from_past_the_end_is_warned_about(self) -> None:
        """The six that answer an underfed program now say they did."""
        carry_on = languages(
            eof_is_a_value=True, input_shape="char_stream", parameterized=False
        )
        # A language that refuses instead is ``test_debug``'s exception.
        for name in [n for n in carry_on if not LANGUAGES[n].underfed_raises][:3]:
            program = esolangs.generate(name, "10010110")
            short = esolangs.encode_inputs(name, [1, 0])
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                esolangs.run(name, program, stdin=short, timeout=10)


@pytest.mark.parametrize(
    "language",
    [*_SPELLED, *languages(source_kind="raster", input_shape="line_per_bit")],
)
def test_numeric_or_line_input_count_is_checked_for_text_and_raster(
    language: str,
) -> None:
    facts = esolangs.describe(language)
    stdin = facts["input_encoding"][0] + "\n"
    with pytest.raises(esolangs.ArgumentError, match="reads 2 line"):
        _check_stdin(language, stdin, "0110")
