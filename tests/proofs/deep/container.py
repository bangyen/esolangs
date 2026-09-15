"""Machine checks backing the Container packed-decoder proof.

Run:  just proofs   (or python tests/proofs/deep/container.py)

The ledger row is `finite lookup`, qualified "the reversed table is one decimal
literal divided by ten in a fixed two-bank network".  That sentence is already
a lemma, and this mechanizes it.

The split is the one the A Painter Ant checks use.  Everything that depends on
``n`` here is *arithmetic* -- where a row lands in a decimal literal (L1) and
what the input weights sum to (L2) -- so it reduces to a closed form that can
be checked at every arity rather than sampled.  Everything behavioural is
confined to a network whose text does not grow with ``n`` at all (L3), so
checking it once checks it for every arity.  L4 counts the pieces to check
they compose; it cannot execute them, and says why.

Programs are built through :func:`_container_packed` rather than
:func:`container`: the shipped entry point dispatches to the tree route at
``n <= 6``, and this is a proof about the packed route.  Calling the entry
point would silently check the wrong construction at exactly the small arities
that are cheap enough to enumerate.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.tools.other import _container_packed


def packed_literal(truth_table: str) -> str:
    """The decimal literal the generator emits, by its own rule."""
    return truth_table[::-1].lstrip("0") or "0"


def row_index(bits: str) -> int:
    """The table row an input vector selects, most-significant bit first."""
    return int(bits, 2)


def check_l1(max_n: int = 12, per_arity: int = 40) -> list[str]:
    """L1: row ``i`` of the table is decimal digit ``i`` of the literal.

    Reversing the spelling rather than converting bases is what puts row zero
    in the units place, and it is why the construction is one linear string
    pass.  The claim has to survive ``lstrip("0")``: stripping leading zeroes
    deletes high rows that are zero, and integer division must still report
    zero for them -- which it does, because a digit past the top of the number
    is zero and so was the row.
    """
    lines = []
    rng = random.Random(11)
    for n in range(1, max_n + 1):
        size = 1 << n
        tables = ["0" * size, "1" * size, "1" + "0" * (size - 1)]
        tables.append("0" * (size - 1) + "1")
        while len(tables) < per_arity:
            tables.append("".join(rng.choice("01") for _ in range(size)))
        stripped = 0
        for table in tables:
            value = int(packed_literal(table))
            for i, bit in enumerate(table):
                digit = (value // 10**i) % 10
                assert digit == int(bit), (
                    f"n={n} row {i}: literal digit {digit} but table says {bit}"
                )
            stripped += size - len(packed_literal(table))
        lines.append(
            f"  n={n:2d}: {len(tables):3d} tables, every one of {size:5d} rows "
            f"placed; {stripped} high zero rows stripped"
        )
    return lines


def check_l2(max_n: int = 12) -> list[str]:
    """L2: the emitted input weights sum to the row index, for every row.

    The generator emits ``+{2 ** (n - 1 - k)} IN>=L{k}`` once per input, so the
    counter it builds is a plain binary place-value sum.  One division has
    already exposed row zero as the units digit, so the number of divisions the
    counter must request is ``1 + index`` -- the ``COUNT=1`` seed is exactly
    that offset, and this checks the two agree at every row of every arity.
    """
    lines = []
    for n in range(1, max_n + 1):
        weights = [2 ** (n - 1 - k) for k in range(n)]
        assert sum(weights) == (1 << n) - 1, f"weights do not span n={n}"
        for index in range(1 << n):
            bits = format(index, f"0{n}b")
            built = sum(w for w, b in zip(weights, bits, strict=True) if b == "1")
            assert built == index, f"n={n}: weights build {built} for row {index}"
            assert 1 + built == 1 + row_index(bits)
        head = weights[:4]
        lines.append(f"  n={n:2d}: all {1 << n:5d} rows counted, weights {head}…")
    return lines


def _families(program: str) -> tuple[list[str], list[str]]:
    """Split the emitted lines into the arity-dependent ones and the rest.

    The arity-dependent text is exactly three families: the tick guards that
    sequence the reads, the per-input ``L{k}`` blocks, and the weight lines of
    the counter.  Everything else is the division network.
    """
    scaling, fixed = [], []
    for line in program.splitlines():
        arity_dependent = (
            line.startswith(("L", "+16", "-16", "+32", "A="))
            or "IN>=L" in line
            or "T>=" in line
        )
        if arity_dependent:
            scaling.append(line)
        else:
            fixed.append(line)
    return scaling, fixed


def check_l3(max_n: int = 11) -> list[str]:
    """L3: the division network is the same text at every arity.

    This is the lemma that makes the behavioural half finite.  The two banks,
    their work pulses and their one-tick continuations are emitted verbatim
    whatever ``n`` is, so a single reading of them covers every arity; only the
    literal, the tick guards and the per-input blocks scale, and those are the
    arithmetic L1 and L2 already cover.
    """
    lines = []
    baseline: list[str] | None = None
    rng = random.Random(3)
    for n in range(1, max_n + 1):
        # One generator per call, not one per character: seeding inside the
        # comprehension would rebuild the same Random for every element and
        # hand back a constant table, which is the one shape that cannot
        # discriminate anything here.
        table = "".join(rng.choice("01") for _ in range(1 << n))
        _scaling, fixed = _families(_container_packed(table))
        if baseline is None:
            baseline = fixed
        assert fixed == baseline, (
            f"the division network changed at n={n}: {set(fixed) ^ set(baseline)}"
        )
        lines.append(f"  n={n:2d}: {len(fixed)} fixed network lines, identical")
    assert baseline is not None
    lines.append(f"  the network is {len(baseline)} lines at every arity above")
    return lines


def check_l4(max_n: int = 11) -> list[str]:
    """L4: the scaling families have exactly the shape L1 and L2 assume.

    This is a structural composition check and not an executed one, for a
    reason worth stating plainly: **the packed route cannot be executed at any
    arity it is used at.**  A bank loses ten per tick, so dividing a ``2**n``
    digit literal down to the requested row takes a number of ticks
    proportional to the literal's *value*, not its length.  At ``n == 7`` that
    is a 128-digit dividend and the interpreter does not return; the arities
    small enough to run are all below the ``n <= 6`` crossover, where
    :func:`container` ships the tree instead.

    That is not a defect in the construction.  The ledger's claim is coverage
    and emitted size -- "O(T) source and construction work" -- and O(T) source
    is exactly what L1 through L3 establish.  Runtime is not claimed anywhere,
    and `docs/limitations.md` is where a runtime figure would belong.  So the
    composition is checked by counting the pieces instead: one read block and
    one weight line per input, and tick guards running to ``2n+2``.
    """
    lines = []
    rng = random.Random(4)
    for n in range(1, max_n + 1):
        table = "".join(rng.choice("01") for _ in range(1 << n))
        # Row 0 set, so the literal can never degenerate to the "0" fallback.
        # High zero rows do still strip -- that is L1's business, not L4's.
        table = "1" + table[1:]
        program = _container_packed(table)
        emitted = program.splitlines()
        blocks = sum(1 for k in range(n) if f"L{k}=65:" in emitted)
        weights = sum(1 for line in emitted if " IN>=L" in line)
        assert blocks == n, f"n={n}: {blocks} read blocks for {n} inputs"
        assert weights == n, f"n={n}: {weights} weight lines for {n} inputs"
        assert f"A={packed_literal(table)}:" in emitted, f"n={n}: literal not emitted"
        assert f"+1 T>={2 * n + 2}" in emitted, f"n={n}: tick guards stop early"
        lines.append(
            f"  n={n:2d}: {blocks} read blocks, {weights} weight lines, "
            f"guards to {2 * n + 2}, literal {len(packed_literal(table))} digits"
        )
    return lines


def main() -> int:
    """Run every lemma and report."""
    print("L1  the reversed literal places row i at decimal digit i (all n)")
    print("\n".join(check_l1()))
    print("\nL2  input weights sum to the row index (arithmetic, all rows)")
    print("\n".join(check_l2()))
    print("\nL3  the two-bank division network does not grow with n")
    print("\n".join(check_l3()))
    print("\nL4  the scaling families have the shape L1 and L2 assume")
    print("\n".join(check_l4()))
    print("\nall lemma checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
