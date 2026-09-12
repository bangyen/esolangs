r"""The README's inline Sophie program is executed, not just displayed."""

import pathlib
import re

from esolangs import generate, run

_README = pathlib.Path(__file__).resolve().parents[1] / "README.md"

_LANGUAGE = "Sophie"
_TABLE = "0110"  # XOR.


def _readme_program() -> str:
    r"""Return the first fenced block under the Examples heading."""
    text = _README.read_text(encoding="utf-8")
    body = text[text.index("## Examples") :]
    match = re.search(r"```\n(.*?)\n```", body, re.DOTALL)
    assert match is not None, "no fenced program under ## Examples"
    return match.group(1)


def test_readme_program_is_what_the_generator_emits() -> None:
    assert _readme_program() == generate(_LANGUAGE, _TABLE)


def test_readme_program_computes_xor_on_every_row() -> None:
    r"""All four rows, not just one: a program that printed a constant."""
    program = _readme_program()
    for row, expected in enumerate(_TABLE):
        stdin = "".join(f"{bit}\n" for bit in format(row, "02b"))
        assert run(_LANGUAGE, program, stdin) == expected


def test_readme_states_the_real_length() -> None:
    r"""The prose says 51 characters; the program has to be that long."""
    program = _readme_program()
    body = _README.read_text(encoding="utf-8")
    assert f"emits {len(program)} characters" in body
