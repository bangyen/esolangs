"""The Workspace column's bit formulas hold at small n, over every row.

Each was derived from the interpreter's snapshot and the generator, not
fitted.  ``L`` is the program's length, ``T`` is 2^n; ``exact`` formulas must be reached
on some table here, ``bound`` ones only never exceeded.
"""

from collections.abc import Callable

import pytest

import esolangs
from esolangs.interpreters.stack_based.sstack import _parse
from esolangs.tools.three_x import _level
from scripts.benchmark import state_bits
from tests.generator_support import CHECK
from tests.proofs._formula import ledger_formulas
from tests.proofs._ledger import load as load_ledger
from tests.proofs.test_execution_formulas import FORMULAS as EXECUTION_FORMULAS
from tests.proofs.test_execution_formulas import _measure, _tables

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


def _intercal(n: int) -> int:
    """Nine bits and a key per variable, S the Execution statement bound."""
    s = 2 * n + 3 + sum(min(2**k, 2 ** (2 ** (n - k)) - 2) for k in range(1, n))
    return 9 * s - 18 + sum(map(bl, range(1, s - 1))) + bl(s)


def _diagram_cap(n: int) -> int:
    """Distinct subtables each depth can hold: FRACTRAN's most states."""
    return sum(min(1 << d, 1 << (1 << (n - d))) for d in range(n + 1))


def _primes(count: int) -> list[int]:
    """The first ``count`` primes."""
    out: list[int] = []
    p = 2
    while len(out) < count:
        if all(p % q for q in out):
            out.append(p)
        p += 1
    return out


def _crement(n: int, _: str) -> int:
    """The whole program; P bounds the shared nodes, N the instructions."""
    p = sum(min(2**k, 4**2 ** (n - k - 1) - 2**2 ** (n - k - 1)) for k in range(n))
    m = 3 * p + 2 * n + 3
    return (
        2 * bl(m)
        + 32
        + bl(2 * n + 3)
        + 2 * n * (10 + bl(m - 1))
        + p * (28 + 3 * bl(2 * n + 2) + 2 * bl(m - 2))
    )


def _inject(n: int, _: str) -> int:
    """The program text after the n reads, its label spans and cursor."""
    spans = sum(bl(3 * i) + bl(3 * i + 2) for i in range(n + 3))
    spans += sum(map(bl, range(2 * n + 5, 6 * n + 5)))
    return 24 * 2**n + 516 * n + 169 + bl(12 * n + 10) + bl(2 * n) + bl(n) + spans


def _subleq(n: int, _: str) -> int:
    """Payload bits, signed references, two patched operands and registers."""
    i, chunks = 8 * n + 47, -(-(2**n) // n)
    b = 3 * i
    registers = (
        bl(3 * i - 3) + 5 * bl(n) + 2 * n + 33 + max(n, bl(n) + 1) + max(1, n - 1)
    )
    return (
        2**n
        + 2 * chunks
        + (chunks + 2) * bl(b + 17 + 2 * chunks)
        + i * bl(b)
        + (2 * i - 1) * bl(b + 17)
        + registers
    )


def _key(i: int) -> int:
    """K(i), the ledger's bound on the ith 3x key's bits."""
    return 2 * bl(2 ** (i - 1) * 3 ** (2 * i - 1)) + 1


def _three_x(n: int, p: str) -> int:
    """Guard residues, read cursor and the 2n + 1 keys, K a key's bits."""
    return (
        n * bl(len(p))
        + 3 * 2**n // 2
        + 2 * n
        + 16
        + bl(2 * n - 1)
        + 2 * _key(2 * n + 1)
        + sum(_key(i) + 3 for i in range(1, 2 * n + 2))
    )


def _forbin(n: int, _: str) -> int:
    """Main's locals twice (frame and scope) and G, the loop cursor's peak."""
    h = max(n - 7, 0)
    loop = [bl(j + 1) + max(1, bl(h - 1 - j)) + 10 for j in range(h)]
    return 32 * n + 71 + 2 * bl(n) + max([bl(h + 1) + 4, *loop])


def _apl(n: int, _: str) -> int:
    """Frame work stacks at the leaf; V and W the serials' widths, n >= 2."""
    f = 2 * n + 7
    v = sum(bl(s) + bl(s + 1) + bl(s + 5) for s in range(2 * n + 15, 9 * n - 5, 7))
    w = bl(2 * n - 1) + bl(2 * n + 3) + bl(2 * n + 13)
    w += bl(f) + 2 * bl(f + 1) + bl(f + 2) + bl(f + 4)
    return 179 * n + 400 + v + w


def _add_sub_jump(n: int, _: str) -> int:
    """Every program address's bits, the T/n packed cells, Q the rest."""
    c = -(-(2**n) // n)
    i = 5 * n + 54
    b = 4 * i
    m = b + 14 + 2 * c
    q = i * bl(b) + (3 * i - 2) * bl(b + 13) + 2 * bl(m - 1) + bl(20 * n + 212) + 23
    return sum(map(bl, range(m))) + c * (n + bl(b + 13 + c)) + 3 * n + 5 * bl(n) + q


def _decleq(n: int, _: str) -> int:
    """The memory tuple and registers; the letters are the ledger's."""

    def ones(x: int) -> int:
        return bin(x).count("1")

    k = min(n, bl(2 * n - 1))
    s, m, c = 2**k, n - k, -(-(n + 18) // 3) * 3
    p = c + 144 * n + 3 * k + 3 * s - 3
    b = sum(bl(18 + i) for i in range(n))
    d = sum(
        2 * bl(18 + m + j) + bl(p + 3 * (j - k + 2) - 3 * 2 ** (k - 1 - j))
        for j in range(k)
    )
    e = sum(
        2 * bl(18 + lv)
        + bl(p + 3 * lv + (2 * u + 1) * 2 ** (m - lv - 1) * (s + 18) - 3 * ones(u))
        for lv in range(m)
        for u in range(2**lv)
    )
    xs = [p + 3 * m + j * (s + 18) - 3 * ones(j) for j in range(2**m)]
    f = sum(
        22 + 6 * s + bl(x) + bl(x + 9) + 2 * bl(x + 10) + bl(x + 14 + s) for x in xs
    )
    r = 3 * bl(p - 3 + 2**m * (s + 18)) + bl(n) + bl(c) + c + k + 8
    return 55 * n + 11 * s + 95 * b + d + e + f + r


#: Formulas the ledger notation cannot state: a case split, a definition,
#: a count taken from the program.
_HAND: dict[str, tuple[Callable[[int, str], int], bool, tuple[int, ...]]] = {
    "CV(N)(C)": (lambda n, p: 17 + bl(2 * n - 1) + bl(len(p)), True, (4, 6)),
    "Container": (lambda n, _: 25 * n + 154 + bl(2 * n + 2) + 2 * bl(n), True, (7,)),
    "Alight": (lambda n, _: 72 * n + 762 + bl(6 * n + 12) + bl(n), True, (3, 5)),
    "BrainIf": (lambda n, p: 13 + bl(len(p.splitlines())) + bl(n), True, (3, 6)),
    # Every path stacks all n input bytes (6 bits) beside '1' and '0'.
    "SStack": (lambda n, p: 6 * n + 12 + bl(len(_parse(p))) + bl(n), True, (3, 6)),
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
    "EGL": (_egl, True, (3, 5)),
    "Dig": (_dig, True, (5,)),
    "Taglate": (_taglate, True, (3, 5)),
    "Grapheme": (_grapheme, True, (3, 5)),
    "BIO": (
        lambda n, _: (
            max(2 * n, 8)
            + sum(bl(10 * n - 8 + 3 * j) for j in range(2**n - 1))
            + bl(4 * 2**n + 10 * n + 37)
        ),
        False,
        (3, 5),
    ),
    "Dimensional": (
        lambda n, _: (
            sum(map(bl, range(2**n)))
            + 5 * 2**n
            + n * (n - 1) // 2
            + 4 * n
            + 6
            + bl(2 * 2**n + 20 * n + 56)
            + bl(2 * n - 1)
        ),
        True,
        (3, 4),
    ),
    "123": (
        lambda n, p: (
            9
            + sum(map(bl, range(1, 5 * 2**n + 3 * n - 2)))
            + bl(len(p))
            + bl(5 * 2**n + 3 * n - 3)
        ),
        False,
        (4, 5),
    ),
    "INTERCAL": (lambda n, _: _intercal(n), False, (3, 6)),
    "BFStack": (
        lambda n, p: (
            n
            + 7
            + bl(n)
            + (max(n - 7, 0) + (3 * min(2**n, 128) + 1) // 5 + 3) * bl(len(p))
        ),
        False,
        (3, 6),
    ),
    "Boolfuck": (
        lambda n, p: (
            bl(len(p) - 1)
            + max(12, bl(2 * n - 2) + 10)
            + n
            + sum(map(bl, range(1, n)))
            + bl(2 * n)
            + bl(n)
        ),
        False,
        (3, 6),
    ),
    "Packlang": (
        lambda n, p: (
            min(2**n, 128)
            + 2 * n
            + min(n, 7)
            + 192
            + 16 * (n > 7)
            + bl(len(p))
            + 2 * bl(n)
        ),
        False,
        (3, 5),
    ),
    "Polynomial": (
        lambda n, _: (
            bl(min(10 * 2**n - 7, 1934) + 10)
            + 1
            + max(
                bl(n + 3),
                bl(49 * (max(min(2**k, 2**2 ** (n - k)) for k in range(n + 1)) - 1)),
            )
            + 2 * bl(n)
        ),
        False,
        (3,),
    ),
    "FRACTRAN": (
        lambda n, _: (
            bl(_primes(n + 1 + _diagram_cap(n))[-1])
            + n
            + 2
            + sum(map(bl, _primes(n + 1)[1:]))
        ),
        False,
        (3, 5),
    ),
    "Streetcode": (
        # Peak car state is 13 + bl(width), width = 2T + 57 + G.
        lambda n, _: (
            n * 2**n
            + 2 * n
            + 25
            + bl(
                2 ** (n + 1) + 57 + sum(max(51, 2 ** (k - 1) + 3) for k in range(1, n))
            )
            + 2 * bl(n)
        ),
        True,
        (6, 7),
    ),
    "Crement": (_crement, False, (3, 6)),
    "Inject": (_inject, True, (5,)),
    "Subleq": (_subleq, False, (3, 5)),
    "3x": (_three_x, False, (3, 5)),
    "Forbin": (_forbin, True, (3, 8)),
    "Algebraic Programming Language": (_apl, True, (3, 5)),
    "Decleq": (_decleq, True, (3, 4)),
    # Code, stack and store each near E, the expanded program, at most 95T - 80.
    "Smu": (
        lambda n, _: 24 * (95 * 2**n - 80) - 1214 + bl(95 * 2**n - 80) + bl(n),
        True,
        (2, 4),
    ),
    "AddSubJump": (_add_sub_jump, False, (3, 5)),
    # Latches never clear: 3T - 6 + n flat slots, 6T - 10 + n under the
    # H-layout. Same-state pulses are an antichain: T/2 + n flat, T + n after.
    "Circuit Diagram": (
        lambda n, _: 7 * 2**n // 2 + 2 * n - 5 if n <= 7 else 7 * 2**n + 2 * n - 9,
        False,
        (3, 6),
    ),
    "Collatz Multiverse": (
        lambda n, p: (
            -(-(2**n) // 4) * (bl(len(p) // 17) + 6)
            + 64 * (bl(len(p) // 17) + 1)
            + (n * n + 168) * (8 * n + bl(len(p)) + 9) // 2
            + 2 * bl(len(p))
            + 115
        ),
        False,
        (3, 6),
    ),
    "Flowchart": (
        lambda n, p: (
            (7 * 2**n + 20 * n + 100) * (bl(len(p)) + 4)
            + sum(bl(j) + 2 for j in range(2**n // 2))
            + 2 * bl(len(p))
            + n
            + 2 * bl(n)
            + 32
        ),
        False,
        (3, 4),
    ),
}


#: Arities where the default (see ``ledger_formulas``) is too slow or too
#: shallow for the construction.
_ARITIES: dict[str, tuple[int, ...]] = {
    "Minsky Swap": (3, 6),
    "Factor": (4,),
    "Clockwise": (3, 6),
    "Back": (3, 6),
    "FALSE": (3, 5),
    "Sophie": (3, 6),
    "NoComment": (5,),
    "6-5": (7,),
    "Circlefuck": (3,),
    "Bitdeque": (5,),
    "ArrowQueue": (1, 6),
    "Thue": (3, 6),
    "Unsquare": (3, 6),
    "Super SNUSP": (5,),
    "Modulous": (3, 6),
    "Minifuck": (5,),
    "LaserFuck": (5,),
    "ROTfuck": (3, 4),
    "Fargo": (6,),
    # Every word and register is below 3^10 < 2^16; measured ~394k bits.
    "Malbolge": (2, 3),
    # Task, then 3n + 6 frames, each one shared subterm and its depth.
    "Unlambda": (2, 3),
    # A T-cell corridor and T - 1 answers at bl(x) + 2 bits each, the ant, ip.
    "A Painter Ant": (3, 6),
    "B-tapemark": (3, 4),
}

#: Generator -> (formula, exact?, arities): the ledger's own clause where
#: it parses (``tests/proofs/_formula.py``), else ``_HAND``.
FORMULAS = ledger_formulas(
    lambda row: row.workspace_clause if " bits" in row.workspace_clause else "",
    _HAND,
    _ARITIES,
)


#: Smallest-arity cases that still measure past the medium band run alone
#: (Container-7 5.7s; 6-5-7 4.9s and Fargo-6 4.6s overrun under load): the
#: per-step state measurement dominates, so they run in the slow band.
_SLOW_AT_MIN: frozenset[tuple[str, int]] = frozenset(
    {("Container", 7), ("6-5", 7), ("Fargo", 6)}
)


def _formula_cases() -> list[object]:
    ledgers = (EXECUTION_FORMULAS, FORMULAS)
    cases = sorted(
        {
            (name, n)
            for ledger in ledgers
            for name, (_, _, arities) in ledger.items()
            for n in arities
        }
    )
    return [
        pytest.param(
            name,
            n,
            marks=pytest.mark.medium
            if (name, n) not in _SLOW_AT_MIN
            and any(name in ledger and n == min(ledger[name][2]) for ledger in ledgers)
            else pytest.mark.slow,
        )
        for name, n in cases
    ]


@pytest.mark.parametrize(("name", "n"), _formula_cases())
def test_execution_and_workspace_formulas_hold(name: str, n: int) -> None:
    formulas = [
        (written, formula, exact)
        for written, ledger in ((False, EXECUTION_FORMULAS), (True, FORMULAS))
        if name in ledger
        for formula, exact, arities in (ledger[name],)
        if n in arities
    ]
    reached = [False] * len(formulas)
    for table in _tables(name, n):
        program = esolangs.generate(name, table)
        measurements = _measure(
            name,
            table,
            written=any(written for written, _, _ in formulas),
            program=program,
        )
        for i, (written, formula, _) in enumerate(formulas):
            claim = formula(n, program)
            actual = measurements[int(written)]
            assert actual <= claim, f"{name} n={n} {table}: {actual} > {claim}"
            reached[i] |= actual == claim
    for found, (_, _, exact) in zip(reached, formulas, strict=True):
        assert found or not exact, f"{name} n={n}: no table reaches the formula"


def test_every_formula_cell_is_checked() -> None:
    """A ``worst``/``at most`` Workspace clause in bits has a formula here."""
    stated = {
        row.generator
        for row in load_ledger().rows
        if row.workspace_clause.startswith(("worst ", "at most "))
        and " bits" in row.workspace_clause
    }
    unchecked = sorted(stated - set(FORMULAS))
    assert not unchecked, f"{unchecked} state a bound with no FORMULAS row; {CHECK}"
    orphaned = sorted(set(FORMULAS) - stated)
    assert not orphaned, f"remove {orphaned} from FORMULAS: no stated bound"


def test_three_x_keys_fit_their_bound() -> None:
    """K(i) covers the 41 shortest constants, every key through n = 20."""
    keys: list = []
    length = 0
    while len(keys) < 41:
        length += 1
        keys.extend(_level(length))
    for i, value in enumerate(keys[:41], 1):
        assert state_bits(value, {}) <= _key(i), (i, value)
