"""The Workspace column's bit formulas hold at small n, over every row.

Each was derived from the interpreter's snapshot and the generator, not
fitted.  ``L`` is the program's length, ``T`` is 2^n; ``exact`` formulas must be reached
on some table here, ``bound`` ones only never exceeded.
"""

from collections.abc import Callable

import pytest

import esolangs
from tests.proofs._ledger import load as load_ledger
from tests.proofs.test_execution_formulas import _tables, _worst

bl = int.bit_length


def _floor1(x: int) -> int:
    """Bits of a non-negative int: zero still costs one."""
    return max(1, bl(x))


def _taglate(n: int, p: str) -> int:
    """Six-bit queue cells; odd n gets a ghost input, m even."""
    m = 2 * -(-n // 2)
    return 24 * 2**m + 12 * m + 12 + bl(m) + bl(len(p) - 4 * 2**m - 7 * m + 1)


def _dig(n: int, p: str) -> int:
    """The R by C grid at a byte a cell, its two coordinates, two counters."""
    lines = p.split("\n")
    rows, cols = len(lines), max(map(len, lines))
    return 8 * rows * cols + bl(rows - 1) + bl(cols - 1) + bl(2 * n - 1) + bl(n) + 10


def _egl(n: int, p: str) -> int:
    """Grid, loop stack and cursor; ``d`` is the digit count of T."""
    d = len(str(2**n))
    return 2 * 2**n + 2 * n + 7 + bl(len(p) - d - 3) + bl(len(p) - d - 9) + 2 * bl(n)


def _grapheme(n: int, _: str) -> int:
    """The call frame's program text, ``d`` the digit count of 2^T."""
    t = 2**n
    d = len(str(2**t))
    lifted = bl(10 ** (d + 1) + 2**t - 1)
    return 16 * d + 112 * n + 312 + bl(14 * n + d + 17) + 2 * lifted + bl(2 * n) + bl(n)


#: Generator -> (bits from n and the program, exact?, arities).  Mirrors the ledger.
FORMULAS: dict[str, tuple[Callable[[int, str], int], bool, tuple[int, ...]]] = {
    "Fish": (lambda n, _: n + 13 + bl(9 * n + 8) + bl(n), True, (3, 6)),
    "Home Row": (lambda n, _: n + 32 + bl(14 * 2**n + 10 * n + 15), True, (3, 5)),
    "Minsky Swap": (lambda n, _: n + 3 + bl(2 ** (n + 1) + 6 * n + 5), True, (3, 6)),
    "Factor": (
        lambda n, _: (
            7 * n + 12 + bl(2 * n + 1) + bl(n) + bl(27 * 2 ** (n - 1) + 16 * n + 14)
        ),
        True,
        (4,),
    ),
    "Clockwise": (
        lambda n, _: 57 * n + 50 + bl(2 * n + 14) + bl(2 ** (n + 1) + 9 * n + 1),
        True,
        (3, 6),
    ),
    "CV(N)(C)": (lambda n, _: 2 * n + 20 + bl(2 * n - 1), True, (4, 6)),
    "Container": (lambda n, _: 25 * n + 154 + bl(2 * n + 2) + 2 * bl(n), True, (7,)),
    "BF-PDA": (lambda n, _: 3 * n + 4, True, (3, 6)),
    "Back": (
        lambda n, _: n + 5 + bl(max(6 * n - 2, 2**n - 1)) + bl(3 * n + 4) + bl(n),
        True,
        (3, 6),
    ),
    "Alight": (lambda n, _: 72 * n + 762 + bl(6 * n + 12) + bl(n), True, (3, 5)),
    "brainfuck": (
        lambda n, p: 2 * n + 6 + bl(2 * n) + bl(n) + bl(len(p)),
        True,
        (3, 6),
    ),
    "BrainIf": (lambda n, p: 13 + bl(len(p.splitlines())) + bl(n), True, (3, 6)),
    "Jaune": (
        lambda n, _: n + 1 + bl(5 * 2**n + 5 * n - 4) + bl(n - 1) + bl(2 * n - 1),
        False,
        (3, 6),
    ),
    "FALSE": (lambda n, _: (2 * n + 56) * (n + 4) + n + 1 + bl(n), False, (3, 5)),
    "Sophie": (lambda n, p: bl(len(p)) + bl(n) + 7, False, (3, 6)),
    "RAM0": (
        lambda n, p: (
            n + bl(len(p.split())) + 2 * _floor1(n - 1) + sum(map(_floor1, range(n)))
        ),
        True,
        (3, 6),
    ),
    "thisthat": (
        lambda n, _: 4 * n + 89 + 2 * bl(n) + sum(map(_floor1, range(n))),
        True,
        (3, 5),
    ),
    "Line": (
        lambda n, _: (
            n
            + 1
            + bl(3 * n - 2)
            + bl(n - 1)
            + bl(2 * n - 1)
            + sum(_floor1(c) + 1 for c in range(n))
        ),
        True,
        (5,),
    ),
    "Suffolk": (
        lambda n, p: bl(len(p) - 1) + max(6, n - 1) + max(19, 4 * n - 1) + bl(n) + 4,
        True,
        (3, 5),
    ),
    "Qoibl": (lambda n, _: 2**n + 3 + bl(n) + bl(n + 2), True, (3, 6)),
    "Piet": (
        lambda n, _: (
            2**n + 2 * n + 7 + bl(3 * 2**n + 5 * n + 15) + bl(2 * n - 1) + bl(n)
        ),
        True,
        (3, 5),
    ),
    "NoComment": (lambda n, p: 32768 + 2**n // 4 + 30 + bl(len(p)), True, (5,)),
    "6-5": (lambda n, _: 2 * 2**n + 7 * n + 9 + bl(n), True, (7,)),
    "S*bleq": (lambda _, p: 3 * len(p), False, (3, 5)),
    "Circlefuck": (
        lambda n, p: (
            6 * len(p) + 10 * n + 7 + bl(len(p) - 1) + bl(len(p) - 2**n - 2) + bl(n)
        ),
        True,
        (3,),
    ),
    "Eval": (lambda n, p: 8 * len(p) + 2**n + n + 2 + bl(len(p)), True, (3, 5)),
    "EGL": (_egl, True, (3, 5)),
    "Dig": (_dig, True, (5,)),
    "Cyclic tag": (lambda n, _: 16 * 2**n + 1 + bl(2 * 2**n + n), True, (3, 5)),
    "Bitwise Cyclic Tag": (
        lambda n, _: 16 * 2**n + 8 + bl(8 * 2**n + n - 2) + bl(2 * 2**n + n + 1),
        True,
        (3, 5),
    ),
    "Bitdeque": (lambda n, _: 2**n + 2 + bl(4 * 2**n + 10 * n - 5), True, (5,)),
    "ArrowQueue": (lambda n, _: 2**n + 11 + bl(3 * 2**n + 6 * n + 5), True, (5, 6)),
    "bit~": (
        lambda n, _: (
            2 * 2**n + 49 + bl(2 * 2**n + 41) + bl(5 * 2**n + 18 * n + 74) + bl(n)
        ),
        True,
        (3, 5),
    ),
    "///": (lambda n, p: 8 * len(p) + 56 + 8 * max(0, 2**n - 15), True, (3, 5)),
    "Smallfuck": (lambda n, p: len(p) + bl(len(p)) + bl(3 * n), True, (3, 6)),
    "Thue": (lambda n, _: 8 * 2**n + 24 + bl(2 * n), True, (3, 6)),
    "Taglate": (_taglate, True, (3, 5)),
    "Unsquare": (
        lambda n, p: 2**n + 12 + bl(len(p)) + bl(len(p) - 33) + 2 * bl(n),
        True,
        (3, 6),
    ),
    "Super SNUSP": (lambda n, p: 2**n + 2 * n + 12 + bl(len(p)) + bl(n), True, (5,)),
    "Modulous": (
        lambda n, _: 6 * 2**n + n + 2 + bl(6 * n + 5) + bl(2 * n - 1) + bl(n),
        True,
        (3, 6),
    ),
    "Minifuck": (
        lambda n, p: 6 * 2**n + 30 + bl(6 * 2**n + 28) + bl(6 * 2**n + 30) + bl(len(p)),
        True,
        (5,),
    ),
    "LaserFuck": (lambda n, _: 12 * 2**n + 2 * n + 11 + 2 * bl(n), True, (5,)),
    "Grapheme": (_grapheme, True, (3, 5)),
}


@pytest.mark.medium
@pytest.mark.parametrize("name", sorted(FORMULAS))
def test_the_workspace_formula_holds(name: str) -> None:
    formula, exact, arities = FORMULAS[name]
    for n in arities:
        reached = False
        for table in _tables(name, n):
            claim = formula(n, esolangs.generate(name, table))
            bits = _worst(name, table, written=True)
            assert bits <= claim, f"{name} n={n} {table}: {bits} > {claim}"
            reached |= bits == claim
        assert reached or not exact, f"{name} n={n}: no table reaches the formula"


def test_every_formula_cell_is_checked() -> None:
    """A ``worst``/``at most`` Workspace clause in bits has a formula here."""
    stated = {
        row.generator
        for row in load_ledger().rows
        if row.workspace_clause.startswith(("worst ", "at most "))
        and " bits" in row.workspace_clause
    }
    assert stated == set(FORMULAS)
