"""Boolean-function generator for Container."""

from itertools import count, pairwise

from esolangs.tools.forbin import (
    _forbin_name,
)
from esolangs.tools.helpers import _ASCII_ZERO, _validate_truth_table

#: The names Container gives its own meaning, which a generated container
#: may not take.  ``_forbin_name`` draws from a mixed-case alphabet and so
#: reaches ``T`` at index 45 and ``IN`` at 754 -- both inside the name count
#: of a wide table, so the collision is live rather than defensive.
_RESERVED = frozenset({"EXIT", "IN", "OUT", "PRINT", "T"})


_Names = dict[tuple[str, int, int], str]


def _allocate_names(uses: dict[tuple[str, int, int], int]) -> _Names:
    """Give the shortest free identifier to the most-referenced container.

    ``uses`` maps a container's key to how many times the emitted program
    spells its name, so the length saved is the reference count; ties break
    on the key, keeping the emission deterministic.
    """
    identifiers = (_forbin_name(index) for index in count())
    names: _Names = {}
    for key in sorted(uses, key=lambda key: (-uses[key], key)):
        name = next(identifiers)
        while name in _RESERVED:
            name = next(identifiers)
        names[key] = name
    return names


def _container_tree(truth_table: str, *, prune: bool = True) -> str:
    """Build a Container program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Container is a synchronous rule system: every tick each container's value
    becomes ``max(old + sum of deltas of satisfied ``X>=Y``/``X<=Y`` rules,
    0)``, the empty-named container reads a line of input into ``IN`` when it
    turns on, ``PRINT`` outputs ``OUT`` when it turns on, and ``EXIT`` halts
    when its value changes.  There is no per-tick conditional, so the
    generator timestamps everything with the tick counter ``T``:

    * The empty container pulses on even ticks ``0..2(n-1)`` (``+1 T>=2k``,
      ``-2 T>=2k+1``, ``+1 T>=2k+2``), reading one bit per pulse.
    * For each bit ``k``, two armed gates (65, dipping to 49; and 47, dipping
      to 48) make their ``IN`` comparisons hold for
      exactly the tick the bit is in ``IN``, testing bit ``k`` once.
    * A prefix survivor creates its two children while bit ``k`` is active;
      the mismatching child is cancelled in that same tick.  The parent then
      expires, so each tree edge costs constant work instead of retesting the
      whole prefix at every leaf.
    * A level whose halves agree is skipped (``prune=False`` keeps it): the
      node is born two higher per skipped level, so it still decays to 1 on
      its next tested bit.  The empty container still pulses ``n`` times, so
      an ignored input costs only its read; a constant is a lone root leaf.
    * At tick ``2n`` an output gate, resting above every leaf's birth value,
      dips to 1, so the surviving leaf adds its entry to ``OUT``; ``PRINT``
      fires and ``EXIT`` halts.

    The last block costs one line per leaf the table sends to 1, so a dense
    table is summed from its **zero** leaves instead: ``OUT`` starts at 49
    and each surviving zero leaf subtracts one, printing ``49 - S``.  The
    clamp at zero never bites, since the value stays at 48 or 49.  Worth up
    to 12.7% at ``n == 4`` (1356 characters down to 1184 for fifteen ones of
    sixteen, before pruning).
    """
    n = _validate_truth_table(truth_table)
    size = 2**n

    # A node is born at one depth and next tests a level (``n`` for a leaf).
    nodes: list[tuple[int, int, int, int]] = []  # (born, tests, lo, parent)

    def settle(depth: int, lo: int) -> int:
        """Return the first level at or below ``depth`` whose halves differ."""
        span = size >> depth
        while (
            prune
            and depth < n
            and truth_table[lo : lo + span // 2]
            == truth_table[lo + span // 2 : lo + span]
        ):
            depth += 1
            span //= 2
        return depth

    def grow(tests: int, lo: int, parent: int) -> None:
        """Add the two children of a node that tests level ``tests``."""
        half = size >> (tests + 1)
        for child_lo in (lo, lo + half):
            nodes.append((tests + 1, settle(tests + 1, child_lo), child_lo, parent))
            if nodes[-1][1] < n:
                grow(nodes[-1][1], child_lo, len(nodes) - 1)

    root_tests = settle(0, 0)
    if root_tests < n:
        grow(root_tests, 0, -1)
    # Emit by birth depth and row, as the unpruned tree did.  A constant
    # table's root is its only leaf; index -1 stands for the root.
    order = sorted(range(len(nodes)), key=lambda i: (nodes[i][0], nodes[i][2]))
    leaves = [i for i in order if nodes[i][1] == n] or [-1]
    ones = sum(truth_table[nodes[i][2] if i >= 0 else 0] == "1" for i in leaves)
    invert = ones > len(leaves) - ones
    wanted = "0" if invert else "1"
    answers = [i for i in leaves if truth_table[nodes[i][2] if i >= 0 else 0] == wanted]

    def key(i: int) -> tuple[str, int, int]:
        if i < 0:
            return ("root", 0, 0)
        born, _tests, lo, _parent = nodes[i]
        return ("node", born, lo >> (n - born))

    # Assign shortest names by how often each is spelt: a node twice, twice
    # per child and once if it adds to ``OUT``; a gate once, and once a test.
    uses: dict[tuple[str, int, int], int] = {key(-1): 6}
    for i in order:
        born, tests, _lo, _parent = nodes[i]
        uses[key(i)] = 6 if tests < n else 2
        gate_key = ("high" if key(i)[2] & 1 else "low", born - 1, 0)
        uses[gate_key] = uses.get(gate_key, 1) + 1
    for i in leaves:
        uses[key(i)] = 2 + (i in answers)
    uses[("output", 0, 0)] = 1 + len(answers)
    tested = sorted({k for side, k, _ in uses if side == "low"})

    names = _allocate_names(uses)

    root = names[("root", 0, 0)]
    output_gate = names[("output", 0, 0)]

    lines = ["T:", "+1 T>=T"]
    lines.append(":")  # the empty-named container reads input
    lines.append("+1 T>=0")
    lines.append("-2 T>=1")
    for k in range(1, n):
        lines.append(f"+2 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
    lines.append(f"+1 T>={2 * n}")
    lines.append("IN=50:")  # a value no real byte matches
    for k in tested:
        low = names[("low", k, 0)]
        high = names[("high", k, 0)]
        lines.append(f"{low}=65:")
        lines.append(f"-16 T>={2 * k}")
        lines.append(f"+32 T>={2 * k + 1}")
        lines.append(f"-16 T>={2 * k + 2}")
        lines.append(f"{high}=47:")
        lines.append(f"+1 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
        lines.append(f"+1 T>={2 * k + 2}")
    lines.append(f"{root}={2 + 2 * root_tests}:")
    lines.append(f"-1 {root}>=1")
    for i in order:
        born, tests, _lo, parent = nodes[i]
        child = names[key(i)]
        value = 2 + 2 * (tests - born)
        lines.append(f"{child}:")
        # The paired parent rules fire only while the parent is exactly 1.
        lines.append(f"+{value} {names[key(parent)]}>=1")
        lines.append(f"-{value} {names[key(parent)]}>=2")
        gate = names[("high" if key(i)[2] & 1 else "low", born - 1, 0)]
        mismatch = f"IN<={gate}" if key(i)[2] & 1 else f"IN>={gate}"
        lines.append(f"-{value} {mismatch}")
        lines.append(f"-1 {child}>=1")
    peak = max(2 + 2 * (n - (nodes[i][0] if i >= 0 else 0)) for i in leaves)
    rest = peak + 1 if peak > 2 else 2
    lines.append(f"{output_gate}={rest}:")
    lines.append(f"-{rest - 1} T>={2 * n - 1}")
    lines.append(f"+{rest - 1} T>={2 * n}")
    # OUT is 48 plus one ``+1`` per leaf the table sends to 1, so a dense
    # table pays for nearly every leaf.  Evaluating the *zero* leaves costs
    # one line each and starts from 49, subtracting: ``49 - S`` is the
    # complement, and since ``S`` is 0 or 1 the value stays at 48 or 49, so
    # the container's clamp at zero never bites.  Whichever leaf set is
    # smaller wins; ties keep the plain form.
    lines.append("OUT:")
    lines.append(f"+{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n}")
    lines.append(f"-{_ASCII_ZERO + 1 if invert else _ASCII_ZERO} T>={2 * n + 1}")
    delta = "-1" if invert else "+1"
    for i in sorted(answers, key=lambda i: nodes[i][2] if i >= 0 else 0):
        lines.append(f"{delta} {names[key(i)]}>={output_gate}")
    lines.append("PRINT:")
    lines.append(f"+1 T>={2 * n}")
    lines.append("EXIT=1:")
    lines.append(f"-1 T>={2 * n + 1}")
    return "\n".join(lines)


def _threshold_deltas(truth_table: str, n: int, *, mirror: bool) -> list[int]:
    """Return the step deltas of the table under one input-weight order.

    Input ``i`` carries weight ``2**i`` when ``mirror`` (so the row index is
    the bit-reversal of the table index) and ``2**(n-1-i)`` otherwise.  Entry
    ``r`` is ``row[r] - row[r-1]``, with entry 0 the base value, so the table
    is the prefix sum and only the nonzero entries cost a line.
    """

    def row(index: int) -> int:
        if mirror:
            index = int(f"{index:0{n}b}"[::-1], 2)
        return int(truth_table[index])

    values = [row(index) for index in range(2**n)]
    return [values[0], *(b - a for a, b in pairwise(values))]


def _container_threshold(truth_table: str) -> str:
    """Build a threshold-sum Container program for the given truth table.

    Halts in ``2n + 2`` ticks whatever the table, and costs one line per
    *step* in the table rather than one per row.

    Each input bit is latched into its own container; a one-tick gate dip
    then lets all ``n`` latches add their binary weights to a row counter in
    a single tick, the same ``value >= gate`` conjunction the tree uses.
    ``OUT`` is the prefix sum ``base + sum(d[r] for r if row >= r)``, one
    ``+-1 C>=r`` line per nonzero ``d``, every one firing in the single tick
    the counter is live.  Whichever of the two weight orders has fewer steps
    wins: the mirror turns a table that depends only on the last input
    (``"01" * 2**(n-1)``, every row a step) into one line.

    The predecessor packed the table into a single decimal literal and
    subtracted ten per tick, so its tick count scaled with that literal's
    *magnitude* -- measured 2.2e6 ticks at ``n == 3``, hence ~1e126 at
    ``n == 7``, which is not a program that can be run.
    """
    n = _validate_truth_table(truth_table)
    mirrored = _threshold_deltas(truth_table, n, mirror=True)
    plain = _threshold_deltas(truth_table, n, mirror=False)
    mirror = sum(map(bool, mirrored[1:])) < sum(map(bool, plain[1:]))
    deltas = mirrored if mirror else plain
    steps = [(row, delta) for row, delta in enumerate(deltas) if row and delta]

    # The counter is named once per step line and so dominates; the gate is
    # named once per input.  Assign the shortest names by actual frequency.
    uses: dict[tuple[str, int, int], int] = {
        ("count", 0, 0): 1 + len(steps),
        ("gate", 0, 0): 1 + n,
    }
    for bit in range(n):
        uses[("latch", bit, 0)] = 2
        uses[("window", bit, 0)] = 2
    names = _allocate_names(uses)
    counter = names[("count", 0, 0)]
    gate = names[("gate", 0, 0)]

    lines = ["T:", "+1 T>=T", ":", "+1 T>=0", "-2 T>=1"]
    for k in range(1, n):
        lines.extend((f"+2 T>={2 * k}", f"-2 T>={2 * k + 1}"))
    lines.append(f"+1 T>={2 * n}")  # cancels the pulse, so there is no n+1th read
    lines.append("IN=50:")  # a value no real byte matches

    # Window k is 49 for exactly the tick input k sits in IN and 65
    # otherwise, so ``IN>=window`` holds exactly when that bit is a one.
    for k in range(n):
        window = names[("window", k, 0)]
        lines.extend(
            (
                f"{window}=65:",
                f"-16 T>={2 * k}",
                f"+32 T>={2 * k + 1}",
                f"-16 T>={2 * k + 2}",
                f"{names[('latch', k, 0)]}:",
                f"+1 IN>={window}",
            )
        )

    # The gate rests at 2 and dips to 1 for tick ``2n`` alone, so a latch at
    # 1 clears it exactly then: the counter takes every weight in that one
    # tick and none after, and is live for tick ``2n + 1`` only.
    lines.extend(
        (
            f"{gate}=2:",
            f"-1 T>={2 * n - 1}",
            f"+2 T>={2 * n}",
            f"-1 T>={2 * n + 1}",
            f"{counter}:",
        )
    )
    for k in range(n):
        weight = 2**k if mirror else 2 ** (n - 1 - k)
        lines.append(f"+{weight} {names[('latch', k, 0)]}>={gate}")

    lines.append(f"OUT={_ASCII_ZERO + deltas[0]}:")
    lines.extend(f"{delta:+d} {counter}>={row}" for row, delta in steps)
    lines.extend(("PRINT:", f"+1 T>={2 * n + 1}", "EXIT=1:", f"-1 T>={2 * n + 1}"))
    return "\n".join(lines)


def container(truth_table: str) -> str:
    """Build a Container program, switching to the threshold-sum decoder."""
    n = _validate_truth_table(truth_table)
    if n <= 6:
        return _container_tree(truth_table)
    return _container_threshold(truth_table)
