r"""Boolean program generator for SStack: a decision tree of one-shot ifs.

Stacks ``b`` and ``c`` hold ``ord("1")`` and ``ord("0")``.  A node reads
its input onto empty ``a`` and runs ``[a\b/~a~ one][a\c/~a~ zero]``.
Popping before the child leaves ``a`` empty at its entry and exit; zero
differs from both ASCII constants, so the loop and other arm cannot run.
A leaf prints ``:b:`` or ``:c:``; a constant subtree reads its remaining inputs
onto ``d`` and prints once.  21 characters a node: O(T) size and build.
Repeated residuals defer through labels on stack e, then run once after
the prefix unwinds. Six-bit labels preserve workspace; inline text and
7n + 3 commands guard admission. Popping before descent reduces three dense
n=16 tables from mean 1,345,047 to 955,490 characters (-28.96%); both builds
executed five rows per table within the command and workspace bounds.
Binary banks price every level before emitting one; a 64-state n=16 control
shrinks 23,897 -> 20,360 characters (-14.80%), with 8,192 old/new native rows.
"""

from itertools import pairwise

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _validate_truth_table,
    constant_span_test,
    subtree_ids,
)
from esolangs.tools.shared_block import (
    BranchCost,
    ContinuationCost,
    add_cost,
    dispatch_cost,
    merge_cost,
    normal_cost,
    repeated_bank,
    repeated_block,
    repeated_blocks,
    repeated_definitions,
)
from esolangs.tools.sstack._binary import best_binary_bank
from esolangs.tools.sstack._ternary import best_ternary_bank
from esolangs.tools.wrap import wrap_chars

_PROLOGUE = '"49/b""48/c"'
_LEAF = {"0": ":c:", "1": ":b:"}


def sstack(truth_table: str) -> str:
    """Build an SStack program printing ``truth_table[row]`` for the inputs."""
    plain, _ = _sstack_tree(truth_table)
    shared = repeated_block(truth_table)
    if shared is None:
        return plain
    candidate, commands = _sstack_tree(truth_table, shared)
    n = _validate_truth_table(truth_table)
    forms = [(plain, 0), (candidate, commands)]
    branching = repeated_definitions(truth_table, branching_only=True)
    branched = set(branching)
    levels = repeated_blocks(truth_table)
    definitions = (
        repeated_definitions(truth_table),
        branching,
        levels,
        tuple(block for block in levels if block in branched),
        repeated_bank(truth_table, ranked=False)[0],
        repeated_bank(truth_table)[0],
    )
    for blocks in dict.fromkeys(definitions):
        if len(blocks) > 1:
            result = _sstack_shared(truth_table, blocks)
            if result is not None:
                forms.append(result)
    admitted = min((program for program, cost in forms if cost <= 7 * n + 3), key=len)
    bank = best_binary_bank(truth_table, _sstack_tree, 7 * n + 3, len(admitted))
    if bank is not None:
        admitted = bank[0]
    ternary = best_ternary_bank(truth_table, _sstack_tree, 7 * n + 3, len(admitted))
    return admitted if ternary is None else ternary[0]


def _sstack_shared(
    table: str, blocks: tuple[tuple[int, int], ...]
) -> tuple[str, int] | None:
    """Defer residuals through six-bit labels; return text and command bound."""
    n = _validate_truth_table(table)
    # A deferral leaves at least two input bytes unread: their twelve bits
    # pay for a six-bit pending label and the temporary comparison label.
    # Completed nonconstant paths retire a tested byte before dispatch;
    # the label alone fits its six bits. Fixed-width labels keep work O(T).
    if not 1 <= len(blocks) <= 63:
        return None
    depths = [depth for depth, _ in blocks]
    if any(depth < 0 or depth > n - 2 for depth in depths) or any(
        left > right for left, right in pairwise(depths)
    ):
        raise ValueError("definitions need increasing depths and two unread inputs")
    if any(
        row < 0 or row % (1 << (n - depth)) or row + (1 << (n - depth)) > len(table)
        for depth, row in blocks
    ):
        raise ValueError("definitions must name aligned table spans")
    ids = subtree_ids(table)
    selected = {
        (depth, ids[depth][row >> (n - depth)]): i
        for i, (depth, row) in enumerate(blocks)
    }
    if len(selected) != len(blocks) or any(key < 2 for _, key in selected):
        raise ValueError("definitions must name distinct nonconstant residuals")
    constant = constant_span_test(table)
    out = [_PROLOGUE]

    def build(remaining: int, lo: int, hi: int) -> ContinuationCost:
        depth = n - remaining
        key = (depth, ids[depth][lo >> remaining])
        if key in selected:
            target = selected[key]
            out.append(f'"{target + 1}/e"')
            return ContinuationCost(1, target=target)
        if constant(lo, hi):
            out.append(";d;" * remaining + _LEAF[table[lo]])
            return ContinuationCost(remaining + 1)
        mid = (lo + hi) // 2
        below = ids[depth + 1]
        if below[lo >> (remaining - 1)] == below[mid >> (remaining - 1)]:
            out.append(";d;")
            return ContinuationCost(1, (build(remaining - 1, lo, mid),))
        out.append(";a;[a\\b/~a~")
        one = build(remaining - 1, mid, hi)
        out.append("][a\\c/~a~")
        zero = build(remaining - 1, lo, mid)
        out.append("]")
        return ContinuationCost(6, (one, zero))

    prefix = build(n, 0, len(table))
    stages = []
    for i, (depth, row) in enumerate(blocks):
        marker = f'"{i + 1}/b"'
        out.append(marker + "[e\\b/~e~~b~")
        del selected[depth, ids[depth][row >> (n - depth)]]
        body = build(n - depth, row, row + (1 << (n - depth)))
        out.append(marker + "]~b~")
        stages.append((i, body))
    tails: dict[int | None, int] = {None: 0}
    for i, body in reversed(stages):
        active = 8 + body.evaluate(tails)
        tails = {target: cost + 3 for target, cost in tails.items()}
        tails[i] = active
    return "".join(out), 2 + prefix.evaluate(tails)


def _sstack_tree(table: str, shared: tuple[int, int] | None = None) -> tuple[str, int]:
    """Emit a tree and the maximum commands of normal and deferred paths."""
    n = _validate_truth_table(table)
    constant = constant_span_test(table)
    ids = subtree_ids(table)
    out = [_PROLOGUE]

    def build(remaining: int, lo: int, hi: int) -> BranchCost:
        depth = n - remaining
        if (
            shared is not None
            and depth == shared[0]
            and ids[depth][lo >> remaining] == ids[depth][shared[1] >> remaining]
        ):
            out.append('"49/e"')
            return None, 1
        if constant(lo, hi):
            out.append(";d;" * remaining + _LEAF[table[lo]])
            return remaining + 1, None
        mid = (lo + hi) // 2
        below = ids[depth + 1]
        if below[lo >> (remaining - 1)] == below[mid >> (remaining - 1)]:
            out.append(";d;")
            return add_cost(build(remaining - 1, lo, mid), 1)
        out.append(";a;[a\\b/~a~")
        one = build(remaining - 1, mid, hi)
        out.append("][a\\c/~a~")
        zero = build(remaining - 1, lo, mid)
        out.append("]")
        return add_cost(merge_cost(one, zero), 6)

    cost = build(n, 0, len(table))
    if shared is not None:
        depth, row = shared
        out.append("[e\\b/~e~")
        shared = None
        body = build(n - depth, row, row + (1 << (n - depth)))
        out.append("]")
        cost = dispatch_cost(cost, normal_cost(body) + 4, 1)
    return "".join(out), normal_cost(cost) + 2


LANGUAGE = Language(
    "SStack",
    "stack_based.sstack",
    boolean=sstack,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    # Whitespace is discarded anywhere, inside a token too.
    wrap=wrap_chars,
)
