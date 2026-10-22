"""Container Boolean program generator: a tick-timed tree, or a threshold sum.

The shorter of two programs ships.  In the tree, the empty container reads
one bit per pulse and a pruned, shared tree of containers survives bit by bit
to a leaf that adds its entry to ``OUT`` at tick ``2n`` (see
:func:`_container_tree`).  In the threshold sum, each bit latches into its own
container and one gate dip adds the binary weights to a row counter, so
``OUT`` is a prefix sum with one line per step in the table
(:func:`_container_threshold`, halting in ``2n + 2`` ticks).

Size:
    Tree up to 2**n lines in the worst case, threshold one line per table
    step; n=6 random 1847: 835 chars, n=10 parity: 2,241 chars.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import count, pairwise
from math import isqrt
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
from esolangs.generation.token_balance import CELL_ASPECT
from esolangs.generation.wrap import balance_score
from esolangs.languages.container.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: The names Container gives its own meaning, which a generated container
#: may not take.  The names draw from a mixed-case alphabet and so reach
#: ``T`` at index 45 and ``IN`` at 754 -- both inside the name count of a
#: wide table, so the collision is live rather than defensive.
_RESERVED = frozenset({"EXIT", "IN", "OUT", "PRINT", "T"})


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


class _TreePlanner:
    """Plan pruned nodes, shared parents, and opposite-side relays.

    The candidate levels, the canonical-copy maps and the plan under
    construction are shared by every step, so they live on ``self``
    instead of in closures over the enclosing function's locals.
    """

    def __init__(self, truth_table: str, n: int, *, prune: bool, share: bool) -> None:
        self.truth_table = truth_table
        self.n = n
        self.prune = prune
        self.share = share
        self.size = 2**n
        self.nodes: list[_Node] = []
        self.parents: dict[int, list[int]] = {}
        self.relays: dict[int, int] = {}
        self.levels: list[list[_Node]] = [[] for _ in range(n + 1)]
        self.ids = subtree_ids(truth_table) if share else []
        self.first: dict[tuple[int, int, int], int] = {}
        self.either: dict[tuple[int, int], int] = {}

    def _settle(self, depth: int, lo: int) -> int:
        """Return the first level whose halves differ."""
        span = self.size >> depth
        while (
            self.prune
            and depth < self.n
            and self.truth_table[lo : lo + span // 2]
            == self.truth_table[lo + span // 2 : lo + span]
        ):
            depth += 1
            span //= 2
        return depth

    def _children(self, tests: int, lo: int, parent: int) -> None:
        if tests < self.n:
            half = self.size >> (tests + 1)
            self.levels[tests + 1].extend(
                _Node(tests + 1, self._settle(tests + 1, row), row, parent)
                for row in (lo, lo + half)
            )

    def _slot(self, node: _Node) -> tuple[int, int, int] | None:
        if not self.share:
            return None
        block = node.lo >> (self.n - node.born)
        return (node.born, self.ids[node.born][block], block & 1)

    def _adopt(self, node: _Node) -> bool:
        """Record ``node`` unless it folds into an earlier copy.

        Return whether the node's children still need growing: a folded
        node never allocates descendants, and a relay's subtree is spent
        once by the copy it feeds.
        """
        slot = self._slot(node)
        if slot in self.first:
            self.parents[self.first[slot]].append(node.parent)
            return False
        i = len(self.nodes)
        self.nodes.append(node)
        self.parents[i] = [node.parent]
        if slot is not None:
            self.first[slot] = i
            identity = (node.born, slot[1])
            if identity in self.either and node.tests < self.n:
                self.relays[i] = self.either[identity]
                return False
            self.either.setdefault(identity, i)
        return True

    def build(self) -> _TreePlan:
        """Resolve copies before growing them, level by level."""
        root_tests = self._settle(0, 0)
        self._children(root_tests, 0, -1)
        # Birth depth and row choose the same canonical copy as the full tree.
        for level in self.levels:
            for node in sorted(level, key=lambda node: node.lo):
                if self._adopt(node):
                    self._children(node.tests, node.lo, len(self.nodes) - 1)
        return _TreePlan(root_tests, self.nodes, self.parents, self.relays)


def _container_plan(truth_table: str, n: int, *, prune: bool, share: bool) -> _TreePlan:
    """Plan pruned nodes, shared parents, and opposite-side relays."""
    return _TreePlanner(truth_table, n, prune=prune, share=share).build()


def _birth_value(born: int, tests: int) -> int:
    """Value a node is born with: 2, plus two per level it skips or has yet to test."""
    return 2 + 2 * (tests - born)


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
    clamp at zero never bites, since the value stays at 48 or 49.  Its share
    of the shipped program is largest on the OR class
    ([ablations.zero_leaf_inversion]).  A leaf that does not answer is never
    read, so
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
    return _TreeEmitter(truth_table, n, plan).build()


class _TreeEmitter:
    """Emit one planned tree, phase by phase.

    The plan, the leaf selection and the allocated names are read by
    every phase, so they live on ``self`` instead of being threaded
    through each emit helper.
    """

    def __init__(self, truth_table: str, n: int, plan: _TreePlan) -> None:
        self.truth_table = truth_table
        self.n = n
        self.nodes, self.root_tests = plan.nodes, plan.root_tests
        self.parents, self.relays = plan.parents, plan.relays
        self.fed: dict[int, list[int]] = {}
        for relay, target in self.relays.items():
            self.fed.setdefault(target, []).append(relay)
        self._select_leaves()
        self._allocate_names()

    def _row_of(self, i: int) -> int:
        # The root (-1) is a constant table's only leaf.
        return self.nodes[i].lo if i >= 0 else 0

    def _select_leaves(self) -> None:
        nodes, n, table = self.nodes, self.n, self.truth_table
        self.leaves = [i for i, node in enumerate(nodes) if node.tests == n] or [-1]
        ones = sum(table[self._row_of(i)] == "1" for i in self.leaves)
        self.invert = ones > len(self.leaves) - ones
        wanted = "0" if self.invert else "1"
        self.answers = {i for i in self.leaves if table[self._row_of(i)] == wanted}
        self.order = [
            i for i, node in enumerate(nodes) if node.tests < n or i in self.answers
        ]

    def _allocate_names(self) -> None:
        nodes, n = self.nodes, self.n
        identifiers = _free_names(_RESERVED)
        self.names = {i: next(identifiers) for i in [-1, *self.order]}
        keys = {
            (nodes[i].born - 1, (nodes[i].lo >> (n - nodes[i].born)) & 1)
            for i in self.order
        }
        self.gates = {key: next(identifiers) for key in sorted(keys)}
        self.root, self.output_gate = self.names[-1], next(identifiers)

    def _pulse_lines(self) -> list[str]:
        # A positive delta is spelt unsigned, as ``int`` reads it.
        lines = ["T:", "1 T>=T"]
        lines.append(":")  # the empty-named container reads input
        lines.append("1 T>=0")
        lines.append("-2 T>=1")
        for k in range(1, self.n):
            lines.append(f"2 T>={2 * k}")
            lines.append(f"-2 T>={2 * k + 1}")
        lines.append(f"1 T>={2 * self.n}")
        return lines

    def _gate_lines(self) -> list[str]:
        # IN starts at 0.  Only a child's mismatch rule reads it, and the
        # first read lands after tick 0, when every child is 0 and clamped.
        lines = ["IN:"]
        for (k, high), gate in self.gates.items():
            sign = 1 if high else -1
            lines.extend(
                (
                    f"{gate}={47 if high else 50}:",
                    f"{sign} T>={2 * k}",
                    f"{-2 * sign} T>={2 * k + 1}",
                    f"{sign} T>={2 * k + 2}",
                )
            )
        return lines

    def _root_lines(self) -> list[str]:
        lines = [f"{self.root}={2 + 2 * self.root_tests}:"]
        if self.root_tests < self.n:
            lines.append(f"-1 {self.root}>=1")
        return lines

    def _node_lines(self, i: int) -> list[str]:
        born, tests = self.nodes[i].born, self.nodes[i].tests
        child = self.names[i]
        value = _birth_value(born, tests)
        lines = [f"{child}:"]
        # The paired parent rules fire only while the parent is exactly 1,
        # and one parent at most is alive: the others are off the path.
        for parent in self.parents[i]:
            lines.append(f"{value} {self.names[parent]}>=1")
            lines.append(f"-{value} {self.names[parent]}>=2")
        high = (self.nodes[i].lo >> (self.n - born)) & 1
        gate = self.gates[born - 1, high]
        mismatch = f"{gate}>=IN" if high else f"IN>={gate}"
        lines.append(f"-{value} {mismatch}")
        if i in self.relays:  # alive one tick after its birth, then gone
            lines.append(f"-{value} {child}>=1")
            return lines
        # A relay is alive a tick late, so it feeds one less than a parent.
        for relay in self.fed.get(i, []):
            lines.append(f"{value - 1} {self.names[relay]}>=1")
        # Only a node that tests must decay, to be 1 when its bit is in
        # IN.  A leaf keeps its birth value, below the output gate's rest.
        if tests < self.n:
            lines.append(f"-1 {child}>=1")
        return lines

    def _output_lines(self) -> list[str]:
        n, nodes = self.n, self.nodes
        peak = max(_birth_value(nodes[i].born if i >= 0 else 0, n) for i in self.leaves)
        rest = peak + 1 if peak > 2 else 2
        # The gate is never restored: EXIT halts the tick after PRINT.
        lines = [f"{self.output_gate}={rest}:", f"-{rest - 1} T>={2 * n - 1}"]
        # Whichever leaf set is smaller wins; ties keep the plain form.  The
        # gate alone keeps OUT at its base until the printing tick.
        lines.append(f"OUT={_ASCII_ZERO + 1 if self.invert else _ASCII_ZERO}:")
        delta = "-1" if self.invert else "1"
        for i in sorted(self.answers, key=self._row_of):
            lines.append(f"{delta} {self.names[i]}>={self.output_gate}")
        lines.append("PRINT:")
        lines.append(f"1 T>={2 * n}")
        lines.append("EXIT=1:")
        lines.append(f"-1 T>={2 * n + 1}")
        return lines

    def build(self) -> str:
        """Assemble the phases in program order."""
        lines = self._pulse_lines()
        lines += self._gate_lines()
        lines += self._root_lines()
        for i in self.order:
            lines += self._node_lines(i)
        lines += self._output_lines()
        return "\n".join(lines)


def _threshold_deltas(truth_table: str) -> list[int]:
    """Return the step deltas of the table under the plain input-weight order.

    Input ``i`` carries weight ``2**(n-1-i)``.  Entry ``r`` is
    ``row[r] - row[r-1]``, with entry 0 the base value, so the table
    is the prefix sum and only the nonzero entries cost a line.
    """
    values = [int(bit) for bit in truth_table]
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
    the counter is live.  The deltas are taken in the plain weight order
    only: a mirrored (bit-reversed) order raced it until the 2026-10 audit
    priced it under the bar and falling with n, even on the two-block
    tilings it was kept for ([ablations.mirror_race]) (retirement candidate #12).
    """
    n = _validate_truth_table(truth_table)
    weights, truth_table = _threshold_weights(truth_table, n)
    deltas, steps = _threshold_steps(truth_table)

    identifiers = _free_names(_RESERVED)
    counter, gate = next(identifiers), next(identifiers)
    latches = [next(identifiers) for _ in range(n)]
    windows = [next(identifiers) for _ in range(n)]

    lines = _threshold_pulse_lines(n)
    lines += _threshold_window_lines(windows, latches, n)
    lines += _threshold_counter_lines(gate, counter, weights, latches, n)
    lines += _threshold_output_lines(counter, deltas, steps, n)
    return "\n".join(lines)


def _threshold_weights(truth_table: str, n: int) -> tuple[list[int], str]:
    """Return the input weights and the projected table."""
    # An ignored input is latched like any other but adds no weight, so the
    # steps are those of the table over the rest.  A constant keeps them all.
    weights, projected = input_weights(truth_table, n)
    if any(weights):
        truth_table = projected
    else:
        weights = [1 << (n - 1 - k) for k in range(n)]
    return weights, truth_table


def _threshold_steps(
    truth_table: str,
) -> tuple[list[int], list[tuple[int, int]]]:
    """Return the plain order's step deltas and their nonzero steps."""
    deltas = _threshold_deltas(truth_table)
    steps = [(row, delta) for row, delta in enumerate(deltas) if row and delta]
    return deltas, steps


def _threshold_pulse_lines(n: int) -> list[str]:
    """Return the tick pulse and the unmatched ``IN`` declaration."""
    lines = ["T:", "+1 T>=T", ":", "+1 T>=0", "-2 T>=1"]
    for k in range(1, n):
        lines.extend((f"+2 T>={2 * k}", f"-2 T>={2 * k + 1}"))
    lines.append(f"+1 T>={2 * n}")  # cancels the pulse, so there is no n+1th read
    lines.append("IN=50:")  # a value no real byte matches
    return lines


def _threshold_window_lines(
    windows: list[str], latches: list[str], n: int
) -> list[str]:
    """Return each input's window and the latch it feeds."""
    # Window k is 49 for exactly the tick input k sits in IN and 65
    # otherwise, so ``IN>=window`` holds exactly when that bit is a one.
    lines: list[str] = []
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
    return lines


def _threshold_counter_lines(
    gate: str,
    counter: str,
    weights: list[int],
    latches: list[str],
    n: int,
) -> list[str]:
    """Return the dipping gate, the counter and its weighted latch rules."""
    # The gate rests at 2 and dips to 1 for tick ``2n`` alone, so a latch at
    # 1 clears it exactly then: the counter takes every weight in that one
    # tick and none after, and is live for tick ``2n + 1`` only.
    lines = [
        f"{gate}=2:",
        f"-1 T>={2 * n - 1}",
        f"+2 T>={2 * n}",
        f"-1 T>={2 * n + 1}",
        f"{counter}:",
    ]
    for k, weight in enumerate(weights):
        if weight:
            lines.append(f"+{weight} {latches[k]}>={gate}")
    return lines


def _threshold_output_lines(
    counter: str, deltas: list[int], steps: list[tuple[int, int]], n: int
) -> list[str]:
    """Return ``OUT`` with its step rules, then ``PRINT`` and ``EXIT``."""
    lines = [f"OUT={_ASCII_ZERO + deltas[0]}:"]
    lines.extend(f"{delta:+d} {counter}>={row}" for row, delta in steps)
    lines.extend(("PRINT:", f"+1 T>={2 * n + 1}", "EXIT=1:", f"-1 T>={2 * n + 1}"))
    return lines


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
    # The tree wins constants, projections and structured tables, the
    # threshold most other tables from n=3: 41 of the 256 n=3 tables keep the
    # tree, ties included (it halts two ticks sooner).
    program = min(
        _container_tree(truth_table, share=True),
        _container_threshold(truth_table),
        key=len,
    )
    if width is None or grid_width(program) <= width:
        return program
    narrow = _narrow_rules(program, width)
    return min(
        narrow,
        _narrow_rules(_container_threshold(truth_table), width),
        key=lambda text: (grid_width(text), len(text)),
    )


def balance_container(table: str, default: str) -> str:
    """Return the squarest of the default and its narrowings at the square width."""
    programs = [default, _container_threshold(table)]
    # Narrowing at w costs no characters until a rule stops fitting, so the
    # square side is isqrt(CELL_ASPECT * characters); the threshold program
    # and the narrowest width are the named alternatives.
    side = isqrt(CELL_ASPECT * len(default))
    candidates = [
        _narrow_rules(program, width) for program in programs for width in (1, side)
    ]
    candidates.append(default)
    return min(candidates, key=balance_score)


LANGUAGE = Language(
    "Container",
    "container",
    category="variable_based",
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
    proof_execution=(execution, True, (3, 7)),
    proof_workspace=(workspace, False, (3, 7)),
)
