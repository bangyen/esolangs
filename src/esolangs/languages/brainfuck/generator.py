"""brainfuck Boolean program generator: a flag-guarded tree or an affine stream.

Input bits sit at cells ``2i`` with flags at ``2i+1``; branches clear both and
one final print reads the result.  Equal sibling halves merge; repeated
residuals use one unused flag per level and emit once in depth order within
the command bound.  A bank uses several unused descendant flags: a same-level
bank, or the union of the one-per-depth picks with the greatest bank, so
blocks at several depths defer.  Two-input banks use four-bit labels with a
retired input holding the high bit, consumed before the shared bodies
execute.  Affine tables stream through three cells instead, at most 66
commands per selected input.  An ignored input before the last kept one is
read bare into the next kept cell, whose read overwrites it.

Size:
    O(T) for dense tables, O(n) for affine ones; n=10 parity: 760 chars,
    n=12 parity: 902 chars, n=10 random 1847: 10,792 chars.

Decisions:
    Flags cut n=10 sparse from 2,646 to 754 chars; folding and shared output
    cut n=10 XOR from 77,939 to 18,495; the affine stream cut n=16 parity
    from 672,691 to 1,186.  An ignored input read bare into the next kept
    cell is 1.9% smaller at n=8 with one ignored, 6.7% with two; a trailing
    one keeps its subtract, as ASCII 48/49 breaks the Workspace bound and
    ``,[-]`` the execution bound (289 > 251 steps).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from esolangs.generation.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    affine_form,
    constant_span_test,
    decision_tree_body,
    essential_inputs,
    in_input_order,
    move_text,
    subtree_ids,
)
from esolangs.generation.shared_block import (
    ContinuationCost,
    _repeated_blocks,
    repeated_block,
)
from esolangs.generation.shared_flag import (
    flag_tree_body,
    shared_flag_tree,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language


class _PendingKey(NamedTuple):
    """Identify a deferred bank body: its decoder label and high-bit cell.

    ``code`` selects the shared body; ``free`` is the retired input cell
    holding the label's high marker, or None when the label needs none.
    """

    code: int
    free: int | None


#: A priced bank prefix whose deferred continuations are pending keys.
_BankCost = ContinuationCost[_PendingKey]


class _BankPlan(NamedTuple):
    """Read-only inputs every bank phase reads: layout, labels and words."""

    n: int
    depth: int
    ids: list[list[int]]
    constant: Callable[[int, int], bool]
    flags: tuple[int, ...]
    result: int
    selected: dict[int, int]
    completed_one: int
    high_bit: int
    table: str
    unwritten: set[int]
    words: dict[int, str]


@dataclass
class _BankState:
    """The bank's emitted text so far, changed only by its named transitions.

    ``count`` is always the length of the joined ``out`` text, ``pos`` is
    always the cell the head rests on, and ``targets`` records each
    deferred body once, in the order its prefix first priced it.
    """

    out: list[str]
    count: int
    pos: int
    targets: dict[_PendingKey, tuple[int, int | None]]

    def emit(self, code: str) -> None:
        """Append emitted text and account its length."""
        self.out.append(code)
        self.count += len(code)

    def move_to(self, target: int) -> None:
        """Emit the run reaching ``target`` and move the head there."""
        self.emit(move_text(self.pos, target, ">", "<"))
        self.pos = target

    def drain(self, source: int, target: int) -> None:
        """Emit a ``[-]``-style transfer of ``source`` into ``target``."""
        self.move_to(source)
        self.emit("[-")
        self.move_to(target)
        self.emit("+")
        self.move_to(source)
        self.emit("]")

    def clear(self, plan: _BankPlan, cell: int) -> int:
        """Clear ``cell`` and return its command price."""
        self.move_to(cell)
        self.emit("[-]")
        return 1 if cell in plan.unwritten else 3

    def inline(self, plan: _BankPlan, word: str) -> int:
        """Emit a shared body for ``word``; return its command count.

        Each word is its own definition: defer its greatest repeat, so a
        nested body shares like a top-level one.  Zero-constant elision
        stays off -- its price is not the bank's price model.
        """
        code, commands = flag_tree_body(
            word,
            tuple(range(plan.depth, plan.n)),
            self.pos,
            plan.result,
            shared=repeated_block(word),
            fold_zero=False,
        )
        self.emit(code)
        self.pos = plan.result
        return commands

    def register_target(self, code: int, free: int | None = None) -> _PendingKey:
        """Record a deferred body and return its key."""
        key = _PendingKey(code, free)
        self.targets[key] = (code, free)
        return key


def _split[Branch](
    state: _BankState,
    bit: int,
    one: Callable[[], Branch],
    zero: Callable[[], Branch],
) -> tuple[Branch, int, Branch, int]:
    """Emit both guarded arms; return their bodies and path overheads.

    The type parameter is real: the bank prices tree prefixes with
    ``Branch`` as ``_BankCost`` and decoder subtrees with ``Branch`` as
    ``dict[int, int]``, sharing one guarded-arm shape.
    """
    beginning = state.count
    flag = bit + 1
    state.move_to(flag)
    state.emit("+")
    state.move_to(bit)
    zero_entry = state.count - beginning + 1
    state.emit("[-")
    state.move_to(flag)
    state.emit("-")
    one_entry = state.count - beginning
    one_body = one()
    finish = state.count
    state.move_to(bit)
    state.emit("]")
    one_finish = state.count - finish
    zero_start = state.count
    state.move_to(flag)
    state.emit("[-")
    one_finish += state.count - zero_start - 1
    zero_entry += state.count - zero_start
    zero_body = zero()
    finish = state.count
    state.move_to(flag)
    state.emit("]")
    return (
        one_body,
        one_entry + one_finish,
        zero_body,
        zero_entry + state.count - finish,
    )


def _leaf_cost(
    state: _BankState,
    plan: _BankPlan,
    lo: int,
    hi: int,
    free: int | None,
    beginning: int,
    sub_id: int,
) -> _BankCost:
    """Price a bank prefix that has reached the suffix depth."""
    code = plan.selected.get(sub_id)
    if code is not None and (not (code & plan.high_bit) or free is not None):
        cells = (*plan.flags, plan.result, free)
        for bit, cell in enumerate(cells):
            if code & (1 << bit):
                if cell is None:
                    raise ValueError("a high marker needs a retired input")
                state.move_to(cell)
                state.emit("+")
        return _BankCost(
            state.count - beginning,
            target=state.register_target(code, free if code & plan.high_bit else None),
        )
    commands = state.inline(plan, plan.table[lo:hi])
    if plan.constant(lo, hi):
        return _BankCost(
            commands,
            target=state.register_target(
                plan.completed_one if plan.table[lo] == "1" else 0
            ),
        )
    return _BankCost(
        commands,
        (
            _BankCost(0, target=state.register_target(0)),
            _BankCost(0, target=state.register_target(plan.completed_one)),
        ),
    )


def _constant_cost(
    state: _BankState, plan: _BankPlan, i: int, lo: int, beginning: int
) -> _BankCost:
    """Price a constant bank prefix, clearing its unvisited inputs."""
    if plan.table[lo] == "1":
        state.move_to(plan.result)
        state.emit("+")
    # Unvisited prefix bits must not masquerade as a high marker.
    adjustment = sum(state.clear(plan, 2 * level) - 3 for level in range(i, plan.depth))
    return _BankCost(
        state.count - beginning + adjustment,
        target=state.register_target(
            plan.completed_one if plan.table[lo] == "1" else 0
        ),
    )


def _node(
    state: _BankState, plan: _BankPlan, i: int, lo: int, hi: int, free: int | None
) -> _BankCost:
    """Price the bank prefix over ``[lo, hi)`` at tree level ``i``."""
    beginning = state.count
    sub_id = plan.ids[i][lo >> (plan.n - i)]
    if i == plan.depth:
        return _leaf_cost(state, plan, lo, hi, free, beginning, sub_id)
    if plan.constant(lo, hi):
        return _constant_cost(state, plan, i, lo, beginning)
    mid = (lo + hi) // 2
    zero_id, one_id = (
        plan.ids[i + 1][lo >> (plan.n - i - 1)],
        plan.ids[i + 1][mid >> (plan.n - i - 1)],
    )
    if zero_id == one_id:
        cleared = state.clear(plan, 2 * i)
        prefix = state.count - beginning + cleared - 3
        return _BankCost(prefix, (_node(state, plan, i + 1, lo, mid, 2 * i),))

    def one_branch() -> _BankCost:
        return _node(state, plan, i + 1, mid, hi, free)

    def zero_branch() -> _BankCost:
        return _node(state, plan, i + 1, lo, mid, 2 * i)

    # An active one guard still tests its cleared input when it closes.
    # Only a zero arm (whose one test has finished) or an ignored input
    # can hold the high marker. With neither available, keep this copy.
    one, one_cost, zero, zero_cost = _split(state, 2 * i, one_branch, zero_branch)
    return _BankCost(0, (_BankCost(one_cost, (one,)), _BankCost(zero_cost, (zero,))))


def _decode(
    state: _BankState,
    plan: _BankPlan,
    scratch: tuple[int, ...],
    bit: int,
    labels: tuple[int, ...],
) -> dict[int, int]:
    """Price each decoder label's shared body; return the label costs."""
    beginning = state.count
    if bit < 0:
        code = labels[0]
        if code == plan.completed_one:
            state.move_to(plan.result)
            state.emit("+")
        elif code != 0:
            return {code: state.inline(plan, plan.words[code])}
        return {code: state.count - beginning}
    groups = [
        tuple(code for code in labels if (code >> bit) & 1 == value) for value in (0, 1)
    ]
    cell = scratch[bit]
    if not groups[0] or not groups[1]:
        if groups[1]:
            state.move_to(cell)
            state.emit("-")
        flat = state.count - beginning
        return {
            label: flat + cost
            for label, cost in _decode(
                state, plan, scratch, bit - 1, groups[1] or groups[0]
            ).items()
        }

    def one_labels() -> dict[int, int]:
        return _decode(state, plan, scratch, bit - 1, groups[1])

    def zero_labels() -> dict[int, int]:
        return _decode(state, plan, scratch, bit - 1, groups[0])

    one, one_cost, zero, zero_cost = _split(state, cell, one_labels, zero_labels)
    return {
        **{label: cost + one_cost for label, cost in one.items()},
        **{label: cost + zero_cost for label, cost in zero.items()},
    }


def _make_bank_plan(table: str, remaining: int) -> _BankPlan | None:
    """Plan a suffix bank, or return None when this level cannot bank."""
    n = _validate_truth_table(table)
    depth = n - remaining
    if remaining < 1 or depth < 2:
        return None
    ids = subtree_ids(table)
    blocks = [(d, row) for d, row, _ in _repeated_blocks(table) if d == depth]
    if len(blocks) < 2:
        return None
    if remaining == 2:
        if len(blocks) > 14:
            raise ValueError("too many nonconstant two-input functions")
        planned_width = 4
        result_bit = 2
    else:
        planned_width = (len(blocks) + 1).bit_length()
        if planned_width > min(remaining + 2, depth):
            return None
        result_bit = min(remaining, planned_width - 1)
    completed_one = 1 << result_bit
    kept = essential_inputs(table, n)
    # Standard reads overwrite the next kept cell for ignored inputs. Their
    # own cells before the last kept input remain zero, so [-] costs one step.
    unwritten = {2 * i for i in range(kept[-1]) if i not in kept}
    codes = [value for value in range(1, 1 << planned_width) if value != completed_one]
    # Reserve R's digit for completed one. All other digits use unread flags;
    # only a word exceeding that capacity needs the retired-input high bit.
    return _BankPlan(
        n=n,
        depth=depth,
        ids=ids,
        constant=constant_span_test(table),
        flags=tuple(2 * (depth + i) + 1 for i in range(result_bit)),
        result=2 * n,
        selected={
            ids[depth][row >> remaining]: codes[i] for i, (_, row) in enumerate(blocks)
        },
        completed_one=completed_one,
        high_bit=1 << (remaining + 1),
        table=table,
        unwritten=unwritten,
        words={
            codes[i]: table[row : row + (1 << remaining)]
            for i, (_, row) in enumerate(blocks)
        },
    )


def _collect_high_marker(
    state: _BankState, plan: _BankPlan, *, collect: bool
) -> tuple[int, int]:
    """Drain any retired-input high marker into its collector cell.

    Return the collector cell and the price every tail pays for the
    collection, whether or not a marker was present.
    """
    collector = 2 * (plan.depth - 1) + 1
    collector_base = 0
    for i in range(plan.depth if collect else 0):
        collector_base += abs(state.pos - 2 * i) + 1
        state.drain(2 * i, collector)
    return collector, collector_base


def _transfer_label_bits(
    state: _BankState, plan: _BankPlan, collector: int, width: int
) -> tuple[tuple[int, ...], int, list[int]]:
    """Move the label metadata into decoder scratch cells.

    Return the scratch cells, the price every tail pays for the transfer,
    and the extra price a tail pays for each label bit it sets.
    """
    scratch = tuple(2 * (plan.depth - width + i) for i in range(width))
    metadata = (*plan.flags, plan.result, collector)[:width]
    transfer_base = 0
    transfer_active: list[int] = []
    for source, target in zip(metadata, scratch, strict=True):
        transfer_base += abs(state.pos - source) + 1
        transfer_active.append(2 * abs(source - target) + 3)
        state.drain(source, target)
    return scratch, transfer_base, transfer_active


def _price_bank(
    state: _BankState,
    plan: _BankPlan,
    prefix: _BankCost,
    decoder: dict[int, int],
    *,
    collector: int,
    collector_base: int,
    transfer_base: int,
    transfer_active: list[int],
) -> int:
    """Move to the result cell and price every deferred tail."""
    final_move = abs(plan.result - state.pos)
    state.move_to(plan.result)
    tails: dict[_PendingKey | None, int] = {
        key: collector_base
        + (2 * abs(collector - free) + 3 if free is not None else 0)
        + transfer_base
        + sum(active for bit, active in enumerate(transfer_active) if code & (1 << bit))
        + decoder[code]
        + final_move
        for key, (code, free) in state.targets.items()
    }
    return prefix.evaluate(tails)


def binary_bank(
    table: str, command_budget: int, *, remaining: int = 2
) -> tuple[str, int] | None:
    """Return a priced suffix bank after the standard identity-order reads."""
    plan = _make_bank_plan(table, remaining)
    if plan is None:
        return None
    state = _BankState(out=[], count=0, pos=2 * (plan.n - 1), targets={})
    # Phase 1: emit the prefix, registering each deferred body it prices.
    prefix = _node(state, plan, 0, 0, len(table), None)
    labels = tuple(sorted({code for code, _ in state.targets.values()}))
    width = max(labels).bit_length()
    # Phase 2: at most one retired input holds a high marker; every other
    # prefix input is zero. Collect it before its cells become decoder bits.
    collector, collector_base = _collect_high_marker(
        state, plan, collect=width == remaining + 2
    )
    # Phase 3: move the label bits into scratch, then decode shared bodies.
    scratch, transfer_base, transfer_active = _transfer_label_bits(
        state, plan, collector, width
    )
    decoder = _decode(state, plan, scratch, width - 1, labels)
    # Phase 4: price the whole bank through its deferred tails.
    commands = _price_bank(
        state,
        plan,
        prefix,
        decoder,
        collector=collector,
        collector_base=collector_base,
        transfer_base=transfer_base,
        transfer_active=transfer_active,
    )
    # The body keeps every value binary and every address lies in 0..2n.
    # Adding ASCII 48 only to R therefore preserves the 2n+6 tape-bit cap.
    if commands > command_budget:
        return None
    return "".join(state.out), commands


def larger_suffix_bank(table: str, command_budget: int) -> tuple[str, int] | None:
    """Emit the eligible non-default level with greatest repeated-span saving."""
    n = _validate_truth_table(table)
    groups: dict[int, tuple[int, int]] = {}
    for depth, _, saving in _repeated_blocks(table):
        count, score = groups.get(depth, (0, 0))
        groups[depth] = count + 1, score + saving
    best: tuple[int, int] | None = None
    for depth, (count, score) in groups.items():
        remaining = n - depth
        width = (count + 1).bit_length()
        if remaining != 2 and count >= 2 and width <= min(remaining + 2, depth):
            candidate = score, remaining
            if best is None or candidate > best:
                best = candidate
    # One scan chooses a level; no bodies are generated for losing levels.
    # Its prefix and disjoint representative spans total O(T). Actual text
    # and commands still decide admission alongside the existing candidates.
    return (
        None if best is None else binary_bank(table, command_budget, remaining=best[1])
    )


__all__ = ["bf_tree", "brainfuck"]


def brainfuck(truth_table: str) -> str:
    """Return a program for a binary, MSB-first ``2**n`` truth table."""
    return bf_tree(truth_table)


_RIGHT, _LEFT = ">", "<"


def bf_tree(truth_table: str) -> str:
    """Return a compact program, consuming every input unconditionally."""
    tree = in_input_order(truth_table, _bf_ordered)
    affine = _affine_stream(truth_table)
    return min((tree, affine), key=len) if affine is not None else tree


def _command_budget(n: int) -> int:
    """Return the command ceiling shared by the affine stream and shared body."""
    return 69 * n + 44


def _affine_stream(table: str) -> str | None:
    """Stream an admitted affine table through one bit and a toggle scratch."""
    n = _validate_truth_table(table)
    form = affine_form(table, n)
    if form is None:
        return None
    bias, coefficients = form
    # Input, accumulator, scratch occupy cells 0, 1, 2. Each selected read
    # costs at most 66 commands; a trailing ignored read must leave a bit
    # rather than ASCII beside the final ASCII output to retain workspace.
    parts = [">+<" if bias else ""]
    commands = 3 * bias + 50
    for i, coefficient in enumerate(coefficients):
        if coefficient:
            parts.append("," + "-" * _ASCII_ZERO + "[->>+<[->-<]>[-<+>]<<]")
            commands += 66
        elif i == n - 1:
            parts.append("," + "-" * _ASCII_ZERO)
            commands += 49
        else:
            parts.append(",")
            commands += 1
    if commands > _command_budget(n):
        return None
    parts.append(">" + "+" * _ASCII_ZERO + ".")
    return "".join(parts)


def _bf_ordered(truth_table: str, perm: tuple[int, ...], *, bank: bool = True) -> str:
    """Emit a permuted table; node i tests cell 2*perm[i], reads stay ordered."""
    n = _validate_truth_table(truth_table)

    # read bits b_i at cell 2i, leaving the flag cells (1, 3, ...) zero; an
    # ignored input is read into the next kept input's cell, which overwrites it
    kept = essential_inputs(truth_table, n)
    last = kept[-1] if kept else -1
    reads, pending = [], ""
    for i in range(n):
        if i in kept or i > last:
            reads.append(pending + "," + "-" * _ASCII_ZERO)
            pending = ""
        else:
            reads.append("")
            pending += ","
    header = (_RIGHT * 2).join(reads)
    cells = [header]
    pos = 2 * max(n - 1, 0)
    tree_start = pos

    # The tree itself.
    body, pos = decision_tree_body(truth_table, _RIGHT, _LEFT, perm, pos)
    cells.append(body)

    # A shared print pays the ASCII offset once rather than at every leaf.
    cells.append(move_text(pos, 2 * n, _RIGHT, _LEFT))
    cells.append("+" * _ASCII_ZERO)
    cells.append(".")
    plain = "".join(cells)
    # The body's share of `_command_budget`.
    budget = _command_budget(n) - len(header) - _ASCII_ZERO - 1
    bodies = []
    shared = shared_flag_tree(
        truth_table,
        perm,
        tree_start,
        2 * n,
        command_budget=budget,
    )
    if shared is not None and shared[1] <= budget:
        bodies.append(shared[0])
    if bank and perm == tuple(range(n)):
        # The banks save 0% on random tables (n=5..16) and on tiled cores below
        # n=14; on a core tiled to n=14 and n=16 binary_bank saves 14.8% and
        # 13.9% (256 two-input words), larger_suffix_bank 10.3% and 12.1%
        # (32 five-input words, 16 classes), against both banks off 18.1% / 15.9%.
        for banked in (
            binary_bank(truth_table, budget),
            larger_suffix_bank(truth_table, budget),
        ):
            if banked is not None:
                bodies.append(banked[0])
    for body in bodies:
        candidate = header + body + "+" * _ASCII_ZERO + "."
        if len(candidate) < len(plain):
            plain = candidate
    return plain


LANGUAGE = Language(
    "brainfuck",
    "brainfuck",
    category="tape_based",
    boolean=brainfuck,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_chars,
)
