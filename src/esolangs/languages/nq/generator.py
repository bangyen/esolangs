"""NQ Boolean generator: a guarded, halting decision tree.

Every node reads and dequeues one input. A true guard enters its lexical
child; the false child follows the group. All leaves halt, so no branch
returns into its sibling. Constant and equal-child folds retain every input
read. Chunk emission and subtree ranks take O(T) time and space, with
expected constant-time rank lookups on O(log T)-bit words. An unfolded
internal node costs six characters and a leaf four.

Size:
    At most 10T-6 characters; n=10 random 1847: 7,154 chars.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.generation.wrap import wrap_chars
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language


def nq(truth_table: str) -> str:
    """Build a program printing space for false or # for true."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
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
        # Keep the read but drop equal-child tests: [ablations.ignored_input].
        if ids[depth + 1][2 * k] == ids[depth + 1][2 * k + 1]:
            stack.append((depth + 1, 2 * k))
        else:
            chunks.append(">1(")
            stack.extend(((depth + 1, 2 * k), ")", (depth + 1, 2 * k + 1)))
    return "".join(chunks)


LANGUAGE = Language(
    "NQ",
    "nq",
    category="queue_based",
    boolean=nq,
    wrap=wrap_chars,
    contract=BooleanContract(
        input_shape="char_stream",
        answer_pattern="([ #])",
        answer_values=(" ", "#"),
        note="The whole output is a space for false or # for true.",
        ignores_whitespace=True,
    ),
    example=Example(expected=" "),
)
