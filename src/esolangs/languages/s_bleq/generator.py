"""S*bleq Boolean program generator: a shared branch tree, or a packed decoder.

Reads every input once; tables up to 16 rows use the hoisted shared tree,
larger ones also build the packed decoder and keep the shorter.  A constant
consumes all inputs before printing.

Size:
    n=10 random 1847: 2,974 chars, n=10 parity: 487 chars,
    n=10 and: 334 chars.
"""

from functools import partial

from esolangs.generation.branch_decoder import hoisted_tree as _sbleq_hoisted
from esolangs.generation.helpers import (
    _validate_truth_table,
    in_input_order,
)
from esolangs.generation.packed_decoder import (
    _sbleq_constant,
    packed_decoder,
)
from esolangs.generation.wrap import wrap_grid
from esolangs.languages.s_bleq.proof_formulas import execution
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

#: Tables up to this many rows keep the shared tree; larger ones also try
#: the packed decoder.
_TREE_ROWS = 16


def s_bleq(truth_table: str) -> str:
    """Read once, then choose a shared tree or packed decoder.

    Each branch destroys its input once; value cells never alias indirect
    targets. Constants consume all inputs before printing.
    """
    n = _validate_truth_table(truth_table)
    if len(set(truth_table)) == 1:
        return _sbleq_constant(n, truth_table[0])
    if len(truth_table) <= _TREE_ROWS:
        return _tree(truth_table)
    packed = packed_decoder(truth_table)
    # A proved lower bound past the packed length settles the race
    # without building the tree (see _tree_min_chars).
    if _tree_min_chars(truth_table, n) > len(packed):
        return packed
    tree = _tree(truth_table)
    return tree if len(tree) < len(packed) else packed


def _tree(truth_table: str) -> str:
    """The hoisted tree, branching on a 1 bit or on a 0 bit: the shorter.

    A branch falls through into the zero half and jumps to the one half, so
    a repeated zero half costs a relay jump a level (AND ran 1.3x its
    complement-input twin NOR); the flipped test costs one constant cell an
    input.
    """
    return min(
        in_input_order(truth_table, _sbleq_hoisted),
        in_input_order(truth_table, partial(_sbleq_hoisted, flip=True)),
        key=len,
    )


def _tree_min_chars(truth_table: str, n: int) -> int:
    """A lower bound on the hoisted tree's characters, from its emission.

    The rendered tree is its cells joined by spaces, so its length is
    the cells' digit counts plus one a cell.  One bottom-up pass over
    the table, keeping a single level of subtable ids, counts the
    distinct subtables whose halves differ -- each is placed once, as
    one branch instruction -- and the distinct targets those branches
    point at; the return expression charges each cell class the
    emission's forced minimum digit width (the read block, branch
    operands, target cells).  A bound past the packed text's length
    proves the packed text wins the race, so the tree need not be
    built: on the scaling witness the tree's text is 3.65x the packed
    at n = 21 and its build peaks at 2.8 GB at n = 25, against the
    packed build's 1.6 GB.
    """
    data = truth_table.encode()
    level: list[int] = []
    seen: dict[tuple[int, int], int] = {}
    fresh = 2
    branches = 0
    targets: set[int] = set()
    flipped: set[int] = set()  # the flipped tree branches to the zero halves
    leaf_bits = 0
    for i in range(0, len(data), 2):
        zero, one = data[i] & 1, data[i + 1] & 1
        leaf_bits |= 1 << zero | 1 << one
        if zero == one:
            level.append(zero)
            continue
        node = seen.get((zero, one))
        if node is None:
            node = fresh
            fresh += 1
            seen[zero, one] = node
            branches += 1
            targets.add(one)
            flipped.add(zero)
        level.append(node)
    while len(level) > 1:
        seen = {}
        above: list[int] = []
        for zero, one in zip(level[::2], level[1::2], strict=True):
            if zero == one and zero < 2:
                above.append(zero)
                continue
            node = seen.get((zero, one))
            if node is None:
                node = fresh
                fresh += 1
                seen[zero, one] = node
                if zero != one:
                    branches += 1
                    targets.add(one)
                    flipped.add(zero)
            above.append(node)
        level = above

    def digits(value: int) -> int:
        return len(str(value))

    # Either polarity may ship (see _tree), so the floor takes the fewer.
    targets = min(targets, flipped, key=len)
    code_base = 13 + 2 * n + len(targets)
    return (
        branches * (6 + digits(13 + 2 * n))
        + len(targets) * (digits(code_base + 3 * n) + 1)
        + n * (digits(code_base + 3) + 1)
        + n * (9 + digits(13 + n))
        + 30
        + 14 * leaf_bits.bit_count()
        + digits(code_base)
    )


LANGUAGE = Language(
    "S*bleq",
    "s_bleq",
    category="tape_based",
    boolean=s_bleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    eof="a failed read leaves the cell alone and the program runs on",
    proof_execution=(execution, True, (3, 4, 5, 6, 7, 8, 9)),
)
