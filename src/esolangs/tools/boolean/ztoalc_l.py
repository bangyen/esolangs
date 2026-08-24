"""Boolean-function generator for Z-to-ALC (L variant).

The generator searches line-numbered programs for one whose runtime
behaviour matches the truth table, checking candidates with a small
simulator (:func:`_ztoalc_ok`) rather than constructing them directly.
"""

from esolangs.tools.boolean.helpers import _validate_truth_table

__all__ = ["ztoalc_l_boolean"]


def _ztoalc_ok(lines: dict[int, str], n: int, inputs: str, expected: str) -> bool:
    """Fast ZTOALC L simulator: True iff ``inputs`` prints ``expected`` once.

    Mirrors the interpreter's semantics exactly: the pointer follows the
    Collatz step (halving evens, ``3n+1`` odds) unless a ``jump`` fires,
    which advances the pointer by one.  A command line visited twice would
    re-execute (re-read, re-branch, or re-print), so any such revisit fails.
    """
    try:
        ptr = int(lines[0])
    except (KeyError, ValueError):
        return False
    var = [0] * n
    inp = list(inputs)
    out: list[str] = []
    visited: set[int] = set()
    steps = 0
    while ptr != 1:
        steps += 1
        if steps > 10**6:  # pragma: no cover - a pathological 10**6-step run
            return False
        index = ptr - 1
        ins = lines.get(index, "")
        if ins:
            if index in visited:
                return False
            visited.add(index)
            if ins.startswith("print"):
                out.append(chr(int(ins.split()[1])))
                if len(out) > 1:
                    return False
            elif ins.startswith("jump"):
                if var[int(ins.split()[2][1])] != 0:
                    ptr += 1
                    continue
            elif "=" in ins:
                if not inp:
                    return False
                var[int(ins.split()[0][1])] = ord(inp.pop(0))
            elif "-" in ins:
                var[int(ins.split()[0][1])] -= int(ins.split()[2])
        ptr = ptr // 2 if ptr % 2 == 0 else 3 * ptr + 1
    return len(out) == 1 and out[0] == expected


def _ztoalc_lines(table: str, n: int, b1: int) -> dict[int, str]:
    """Place the reads, normalizes, branches, and leaves for ``table``."""
    start = b1 * 4**n
    lines: dict[int, str] = {0: str(start)}
    for i in range(n):
        lines[start // 2 ** (2 * i) - 1] = f"x{i} = input"
        lines[start // 2 ** (2 * i + 1) - 1] = f"x{i} - 48"

    def build(combos: list[int], root: int, depth: int) -> None:
        results = {table[c] for c in combos}
        if len(results) == 1:
            lines[root - 1] = f"print {48 + int(results.pop())}"
            return
        lines[root - 1] = f"jump a x{depth}"
        bit = n - 1 - depth
        zero = [c for c in combos if not (c >> bit) & 1]
        one = [c for c in combos if (c >> bit) & 1]
        build(zero, root // 2, depth + 1)
        build(one, 3 * root + 4, depth + 1)

    build(list(range(2**n)), b1, 0)
    return lines


def _ztoalc_symmetric(table: str, n: int) -> list[str] | None:
    """Build a branch-free linear program for a popcount-symmetric table.

    If ``table[c]`` depends only on ``popcount(c)``, the result is computable
    without a decision tree: sum the normalized input bits into ``s``, look
    the result up in a small ``n + 1``-entry table, and print it.  Every
    line sits on the pure power-of-two descent from ``2**L``, so the
    trajectory never revisits a line and no placement search is needed.
    The program is ``2**L`` lines (``L`` commands), so it is huge but
    collision-free; returns ``None`` for non-symmetric tables.
    """
    value: dict[int, str] = {}
    for combo in range(2**n):
        count = bin(combo).count("1")
        if count in value and value[count] != table[combo]:
            return None
        value[count] = table[combo]
    cmds: list[str] = []
    for i in range(n):
        cmds.append(f"x{i} = input")
        cmds.append(f"x{i} - 48")
    cmds.append("s = 0")
    for i in range(n):
        cmds.append(f"s += x{i}")
    cmds.append(f"t = [{n + 1}]")
    for count in range(n + 1):
        if value.get(count, "0") == "1":
            cmds.append(f"t[{count}] = 1")
    cmds.append("r = t[s]")
    cmds.append("r + 48")
    cmds.append("print r")
    size = 2 ** len(cmds)
    if size > 2**22:  # pragma: no cover - would build >2**22 program lines
        return None
    prog = [""] * size
    prog[0] = str(size)
    for j, cmd in enumerate(cmds):
        prog[2 ** (len(cmds) - j) - 1] = cmd
    return prog


def ztoalc_l_boolean(truth_table: str) -> str:
    """Build a ZTOALC L program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    ZTOALC L's control flow is the Collatz trajectory of line 1, so the
    generator lays out a decision tree on `p * 2**k` descents: branching at
    an even root lets a zero bit continue the descent (the Collatz step
    halves it) while a one bit jumps to `root + 1`, whose Collatz step is
    `3 * root + 4`.  When `root` is a multiple of four that lands on another
    `4 * q`, so a `b1` divisible by four makes every branch child a clean
    descent by construction.  That is sufficient but not necessary, and the
    program is `b1 * 4**n` lines long, so every `b1` is tried in turn and
    the simulator is the sole gate: a smaller start that happens to place
    without a collision is kept, which is what keeps these programs as
    short as they are.  The reads and normalizations ride the initial
    `b1 * 4**n` descent.

    When the tree search finds no collision-free placement (dense tables
    like XOR4), a branch-free *linear* program is tried instead for
    popcount-symmetric tables: sum the bits and look the result up in a
    small table.  That program is guaranteed collision-free (a pure
    power-of-two descent) but huge (``2**L`` lines), so it is gated by a
    size limit and the generator raises :class:`ValueError` only for dense,
    non-symmetric tables past ``n == 3``.

    Verified exhaustively for every table at ``n <= 3`` and for structured
    and symmetric tables at ``n == 4``; all tests run the real interpreter.
    """
    n = _validate_truth_table(truth_table)
    # Every ``b1`` is tried, not just the multiples of four.  A one-branch
    # jumps to ``root + 1``, whose Collatz step is ``3 * root + 4`` -- a
    # multiple of four only when ``root`` is, so the ``b1 % 4 == 0`` family
    # is the one where every branch child is *constructively* another clean
    # ``4q`` descent.  That is sufficient, not necessary: a smaller start
    # outside it loses the guarantee but often still places without a
    # collision, and the simulator below is what decides either way.  Since
    # the program is ``b1 * 4**n`` lines long, those smaller starts are
    # worth having -- AND drops from 384 lines to 96.
    for b1 in range(1, 4000):
        lines = _ztoalc_lines(truth_table, n, b1)
        if all(
            _ztoalc_ok(
                lines,
                n,
                "".join(str((c >> (n - 1 - i)) & 1) for i in range(n)),
                truth_table[c],
            )
            for c in range(2**n)
        ):
            size = max(lines) + 1
            return "\n".join(lines.get(i, "") for i in range(size))
    linear = _ztoalc_symmetric(truth_table, n)
    if linear is not None:
        return "\n".join(linear)
    raise ValueError(
        "the ZTOALC L boolean generator found no collision-free placement for "
        f"this table at n == {n}",
    )
