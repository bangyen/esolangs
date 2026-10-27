"""Taglate through the shared API, CLI and machinery."""

import pytest

import esolangs
from tests.runtime.test_input_encoding import XOR


class TestAnswerMode:
    """The structured counterpart to the ``answer_convention`` prose."""

    def test_every_language_declares_one_of_three_modes(self) -> None:
        modes = {esolangs.describe(n)["answer_mode"] for n in esolangs.list_languages()}
        assert modes == {"output", "termination", "dump"}

    @pytest.mark.slow
    def test_output_mode_means_the_printed_answer_is_the_table(self) -> None:
        """The classification is held to the interpreters, not just asserted."""
        wrong = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["boolean_generator"]:
                continue
            if facts["parameterized"] or facts["answer_mode"] != "output":
                continue
            program = esolangs.generate(name, XOR)
            got = "".join(
                esolangs.run(
                    name,
                    program,
                    stdin=esolangs.encode_inputs(name, [(row >> 1) & 1, row & 1]),
                    timeout=30,
                ).strip()[-1:]
                or "?"
                for row in range(4)
            )
            if got != XOR:
                wrong.append((name, got))
        assert wrong == []


def test_odd_arities_take_no_padding() -> None:
    assert esolangs.encode_inputs("Taglate", [1, 0, 1]) == "101"
    assert esolangs.encode_inputs("Taglate", [1, 0]) == "10"
