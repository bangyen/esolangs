"""Validation and warnings for stdin passed through the public API."""

import warnings

import esolangs
from esolangs.registry import LANGUAGES
from tests.support.pick import languages
from tests.support.reference import REFERENCE


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
