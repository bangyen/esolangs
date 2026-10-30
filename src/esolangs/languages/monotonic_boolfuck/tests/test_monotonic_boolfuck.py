"""Monotonic Boolfuck conventions and the generator's walk."""

import pytest

from esolangs.languages.monotonic_boolfuck.generator import monotonic_boolfuck
from esolangs.languages.monotonic_boolfuck.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.support.raises import assert_rejected_with_hint
from tests.support.witness_tables import witnesses


def out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        ("1;", "", "\x01"),
        ("11;", "", "\x01"),
        (";", "", "\x00"),
        ("<1;>;<;", "", "\x05"),
        (",;>" * 8, "A", "A"),
        (",;" * 8, "A", "\xff"),  # the set cell swallows the rest,
        # A set bit consumes input without storing it.
        ("1" + ",;" * 8, "\xff", "\xff"),
        # A clear bit stays clear on a 0 and sets on a 1.
        (",;,;", "\x02", "\x02"),
        ("[;]1;", "", "\x01"),
        ("1>;<;", "", "\x02"),
        ("ignored text", "", ""),
    ],
)
def test_conventions(code: str, stdin: str, expected: str) -> None:
    assert out(code, stdin) == expected


def test_closing_bracket_retests_its_opener() -> None:
    """``]`` is unconditional: the cell it leaves on, not the loop's, decides."""
    assert out("1[>]<;") == "\x01"
    assert out("1[>]>;") == "\x00"


@pytest.mark.medium
def test_hints_for_bad_programs() -> None:
    assert_rejected_with_hint("Monotonic Boolfuck", "[", "close this '[' with ']'")


@pytest.mark.parametrize("n", [1, 2, 3])
def test_all_tables_up_to_three_inputs(n: int) -> None:
    for table in witnesses(n):
        code = monotonic_boolfuck(table)
        for row in range(1 << n):
            assert out(code, f"{row:0{n}b}") == table[row]


def test_nodes_diverge_by_pointer_not_by_flag() -> None:
    """A tested input is one read and a pair of loops; an ignored one tests nothing."""
    tested = monotonic_boolfuck("0110")
    assert (
        tested.count("[") == 4
    )  # root node; bottom nodes: x prints bare, not x one pair
    ignored = monotonic_boolfuck("0011")  # depends on input 0 only
    assert ignored.count("[") == 2  # one node
    assert out(monotonic_boolfuck("0101"), "11") == "1"  # ignores the first input
    assert out(monotonic_boolfuck("0101"), "10") == "0"
