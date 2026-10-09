"""Boolean execution reads registry contracts rather than example documentation."""

import subprocess
import sys

import pytest

from esolangs.registry import LANGUAGES, parameterized_ids, resolve
from esolangs.tools.examples import BOOLEAN_EXAMPLES


def test_examples_derive_the_registered_io_contract() -> None:
    for stem, example in BOOLEAN_EXAMPLES.items():
        lang = LANGUAGES[resolve(stem.replace("-", " "))]
        contract = lang.contract
        assert contract.parameterized == (example.fill is not None), stem
        for field in (
            "alphabet",
            "input_shape",
            "ghost_digit",
            "answer_mode",
            "answer_pattern",
            "answer_values",
            "note",
        ):
            assert getattr(example, field) == getattr(contract, field), (stem, field)
    assert parameterized_ids() == frozenset(
        LANGUAGES[resolve(stem.replace("-", " "))].id
        for stem, example in BOOLEAN_EXAMPLES.items()
        if example.fill is not None
    )


@pytest.mark.medium
def test_stripped_docstrings_preserve_all_answer_mechanisms() -> None:
    code = """
import esolangs
from esolangs._evaluate import _evaluate
from tests.stdin_check import _check_stdin
for name in (
    'brainfuck', 'Fargo', 'Grapheme', 'Taglate',
    'RAM0', 'INTERCAL', '123', 'Vandevelo',
):
    program = esolangs.generate(name, '0110')
    result = _evaluate(name, program, inputs=2)
    if result != '0110':
        raise AssertionError((name, result))
for name, stdin in (
    ('brainfuck', '01'), ('Fargo', '1\\n'),
    ('Grapheme', '%\\nA\\n'), ('Taglate', '01'),
):
    _check_stdin(name, stdin, '0110')
try:
    esolangs.describe('brainfuck')
except esolangs.ProgramError as exc:
    if '-OO' not in str(exc):
        raise
else:
    raise AssertionError('describe accepted missing documentation')
"""
    result = subprocess.run(
        [sys.executable, "-OO", "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
