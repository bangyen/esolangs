"""The Workspace column's bit formulas hold at small n, over every row.

Each was derived from the interpreter's snapshot and the generator, not
fitted.  ``L`` is the program's length, ``T`` is 2^n; ``exact`` formulas must be reached
on some table here, ``bound`` ones only never exceeded.
"""

import random
from collections.abc import Callable

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.interpreters.stack_based.sstack import _parse
from scripts.benchmark import WrittenState
from tests.proofs._ledger import load as load_ledger
from tests.proofs.deep.execution import run_to_answer
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


def _intercal(n: int) -> int:
    """Nine bits and a key per variable, S the Execution statement bound."""
    s = 2 * n + 3 + sum(min(2**k, 2 ** (2 ** (n - k)) - 2) for k in range(1, n))
    return 9 * s - 18 + sum(map(bl, range(1, s - 1))) + bl(s)


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
    """I instructions over operands up to B + 17, C chunks, the registers."""
    i, chunks = 8 * n + 45, -(-(2**n) // n)
    b = 3 * i
    registers = (
        bl(3 * i - 3) + 5 * bl(n) + 2 * n + 33 + max(n, bl(n) + 1) + max(1, n - 1)
    )
    return (
        2**n
        + chunks
        + i * bl(b)
        + (2 * i - 1) * bl(b + 17)
        + bl(b + 17 + chunks)
        + registers
    )


def _three_x(n: int, p: str) -> int:
    """Guard residues, read cursor and the 2n + 1 keys, K a key's bits."""

    def key(i: int) -> int:
        return 2 * bl(2 ** (i - 1) * 3 ** (2 * i - 1)) + 1

    return (
        n * bl(len(p))
        + 3 * 2**n // 2
        + 2 * n
        + 16
        + bl(2 * n - 1)
        + 2 * key(2 * n + 1)
        + sum(key(i) + 3 for i in range(1, 2 * n + 2))
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
    "Piet++": (
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
    "BIO": (
        lambda n, _: (
            max(2 * n, 8)
            + sum(bl(10 * n - 8 + 3 * j) for j in range(2**n - 1))
            + bl(4 * 2**n + 10 * n + 37)
        ),
        True,
        (3, 5),
    ),
    "Dimensional": (
        lambda n, _: (
            sum(map(bl, range(2**n)))
            + 5 * 2**n
            + n * (n - 1) // 2
            + 4 * n
            + 6
            + bl(2 * 2**n + 20 * n + 40)
            + bl(2 * n - 1)
        ),
        True,
        (3, 4),
    ),
    "Forþ": (lambda n, _: (2 * n + 364) * 2**n + 43 * n + 2 * bl(n), False, (3, 5)),
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
    "Underload": (
        lambda n, p: (
            24 * len(p)
            + 120 * 2**n
            + 32 * n
            - 176
            + bl(2 * len(p) + 10 * 2**n + 6 * n - 14)
        ),
        False,
        (3, 6),
    ),
    "ROTfuck": (
        lambda n, p: (
            2 * 2**n
            + 5 * n
            + 35
            + bl(2080 * len(p))
            + bl(2 * 2**n + 6)
            + bl(len(p))
            + bl(n)
        ),
        False,
        (3, 4),
    ),
    "Painfuck": (
        lambda n, p: 2 * n + 5 + 3 * bl(n) + (n + 1) * bl(len(p)),
        False,
        (3, 6),
    ),
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
    "Fargo": (lambda _, p: 16 * (len(p) - 3) + bl(len(p)) + 11, False, (6,)),
    "FRACTRAN": (
        lambda n, _: n + 4 + sum(bl(p) + 1 for p in _primes(12 + n)[12:]),
        False,
        (7,),
    ),
    "Streetcode": (
        lambda n, _: (
            n * 2**n
            + 2 * n
            + 24
            + bl(52 + sum(max(51, 2 ** (k - 1) + 3) for k in range(1, n)))
            + 2 * bl(n)
        ),
        True,
        (6,),
    ),
    "Crement": (_crement, False, (3, 6)),
    "Inject": (_inject, True, (5,)),
    "Subleq": (_subleq, False, (3, 5)),
    "3x": (_three_x, False, (3, 5)),
    "Forbin": (_forbin, True, (3, 8)),
    "Algebraic Programming Language": (_apl, True, (3, 5)),
    "Decleq": (_decleq, True, (3, 4)),
    # Every word and register is below 3^10 < 2^16; measured ~394k bits.
    "Malbolge": (lambda n, _: 16 * 3**10 + 49 + bl(n), False, (2, 3)),
    # Task, then 3n + 6 frames, each one shared subterm and its depth.
    "Unlambda": (
        lambda n, p: (
            12 * len(p)
            + 60
            + (3 * n + 6) * (8 * len(p) + 24 + bl(3 * n + 6))
            + 9
            + bl(n)
        ),
        False,
        (2, 3),
    ),
    # A T-cell corridor and T - 1 answers at bl(x) + 2 bits each, the ant, ip.
    "A Painter Ant": (
        lambda n, p: 2 * (n + 1) * 2**n + 4 + bl(len("".join(p.split())) - 1),
        True,
        (3, 6),
    ),
    # Code, stack and store each near E, the expanded program, at most 95T - 80.
    "Smu": (
        lambda n, _: 24 * (95 * 2**n - 80) - 1214 + bl(95 * 2**n - 80) + bl(n),
        True,
        (2, 4),
    ),
    "AddSubJump": (_add_sub_jump, False, (3, 5)),
    "B-tapemark": (
        lambda n, _: (
            (4 * 2**n + 31 * n + 5) * (8 + bl(3 * 2**n + n + 3) + bl(9 * n + 3))
            + (2**n + 4 * n) * (10 + 2 * bl(8 * 2**n + 50 * n))
            + 4 * bl(8 * 2**n + 50 * n)
            + bl(n)
            + 12
        ),
        False,
        (3, 4),
    ),
    "Circuit Diagram": (lambda n, _: 9 * 2**n + 3 * n - 12, False, (3, 6)),
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


def _unlambda_chain(n: int) -> str:
    """X then a staircase, twice: the root binds X, then a chain of levels."""
    k = n - 2
    x = f"{random.Random(1).getrandbits(1 << k):0{1 << k}b}"

    def chain(flip: int) -> str:
        return str(flip) + "".join(
            str((j + flip) % 2) * (1 << (j - 1)) for j in range(1, k + 1)
        )

    return x + chain(0) + x + chain(1)


@pytest.mark.medium
def test_unlambda_workspace_is_not_linear() -> None:
    """Every 0-selected level keeps a copy of the share: peak/L grows with n."""
    formula = FORMULAS["Unlambda"][0]
    per_char = []
    for n in (5, 7):
        table = _unlambda_chain(n)
        program = esolangs.generate("Unlambda", table)
        row = 1 << (n - 2)  # inputs 0, 1, 0, ..., 0: down X's zero path
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        stdin = esolangs.encode_inputs("Unlambda", bits, truth_table=table)
        machine = make_vm("Unlambda", program, stdin=stdin)
        state = WrittenState(machine.snapshot())
        run_to_answer(machine, sample=state.sample)
        assert state.bits <= formula(n, program)
        per_char.append(state.bits / len(program))
    # Measured 7.58 then 16.60; a linear workspace would hold it flat.
    assert per_char[1] > 1.5 * per_char[0], per_char
