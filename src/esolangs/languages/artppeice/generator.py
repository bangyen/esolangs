"""artppeice Boolean program generator: a skip counter beside the table.

The first pass reads each input line into its own queue and dequeues the
bit: a 1 sends ``w`` words ``0`` into the counter, queue ``1``, a 0 sends
them into the sink ``0``.  Then ``P`` closes the counter, which holds a
``0`` per unit of the index and the ``P``.  Later passes find each input
queue holding a ``0``, so their setup only feeds the sink, emptied at
every pass's end.  Queue ``E`` names each queue due a ``0`` and refills
itself.

Each entry copy dequeues the counter and the table in step.  The
counter's ``P`` puts a ``0`` in queue ``P`` first; the table entry then
adds its digit, and dequeuing ``P`` drops its first word, so only the
indexed copy leaves the digit for quitting ``P`` to print.  The next copy
halts on the empty counter.  A pass holds ceil(n/4) copies, so its O(n)
setup lines cost O(1) steps an entry.  The table is one queue, ``D`` per 0 entry and
``0`` per 1, where ``D``, given defaults, sends the digit to ``P``; or,
for small tables, two queues naming ``P`` at the 0s and at the 1s.

The weights are the essential inputs' binary place values, or 1 each with
the table by popcount for a symmetric table; the shortest program ships.

Size:
    2 characters per counter word and per entry, about 110 per input:
    O(T) characters; n=4 parity: 587 chars, n=10 random 1847: 5,486 chars

Decisions:
    The screening probe's gate tree, with no executed back-edge, emitted
    153,124 characters at n=6 against 1,172; the loop pays the index in
    passes instead.
"""

from esolangs.generation.helpers import (
    WeightedLookup,
    _validate_truth_table,
    input_weights,
    symmetric_weights,
)
from esolangs.generation.requests import GenerationRequest
from esolangs.runtime._program import Program


def _name(i: int) -> str:
    """Input ``i``'s queue: lowercase, clear of the fixed uppercase and digits."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    return letters[i] if i < 26 else f"{letters[i % 26]}{i // 26}"


def _log(lookup: WeightedLookup, *, split: bool) -> str:
    """Emit ``lookup``; ``split`` keeps one table queue per digit."""
    n = len(lookup.weights)
    # Each pass replays O(n) setup lines; ceil(n/4) entries a pass keep the
    # steps O(T).
    copies = max(1, -(-n // 4))
    weighted = [_name(i) for i, w in enumerate(lookup.weights) if w]
    defaults = [] if split else ["D"] * copies
    lines = [
        "-!- 0 has joined. ()",
        "-!- 1 has joined. ()",
        f"-!- E has joined. ({' '.join([*weighted, '1', *defaults])} E)",
    ]
    for i, weight in enumerate(lookup.weights):
        lines.append(f"-!- {_name(i)} has joined.")
        if weight:
            lines += [f"<{_name(i)}> " + " ".join("0" * weight), "<E> 0"]
    lines.append("<E> P")
    if split:
        zeros = " ".join("P" if bit == "0" else "0" for bit in lookup.table)
        ones = " ".join("P" if bit == "1" else "0" for bit in lookup.table)
        lines += [f"-!- U has joined. ({zeros})", f"-!- V has joined. ({ones})"]
        entry = ["-!- P has joined. ()", "<1> 0", "<U> 0", "<V> 1"]
        tail = []
    else:
        table = " ".join("D" if bit == "0" else "0" for bit in lookup.table)
        lines.append(f"-!- T has joined. ({table})")
        entry = [
            "-!- P has joined. ()",
            "-!- D has joined. ()",
            "<1> 0",
            "<T> P",
            "<E> 0 P",
            "<D> 0",
            "<D> 1",
        ]
        tail = ["-!- D has quit. ()"]
    lines += [*entry, "<P>", "-!- P has quit.", *tail] * copies
    # With nothing to re-arm, the split program halts in pass 2 before
    # ``E`` would need refilling.
    if weighted or not split:
        lines.append(f"<E> {' '.join([*weighted, '0', *defaults])} E")
    lines.append("-!- 0 has quit. ()")
    return "\n".join("00:00:00 " + line for line in lines)


def artppeice(truth_table: str) -> str:
    """Build an artppeice program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    candidates = [input_weights(truth_table, n)]
    symmetric = symmetric_weights(truth_table, n)
    if symmetric is not None:
        candidates.append(symmetric)
    return min(
        (_log(lookup, split=split) for lookup in candidates for split in (False, True)),
        key=len,
    )


def artppeice_request(request: GenerationRequest) -> Program:
    """Emit source through a typed backend request."""
    return artppeice(request.table)
