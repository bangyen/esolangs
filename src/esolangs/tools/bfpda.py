"""Boolean template generator for bfpda."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    constant_span_test,
    subtree_ids,
)
from esolangs.tools.shared_block import (
    BranchCost,
    add_cost,
    dispatch_cost,
    merge_cost,
    normal_cost,
    repeated_block,
)
from esolangs.tools.wrap import wrap_chars

__all__ = ["BFPDA_PAIR", "bfpda"]


BFPDA_PAIR = ("x", "@")


def bfpda(truth_table: str) -> str:
    """Return a BF-PDA template for a binary, MSB-first ``2**n`` truth table.

    The last input is tested first; every arm empties the stack so its ``]``
    exits. A shared residual returns a flag protected by zero sentinels,
    then runs once after the prefix. Two distinct quarter residuals can
    both share a binary classifier; inline text and the existing command
    bound guard admission. Characters outside @.<>[] are comments; the first
    marker is a bare @.
    """
    plain, _ = _bfpda_tree(truth_table)
    n = _validate_truth_table(truth_table)
    reflected = _reflected(truth_table, n)
    shared = repeated_block(reflected)
    candidates = [plain]
    if shared is not None:
        candidate, commands = _bfpda_tree(truth_table, shared)
        if commands <= 10 * n + 2:
            candidates.append(candidate)
    if n >= 4:
        span = 1 << (n - 2)
        blocks = tuple(
            dict.fromkeys(reflected[i : i + span] for i in range(0, 1 << n, span))
        )
        if len(blocks) == 2:
            candidate, commands = _bfpda_tree(
                truth_table, classes=(blocks[0], blocks[1])
            )
            if commands <= 10 * n + 2:
                candidates.append(candidate)
    return min(candidates, key=len)


def _reflected(table: str, n: int) -> str:
    """Put the last input first, as the stack tests it."""
    return "".join(table[int(f"{row:0{n}b}"[::-1], 2)] for row in range(1 << n))


def _bfpda_tree(
    table: str,
    shared: tuple[int, int] | None = None,
    *,
    classes: tuple[str, str] | None = None,
) -> tuple[str, int]:
    """Emit an inline tree or a sentinel-protected shared residual."""
    n = _validate_truth_table(table)

    # Marker then bit, per input in name order.
    head = "<".join(["@<" + TEMPLATE_CHAR] * n)

    def leaf(level: int, value: str) -> str:
        # ``left`` cells still hold untested inputs; a one stops on the bottom
        # marker and prints it (left == 0: only that marker remains).
        left = 2 * (n - level)
        if value == "0":
            return ">" * left + "."
        return ">" * (left - 1) + ".>" if left else "@.>"

    # The stack hands back the *last* input first: level ``i`` tests input
    # ``n - 1 - i``, row bit ``i``; bit-reversed, each subtree is a span.
    reflected = _reflected(table, n)
    constant = constant_span_test(reflected)
    ids = subtree_ids(reflected)
    pieces = [head]
    protected = shared is not None or classes is not None

    def node(i: int, lo: int, hi: int) -> BranchCost:
        if classes is not None and i == 2:
            code = "<@<" + ("@" if reflected[lo:hi] == classes[1] else "")
            pieces.append(code)
            return len(code), None
        if (
            shared is not None
            and i == shared[0]
            and ids[i][lo >> (n - i)] == ids[i][shared[1] >> (n - i)]
        ):
            pieces.append("<@")
            return None, 2
        if i == n or (classes is None and constant(lo, hi)):
            code = leaf(i, reflected[lo]) + ("<" if shared is not None else "")
            pieces.append(code)
            return len(code), None
        mid = (lo + hi) // 2
        below = ids[i + 1]
        if below[lo >> (n - i - 1)] == below[mid >> (n - i - 1)]:
            pieces.append(">>")
            return add_cost(node(i + 1, lo, mid), 2)
        pieces.append("[>>")
        one = node(i + 1, mid, hi)
        pieces.append("<<]>[>" if protected else "]>[>")
        zero = node(i + 1, lo, mid)
        pieces.append("<]>" if protected else "]")
        if not protected:
            return add_cost(merge_cost(add_cost(one, 3), add_cost(zero, 2)), 3)
        # Each child returns a flag above its remaining input stack. Two
        # zero sentinels suppress the other arm after a one-side return;
        # one zero closes a zero-side return, then the common pop exposes
        # the flag again. At depth >= 2 this stays below the input peak.
        return add_cost(merge_cost(add_cost(one, 5), add_cost(zero, 3)), 4)

    cost = node(0, 0, 1 << n)
    if classes is not None:
        span = 1 << (n - 2)
        rows = tuple(
            next(i for i in range(0, 1 << n, span) if reflected[i : i + span] == block)
            for block in classes
        )
        classes = None
        protected = False
        pieces.append("[>>")
        one = node(2, rows[1], rows[1] + (1 << (n - 2)))
        pieces.append("]>[>")
        zero = node(2, rows[0], rows[0] + (1 << (n - 2)))
        pieces.append("]")
        body = add_cost(merge_cost(add_cost(one, 3), add_cost(zero, 2)), 3)
        cost = normal_cost(cost) + normal_cost(body), None
    elif shared is not None:
        depth, row = shared
        pieces.append("[>")
        shared = None
        protected = False
        body = node(depth, row, row + (1 << (n - depth)))
        pieces.append("]")
        cost = dispatch_cost(cost, normal_cost(body) + 3, 1)
    return "".join(pieces), 4 * n - 1 + normal_cost(cost)


LANGUAGE = Language(
    "BF-PDA",
    "stack_based.bf_pda",
    boolean=bfpda,
    contract=BooleanContract(),
    wrap=wrap_chars,
    empty_program="BF-PDA program cannot be empty",
    example=Example(pair=BFPDA_PAIR),
)
