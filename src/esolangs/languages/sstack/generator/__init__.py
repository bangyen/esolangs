r"""SStack Boolean program generator: a decision tree of one-shot ifs.

Stacks ``b`` and ``c`` hold ``ord("1")`` and ``ord("0")``.  A node reads
its input onto empty ``a`` and runs ``[a\b/~a~ one][a\c/~a~ zero]``.
Popping before the child leaves ``a`` empty at its entry and exit; zero
differs from both ASCII constants, so the loop and other arm cannot run.
A leaf prints ``:b:`` or ``:c:``; a constant subtree reads its remaining inputs
onto ``d`` and prints once.  Repeated residuals defer through labels on stack
``e``, then run once after the prefix unwinds.  Six-bit labels preserve
workspace; inline text and 7n + 3 commands guard admission.  Binary banks
price every level before emitting one.  A last-level ``01`` node prints its
input byte, ``;a;:a:~a~``, not two arms.

Size:
    21 characters a node: O(T) size and build; n=10 random 1847: 13,658
    chars, n=12 random 1847: 53,351 chars, n=16 parity: 16,617 chars.

Decisions:
    Popping before descent is the one-shot loop skeleton every form
    shares, so it carries no ablation price; a pop-after variant changes
    the loop's semantics, not just its text.  Binary banks: a
    64-state n=16 control shrinks 23,897 -> 20,360 characters (-14.80%), with
    8,192 old/new native rows.
"""

from itertools import pairwise

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.shared_block import (
    BranchCost,
    ContinuationCost,
    add_cost,
    dispatch_cost,
    merge_cost,
    normal_cost,
    repeated_bank,
    repeated_block,
)
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.sstack.generator._binary import _PROLOGUE, best_binary_bank
from esolangs.languages.sstack.generator._walk import _Hooks, _TreeWalk
from esolangs.languages.sstack.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

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
    # Only the two same-level banks race ([ablations.multi_block_deferral]).
    banks = (repeated_bank(truth_table, ranked=False)[0], repeated_bank(truth_table)[0])
    for blocks in dict.fromkeys(banks):
        if len(blocks) > 1:
            result = _sstack_shared(truth_table, blocks)
            if result is not None:
                forms.append(result)
    admitted = min((program for program, cost in forms if cost <= 7 * n + 3), key=len)
    bank = best_binary_bank(truth_table, _sstack_tree, 7 * n + 3, len(admitted))
    return admitted if bank is None else bank[0]


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
    out = [_PROLOGUE]

    def hit(
        depth: int, key: int, _lo: int, _remaining: int, _context: object
    ) -> ContinuationCost[int] | None:
        if (depth, key) not in selected:
            return None
        target = selected[depth, key]
        out.append(f'"{target + 1}/e"')
        return ContinuationCost(1, target=target)

    def leaf(
        _depth: int, _key: int, lo: int, remaining: int, _context: object
    ) -> ContinuationCost[int]:
        out.append(";d;" * remaining + _LEAF[table[lo]])
        return ContinuationCost(remaining + 1)

    walk: _TreeWalk[ContinuationCost[int]] = _TreeWalk(
        ids,
        out.append,
        _Hooks(
            hit=hit,
            leaf=leaf,
            skipped=lambda child: ContinuationCost(1, (child,)),
            branched=lambda one, zero: ContinuationCost(6, (one, zero)),
            ident=lambda: ContinuationCost(3),
        ),
    )
    prefix = walk.walk(n, 0)
    stages = []
    for i, (depth, row) in enumerate(blocks):
        marker = f'"{i + 1}/b"'
        out.append(marker + "[e\\b/~e~~b~")
        del selected[depth, ids[depth][row >> (n - depth)]]
        body = walk.walk(n - depth, row)
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
    ids = subtree_ids(table)
    out = [_PROLOGUE]

    def hit(
        depth: int,
        key: int,
        _lo: int,
        remaining: int,
        defer: tuple[int, int] | None,
    ) -> BranchCost | None:
        """Price a jump to ``defer``'s shared body where the span recurs there."""
        if defer is None or depth != defer[0]:
            return None
        if key != ids[depth][defer[1] >> remaining]:
            return None
        out.append('"49/e"')
        return None, 1

    def leaf(
        _depth: int,
        _key: int,
        lo: int,
        remaining: int,
        _defer: tuple[int, int] | None,
    ) -> BranchCost:
        out.append(";d;" * remaining + _LEAF[table[lo]])
        return remaining + 1, None

    walk: _TreeWalk[BranchCost] = _TreeWalk(
        ids,
        out.append,
        _Hooks(
            hit=hit,
            leaf=leaf,
            skipped=lambda child: add_cost(child, 1),
            branched=lambda one, zero: add_cost(merge_cost(one, zero), 6),
            ident=lambda: (3, None),
        ),
    )
    cost = walk.walk(n, 0, shared)
    if shared is not None:
        depth, row = shared
        out.append("[e\\b/~e~")
        # The shared body itself is emitted inline: nothing defers inside it.
        body = walk.walk(n - depth, row, None)
        out.append("]")
        cost = dispatch_cost(cost, normal_cost(body) + 4, 1)
    return "".join(out), normal_cost(cost) + 2


LANGUAGE = Language(
    "SStack",
    "sstack",
    category="stack_based",
    boolean=sstack,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    # Whitespace is discarded anywhere, inside a token too.
    wrap=wrap_chars,
    proof_workspace=(workspace, True, (3, 6)),
)
