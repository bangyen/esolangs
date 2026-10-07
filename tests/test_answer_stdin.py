"""Validation and warnings for stdin passed through the public API."""

import warnings

import pytest

import esolangs
from tests.stdin_check import _check_stdin

#: ``_check_stdin`` arguments it refuses, and what the refusal says.
_REFUSED = {
    # 0/1 lines into Grapheme, the sharpest edge in the package.
    "it_catches_the_wrong_alphabet": (("Grapheme", "0\n1\n"), "spells its bits"),
    # Six lines into a three-input program answered the first three.
    "it_catches_a_surplus_line": (
        ("brainfuck", "110011", "00010111"),
        "reads 3 characters",
    ),
    "it_catches_a_missing_line": (
        ("brainfuck", "10", "00010111"),
        "reads 3 characters",
    ),
    # What `run` could not check, because it does not know the arity.
    "it_catches_an_out_of_range_row_index": (
        ("Fargo", "8\n", "00010111"),
        "out of range",
    ),
    # ``"\u00b2".isdigit()`` is true, but ``int`` rejects it.
    "a_superscript_digit_is_refused_not_int_parsed": (
        ("Fargo", "\u00b2", "01"),
        "decimal row index",
    ),
    # brainfuck reads the space as a character, so it stays refused.
    "whitespace_still_counts_for_a_reader_that_reads_it": (
        ("brainfuck", "0 1", "0110"),
        "unexpected character",
    ),
    # A template language reads none, so there is nothing to judge.
    "it_refuses_a_language_with_no_stdin": (("Minifuck", "1\n0\n"), "reads no stdin"),
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

    def test_it_catches_taglates_pad(self) -> None:
        """Its odd input count costs an extra line, and the shape says so."""
        _check_stdin(
            "Taglate",
            esolangs.encode_inputs("Taglate", [1, 0, 1], truth_table="00010111"),
            "00010111",
        )
        with pytest.raises(esolangs.ArgumentError):
            _check_stdin("Taglate", "1\n0\n1\n", "00010111")

    def test_a_one_line_language_has_its_bits_counted(self) -> None:
        """Clockwise's underfeed is a shorter string, not a missing line."""
        _check_stdin("Clockwise", "101", "00010111")
        with pytest.raises(esolangs.ArgumentError, match="reads 3 characters"):
            _check_stdin("Clockwise", "10", "00010111")


class TestRunSaysWhenStdinLooksWrong:
    """Silence was indistinguishable from correctness, from Python."""

    def test_a_surplus_line_is_warned_about(self) -> None:
        """Six lines into a three-input program answered the first three."""
        program = esolangs.generate("brainfuck", "00010111")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            answer = esolangs.run("brainfuck", program, stdin="110011", timeout=10)
        # A warning, not a refusal: the run still happened and still answered.
        assert answer == "1"

    def test_the_wrong_alphabet_is_warned_about(self) -> None:
        """The same judgement `check_stdin` raises, rendered as advice."""
        program = esolangs.generate("Grapheme", "0110")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            esolangs.run("Grapheme", program, stdin="0\n1\n", timeout=10)

    # Generates and runs one program per language, like the wrap test above.
    @pytest.mark.medium
    def test_the_documented_path_is_silent(self) -> None:
        """A warning that fires on correct input is worse than none."""
        import warnings

        noisy = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["boolean_generator"] or facts["parameterized"]:
                continue
            program = esolangs.generate(name, "0110")
            if facts["answer_mode"] == "termination":
                continue
            stdin = esolangs.encode_inputs(name, [1, 0], truth_table="0110")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                esolangs.run(name, program, stdin=stdin, timeout=20)
            if caught:
                noisy.append(f"{name}: {caught[0].message}")
        assert not noisy, "\n".join(noisy)

    def test_a_program_that_reads_nothing_is_not_warned_about(self) -> None:
        """Reading none of what it was given is not an arity mistake."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            esolangs.run("brainfuck", "+.", stdin="1\n0\n", timeout=10)
        assert not [c for c in caught if "lines supplied" in str(c.message)]

    def test_taking_a_value_from_past_the_end_is_warned_about(self) -> None:
        """The six that answer an underfed program now say they did."""
        for name in ("Circuit Diagram", "Flowchart", "S*bleq"):
            program = esolangs.generate(name, "10010110")
            short = esolangs.encode_inputs(name, [1, 0])
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                esolangs.run(name, program, stdin=short, timeout=10)

    def test_forgetting_stdin_entirely_is_warned_about(self) -> None:
        """Fargo answered row 0 -- the starkest case, since nothing was fed."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            esolangs.run(
                "Fargo", esolangs.generate("Fargo", "10010110"), stdin="", timeout=10
            )

    def test_a_language_whose_documented_stop_is_eof_is_not_warned_about(
        self,
    ) -> None:
        """Suffolk's programs end *by* running out of input."""
        import warnings

        program = esolangs.generate("Suffolk", "0110")
        stdin = esolangs.encode_inputs("Suffolk", [1, 0], truth_table="0110")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert esolangs.run("Suffolk", program, stdin=stdin, timeout=20) == "1"
        assert not caught


@pytest.mark.parametrize("language", ["Grapheme", "Line", "Piet"])
def test_numeric_or_line_input_count_is_checked_for_text_and_raster(
    language: str,
) -> None:
    facts = esolangs.describe(language)
    stdin = facts["input_encoding"][0] + "\n"
    with pytest.raises(esolangs.ArgumentError, match="reads 2 line"):
        _check_stdin(language, stdin, "0110")
