"""Boolean-function generator for Container."""

from dataclasses import dataclass
from itertools import count, pairwise

from esolangs.tools.forbin import (
    _forbin_name,
)
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    input_weights,
    subtree_ids,
)

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


@dataclass
class _TreePlan:
    n: int
    root_tests: int
    nodes: list[tuple[int, int, int, int]]
    order: list[int]
    parents: dict[int, list[int]]
    relays: dict[int, int]

    def key(self, index: int) -> tuple[str, int, int]:
        if index < 0:
            return ("root", 0, 0)
        born, _tests, lo, _parent = self.nodes[index]
        return ("node", born, lo >> (self.n - born))


def _container_plan(truth_table: str, n: int, *, prune: bool, share: bool) -> _TreePlan:
    """Plan pruned nodes, shared parents, and opposite-side relays."""
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
    # ``parents[i]`` lists every node that gives birth to ``i``; a node
    # missing from it is folded or lies under a fold or a relay.  ``first``
    # holds the copy for a (depth, subtable, side) and ``either`` the first
    # side seen, which a node on the other side relays to.
    parents = {i: [nodes[i][3]] for i in order}
    relays: dict[int, int] = {}
    if share:
        ids = subtree_ids(truth_table)
        first: dict[tuple[int, int, int], int] = {}
        either: dict[tuple[int, int], int] = {}
        for i in order:
            born, tests, lo, parent = nodes[i]
            if parent >= 0 and (parent not in parents or parent in relays):
                del parents[i]  # inside a folded copy
                continue
            block = lo >> (n - born)
            slot = (born, ids[born][block], block & 1)
            if slot in first:
                parents[first[slot]].append(parent)
                del parents[i]
                continue
            first[slot] = i
            if (born, slot[1]) in either:
                if tests < n:
                    relays[i] = either[born, slot[1]]
            else:
                either[born, slot[1]] = i
        order = [i for i in order if i in parents]
    return _TreePlan(n, root_tests, nodes, order, parents, relays)


def _container_names(
    plan: _TreePlan, order: list[int], answers: list[int]
) -> tuple[_Names, list[int]]:
    """Allocate identifiers from emitted reference counts and return tested levels."""
    n, root_tests, nodes = plan.n, plan.root_tests, plan.nodes
    parents, relays, key = plan.parents, plan.relays, plan.key
    # Assign shortest names by how often each is spelt: a node once, once
    # more if it decays, twice per child it feeds and once if it adds to
    # ``OUT``; a gate once, and once a test.
    uses: dict[tuple[str, int, int], int] = {key(-1): 1 + (root_tests < n)}
    for i in order:
        born, tests, _lo, _parent = nodes[i]
        uses[key(i)] = uses.get(key(i), 0) + 1 + (tests < n) + (i in relays)
        for parent in parents[i]:
            uses[key(parent)] = uses.get(key(parent), 0) + 2
        gate_key = ("high" if key(i)[2] & 1 else "low", born - 1, 0)
        uses[gate_key] = uses.get(gate_key, 1) + 1
    for i in answers:
        uses[key(i)] += 1
    uses[("output", 0, 0)] = 1 + len(answers)
    tested = sorted({k for side, k, _ in uses if side in ("low", "high")})

    names = _allocate_names(uses)

    return names, tested


def _container_tree(
    truth_table: str, *, prune: bool = True, share: bool = False
) -> str:
    """Build a Container program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Container is a synchronous rule system: every tick each container's value
    becomes ``max(old + sum of deltas of satisfied ``X>=Y``/``X<=Y`` rules,
    0)``, the empty-named container reads a line of input into ``IN`` when it
    turns on, ``PRINT`` outputs ``OUT`` when it turns on, and ``EXIT`` halts
    when its value changes.  There is no per-tick conditional, so the
    generator timestamps everything with the tick counter ``T``:

    * The empty container pulses on even ticks ``0..2(n-1)`` (``1 T>=2k``,
      ``-2 T>=2k+1``, ``1 T>=2k+2``), reading one bit per pulse.
    * For each bit ``k``, two armed gates (50, dipping to 49; and 47, dipping
      to 48) make their ``IN`` comparisons hold for
      exactly the tick the bit is in ``IN``, testing bit ``k`` once.
    * A prefix survivor creates its two children while bit ``k`` is active;
      the mismatching child is cancelled in that same tick.  The parent then
      expires, so each tree edge costs constant work instead of retesting the
      whole prefix at every leaf.  A leaf never decays: it holds its birth
      value until the output gate reads it.
    * A level whose halves agree is skipped (``prune=False`` keeps it): the
      node is born two higher per skipped level, so it still decays to 1 on
      its next tested bit.  The empty container still pulses ``n`` times, so
      an ignored input costs only its read; a constant is a lone root leaf.
    * At tick ``2n`` an output gate, resting above every leaf's birth value,
      dips to 1, so the surviving leaf adds its entry to ``OUT`` (which holds
      48 from the start); ``PRINT`` fires and ``EXIT`` halts.

    The last block costs one line per leaf the table sends to 1, so a dense
    table is summed from its **zero** leaves instead: ``OUT`` starts at 49
    and each surviving zero leaf subtracts one, printing ``49 - S``.  The
    clamp at zero never bites, since the value stays at 48 or 49.  Worth up
    to 12.7% at ``n == 4`` (1356 characters down to 1184 for fifteen ones of
    sixteen, before pruning).  A leaf that does not answer is never read, so
    it is not emitted, and a gate no emitted child names is not declared.

    ``share`` folds a node into the first live node at its depth with the
    same subtable (``subtree_ids``): only one parent is ever alive, so the
    copy takes a pair of birth rules from each, and the folded subtree is
    not emitted.  That works on the copy's own side only, since a node's
    mismatch rule names its side's gate.  A folded node on the other side
    is a *relay* instead: born and cancelled like the node, it kills itself
    the tick after and feeds the copy one less, so the copy still decays to
    1 on its next tested bit and its subtree is spent once.
    """
    n = _validate_truth_table(truth_table)
    plan = _container_plan(truth_table, n, prune=prune, share=share)
    nodes, root_tests = plan.nodes, plan.root_tests
    order, parents, relays = plan.order, plan.parents, plan.relays
    fed: dict[int, list[int]] = {}
    for relay, target in relays.items():
        fed.setdefault(target, []).append(relay)
    leaves = [i for i in order if nodes[i][1] == n] or [-1]
    ones = sum(truth_table[nodes[i][2] if i >= 0 else 0] == "1" for i in leaves)
    invert = ones > len(leaves) - ones
    wanted = "0" if invert else "1"
    answers = [i for i in leaves if truth_table[nodes[i][2] if i >= 0 else 0] == wanted]
    order = [i for i in order if nodes[i][1] < n or i in answers]

    key = plan.key
    names, tested = _container_names(plan, order, answers)

    root = names[("root", 0, 0)]
    output_gate = names[("output", 0, 0)]

    # A positive delta is spelt unsigned, as ``int`` reads it.
    lines = ["T:", "1 T>=T"]
    lines.append(":")  # the empty-named container reads input
    lines.append("1 T>=0")
    lines.append("-2 T>=1")
    for k in range(1, n):
        lines.append(f"2 T>={2 * k}")
        lines.append(f"-2 T>={2 * k + 1}")
    lines.append(f"1 T>={2 * n}")
    # IN starts at 0.  Only a child's mismatch rule reads it, and the first
    # read lands after tick 0, when every child is still 0 and clamped.
    lines.append("IN:")
    for k in tested:
        # 50 is above every byte IN holds, and dips to 49 for one tick.
        if ("low", k, 0) in names:
            lines.append(f"{names[('low', k, 0)]}=50:")
            lines.append(f"-1 T>={2 * k}")
            lines.append(f"2 T>={2 * k + 1}")
            lines.append(f"-1 T>={2 * k + 2}")
        if ("high", k, 0) in names:
            lines.append(f"{names[('high', k, 0)]}=47:")
            lines.append(f"1 T>={2 * k}")
            lines.append(f"-2 T>={2 * k + 1}")
            lines.append(f"1 T>={2 * k + 2}")
    lines.append(f"{root}={2 + 2 * root_tests}:")
    if root_tests < n:
        lines.append(f"-1 {root}>=1")
    for i in order:
        born, tests, _lo, _parent = nodes[i]
        child = names[key(i)]
        value = 2 + 2 * (tests - born)
        lines.append(f"{child}:")
        # The paired parent rules fire only while the parent is exactly 1,
        # and one parent at most is alive: the others are off the path.
        for parent in parents[i]:
            lines.append(f"{value} {names[key(parent)]}>=1")
            lines.append(f"-{value} {names[key(parent)]}>=2")
        gate = names[("high" if key(i)[2] & 1 else "low", born - 1, 0)]
        mismatch = f"{gate}>=IN" if key(i)[2] & 1 else f"IN>={gate}"
        lines.append(f"-{value} {mismatch}")
        if i in relays:  # alive one tick after its birth, then gone
            lines.append(f"-{value} {child}>=1")
            continue
        # A relay is alive a tick late, so it feeds one less than a parent.
        for relay in fed.get(i, []):
            lines.append(f"{value - 1} {names[key(relay)]}>=1")
        # Only a node that tests must decay, to be 1 when its bit is in
        # IN.  A leaf keeps its birth value, below the output gate's rest.
        if tests < n:
            lines.append(f"-1 {child}>=1")
    peak = max(2 + 2 * (n - (nodes[i][0] if i >= 0 else 0)) for i in leaves)
    rest = peak + 1 if peak > 2 else 2
    # The gate is never restored: EXIT halts the tick after PRINT.
    lines.append(f"{output_gate}={rest}:")
    lines.append(f"-{rest - 1} T>={2 * n - 1}")
    # OUT is 48 plus one ``+1`` per leaf the table sends to 1, so a dense
    # table pays for nearly every leaf.  Evaluating the *zero* leaves costs
    # one line each and starts from 49, subtracting: ``49 - S`` is the
    # complement, and since ``S`` is 0 or 1 the value stays at 48 or 49, so
    # the container's clamp at zero never bites.  Whichever leaf set is
    # smaller wins; ties keep the plain form.  The gate alone keeps OUT at
    # its base until the printing tick.
    lines.append(f"OUT={_ASCII_ZERO + 1 if invert else _ASCII_ZERO}:")
    delta = "-1" if invert else "1"
    for i in sorted(answers, key=lambda i: nodes[i][2] if i >= 0 else 0):
        lines.append(f"{delta} {names[key(i)]}>={output_gate}")
    lines.append("PRINT:")
    lines.append(f"1 T>={2 * n}")
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
    # An ignored input is latched like any other but adds no weight, so the
    # steps are those of the table over the rest.  A constant keeps them all.
    weights, projected = input_weights(truth_table, n)
    if any(weights):
        truth_table = projected
    else:
        weights = [1 << (n - 1 - k) for k in range(n)]
    essential = sum(map(bool, weights))
    mirrored = _threshold_deltas(truth_table, essential, mirror=True)
    plain = _threshold_deltas(truth_table, essential, mirror=False)
    mirror = sum(map(bool, mirrored[1:])) < sum(map(bool, plain[1:]))
    deltas = mirrored if mirror else plain
    steps = [(row, delta) for row, delta in enumerate(deltas) if row and delta]

    # The counter is named once per step line and so dominates; the gate is
    # named once per input.  Assign the shortest names by actual frequency.
    uses: dict[tuple[str, int, int], int] = {
        ("count", 0, 0): 1 + len(steps),
        ("gate", 0, 0): 1 + essential,
    }
    for bit in range(n):
        uses[("latch", bit, 0)] = 1 + bool(weights[bit])
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
    for k, weight in enumerate(weights):
        if weight:
            # The mirror reverses the essential inputs' ranks.
            weight = (1 << (essential - 1)) // weight if mirror else weight
            lines.append(f"+{weight} {names[('latch', k, 0)]}>={gate}")

    lines.append(f"OUT={_ASCII_ZERO + deltas[0]}:")
    lines.extend(f"{delta:+d} {counter}>={row}" for row, delta in steps)
    lines.extend(("PRINT:", f"+1 T>={2 * n + 1}", "EXIT=1:", f"-1 T>={2 * n + 1}"))
    return "\n".join(lines)


def _narrow_rule_parts(program: str, width: int) -> list[str | tuple[int, str]]:
    """Factor numeric conditions, retaining deltas before their partition."""
    lines = program.splitlines()
    occupied = {
        line[:-1].split("=", 1)[0] for line in lines if line.endswith(":")
    } | _RESERVED
    identifiers = (_forbin_name(index) for index in count())
    constants: dict[str, str] = {}
    declarations: list[str] = []
    declared: set[str] = set()
    output: list[str | tuple[int, str]] = []
    for line in lines:
        if line.endswith(":"):
            output.append(line)
            continue
        delta_text, condition = line.split()
        delta = int(delta_text)
        operator = "<=" if "<=" in condition else ">="
        left, right = condition.split(operator)
        if len(f"{delta} {condition}") > width and right.isdecimal():
            if right not in constants:
                name = next(identifiers)
                while name in occupied:
                    name = next(identifiers)
                occupied.add(name)
                constants[right] = name
            name = constants[right]
            # ``Container<=Constant`` only: a named bound flips to ``>=``.
            replacement = f"{left}>={name}" if operator == ">=" else f"{name}>={left}"
            declaration = f"{name}={right}:"
            if max(len(declaration), len(f"{delta} {replacement}")) < len(line):
                condition = replacement
                if name not in declared:
                    declarations.append(declaration)
                    declared.add(name)
        output.append((delta, condition))
    return output + declarations


def _narrow_rules(program: str, width: int) -> str:
    """Factor numeric conditions and partition deltas into complete rules."""
    output: list[str] = []
    for part in _narrow_rule_parts(program, width):
        if isinstance(part, str):
            output.append(part)
            continue
        delta, condition = part
        # Splitting a delta under one condition leaves every synchronous tick equal.
        digits = max(1, width - len(condition) - 1 - (delta < 0))
        bound = 10 ** min(digits, len(str(abs(delta)))) - 1
        quotient, remainder = divmod(abs(delta), bound)
        sign = "-" if delta < 0 else ""
        output.extend(f"{sign}{bound} {condition}" for _ in range(quotient))
        if remainder:
            output.append(f"{sign}{remainder} {condition}")
    return "\n".join(output)


def container(truth_table: str, width: int | None = None) -> str:
    """Build Container rules; narrow widths factor constants and deltas."""
    n = _validate_truth_table(truth_table)
    if n <= 6:
        program = _container_tree(truth_table, share=True)
    else:
        program = _container_threshold(truth_table)
    if width is None or width <= 0 or max(map(len, program.splitlines())) <= width:
        return program
    narrow = _narrow_rules(program, width)
    if n > 6:
        return narrow
    return min(
        narrow,
        _narrow_rules(_container_threshold(truth_table), width),
        key=lambda text: (max(map(len, text.splitlines())), len(text)),
    )


def balance_container(table: str, default: str) -> str:
    """Compare rule-fit and decimal-delta budget transitions."""
    from esolangs.tools.wrap import balance_score

    n = _validate_truth_table(table)
    span = max(map(len, default.splitlines()))
    programs = [default]
    if n <= 6:
        programs.append(_container_threshold(table))
    thresholds = {1}
    for program in programs:
        # Constant names stay fixed between original rule-fit thresholds.
        boundaries = {1, span}
        boundaries.update(
            len(str(int(delta))) + 1 + len(condition)
            for line in program.splitlines()
            if not line.endswith(":")
            for delta, condition in [line.split()]
        )
        boundaries = {value for value in boundaries if value <= span}
        for lower, stop in pairwise(sorted(boundaries)):
            thresholds.add(lower)
            for part in _narrow_rule_parts(program, lower):
                if isinstance(part, str):
                    continue
                delta, condition = part
                # Within a naming regime only the permitted decimal digits
                # change a rule. One-digit deltas already apply at its start.
                overhead = len(condition) + 1 + (delta < 0)
                thresholds.update(
                    overhead + digits
                    for digits in range(2, len(str(abs(delta))) + 1)
                    if lower < overhead + digits < stop
                )
    candidates = [default]
    for width in thresholds:
        candidates.append(
            min(
                (_narrow_rules(program, width) for program in programs),
                key=lambda text: (max(map(len, text.splitlines())), len(text)),
            )
        )
    return min(candidates, key=balance_score)
