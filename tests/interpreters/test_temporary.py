"""Unit tests for The Temporary Stack interpreter."""

import io
from contextlib import redirect_stdout

from esolangs.interpreters.stack_based.temporary import run


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run(code)
    return buffer.getvalue()


class TestTemporaryStack:
    def test_hello_world(self) -> None:
        """Hello World program from esolangs.org."""
        assert run_and_capture('o *Ifmmp-!xpsme" v11 v2297') == "Hello, world!\n"

    def test_squish(self) -> None:
        """The bottom value is squished and output when the rest outweigh it."""
        assert run_and_capture("v1 v3") == "0"

    def test_ascii_output_mode(self) -> None:
        """o switches output to ASCII characters."""
        assert run_and_capture("o v66 v133") == "A"
