"""Clockwise through the shared API, CLI and machinery."""

import esolangs
from esolangs import run


def test_clockwise_is_not_marked_because_it_never_reads_past_an_end() -> None:
    """Its underfed input is a shorter one-line string: no EOF happens."""
    assert esolangs.describe("Clockwise").eof_is_a_value is False
    program = esolangs.generate("Clockwise", "10010110")
    short = esolangs.encode_inputs("Clockwise", [1, 0])
    output = run(
        "Clockwise",
        program,
        stdin=short,
        limits=esolangs.ExecutionLimits(execution_timeout=10),
    ).output
    esolangs.read_answer("Clockwise", output)


def test_the_input_is_a_bit_string() -> None:
    assert esolangs.encode_inputs("Clockwise", [1, 1, 1, 1]) == "1111"


def test_inputs_are_seven_bits_per_character() -> None:
    assert esolangs.describe("Clockwise").input_shape == "char_stream_cyclic"
    assert esolangs.encode_inputs("Clockwise", [1, 0, 1]) == "101"
