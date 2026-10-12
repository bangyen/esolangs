"""Unary through the shared API and generator contract."""

import esolangs


def test_unary_generator_declares_byte_inputs_and_termination_answers() -> None:
    description = esolangs.describe("Unary")
    assert description["input_encoding"] == ("\x00", "\xff")
    assert description["answer_mode"] == "termination"
    assert esolangs.encode_inputs("Unary", (0, 1)) == "\x00\xff"
    assert esolangs.generate("Unary", "01").count("0") == 887
