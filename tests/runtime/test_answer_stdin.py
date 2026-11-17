"""Native stdin consumption through the public API."""

import esolangs
from tests.support.reference import REFERENCE


class TestNativeInputConsumption:
    def test_surplus_input_preserves_the_answer(self) -> None:
        """Six lines into a three-input program answered the first three."""
        program = esolangs.generate(REFERENCE, "00010111")
        answer = esolangs.run(
            REFERENCE,
            program,
            stdin="110011",
            limits=esolangs.ExecutionLimits(execution_timeout=10),
        ).output
        assert answer == "1"

    def test_unread_input_does_not_change_output(self) -> None:
        """Reading none of what it was given is not an arity mistake."""

        assert (
            esolangs.run(
                REFERENCE,
                "+.",
                stdin="1\n0\n",
                limits=esolangs.ExecutionLimits(execution_timeout=10),
            ).output
            == "\x01"
        )
