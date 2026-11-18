r"""Q-BAL Boolean program generator: shift the table integer by the row.

One attachment, run once: ``N/2^(in\w+...+in)|2->out``.  ``N`` is the
integer whose bit ``r`` is row ``r`` of the table read at the essential
inputs; each ``in`` pops one input line, weighted by its place in that row,
so the exponent is the row and ``|2`` keeps the answer bit.  An ignored
input is read as ``in\0``.  A constant table prints ``b+0\(in+...+in)``.

Size:
    Theta(T) text: about 0.3T digits for ``N`` plus O(n^2) for the weights;
    n=4 parity: 34 chars, n=10 random 1847: 376 chars.

Decisions:
    The screening probe's decision tree (a relative branch ``; + k \ (in != 0)
    -> ;`` per node) emits 38,136 chars at n=10; the integer needs no branch.
    Every operator group here reads the same under the conventional order of
    operations, so the literal "^ \ / | + -" order is not load-bearing.
"""

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def q_bal(truth_table: str) -> str:
    """Build a Q-BAL program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    kept = essential_inputs(truth_table, n)
    if not kept:
        return f"{truth_table[0]}+0\\({'+'.join(['in'] * n)})->out"
    table = read_at(truth_table, kept, n)
    weight = {i: 1 << (len(kept) - 1 - slot) for slot, i in enumerate(kept)}
    terms = [
        "in" if weight.get(i) == 1 else f"in\\{weight.get(i, 0)}" for i in range(n)
    ]
    return f"{int(table[::-1], 2)}/2^({'+'.join(terms)})|2->out"


def q_bal_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return q_bal(request.table)
