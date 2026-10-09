"""Taglate through the shared API, CLI and machinery."""

import pytest

import esolangs
from tests.test_input_encoding import XOR


class TestAnswerMode:
    """The structured counterpart to the ``answer_convention`` prose."""

    def test_every_language_declares_one_of_three_modes(self) -> None:
        modes = {esolangs.describe(n)["answer_mode"] for n in esolangs.list_languages()}
        assert modes == {"output", "termination", "dump"}

    def test_taglates_shape_names_its_padding(self) -> None:
        """Plain ``line_per_bit`` hid the pad digit its n=3 program needs."""
        assert esolangs.describe("Taglate")["input_shape"] == "char_stream_padded"

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
