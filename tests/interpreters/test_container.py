"""Unit tests for the Container interpreter."""

import io
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.other.container import run
from esolangs.interpreters.io import IO

HELLO_WORLD = [
    "A:",
    "+1 EXIT>=1",
    "",
    "PRINT:",
    "+1 PRINT<=0",
    "-1 PRINT>=1",
    "",
    "OUT:",
    "+72 A>=0",
    "-115 A>=2",
    "+93 A>=4",
    "-100 A>=6",
    "+103 A>=8",
    "-173 A>=10",
    "+114 A>=11",
    "+0 A>=12",
    "+99 A>=14",
    "-194 A>=16",
    "+205 A>=18",
    "-214 A>=20",
    "+106 A>=21",
    "+0 A>=22",
    "-59 A>=24",
    "",
    "EXIT=1:",
    "-1 A>=24",
]


class TestContainer:
    def test_hello_world(self) -> None:
        """Hello, World! program from esolangs.org."""
        buffer = io.StringIO()
        with pytest.raises(SystemExit) as exc, redirect_stdout(buffer):
            run(HELLO_WORLD, io=IO())
        assert exc.value.code == 0
        assert buffer.getvalue() == "Hello, world!"

    def test_container_update_clamps_at_zero(self) -> None:
        """Negative results are clamped to zero."""
        from esolangs.interpreters.other.container import Con

        con = Con("A")
        con.add("-5 B>=1")
        assert con.update({"A": 2, "B": 1}) == 0
        assert con.update({"A": 2, "B": 0}) == 2

    def test_input_container(self) -> None:
        """An empty-named container going 0 -> 1 reads a character of input."""
        from unittest.mock import patch

        code = [":", "+1 A>=0", "", "A:", "+1 EXIT>=1", "", "EXIT=1:", "-1 A>=0"]
        with (
            patch("builtins.input", return_value="Z"),
            pytest.raises(SystemExit) as exc,
            redirect_stdout(io.StringIO()),
        ):
            run(code, IO())
        assert exc.value.code == 0
