"""Unit tests for the ZTOALC L interpreter."""

import io
from contextlib import redirect_stdout
from typing import List

from esolangs.interpreters.other.ztoalc import run


def run_and_capture(code: List[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code)
    return buffer.getvalue()


class TestZTOALC:
    def test_print_constant(self) -> None:
        assert run_and_capture(["10", "print 65"]) == "A"

    def test_print_other_constant(self) -> None:
        assert run_and_capture(["2", "print 66"]) == "B"
