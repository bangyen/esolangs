"""Boolean-function generator for Eval.

Named ``eval_lang`` because the generator itself is called ``eval``, and a
module of that name reads as the builtin wherever it is imported.
"""

from functools import cache
from math import factorial

from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    permute_truth_table,
    read_at,
)

# Eval's two stacks and the ops that move values between them.  ``~`` swaps
# which stack is active, ``*`` reverses the active one, and ``=`` pops the
# active stack onto the other.  The pair is a spindle: moving values across
# reverses them, so composing the three reaches essentially any arrangement.
_EVAL_TREE_STACK, _EVAL_READ_STACK = 0, 1

#: How each input is set: stage the bit on the tree stack (``0`` pushes a
#: zero, the backtick a one), then ``=`` moves it to the input stack.  The
#: template spells each input as a run of :data:`TEMPLATE_CHAR` this wide.
EVAL_ZERO, EVAL_ONE = "0=", "`="
_EVAL_INPUT = TEMPLATE_CHAR * len(EVAL_ZERO)


# Longest op string worth building.  Costs run to roughly 3 characters per
# displaced input, and an arrangement that expensive has already lost to the
# folds it was meant to buy; the cap also bounds how deep any program can
# reach, which is what makes the construction below finite.
_EVAL_MAX_OPS = 16


# Reorder words, built not stored: skeletons over ``~``, ``*`` and
# ``=``-runs with ``~~``, ``**`` and adjacent ``=``-runs ruled out, run
# lengths pinned by conservation (``~`` parity fixes direction; out-runs
# and in-runs must balance at every prefix so the tree stack ends empty),
# enumerated by length then ``~`` < ``*`` < ``=``.
# The law over-approximates only (37255 words for 735 arrangements;
# first-claim-wins discards the rest), so nothing is lost, only re-spelled;
# byte-identical to the 735-entry catalog at n = 1..14.  Finite at every
# n: a word moves at most six values, so reach plateaus (620, 691, 717,
# 728, 733, 735 over n = 7..12).  ``test_reorder_catalog_matches_search``
# replays the old BFS.
_EVAL_OP_RANK = {"~": 0, "*": 1, "=": 2}


def _eval_skeletons(max_ops: int) -> list[str]:
    """Reorder-word skeletons, ``E`` marking an ``=``-run of unfixed length.

    Starts with ``~``; no ``~~``, ``**`` or adjacent runs, which shorter
    skeletons already spell.
    """
    out: list[str] = []

    def grow(skeleton: str, last: str, cost: int) -> None:
        if skeleton:
            out.append(skeleton)
        if cost >= max_ops:
            return
        for char in "~*E":
            if char == last and char != "E":
                continue
            if char == "E" and last == "E":
                continue
            if not skeleton and char != "~":
                continue
            grow(skeleton + char, char, cost + 1)

    grow("", "", 0)
    return out


def _eval_run_directions(skeleton: str) -> list[int]:
    """Which stack each ``E`` run pops from, by the ``~`` parity before it."""
    active = _EVAL_TREE_STACK
    directions: list[int] = []
    for char in skeleton:
        if char == "~":
            active = 1 - active
        elif char == "E":
            directions.append(active)
    return directions


def _eval_fill_runs(
    skeleton: str,
    directions: list[int],
    budget: int,
    words: set[str],
) -> None:
    """Add every word spelling ``skeleton`` whose runs balance within budget.

    Runs fill left to right against the cap; ``balance`` is out-mass minus
    in-mass and must land at zero.  The last run is an in-run whose length
    is forced to ``balance``, which cuts the walk from 1091320 calls to
    690617; the caller's skip takes it to 348053.
    """
    count = len(directions)
    last = count - 1

    def fill(index: int, spent: int, balance: int, runs: tuple[int, ...]) -> None:
        side = directions[index]
        remaining = count - index - 1
        ceiling = budget - spent - remaining
        if side == _EVAL_TREE_STACK:
            # An in-run can only carry back what is already parked.
            ceiling = min(ceiling, balance)
        if index == last:
            # The last run is an in-run of exactly ``balance``: anything
            # shorter leaves values stranded on the tree stack, anything
            # longer pops it empty.  A run still has to be non-empty and
            # still has to fit what the cap leaves.
            if 1 <= balance <= ceiling:
                parts = iter((*runs, balance))
                words.add(
                    "".join(
                        "=" * next(parts) if char == "E" else char for char in skeleton
                    )
                )
            return
        for length in range(1, ceiling + 1):
            shift = length if side == _EVAL_READ_STACK else -length
            fill(index + 1, spent + length, balance + shift, (*runs, length))

    fill(0, 0, 0, ())


@cache
def _eval_reorders(max_ops: int = _EVAL_MAX_OPS) -> tuple[str, ...]:
    """Every reorder word the cap admits, shortest first then ``~*=``."""
    words: set[str] = set()
    for skeleton in _eval_skeletons(max_ops):
        directions = _eval_run_directions(skeleton)
        if not directions:
            # No transfers: the only word worth emitting is a bare
            # reversal of the read stack; longer identity spellings are
            # discarded by the fold anyway.
            if skeleton == "~*~":
                words.add(skeleton)
            continue
        if directions[-1] == _EVAL_READ_STACK:
            # A final out-run leaves the balance positive (values parked),
            # so it spells no word; 32721 of 65535 skeletons.
            continue
        _eval_fill_runs(
            skeleton, directions, max_ops - (len(skeleton) - len(directions)), words
        )
    ordered = sorted(
        words, key=lambda word: (len(word), [_EVAL_OP_RANK[c] for c in word])
    )
    return ("", *ordered)


@cache
def _eval_stack_programs(n: int) -> dict[tuple[int, ...], str]:
    """Shortest ops rearranging the staged bits into each arrangement.

    Maps each input stack (bottom to top, by input index) to the ops
    producing it: every catalog program is replayed cheapest first and the
    first to reach an arrangement claims it.  Programs that underflow or
    leave the tree stack dirty are skipped; through ``n == 4`` the reachable
    arrangements are 1, 2, 6 and 24, and from ``n == 12`` all 735 programs
    claim distinct ones.

    **A runtime reorder, not a relabelling**: the input runs keep their
    places and the nodes name no input, so the arrangement alone decides
    which input a level tests.
    """
    reached: dict[tuple[int, ...], str] = {}
    # Arrangements are permutations, so ``n!`` claimed is exhaustive, not
    # a heuristic.  Fires at n <= 4; from n = 5 reach is 119 of 120.
    everything = factorial(n)
    for ops in _eval_reorders():
        stacks: tuple[list[int], list[int]] = ([], list(range(n)))
        active = _EVAL_TREE_STACK
        for op in ops:
            if op == "~":
                active = 1 - active
            elif op == "*":
                stacks[active].reverse()
            elif stacks[active]:
                stacks[1 - active].append(stacks[active].pop())
            else:
                break
        else:
            arrangement = tuple(stacks[_EVAL_READ_STACK])
            if (
                active == _EVAL_TREE_STACK
                and not stacks[_EVAL_TREE_STACK]
                and arrangement not in reached
            ):
                reached[arrangement] = ops
                if len(reached) == everything:
                    break
    return reached


def eval(truth_table: str) -> str:  # noqa: A001 - the language is named "Eval"
    """Build an Eval template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  The program prints ``'0'`` or ``'1'``.

    Each placeholder stages one equal-width bit on the input stack; the
    table's bits are pushed on the other stack and each input halves it (a
    zero discards the top half; a one reverses, discards, reverses back).
    Duplicating the input lets both branches share one semicolon run,
    totalling ``T/2 + T/4 + ... < T``; ignored inputs are drained after one
    bottom-up dependency pass.
    """
    n = _validate_truth_table(truth_table)
    table = permute_truth_table(truth_table, tuple(reversed(range(n))))
    return _eval_ordered(table, "")


def _eval_cost(truth_table: str, ops: str) -> int:
    """Return :func:`_eval_ordered`'s exact rendered length without emitting it."""
    return len(_eval_ordered(truth_table, ops))


def _eval_dependencies(truth_table: str) -> list[int]:
    """Return essential levels in one bottom-up pass over the table."""
    n = _validate_truth_table(truth_table)
    nodes = [int(bit) for bit in truth_table]
    used: list[int] = []
    ids: dict[tuple[int, int], int] = {}
    next_id = 2
    for level in reversed(range(n)):
        parents: list[int] = []
        matters = False
        for index in range(0, len(nodes), 2):
            pair = (nodes[index], nodes[index + 1])
            matters |= pair[0] != pair[1]
            node = ids.get(pair)
            if node is None:
                node = next_id
                ids[pair] = node
                next_id += 1
            parents.append(node)
        if matters:
            used.append(level)
        nodes = parents
    return list(reversed(used))


def _eval_ordered(truth_table: str, ops: str) -> str:
    """Emit one input order's linear lookup; see :func:`eval`."""
    n = _validate_truth_table(truth_table)
    used = _eval_dependencies(truth_table)
    reduced = read_at(truth_table, used, n)
    bits = _EVAL_INPUT * n
    values = "".join("`" if bit == "1" else "0" for bit in reduced)
    out = [bits, ops, values]
    remaining = len(reduced)
    used_set = set(used)
    for level in range(n):
        if level not in used_set:
            out.append("~;~")
            continue
        remaining //= 2
        out.extend(("~^=~?*", ";" * remaining, "~=~?*"))
    out.append(".")
    return "".join(out)
