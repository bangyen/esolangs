"""Execution tests for the Smu boolean generator."""

import random

from esolangs.languages import generators as tools
from esolangs.languages.smu.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.generators.sample_tables import five_input_sample


def execute(program: str, row: int, n: int) -> tuple[str, int]:
    io = ScriptedIO(format(row, f"0{n}b"))
    run(program, io)
    return io.getvalue(), io.position()


def test_every_three_input_table_runs_every_row() -> None:
    """Folds, pads and macros all answer, and every table reads all its bytes."""
    for value in range(256):
        table = format(value, "08b")
        program = tools.smu(table)
        for row in range(8):
            assert execute(program, row, 3) == (table[row], 3), (table, row)


def test_sharing_totals() -> None:
    """A macro is kept only where it is shorter; the totals pin the rule."""
    three = [format(value, "08b") for value in range(256)]
    assert sum(len(tools.smu(table)) for table in three) == 32174
    assert sum(len(tools.smu(table)) for table in five_input_sample()) == 36687
    # Past 47 macros names take a digit, so which ones earn the short names
    # and whether a long name still pays both show in the length.
    wide = format(random.Random(3).getrandbits(1 << 11), f"0{1 << 11}b")
    assert len(tools.smu(wide)) == 2128


def test_macro_break_even_stays_inline() -> None:
    """At (uses - 1) * len == (uses + 2) * len(name) the subtree stays inline.

    This table's shared subtrees sit exactly on the keep rule's break-even:
    defining them would change the text but not the length (155 either way),
    and the strict ``>`` leaves them inline.
    """
    assert tools.smu("0011110001101101") == (
        "k((())=())kn(+)=(|)=()+kkkkkkk()nm(+)=(+)()+(|)=()+kkkkkkk()m"
        "z(())=(||||++||)zo(())=(+|||++||)o"
        "X)(X"
        "Y)nY"
        "a(o)mab(zXoYb((((z)mXaYX(aX(z)mYYX((bX(oXzYYX(aXbYYY"
    )


def test_twice_used_subtree_earns_a_two_letter_macro() -> None:
    """The keep rule's +2: a subtree used twice against a two-letter name.

    At n = 11 this seed's tree has a subtree used twice under a two-letter name:
    (2 - 1) * 9 > (2 + 2) * 2 keeps it, while a +3 constant would tie the
    test at 9 and drop it, at +1 character.
    """
    table = format(random.Random(321).getrandbits(1 << 11), f"0{1 << 11}b")
    assert len(tools.smu(table)) == 2094


def test_an_ignored_input_is_one_pad() -> None:
    """Equal halves are ``(X)m``, three characters, not ``(X)(X)n``."""
    inner = "0110100110010110"
    for at in (0, 2):
        low = 4 - at
        table = "".join(
            inner[row >> (low + 1) << low | row & ((1 << low) - 1)] for row in range(32)
        )
        program = tools.smu(table)
        for row in range(32):
            assert execute(program, row, 5) == (table[row], 5), (at, row)
    assert len(tools.smu(inner + inner)) - len(tools.smu(inner)) == 3
