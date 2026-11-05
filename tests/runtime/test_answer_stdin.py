"""Native stdin consumption through the public API."""

import esolangs
from esolangs import compat
from esolangs.registry import LANGUAGES
from tests.support.pick import languages
from tests.support.reference import REFERENCE


class TestNativeInputConsumption:
    def test_surplus_input_preserves_the_answer(self) -> None:
        """Six lines into a three-input program answered the first three."""
        program = compat.generate(REFERENCE, "00010111")
        answer = esolangs.run(REFERENCE, program, stdin="110011", timeout=10).output
        assert answer == "1"

    def test_unread_input_does_not_change_output(self) -> None:
        """Reading none of what it was given is not an arity mistake."""

        assert (
            esolangs.run(REFERENCE, "+.", stdin="1\n0\n", timeout=10).output == "\x01"
        )

    def test_underfed_programs_use_the_native_eof_value(self) -> None:
        carry_on = languages(
            eof_is_a_value=True, input_shape="char_stream", parameterized=False
        )
        # A language that refuses instead is ``test_debug``'s exception.
        for name in [n for n in carry_on if not LANGUAGES[n].runtime.underfed_raises][
            :3
        ]:
            program = compat.generate(name, "10010110")
            short = esolangs.encode_inputs(name, [1, 0])
            output = esolangs.run(name, program, stdin=short, timeout=10).output
            assert esolangs.read_answer(name, output) in {"0", "1"}
