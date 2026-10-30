"""Nandypants Boolean program generator: a label-DAG over the shared decision diagram.

Both tapes start at 1 (``v^``) and ``a`` stays 1 for the whole run, so a test
``NAND(a, b)`` is the complement of ``b``.  Each node of the quasi-reduced
decision diagram (equal subtables at one depth are one block) is the code
``7 junk reads, /, tests``: the first bit of an input byte is its value, the
other seven are discarded at the head of the next block.  ``/ L0`` jumps to
``L0`` when the bit is 0 (an odd label jumps forward to its last occurrence,
which is the child's head); ``v L1`` makes ``b = 0`` and jumps for the 1 edge.
A child that follows its parent in the layout takes the fall-through and needs
no label.  Blocks are laid out by depth, so every jump is forward.  A constant
subtable is one block that reads its remaining inputs and prints the answer
byte, with b moved to a second cell holding 1 so ``^`` toggles a between bits.

Size:
    Theta(T / log T) blocks of O(log T) digits: Theta(T) characters; n=4
    parity: 130 chars

Decisions:
    A space separates adjacent labels, since any digit run is one number.
"""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.languages.nandypants.proof_formulas import workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: The answer byte (ASCII ``0`` / ``1``, low bit first) as ``\`` and ``^``
#: after the pointer move onto the cell that holds 1; a starts at 1 and ends 0.
_PRINT = {"0": ">^\\\\\\\\^\\\\^\\\\", "1": ">\\^\\\\\\^\\\\^\\\\"}
_END = "1"  # label every printer jumps to; its last occurrence ends the program


def _odd_labels(count: int) -> list[str]:
    """The first ``count`` odd numbers after 1, fewest digits first."""
    return [str(2 * i + 3) for i in range(count)]


def nandypants(truth_table: str) -> str:
    """Build a Nandypants program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    # (depth, id) -> (child ids) for a node, None for a constant block.
    order: list[tuple[int, int]] = []
    kids: dict[tuple[int, int], tuple[int, int] | None] = {}
    frontier = {ids[0][0]: 0}
    for depth in range(n + 1):
        following: dict[int, int] = {}
        for ident, pos in frontier.items():
            order.append((depth, ident))
            if ident < 2:
                kids[depth, ident] = None
                continue
            zero, one = ids[depth + 1][2 * pos], ids[depth + 1][2 * pos + 1]
            kids[depth, ident] = (zero, one)
            following.setdefault(zero, 2 * pos)
            following.setdefault(one, 2 * pos + 1)
        frontier = following

    # Plan each node's tests against the block that follows it.
    plan: dict[tuple[int, int], list[tuple[str, tuple[int, int]]]] = {}
    for index, key in enumerate(order):
        pair = kids[key]
        if pair is None:
            continue
        depth = key[0] + 1
        c0, c1 = (depth, pair[0]), (depth, pair[1])
        after = order[index + 1] if index + 1 < len(order) else None
        if c0 == c1 and after == c0:
            tests: list[tuple[str, tuple[int, int]]] = []
        elif after == c1:
            tests = [("", c0)]
        elif after == c0:
            tests = [("v", c1)]
        else:
            tests = [("", c0), ("v", c1)]
        plan[key] = tests

    # Jump targets take labels in layout order ([ablations.label_rank]).
    targets = {target for tests in plan.values() for _, target in tests}
    jumped = [key for key in order if key in targets]
    label = dict(zip(jumped, _odd_labels(len(jumped)), strict=True))

    tokens = ["v^>v<"]
    for key in order:
        if key in label:
            tokens.append(label[key])
        pair = kids[key]
        reads = 8 * (n - key[0]) + (7 if key[0] else 0)
        if pair is None:
            tokens += ["/" * reads, _PRINT[str(key[1])], _END]
            continue
        tokens.append("/" * ((7 if key[0] else 0) + 1))
        for move, target in plan[key]:
            tokens += [move, label[target]] if move else [label[target]]
    out: list[str] = []
    for token in tokens:
        if out and out[-1][-1].isdigit() and token[0].isdigit():
            out.append(" ")
        out.append(token)
    return "".join(out)


LANGUAGE = Language(
    "Nandypants",
    "nandypants",
    category="tape_based",
    boolean=nandypants,
    contract=BooleanContract(input_shape="char_stream"),
    no_wrap="a line break inside a label would split one number into two",
    proof_workspace=(workspace, False, (3, 4, 5, 6, 7)),
)
