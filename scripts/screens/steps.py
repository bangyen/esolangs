"""Screen every boolean generator for execution-step upside at n=3.

The execution-time twin of ``input_reorder.py`` and ``transforms.py``: each
generator builds all 256 three-input tables once, and every row of each is
stepped to its answer with ``benchmark.py``'s counter (the ``commands``
field ``check_generator_sizes.py`` pins).  A table's cost is its steps
summed over its 8 rows, and every column is a lookup over those totals:
relabelling rows does not change their sum, so a flipped or permuted
table's total is the transformed program's.  A percentage is
``100 * (1 - sum(min)/sum(own))``, the minimum taken over:

``order``
    The 6 input orders, as ``input_reorder.py``.
``outneg``
    The table or its complement.
``inpol``
    The 8 input-polarity flips.
``npn``
    All three together (96 candidates).

A termination-answer language (123, ArrowQueue, Crement, Vandevelo)
answers by looping, so a looping row is charged the steps to its first
repeated state -- where the proof of the loop is complete -- found with
Brent's algorithm and a second pass for the loop's start; its halting
rows count to the halt, as everywhere else.  Line and Piet
are raster (no text generator) and A Painter Ant is not steppable, so
none of the three has a row.  A row still running at ``--cap`` steps
drops its table from every column, and the dropped count is printed.

Every figure is an upper bound, as the size screens' are: it charges
nothing for the inverter a negated build runs, or the rewiring a flip or
reorder needs.
"""

import argparse
import sys
from collections.abc import Callable
from itertools import permutations
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _build import TABLES, chosen
from benchmark import _bits, _commands

import esolangs
from esolangs.tools.helpers import permute_truth_table
from esolangs.vm import VM

PERMS = list(permutations(range(3)))


def _machine(name: str, program: str, row: int) -> VM:
    """Return a fresh machine for one row, fed as ``benchmark._commands``."""
    bits = _bits(row, 3)
    if esolangs.describe(name)["parameterized"]:
        return esolangs.make_vm(name, esolangs.instantiate(name, program, bits), "")
    return esolangs.make_vm(name, program, esolangs.encode_inputs(name, bits))


def _to_verdict(name: str, program: str, row: int, cap: int) -> int | None:
    """Return a termination row's steps to its halt or first repeated state.

    Brent's algorithm finds a loop's length; a machine that length ahead
    of a fresh one then meets it where the loop starts, so the count is
    exact rather than Brent's up-to-twice overshoot.
    """
    machine = _machine(name, program, row)
    tortoise, power, length, steps = machine.snapshot(), 1, 0, 0
    while True:
        machine.step()
        steps += 1
        length += 1
        if machine.halted:
            return steps
        if steps > cap:
            return None
        if machine.snapshot() == tortoise:
            break
        if length == power:
            tortoise, power, length = machine.snapshot(), power * 2, 0
    ahead, behind = _machine(name, program, row), _machine(name, program, row)
    for _ in range(length):
        ahead.step()
    start = 0
    while ahead.snapshot() != behind.snapshot():
        ahead.step()
        behind.step()
        start += 1
    return start + length


def total(name: str, table: str, cap: int, *, loops: bool) -> int | None:
    """Return the steps summed over every row, or None if one hit ``cap``."""
    program = esolangs.generate(name, table)
    assert isinstance(program, str)
    steps = 0
    for row in range(8):
        if loops:
            count = _to_verdict(name, program, row, cap)
        else:
            count = _commands(name, program, table, row, cap)
        if count is None:
            return None
        steps += count
    return steps


def _negate(table: str) -> str:
    return table.translate(str.maketrans("01", "10"))


def _flip(table: str, mask: int) -> str:
    return "".join(table[row ^ mask] for row in range(len(table)))


def upside(steps: dict[str, int], candidates: Callable[[str], list[str]]) -> float:
    """Return the % of steps saved by building the cheapest candidate."""
    own = best = 0
    for table, count in steps.items():
        own += count
        best += min(steps.get(c, count) for c in candidates(table))
    return 100 * (1 - best / own)


Row = tuple[int, float, float, float, float, int, float]


def screen(name: str, cap: int) -> Row | None:
    """Return (steps, order %, outneg %, inpol %, npn %, dropped, seconds)."""
    start = perf_counter()
    loops = esolangs.describe(name)["answer_mode"] == "termination"
    steps: dict[str, int] = {}
    dropped = 0
    for table in TABLES:
        try:
            count = total(name, table, cap, loops=loops)
        except ValueError:
            continue
        if count is None:
            dropped += 1
        else:
            steps[table] = count
    if not steps:
        return None
    order = upside(steps, lambda t: [permute_truth_table(t, p) for p in PERMS])
    outneg = upside(steps, lambda t: [t, _negate(t)])
    inpol = upside(steps, lambda t: [_flip(t, mask) for mask in range(8)])
    npn = upside(
        steps,
        lambda t: [
            _flip(permute_truth_table(u, perm), mask)
            for u in (t, _negate(t))
            for perm in PERMS
            for mask in range(8)
        ],
    )
    elapsed = perf_counter() - start
    return sum(steps.values()), order, outneg, inpol, npn, dropped, elapsed


def main() -> None:
    """Screen the registry and print one row per language, best NPN first."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("languages", nargs="*", help="registry names (default all)")
    parser.add_argument("--cap", type=int, default=200_000, help="steps per row")
    args = parser.parse_args()
    rows = []
    for key, _gen in chosen(args.languages):
        if not esolangs.describe(key)["steppable_to_answer"]:
            continue
        result = screen(key, args.cap)
        if result is not None:
            rows.append((key, *result))
    rows.sort(key=lambda row: (-row[5], row[0]))
    print(
        f"{'language':<32}{'steps':>10}{'order%':>8}{'outneg%':>8}{'inpol%':>8}"
        f"{'npn%':>7}{'drop':>6}{'sec':>7}"
    )
    for key, count, order, outneg, inpol, npn, dropped, elapsed in rows:
        print(
            f"{key:<32}{count:>10}{order:>8.1f}{outneg:>8.1f}{inpol:>8.1f}"
            f"{npn:>7.1f}{dropped:>6}{elapsed:>7.1f}"
        )


if __name__ == "__main__":
    main()
