"""Tests for the Nandypants interpreter."""

import pytest

from esolangs.languages.nandypants.interpreter import run
from esolangs.runtime.io import ScriptedIO

CAT = r"0}/>v>^<<^>^\}^0"


def _run(code: str, stdin: str = "") -> tuple[str, bool]:
    """Return the output and whether the run ended on EOF."""
    io = ScriptedIO(stdin)
    try:
        run(code, io)
    except EOFError:
        return io.getvalue(), True
    return io.getvalue(), False


def test_the_pages_cat_copies_input_until_eof() -> None:
    assert _run(CAT, "Hi!") == ("Hi!", True)


def test_input_is_reduced_modulo_256() -> None:
    assert _run(CAT, "Ł") == ("A", True)


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        (r"^\ ", "", "\x01"),  # NAND(0,0)=1; a partial byte is zero padded
        (r"^^\ v^\ ", "", "\x01"),  # a stays 1 while b=0, clears once b=1
        (r"/\ ", "\x01", "\x00"),  # a read sets b, never a
        (r"v^/^\ ", "\x00", "\x01"),  # a=1 NAND b=0 is 1
        (r"v^/^\ ", "\x01", "\x00"),  # a=1 NAND b=1 is 0
        (r"v^}\{\ ", "", "\x02"),  # tape a's right cell is 0, the left is 1
        (r"v^<\ ", "", "\x01"),  # moving b leaves a alone
        (r"hello, world", "", ""),  # other characters are ignored
        (r"3 ^\ 3 \ ", "", "\x00"),  # NAND 1: the first odd 3 jumps to the last
        (r"v^ 3 \ 3 ", "", "\x01"),  # NAND 0: it falls through
        (r"5 3 8 \ ", "", "\x00"),  # a lone label does nothing
        (r"003 ^\ 3 ", "", ""),  # 003 and 3 are one label
    ],
)
def test_commands(code: str, stdin: str, expected: str) -> None:
    assert _run(code, stdin) == (expected, False)
