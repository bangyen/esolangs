"""Public Thue syntax diagnostics."""

import re

import pytest

from esolangs.interpreters.other.thue import run
from tests.interpreters.runner import run_program


@pytest.mark.parametrize(
    ("program", "message"),
    [
        ("a::=b\na\n", "nothing but whitespace on either side"),
        ("nonsense\n::=\na", "has no '::='"),
        ("::=x\n::=\na", "empty left-hand side"),
    ],
)
def test_a_malformed_program_is_refused(program: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        run_program(run, program)
