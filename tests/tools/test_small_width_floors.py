"""Execute the narrow fresh-cell and single-character constructions."""

import pytest

import esolangs
from esolangs.exceptions import TemplateError


@pytest.mark.medium
def test_false_single_character_floor_executes_every_small_table() -> None:
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            program = esolangs.generate("FALSE", table, 1)
            assert max(map(len, program.splitlines())) == 1
            for row, expected in enumerate(table):
                stdin = "\n".join(format(row, f"0{n}b")) + "\n"
                assert (
                    esolangs.run_bounded("FALSE", program, stdin, max_steps=100_000)
                    == expected
                )


@pytest.mark.medium
@pytest.mark.parametrize("language", ["BF-PDA", "FALSE", "Home Row", "RAM0"])
def test_narrow_small_tokens_keep_larger_input_order(language: str) -> None:
    for n in range(4, 7):
        table = "".join(
            str((row * 17 + row // 3).bit_count() % 2) for row in range(1 << n)
        )
        program = esolangs.generate(language, table, 1)
        if language != "RAM0":
            assert max(map(len, program.splitlines())) == 1
        for row, expected in enumerate(table):
            bits = [int(char) for char in format(row, f"0{n}b")]
            code = (
                esolangs.instantiate(language, program, bits)
                if language != "FALSE"
                else program
            )
            stdin = "\n".join(map(str, bits)) + "\n" if language == "FALSE" else ""
            output = esolangs.run_bounded(language, code, stdin, max_steps=100_000)
            assert (
                output.startswith(f"z: {expected}\n")
                if language == "RAM0"
                else output == expected
            )


def test_factored_setters_reduce_public_template_floors() -> None:
    for name, floor in (("BF-PDA", 1), ("Home Row", 1), ("RAM0", 2)):
        template = esolangs.generate(name, "0110", 1)
        assert max(map(len, template.splitlines())) == floor
        for row in range(4):
            bits = [int(char) for char in format(row, "02b")]
            code = esolangs.instantiate(name, template, bits, truth_table="0110")
            plain = esolangs.instantiate(name, str(template), bits, truth_table="0110")
            assert code == plain
            with pytest.raises(TemplateError, match="template"):
                esolangs.instantiate(name, str(template), bits, truth_table="0001")
