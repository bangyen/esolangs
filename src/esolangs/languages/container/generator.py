"""Boolean-function generator for Container."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import count, pairwise
from string import ascii_letters
from typing import NamedTuple

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    grid_width,
    input_weights,
    short_name,
    subtree_ids,
)
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: The names Container gives its own meaning, which a generated container
#: may not take.  The names draw from a mixed-case alphabet and so reach
#: ``T`` at index 45 and ``IN`` at 754 -- both inside the name count of a
#: wide table, so the collision is live rather than defensive.
_RESERVED = frozenset({"EXIT", "IN", "OUT", "PRINT", "T"})

#: Largest ``n`` built as a tree; wider tables use the threshold sum.
_TREE_MAX_N = 6


def _free_names(taken: Iterable[str]) -> Iterator[str]:
    """Yield the shortest letter names not in ``taken``."""
    for index in count():
        name = short_name(index, ascii_letters)
        if name not in taken:
            yield name


class _Node(NamedTuple):
    """A node born at depth ``born``, next testing level ``tests`` (``n``: leaf)."""

    born: int
    tests: int
    lo: int
    parent: int


@dataclass
class _TreePlan:
    root_tests: int
    nodes: list[_Node]
    parents: dict[int, list[int]]
    relays: dict[int, int]


def _container_plan(truth_table: str, n: int, *, prune: bool, share: bool) -> _TreePlan:
    """Plan pruned nodes, shared parents, and opposite-side relays."""
    size = 2**n

    nodes: list[_Node] = []
    parents: dict[int, list[int]] = {}
    relays: dict[int, int] = {}
    levels: list[list[_Node]] = [[] for _ in range(n + 1)]
    ids = subtree_ids(truth_table) if share else []
    first: dict[tuple[int, int, int], int] = {}
    either: dict[tuple[int, int], int] = {}

    def settle(depth: int, lo: int) -> int:
        """Return the first level whose halves differ."""
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

    def children(tests: int, lo: int, parent: int) -> None:
        if tests < n:
            half = size >> (tests + 1)
            levels[tests + 1].extend(
                _Node(tests + 1, settle(tests + 1, row), row, parent)
                for row in (lo, lo + half)
            )

    root_tests = settle(0, 0)
    children(root_tests, 0, -1)
    # Resolve copies before growing them: folded nodes never allocate descendants.
    # Birth depth and row choose the same canonical copy as the full tree.
    for level in levels:
        for node in sorted(level, key=lambda node: node.lo):
            born, tests, lo, parent = node
            block = lo >> (n - born)
            slot = (born, ids[born][block], block & 1) if share else None
            if slot in first:
                parents[first[slot]].append(parent)
                continue
            i = len(nodes)
            nodes.append(node)
            parents[i] = [parent]
            if slot is not None:
                first[slot] = i
                identity = (born, slot[1])
                if identity in either and tests < n:
                    relays[i] = either[identity]
                    continue
                either.setdefault(identity, i)
            children(tests, lo, i)
    return _TreePlan(root_tests, nodes, parents, relays)


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
    parents, relays = plan.parents, plan.relays
    fed: dict[int, list[int]] = {}
    for relay, target in relays.items():
        fed.setdefault(target, []).append(relay)

    def row_of(i: int) -> int:  # the root (-1) is a constant table's only leaf
        return nodes[i].lo if i >= 0 else 0

    leaves = [i for i, node in enumerate(nodes) if node.tests == n] or [-1]
    ones = sum(truth_table[row_of(i)] == "1" for i in leaves)
    invert = ones > len(leaves) - ones
    wanted = "0" if invert else "1"
    answers = {i for i in leaves if truth_table[row_of(i)] == wanted}
    order = [i for i, node in enumerate(nodes) if node.tests < n or i in answers]

    identifiers = _free_names(_RESERVED)
    names = {i: next(identifiers) for i in [-1, *order]}
    keys = {
        (nodes[i].born - 1, (nodes[i].lo >> (n - nodes[i].born)) & 1) for i in order
    }
    gates = {key: next(identifiers) for key in sorted(keys)}
    root, output_gate = names[-1], next(identifiers)

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
    for (k, high), gate in gates.items():
        sign = 1 if high else -1
        lines.extend(
            (
                f"{gate}={47 if high else 50}:",
                f"{sign} T>={2 * k}",
                f"{-2 * sign} T>={2 * k + 1}",
                f"{sign} T>={2 * k + 2}",
            )
        )
    lines.append(f"{root}={2 + 2 * root_tests}:")
    if root_tests < n:
        lines.append(f"-1 {root}>=1")
    for i in order:
        born, tests = nodes[i].born, nodes[i].tests
        child = names[i]
        value = 2 + 2 * (tests - born)
        lines.append(f"{child}:")
        # The paired parent rules fire only while the parent is exactly 1,
        # and one parent at most is alive: the others are off the path.
        for parent in parents[i]:
            lines.append(f"{value} {names[parent]}>=1")
            lines.append(f"-{value} {names[parent]}>=2")
        high = (nodes[i].lo >> (n - born)) & 1
        gate = gates[born - 1, high]
        mismatch = f"{gate}>=IN" if high else f"IN>={gate}"
        lines.append(f"-{value} {mismatch}")
        if i in relays:  # alive one tick after its birth, then gone
            lines.append(f"-{value} {child}>=1")
            continue
        # A relay is alive a tick late, so it feeds one less than a parent.
        for relay in fed.get(i, []):
            lines.append(f"{value - 1} {names[relay]}>=1")
        # Only a node that tests must decay, to be 1 when its bit is in
        # IN.  A leaf keeps its birth value, below the output gate's rest.
        if tests < n:
            lines.append(f"-1 {child}>=1")
    peak = max(2 + 2 * (n - (nodes[i].born if i >= 0 else 0)) for i in leaves)
    rest = peak + 1 if peak > 2 else 2
    # The gate is never restored: EXIT halts the tick after PRINT.
    lines.append(f"{output_gate}={rest}:")
    lines.append(f"-{rest - 1} T>={2 * n - 1}")
    # Whichever leaf set is smaller wins; ties keep the plain form.  The
    # gate alone keeps OUT at its base until the printing tick.
    lines.append(f"OUT={_ASCII_ZERO + 1 if invert else _ASCII_ZERO}:")
    delta = "-1" if invert else "1"
    for i in sorted(answers, key=row_of):
        lines.append(f"{delta} {names[i]}>={output_gate}")
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

    identifiers = _free_names(_RESERVED)
    counter, gate = next(identifiers), next(identifiers)
    latches = [next(identifiers) for _ in range(n)]
    windows = [next(identifiers) for _ in range(n)]

    lines = ["T:", "+1 T>=T", ":", "+1 T>=0", "-2 T>=1"]
    for k in range(1, n):
        lines.extend((f"+2 T>={2 * k}", f"-2 T>={2 * k + 1}"))
    lines.append(f"+1 T>={2 * n}")  # cancels the pulse, so there is no n+1th read
    lines.append("IN=50:")  # a value no real byte matches

    # Window k is 49 for exactly the tick input k sits in IN and 65
    # otherwise, so ``IN>=window`` holds exactly when that bit is a one.
    for k in range(n):
        window = windows[k]
        lines.extend(
            (
                f"{window}=65:",
                f"-16 T>={2 * k}",
                f"+32 T>={2 * k + 1}",
                f"-16 T>={2 * k + 2}",
                f"{latches[k]}:",
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
            lines.append(f"+{weight} {latches[k]}>={gate}")

    lines.append(f"OUT={_ASCII_ZERO + deltas[0]}:")
    lines.extend(f"{delta:+d} {counter}>={row}" for row, delta in steps)
    lines.extend(("PRINT:", f"+1 T>={2 * n + 1}", "EXIT=1:", f"-1 T>={2 * n + 1}"))
    return "\n".join(lines)


def _narrow_rule_parts(program: str, width: int) -> list[str | tuple[int, str]]:
    """Reduce numeric conditions to factors, retaining deltas before their partition."""
    lines = program.splitlines()
    occupied = {
        line[:-1].split("=", 1)[0] for line in lines if line.endswith(":")
    } | _RESERVED
    identifiers = _free_names(occupied)
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
                constants[right] = next(identifiers)
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
    """Reduce numeric conditions to factors and partition deltas into complete rules."""
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
    if n <= _TREE_MAX_N:
        program = _container_tree(truth_table, share=True)
    else:
        program = _container_threshold(truth_table)
    if width is None or width <= 0 or grid_width(program) <= width:
        return program
    narrow = _narrow_rules(program, width)
    if n > _TREE_MAX_N:
        return narrow
    return min(
        narrow,
        _narrow_rules(_container_threshold(truth_table), width),
        key=lambda text: (grid_width(text), len(text)),
    )


def balance_container(table: str, default: str) -> str:
    """Compare rule-fit and decimal-delta budget transitions."""
    n = _validate_truth_table(table)
    span = grid_width(default)
    programs = [default]
    if n <= _TREE_MAX_N:
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
                key=lambda text: (grid_width(text), len(text)),
            )
        )
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Container",
    "container",
    category="other",
    boolean=container,
    split=True,
    contract=BooleanContract(
        note="Container prints the answer; module.run returns the EXIT code.",
        input_shape="char_stream",
    ),
    balance=balance_container,
    no_wrap="each line declares a container or one of its rules",
    # Wiki: the empty container sets IN "with EOF returning 0".
    eof="an exhausted read sets IN to the spec's 0",
)
