"""Validation hints give executable examples and preserve diagnostics."""

import pytest

import esolangs
from esolangs._validate import check_bits, check_scale, check_timeout, check_whole
from esolangs.interpreters.source_hints import error_text


@pytest.mark.parametrize("table", ["", "0120", "010", "1"])
def test_truth_table_hint(table: str) -> None:
    with pytest.raises(esolangs.TruthTableError) as caught:
        esolangs.generate("brainfuck", table)
    assert caught.value.__notes__[0].startswith("hint:")
    assert error_text(caught.value).startswith(str(caught.value) + "\nhint:")


@pytest.mark.parametrize("table", ["0110", "00", "11"])
def test_truth_table_examples_execute(table: str) -> None:
    program = esolangs.generate("brainfuck", table)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = [(row >> shift) & 1 for shift in reversed(range(inputs))]
        output = esolangs.run(
            "brainfuck", program, stdin=esolangs.encode_inputs("brainfuck", bits)
        )
        assert esolangs.read_answer("brainfuck", output) == expected


def test_template_hint_and_example() -> None:
    template = esolangs.generate("Minifuck", "0110")
    with pytest.raises(esolangs.TemplateError) as caught:
        esolangs.instantiate("Minifuck", template, [0])
    assert "exactly 2 integer bits" in caught.value.__notes__[0]
    program = esolangs.instantiate("Minifuck", template, [0, 1])
    assert esolangs.read_answer("Minifuck", esolangs.run("Minifuck", program)) == "1"


def test_option_hints_preserve_messages() -> None:
    with pytest.raises(esolangs.ArgumentError) as caught:
        check_whole(-1, "max_steps")
    assert str(caught.value) == "max_steps must be a non-negative integer, got -1"
    assert "max_steps=0" in caught.value.__notes__[0]
    for check, value, example in (
        (check_timeout, 0, "timeout=5.0"),
        (check_scale, 0, "scale=1"),
        (check_bits, [], "[0, 1]"),
    ):
        with pytest.raises(esolangs.ArgumentError) as caught:
            check(value)
        assert example in caught.value.__notes__[0]
    check_timeout(5.0)
    assert check_whole(0, "max_steps") == 0
    assert check_scale(1) == 1
    assert check_bits([0, 1]) == [0, 1]


def test_generator_cap_hint() -> None:
    with pytest.raises(esolangs.GeneratorCapError) as caught:
        esolangs.generate("Befunge", "0010" * (1 << 12))
    assert "fixed 80x25 grid" in caught.value.__notes__[0]
