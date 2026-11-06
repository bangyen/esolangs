"""NQ Boolean generator: a guarded, halting decision tree.

Every node reads and dequeues one input. A true guard enters its lexical
child; the false child follows the group. All leaves halt, so no branch
returns into its sibling. Constant and equal-child folds retain every input
read. Root constants enqueue the answer before the reads append behind it.
Chunk emission and subtree ranks take O(T) time and space, with
expected constant-time rank lookups on O(log T)-bit words. An unfolded
internal node costs six characters and a leaf four. Parity pairs share WH
using guards over complete enqueue operands; other guards stay grouped.
Both guard-binding readings agree.

Size:
    At most 10T-6 characters; parity 9T-6. n=10 random 1847: 7,154 chars.
    Root constants: n + 4 chars and n + 3 commands.
"""

from esolangs.generation.algebraic import parity_bias
from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.languages.nq.interpreter import guard_dialect


def nq(truth_table: str, *, guard_binding: str = "opcode") -> str:
    """Build a program printing space for false or # for true."""
    guard_dialect(guard_binding)
    if (
        isinstance(truth_table, str)
        and truth_table
        and truth_table.count(truth_table[0]) == len(truth_table)
    ):
        n = _validate_truth_table(truth_table)
        # Keep the answer at the front while reads append behind it.
        return ("+0" if truth_table[0] == "0" else "+2") + "r" * n + "WH"
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    parity = parity_bias(truth_table) is not None
    chunks: list[str] = []
    stack: list[tuple[int, int] | str] = [(0, 0)]
    while stack:
        task = stack.pop()
        if isinstance(task, str):
            chunks.append(task)
            continue
        depth, k = task
        node = ids[depth][k]
        # Canonical fold, with ordered remaining reads: [ablations.constant_fold].
        if node < 2:
            chunks.extend(("r-" * (n - depth), "+2WH" if node else "+0WH"))
            continue
        chunks.append("r-")
        # Complete + operands bind identically in both dialects. The two
        # parity leaf guards share WH, saving exactly T characters overall.
        # [ablations.trick_prototype_20261102_parity_leaf_pair]
        if parity and depth + 1 == n:
            low, high = ids[n][2 * k], ids[n][2 * k + 1]
            chunks.append(f">1+{2 * high}>0+{2 * low}WH")
            continue
        # Keep the read but drop equal-child tests: [ablations.ignored_input].
        if ids[depth + 1][2 * k] == ids[depth + 1][2 * k + 1]:
            stack.append((depth + 1, 2 * k))
        else:
            chunks.append(">1(")
            stack.extend(((depth + 1, 2 * k), ")", (depth + 1, 2 * k + 1)))
    return "".join(chunks)
