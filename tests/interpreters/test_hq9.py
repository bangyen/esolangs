"""HQ9+ Hello World; the oracle in test_hq9_semantics.py covers the rest."""

import pytest

from esolangs.interpreters.register_based.hq9 import run
from tests.interpreters.runner import run_program


@pytest.mark.parametrize("code", ["H", "h"])
def test_greeting(code: str) -> None:
    assert run_program(run, code) == "Hello, world!\n"
