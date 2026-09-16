"""Boolean-function generator for Eval.

Named ``eval_lang`` because the generator itself is called ``eval``, and a
module of that name reads as the builtin wherever it is imported.
"""

from functools import cache
from math import factorial

from esolangs.tools.helpers import _validate_truth_table, permute_truth_table, read_at

# Eval's two stacks and the ops that move values between them.  ``~`` swaps
# which stack is active, ``*`` reverses the active one, and ``=`` pops the
# active stack onto the other.  The pair is a spindle: moving values across
# reverses them, so composing the three reaches essentially any arrangement.
_EVAL_TREE_STACK, _EVAL_READ_STACK = 0, 1


# Longest op string worth building.  Costs run to roughly 3 characters per
# displaced input, and an arrangement that expensive has already lost to the
# folds it was meant to buy; the cap also bounds how deep any program can
# reach, which is what makes the construction below finite.
_EVAL_MAX_OPS = 16


# The reorder words, built rather than stored.  A word is a skeleton over
# ``~``, ``*`` and ``=``-runs, and only three shapes are ever redundant:
# ``~~`` and ``**`` are the identity, and two adjacent ``=``-runs are one
# run.  Ruling those out leaves the skeletons below, and the run lengths
# are pinned by a conservation law: the ``~`` parity before a run fixes
# which way it moves, and a word can only end with the tree stack empty if
# everything pushed onto it comes back, so the out-runs and the in-runs
# must sum alike -- and it must hold at every prefix, since an in-run can
# only carry back what is already parked.  Enumerating (skeleton, run
# lengths) under that law, in order of length and then ``~`` < ``*`` <
# ``=``, gives the words ``_eval_stack_programs`` folds.
#
# The law over-approximates and never under-approximates: it admits longer
# spellings of arrangements a shorter word already reaches -- 37255 words
# for the 735 arrangements the cap allows -- which first-claim-wins
# discards.  That is what makes the construction safe: no arrangement can be
# lost, only re-spelled.  The fold this feeds is byte-identical to the
# 735-entry catalog it replaced, at every ``n`` from 1 to 14.  The set is
# finite for *every* ``n``: a word moves at most six values, deeper ones
# riding along in rigid whole-stack reversals, so arrangements stop appearing
# once the stack outgrows that reach (620, 691, 717, 728, 733, 735 over
# ``n == 7..12``, then constant).  ``test_reorder_catalog_matches_search``
# replays the replaced breadth-first search and asserts byte equality.
_EVAL_OP_RANK = {"~": 0, "*": 1, "=": 2}


def _eval_skeletons(max_ops: int) -> list[str]:
    """Reorder-word skeletons, ``E`` marking an ``=``-run of unfixed length.

    A skeleton starts with ``~`` -- the read stack holds the bits, so
    nothing can happen before the first switch -- and carries no ``~~``,
    no ``**`` and no two adjacent runs, each of which spells a word some
    shorter skeleton already spells.
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

    The runs are filled left to right, spending the cap as we go, so the
    walk never builds a word it would only discard for length.  ``balance``
    is the running out-mass minus in-mass; a word is valid exactly when it
    lands back at zero, every value pushed onto the tree stack having come
    home.

    The caller only passes skeletons whose *last* run is an in-run, so the
    final run's length is not searched: it has to be exactly ``balance`` to
    land at zero, and the walk emits at that one length when the budget
    still affords it.  Collapsing the innermost -- and by far the widest --
    level of the recursion from a loop to a single test cuts the walk from
    1091320 calls to 690617; the caller's skip takes it to 348053.
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
            # A skeleton ending in an out-run spells no word at all.  An
            # in-run is capped at ``balance``, so the balance never goes
            # negative; a final out-run then adds at least one and leaves it
            # strictly positive, meaning values are still parked on the tree
            # stack when the word ends.  Half the skeletons (32721 of 65535)
            # are this shape, and filling them was pure waste.
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

    Returns the input stack (bottom to top, by input index) mapped to the
    ops producing it.  The staging blocks leave the bits on the input stack
    and nothing else, so these ops run between the staging and the tree and
    are free to reverse or shuttle them.

    Each catalog program is replayed on the staged stacks, and the first to
    reach an arrangement claims it -- valid because the catalog holds every
    program the cap admits, cheapest first.  A program that pops an empty
    stack at this ``n`` is skipped, and one that leaves values on the tree
    stack (or the wrong stack active) ends unusable, since the tree expects
    to start from a bare tree stack; at small ``n`` the catalog collapses
    onto the reachable arrangements -- 1, 2, 6 and 24 through ``n == 4`` --
    and from ``n == 12`` all 735 programs claim distinct arrangements.

    **This is a runtime reorder, not a relabelling.**  The ``{Xi}`` blocks
    keep their slots and the harness fills them as before; what changes is
    the emitted program, which now rearranges the stack the nodes pop from.
    The nodes themselves name no input -- each is ``~=~?`` plus a semicolon
    run fixed by its heap index -- so the arrangement alone decides which
    input a level tests.
    """
    reached: dict[tuple[int, ...], str] = {}
    # A word only shuttles and reverses, never copies or drops, so every
    # arrangement it can leave is a permutation of ``range(n)``.  Once ``n!``
    # of them are claimed there is nothing left for a later word to claim,
    # and first-claim-wins means the ones already held are the cheapest --
    # so stopping is not a heuristic.  It fires at ``n <= 4``, where the
    # catalog collapses onto all ``n!`` arrangements; from ``n == 5`` the
    # reach is short of ``n!`` (119 of 120) and the loop runs to the end.
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
    inputs (most significant first); the table length implies ``n``.  The
    program prints ``'0'`` or ``'1'``.

    Eval has no input command, so each placeholder stages one equal-width bit
    on the input stack.  The table's result bits are pushed on the other
    stack, then each input halves that candidate stack.  A zero discards its
    top half; a one reverses, discards the same half, and reverses back.

    Duplicating the input before the first conditional preserves it for the
    second, so both branches share one semicolon run.  Those runs total
    ``T/2 + T/4 + ... < T`` commands; the table contributes ``T`` pushes and
    every other level cost is constant.  Ignored inputs are drained without
    halving after one linear bottom-up dependency pass.
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
    bits = "".join("{X" + str(i) + "}" for i in range(n))
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
