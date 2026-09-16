"""Machine checks backing the %^2^-1 parameterized-contract wall.

Run:  just proofs   (or python tests/proofs/deep/pct_squared_minus_one.py)

The ledger row is `exception`, and `docs/proofs.md` proves that no `{Xi}`
template computes the suite's dense seventeen-input fixture: between two
placeholders the accumulator is the whole state, the reset leaves at most
6263 distinguishable accumulator classes, and the fixture forces more
distinct cofactors than that at every thirteen-input cut.

L1 is the class lemma, executed on the shipped interpreter: two deep values
congruent mod 256 print the same bytes under every word and end deep and
congruent, both over the limit, or equal -- and, as the positive control,
incongruent deep values do print differently.  L2 is the counting witness:
the minimum over all 2380 thirteen-input subsets of the number of distinct
four-input cofactors of ``_dense(17)``, computed exhaustively, against the
6263 bound.  L3 is the arithmetic that places the wall at seventeen: at
sixteen inputs no cut can exceed ``2**12`` classes.
"""

from __future__ import annotations

import random
import sys
from itertools import combinations
from operator import itemgetter
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.interpreters.io import IO
from esolangs.interpreters.register_based.pct_squared_minus_one import _Machine
from tests.tools.test_boolean_contract import _dense

#: Cost band; see ``__main__.py``.  L2 gathers 2380 cofactor tables of a
#: 131072-row fixture, ~8s; L1 runs 3000 words twice, under a second.
BAND = "by-hand"
COST = 9.0

LIMIT = 3003
#: In-window values plus deep residue classes mod 256.
CLASSES = 2 * LIMIT + 1 + 256
WITNESS_N, CUT = 17, 13


class _Capture(IO):
    """Collect what a run prints."""

    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []

    def print_char(self, char: str) -> None:
        self.out.append(char)

    def print_num(self, num: int) -> None:
        self.out.append(str(num))


def _run(word: str, acc: int) -> tuple[str, int]:
    """Run ``word`` from a preset accumulator; the output and final value."""
    io = _Capture()
    machine = _Machine(word, io)
    machine.state = (0, acc)
    while not machine.halted:
        machine.step()
    return "".join(io.out), machine.state[1]


def check_l1(words: int = 3000) -> list[str]:
    """L1: deep values congruent mod 256 are one class; incongruent are not."""
    rng = random.Random(3)
    for _ in range(words):
        word = "".join(rng.choice("siimp'e") for _ in range(rng.randint(1, 40)))
        x = -rng.randint(LIMIT + 1, 10**6)
        y = x - 256 * rng.randint(1, 1000)
        out_x, end_x = _run(word, x)
        out_y, end_y = _run(word, y)
        assert out_x == out_y, (word, x, y, out_x, out_y)
        together = (
            end_x < -LIMIT and end_y < -LIMIT and (end_x - end_y) % 256 == 0
        ) or ((end_x > LIMIT and end_y > LIMIT) or end_x == end_y)
        assert together, (word, x, y, end_x, end_y)
    differ = 0
    controls = 2000
    for _ in range(controls):
        word = "".join(rng.choice("sim") for _ in range(rng.randint(0, 5))) + "e"
        x = -rng.randint(LIMIT + 1, 10**6)
        y = x - rng.randint(1, 255)
        differ += _run(word, x)[0] != _run(word, y)[0]
    assert differ > controls // 2, differ
    for acc in (-LIMIT - 1, -5000, -123456):
        for command in "siimp'":
            mid = _run(command, acc)[1]
            end = _run(command + "s", acc)[1]
            assert mid < acc or mid == 0 or (command == "p" and mid == -acc), (
                acc,
                command,
            )
            assert end < acc or end == -2, (acc, command, end)
    return [
        f"  {words} random words: every congruent deep pair printed the same and "
        "stayed one class",
        f"  positive control: {differ} of {controls} incongruent deep pairs printed "
        "differently",
        "  every command from a deep value leaves it deeper or destroys it",
    ]


def cofactor_minimum(table: bytes, n: int, k: int) -> tuple[int, tuple[int, ...]]:
    """The fewest distinct ``(n-k)``-input cofactors over every ``k``-subset."""
    worst: tuple[int, tuple[int, ...]] | None = None
    for subset in combinations(range(n), k):
        # Input ``i`` is bit ``n - 1 - i`` of the row index.
        offsets = [0]
        for i in subset:
            offsets += [o + (1 << (n - 1 - i)) for o in offsets]
        bases = [0]
        for i in range(n):
            if i not in subset:
                bases += [b + (1 << (n - 1 - i)) for b in bases]
        gather = itemgetter(*offsets)
        distinct = len(set(zip(*(gather(table[b:]) for b in bases), strict=True)))
        if worst is None or distinct < worst[0]:
            worst = (distinct, subset)
    assert worst is not None
    return worst


def check_l2() -> list[str]:
    """L2: every thirteen-input cut of ``_dense(17)`` exceeds the class bound."""
    table = _dense(WITNESS_N).encode()
    fewest, subset = cofactor_minimum(table, WITNESS_N, CUT)
    assert fewest > CLASSES, (fewest, subset)
    return [
        f"  _dense({WITNESS_N}): {fewest} distinct cofactors at the worst of the "
        f"{sum(1 for _ in combinations(range(WITNESS_N), CUT))} cuts, "
        f"subset {subset}, against {CLASSES} classes",
    ]


def check_l3() -> list[str]:
    """L3: the count cannot bite below seventeen inputs."""
    for n in range(1, WITNESS_N):
        ceiling = max(min(2**k, 2 ** (2 ** (n - k))) for k in range(n + 1))
        assert ceiling <= CLASSES, (n, ceiling)
    return [
        f"  through {WITNESS_N - 1} inputs every cut has at most "
        f"{max(min(2**k, 2 ** (2 ** (16 - k))) for k in range(17))} classes"
    ]


def main() -> int:
    """Run the lemmas and print the report."""
    lemmas = (
        ("L1  deep residues are one class", check_l1),
        ("L2  the seventeen-input witness", check_l2),
        ("L3  no witness below seventeen", check_l3),
    )
    for title, check in lemmas:
        print(title)
        for line in check():
            print(line)
    print(f"\n{CLASSES} classes; the wall stands at {WITNESS_N} inputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
