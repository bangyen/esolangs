"""Machine checks backing the Container wide-table proof.

Run:  just proofs   (or python tests/proofs/deep/container.py)

The ledger row is `finite lookup`, qualified "the table is the prefix sum of
its own steps, summed against a one-tick row counter".  That sentence is a
lemma, and this mechanizes it.

The split is the one the A Painter Ant checks use.  L1 and L2 are
*arithmetic* -- where a row lands in the prefix sum, and what the input
weights sum to -- so they reduce to closed forms checkable at every arity
rather than sampled.  L3 counts the pieces to check they compose.  L4 then
**executes** every row, which is possible at all only because the route halts
in ``2n + 2`` ticks: its predecessor packed the table into one decimal
literal and subtracted ten per tick, so its tick count scaled with the
literal's *magnitude* (measured 2.2e6 ticks at ``n == 3``, hence ~1e126 at
``n == 7``) and no arity it shipped at could be run.

Programs are built through :func:`_container_threshold` rather than
:func:`container`: the shipped entry point dispatches to the tree route at
``n <= 6``, and this is a proof about the wide route.  Calling the entry
point would silently check the wrong construction at exactly the small
arities that are cheap enough to enumerate.
"""

from __future__ import annotations

import random
import re
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.container import _Machine
from esolangs.tools.other import _container_threshold

#: Cost band; see ``__main__.py``. L1 enumerates every row of twelve arities
#: and L4 executes every row of six wide tables; 3.1s measured.  Weakening a
#: proof to fit a gate is the wrong trade.
BAND = "by-hand"
COST = 4.0

_ASCII_ZERO = 48
_STEP = re.compile(r"([+-]\d+) (\w+)>=(\d+)")
_WEIGHT = re.compile(r"\+(\d+) (\w+)>=(\w+)")


def parse(program: str) -> tuple[int, list[int], list[tuple[int, int]]]:
    """Return ``(base, weights, steps)`` read out of the *emitted* program.

    Reading the emitted text rather than recomputing the generator's rule is
    the point: a program whose lines disagreed with the rule would otherwise
    leave every lemma below green while computing the wrong function.
    ``weights`` is in input order, ``steps`` is ``(row, delta)``.
    """
    lines = program.splitlines()
    out_at = next(i for i, line in enumerate(lines) if line.startswith("OUT="))
    print_at = lines.index("PRINT:")
    count_at = max(i for i in range(out_at) if lines[i].endswith(":"))
    base = int(lines[out_at][len("OUT=") : -1]) - _ASCII_ZERO
    weights = []
    for line in lines[count_at + 1 : out_at]:
        match = _WEIGHT.fullmatch(line)
        assert match, f"not a weight line: {line!r}"
        weights.append(int(match[1]))
    steps = []
    for line in lines[out_at + 1 : print_at]:
        match = _STEP.fullmatch(line)
        assert match, f"not a step line: {line!r}"
        steps.append((int(match[3]), int(match[1])))
    return base, weights, steps


def row_of(index: int, weights: list[int], n: int) -> int:
    """The counter value the table's row ``index`` drives the program to."""
    bits = format(index, f"0{n}b")
    return sum(w for w, b in zip(weights, bits, strict=True) if b == "1")


def tables(n: int, count: int, seed: int) -> list[str]:
    """Structured corners plus random dense tables of arity ``n``."""
    size = 1 << n
    rng = random.Random(seed)
    out = ["0" * size, "1" * size, "1" + "0" * (size - 1), "0" * (size - 1) + "1"]
    out.append("01" * (size // 2))  # every row a step under the plain order
    while len(out) < count:
        out.append("".join(rng.choice("01") for _ in range(size)))
    return out


def check_l1(max_n: int = 12, per_arity: int = 40) -> list[str]:
    """L1: the prefix sum of the emitted steps is the table, at every row.

    ``OUT`` starts at the base and every ``+-1 C>=r`` line adds its delta
    exactly when the counter reaches ``r``, so what the program prints for
    counter value ``v`` is ``base + sum(d for r, d in steps if v >= r)``.
    That telescopes to the table, which is why the cost is one line per
    *step* rather than one per row -- and why the printed byte can never
    leave ``{48, 49}`` and meet the interpreter's clamp at zero.
    """
    lines = []
    for n in range(1, max_n + 1):
        checked = 0
        for table in tables(n, per_arity, seed=11 + n):
            base, weights, steps = parse(_container_threshold(table))
            assert base in (0, 1), f"n={n}: base {base} is not a bit"
            # The prefix sum is accumulated once over the counter's range,
            # not re-summed per row: the per-row form is quadratic in the
            # table and pushed this lemma past ten minutes at n=12.
            summed = [0] * (1 << n)
            summed[0] = base
            for step_row, delta in steps:
                summed[step_row] += delta
            for value in range(1, 1 << n):
                summed[value] += summed[value - 1]
            for index, bit in enumerate(table):
                value = summed[row_of(index, weights, n)]
                assert value == int(bit), (
                    f"n={n} row {index}: prefix sum {value} but table says {bit}"
                )
            checked += len(steps)
        lines.append(
            f"  n={n:2d}: {per_arity:3d} tables, every one of {1 << n:5d} rows "
            f"summed; {checked} step lines total"
        )
    return lines


def check_l2(max_n: int = 12) -> list[str]:
    """L2: the emitted weights are a place-value system, in either order.

    The generator emits one ``+w latch>=gate`` line per input and picks
    between weight ``2**(n-1-k)`` (the table index itself) and ``2**k`` (its
    bit-reversal), whichever spells fewer steps.  Either way the map from
    input vector to counter value must be a *bijection* onto ``0..2**n-1``,
    or two table rows would share a counter value and one of them would be
    wrong.  Both orders are checked at every row.
    """
    lines = []
    for n in range(1, max_n + 1):
        seen = set()
        for table in tables(n, 6, seed=3 + n):
            _base, weights, _steps = parse(_container_threshold(table))
            assert sorted(weights) == [1 << k for k in range(n)], (
                f"n={n}: weights {weights} are not the powers of two"
            )
            counters = {row_of(index, weights, n) for index in range(1 << n)}
            assert counters == set(range(1 << n)), f"n={n}: weights are not a bijection"
            seen.add(tuple(weights))
        lines.append(f"  n={n:2d}: all {1 << n:5d} rows distinct, {len(seen)} order(s)")
    return lines


def check_l3(max_n: int = 12) -> list[str]:
    """L3: the scaling families have the shape L1 and L2 assume.

    One window block, one latch and one weight line per input; the gate dips
    for tick ``2n`` alone, which is the single tick in which every latch adds
    its weight; and the read pulse is cancelled at ``2n`` so there is no
    ``n+1``th read.  Nothing else scales with ``n`` but the step lines.
    """
    lines = []
    for n in range(1, max_n + 1):
        table = tables(n, 6, seed=4 + n)[-1]
        emitted = _container_threshold(table).splitlines()
        _base, weights, steps = parse("\n".join(emitted))
        windows = sum(1 for line in emitted if line.endswith("=65:"))
        latches = sum(1 for line in emitted if " IN>=" in line)
        assert windows == n, f"n={n}: {windows} windows for {n} inputs"
        assert latches == n, f"n={n}: {latches} latches for {n} inputs"
        assert len(weights) == n, f"n={n}: {len(weights)} weight lines"
        assert f"-1 T>={2 * n - 1}" in emitted, f"n={n}: the gate never dips"
        assert f"+2 T>={2 * n}" in emitted, f"n={n}: the gate never lifts"
        assert f"+1 T>={2 * n}" in emitted, f"n={n}: an n+1th read is not cancelled"
        assert f"+1 T>={2 * n + 1}" in emitted, f"n={n}: PRINT fires at the wrong tick"
        assert len(steps) <= 1 << n, f"n={n}: more steps than rows"
        lines.append(
            f"  n={n:2d}: {windows} windows, {latches} latches, {len(weights)} "
            f"weights, gate dips at {2 * n}, {len(steps)} steps"
        )
    return lines


def check_l4(arities: tuple[int, ...] = (7, 8, 9)) -> list[str]:
    """L4: every row of a dense wide table runs, under a hard tick budget.

    The lemma the packed predecessor could not have.  Each run is capped at
    ``2n + 2`` ticks, so a construction that merely *converges* fails here
    instead of hanging the band; L1 through L3 are arithmetic about emitted
    text and cannot see a tick count at all.
    """
    lines = []
    for n in arities:
        budget = 2 * n + 2
        for table in tables(n, 6, seed=7 + n)[-2:]:
            program = _container_threshold(table)
            worst = 0
            for index in range(1 << n):
                bits = format(index, f"0{n}b")
                stream = ScriptedIO("".join(f"{b}\n" for b in bits))
                machine = _Machine(program.splitlines(), stream)
                ticks = 0
                while not machine.halted:
                    assert ticks < budget, f"n={n}: still running after {budget} ticks"
                    machine.step()
                    ticks += 1
                worst = max(worst, ticks)
                assert stream.getvalue() == table[index], (
                    f"n={n} row {index}: printed {stream.getvalue()!r}"
                )
            lines.append(
                f"  n={n:2d}: all {1 << n:5d} rows executed, {worst} ticks each, "
                f"{len(program)} characters"
            )
    return lines


def main() -> int:
    """Run every lemma and report."""
    print("L1  the prefix sum of the emitted steps is the table (all n, all rows)")
    print("\n".join(check_l1()))
    print("\nL2  the input weights are a bijection onto the rows (all n, all rows)")
    print("\n".join(check_l2()))
    print("\nL3  the scaling families have the shape L1 and L2 assume")
    print("\n".join(check_l3()))
    print("\nL4  every row of a dense wide table executes inside 2n+2 ticks")
    print("\n".join(check_l4()))
    print("\nall lemma checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
