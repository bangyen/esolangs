r"""Boolean generators that embed each input once.

Input ``i`` is a run of :data:`TEMPLATE_CHAR` as wide as its setter, in
name order; the harness fills the runs and runs one program per row.
Equal-width setters keep bits out of the program length.  Each language's
``(zero, one)`` pair is one constant its generator module owns (the
``*_PAIR`` below for the five generators this module hosts); the example
in :mod:`esolangs.tools.examples` reads the same constant, so the widths
the generator lays and the text the fill substitutes cannot drift apart.
"""

# Re-exported (``x as x``): this module is the import site for the family.
from esolangs.tools.a_painter_ant import a_painter_ant
from esolangs.tools.arrowqueue import (
    _MIDDLE as _MIDDLE,
)
from esolangs.tools.arrowqueue import (
    _STAGE as _STAGE,
)
from esolangs.tools.arrowqueue import (
    _TREE_0 as _TREE_0,
)
from esolangs.tools.arrowqueue import (
    _TREE_1 as _TREE_1,
)
from esolangs.tools.arrowqueue import (
    _TREE_BRANCH_0 as _TREE_BRANCH_0,
)
from esolangs.tools.arrowqueue import (
    _TREE_BRANCH_1 as _TREE_BRANCH_1,
)
from esolangs.tools.arrowqueue import (
    _connect as _connect,
)
from esolangs.tools.arrowqueue import (
    _drained_leaf as _drained_leaf,
)
from esolangs.tools.arrowqueue import (
    _header as _header,
)
from esolangs.tools.arrowqueue import (
    _tree as _tree,
)
from esolangs.tools.arrowqueue import arrowqueue as arrowqueue
from esolangs.tools.back import (
    _back_ordered as _back_ordered,
)
from esolangs.tools.back import back as back
from esolangs.tools.cod import cod
from esolangs.tools.eval_lang import (
    _eval_ordered as _eval_ordered,
)
from esolangs.tools.eval_lang import eval as eval  # noqa: A004 - named "Eval"
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    TEMPLATE_CHAR,
    _validate_truth_table,
    best_input_order,
    decision_tree_tokens,
    essential_inputs,
    read_at,
)
from esolangs.tools.helpers import (
    permute_truth_table as permute_truth_table,
)
from esolangs.tools.minifuck import minifuck
from esolangs.tools.nocomment import nocomment as nocomment
from esolangs.tools.one_two_three import one_two_three
from esolangs.tools.pct_squared_minus_one import pct_squared_minus_one
from esolangs.tools.ram0 import (
    _ram0_ordered as _ram0_ordered,
)
from esolangs.tools.ram0 import ram0 as ram0
from esolangs.tools.wii2d import wii2d

__all__ = [
    "a_painter_ant",
    "arrowqueue",
    "back",
    "bfpda",
    "bio",
    "bitdeque",
    "cod",
    "eval",
    "minifuck",
    "minsky_swap",
    "nocomment",
    "one_two_three",
    "pct_squared_minus_one",
    "ram0",
    "wii2d",
]


def _runs(pair: tuple[str, str], n: int) -> list[str]:
    """Each input's run of :data:`TEMPLATE_CHAR`, as wide as its setter."""
    return [TEMPLATE_CHAR * len(pair[0])] * n


BIO_PAIR = ("0oz;", "0ox;")
#: Four is minimal: a search over ``<>@[]`` finds no equal-width pair under it.
BFPDA_PAIR = ("<[@]", "<@@@")
BITDEQUE_PAIR = ("PUSH INVERT", "INVERT PUSH")
#: Even widths: ``*`` swaps the pointer, so a one-wide zero would move it.
MINSKY_SWAP_PAIR = ("**", "++")
#: ``j`` is the pad: a gate tests this cell next, so it must leave value and pointer.
HOME_ROW_PAIR = ("as", "aj")


# A decision-tree node: ("leaf", leaf_id, value, None, None) or
# ("node", node_id, level, zero_subtree, one_subtree).
type _Node = tuple[str, int, int, _Node | None, _Node | None]


def bio(truth_table: str) -> str:
    """Build a BIO template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Each
    input is the same four-character unit: ``0ox;`` (``x += 1``) for a one,
    ``0oz;`` (a write nothing reads) for a zero.  The template carries the
    weight by Horner: before every run but the first it doubles ``x``
    through ``y`` (:data:`_BIO_DOUBLE`), so ``x`` ends as the index and ``y``
    at zero -- eight commands per input at any arity.  ``y`` starts at
    ``table[0]``; ``2**n - 1`` nested loops each decrement ``x`` and adjust
    ``y`` on a table transition (``0oy`` rise, ``1oy`` fall), so the ops
    telescope to ``y = table[V]``, printed with ``1iy``.
    """
    n = _validate_truth_table(truth_table)

    def yop(a: str, b: str) -> str:
        if a == b:
            return ""
        return "0oy;" if a == "0" else "1oy;"

    pack = _BIO_DOUBLE.join(_runs(BIO_PAIR, n))
    inner = ""
    for j in range(2**n - 1, 0, -1):
        body = "1ox;" + yop(truth_table[j - 1], truth_table[j]) + inner
        inner = "0ix{" + body + "};"
    init = "0oy;" if truth_table[0] == "1" else ""
    return pack + init + inner + "0oy;" * _ASCII_ZERO + "1iy;"


#: ``x = 2 * x`` through ``y``: the first loop moves each unit of ``x`` into
#: ``y`` twice, the second moves ``y`` back; both registers stay non-negative,
#: so each loop terminates and ``y`` ends at zero.
_BIO_DOUBLE = "0ix{1ox;0oy;0oy;};0iy{1oy;0ox;};"


def bfpda(truth_table: str) -> str:
    """Build a BF-PDA template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Each
    run is a four-character push of its bit; the load pushes every ``<@`` +
    run pair so the stack holds all bits and markers with ``b0`` on top.
    Characters outside ``@.<>[]`` are comments.  A node tests and consumes
    its bit with ``[ > one < ] > [ > zero < ] >``: ``[`` enters on a one,
    ``>`` pops it, the one-branch pops the marker, ``<`` pushes a zero to
    break; on a zero the outer ``>`` pops the bit and the second loop tests
    the marker, a constant 1 embedded directly.  A leaf pops the remaining
    ``2*(n-level)`` and prints.
    """
    n = _validate_truth_table(truth_table)

    # Marker then bit, in name order, so the tree tests the last input
    # first (the same tree reflected; the reversed load bought nothing and
    # put the runs out of order).
    head = "".join("<@" + run for run in _runs(BFPDA_PAIR, n))

    def leaf(level: int, value: str) -> str:
        drain_preloaded_bits = ">" * (2 * (n - level))
        print_answer = ("<@" if value == "1" else "<") + ".>"
        return drain_preloaded_bits + print_answer

    # Not routed through :func:`decision_tree_tokens`: a plain string with no
    # index to thread, so its token lists would be one-element lists throughout.
    def node(i: int, rows: list[int]) -> str:
        results = {truth_table[r] for r in rows}
        if i == n or len(results) == 1:
            return leaf(i, results.pop() if i < n else truth_table[rows[0]])
        # The load pushes in name order, so the stack hands back the *last*
        # input first: level ``i`` tests input ``n - 1 - i``, whose row bit
        # is at position ``i``.
        zero = [r for r in rows if ((r >> i) & 1) == 0]
        one = [r for r in rows if ((r >> i) & 1) == 1]
        sub0 = node(i + 1, zero)
        sub1 = node(i + 1, one)
        # one-branch pops ~bi first (expose next bit); zero-branch has it popped
        # by the node's own loop
        return "[>" + ">" + sub1 + "<]>[>" + sub0 + "<]>"

    return head + node(0, list(range(2**n)))


def bitdeque(truth_table: str) -> str:
    """Build a Bitdeque template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Every
    bit is the fixed pair ``PUSH INVERT`` (zero) / ``INVERT PUSH`` (one),
    so the load is always ``2n`` commands and no absolute ``GOTO`` moves;
    the register flips after every block, so odd positions push complemented,
    which the table absorbs (:func:`_bitdeque_ordered`).  Bits are pushed in
    reverse so ``POP`` yields the MSB first.  A node pops and ``GOTO``s to
    the one-subtree; a leaf drains with ``n+1`` ``POP``s, pushes the answer,
    restores the register with ``INVERT``, and uses a low-address halt
    trampoline.  The split order is whichever is shortest
    (:func:`~esolangs.tools.helpers.best_input_order`): a deque's
    ``EJECT``/``INJECT`` work the head, so any bit can be brought to an end
    at two commands per position, measured not modelled.  Rotations happen
    inside the tree; the load is byte-identical under every order.
    """
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _bitdeque_ordered)
    return _bitdeque_linear(truth_table)


def _bitdeque_linear(truth_table: str) -> str:
    """Push the table, then discard its prefix and suffix in O(T) text.

    After the table is pushed, each run pushes its bit, ``POP`` takes it into
    the register, and a ``GOTO`` picks a discard block: ``EJECT`` the upper
    half off the head for a one, ``POP`` the lower half off the tail for a
    zero, ``2**(n-1-i)`` commands each, meeting at a block that zeroes the
    register.  The last input skips that.  ``2T`` commands long, ``T`` executed.
    """
    n = _validate_truth_table(truth_table)
    tokens: list[str] = []
    register = 0
    for bit in truth_table:
        value = int(bit)
        if value != register:
            tokens.append("INVERT")
            register = value
        tokens.append("PUSH")
    if register:
        tokens.append("INVERT")
    at = len(tokens)
    for i, run in enumerate(_runs(BITDEQUE_PAIR, n)):
        k = 2 ** (n - 1 - i)
        # ``run`` is one token of text but two commands once filled.
        at += 2
        # Command indices, with ``at`` the ``POP`` that reads the bit back:
        # the zero block spans ``at + 2 .. at + k + 1``, its exit ``at + k +
        # 2 .. at + k + 4``, the one block ``at + k + 5 .. at + 2k + 4`` and
        # the shared reset begins at ``at + 2k + 5``.
        one_block = at + k + 5
        meet = at + 2 * k + 5
        tokens += [run, "POP", f"GOTO {one_block}"]
        tokens += ["POP"] * k
        # Force the register to one, then jump: a one skips the INVERT.
        tokens += [f"GOTO {at + k + 4}", "INVERT", f"GOTO {meet}"]
        tokens += ["EJECT"] * k
        at = meet
        if i < n - 1:
            # Force the register to zero: a one skips the first INVERT.
            tokens += [f"GOTO {at + 2}", "INVERT", "INVERT"]
            at += 3
    return " ".join(tokens)


def _bitdeque_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's Bitdeque template; see :func:`bitdeque`.

    ``perm`` is spent on the rotations before a node consumes its bit, a
    function of the level alone, so a node's width is well-defined.  The
    identity order emits no rotation.  Odd load positions push complemented;
    the tree reads the table with those inputs complemented back
    (``row ^ mask``), a relabelling that folds as the table did.
    """
    n = _validate_truth_table(truth_table)
    # Level ``level`` tests input ``perm[level]``, whose load position is
    # its name; the row bit for a level is ``n - 1 - level``.
    mask = sum(1 << (n - 1 - level) for level in range(n) if perm[level] % 2)
    seen = "".join(truth_table[row ^ mask] for row in range(2**n))

    def leaf(answer: str) -> list[str]:
        out = ["POP"] * (n + 1)
        if answer == "1":
            out.append("INVERT")
        out.append("PUSH")
        if answer == "0":
            out.append("INVERT")
        out.append("GOTO 0")
        return out

    # Simulate the deque per level: the tail (``POP``) is input ``n - 1``,
    # the head input 0.  Name order costs nothing over reversed -- the
    # rotation-length multisets are identical over every order at n=2,3,4.
    deque = list(range(n))
    rotations: list[list[str]] = []
    for level in range(n):
        want = perm[level]
        index = deque.index(want)
        from_tail = len(deque) - 1 - index
        if from_tail <= index:
            # Nearer the tail: rotate the tail round to the head, then POP.
            rotations.append(["POP", "INJECT"] * from_tail + ["POP"])
            for _ in range(from_tail):
                deque.insert(0, deque.pop())
            deque.pop()
        else:
            # Nearer the head: rotate the head round to the tail, then EJECT.
            rotations.append(["EJECT", "PUSH"] * index + ["EJECT"])
            for _ in range(index):
                deque.append(deque.pop(0))
            deque.pop(0)

    def width(level: int) -> int:
        # the rotation, its consuming pop, and the node's own ``GOTO``
        return len(rotations[level]) + 1

    # Each input's run fills to two commands, which is what ``start`` below
    # counts; see the docstring for why the load is byte-identical per order.
    # Initially command 0 falls through on zero and commands 1/2 skip the
    # trampoline.  A leaf returns with one, so ``GOTO 0`` reaches command 3;
    # only that command carries the widening end address.
    prelude = ["GOTO 3", "INVERT", "GOTO 4", "GOTO@END", "INVERT"]
    # The setters read the route off the template's prefix, so they are
    # handed the prelude, whose opening ``GOTO 3`` names this one.
    load_block_in_name_order = _runs(BITDEQUE_PAIR, n)

    # A node spends its rotation, its pop and its ``GOTO`` before either
    # subtree, so the walker's ``at`` lands on this node and ``at +
    # width(level)`` on the zero subtree.  The load block occupies ``2n``
    # commands ahead of the tree, which is where the indices start, so the
    # ``GOTO`` operands are right after substitution.
    def leaf_tokens(_level: int, row: int) -> list[str]:
        return leaf(seen[row])

    def node(level: int, zero: list[str], one: list[str], at: int) -> list[str]:
        return [
            *rotations[level],
            f"GOTO {at + width(level) + len(zero)}",
            *zero,
            *one,
        ]

    tree = decision_tree_tokens(
        seen,
        leaf_tokens,
        node,
        parent_width=width,
        start=len(prelude) + 2 * n,
        collapse=True,
    )
    end = len(prelude) + 2 * n + len(tree)
    tokens = prelude + load_block_in_name_order + tree
    return " ".join("GOTO " + str(end) if t == "GOTO@END" else t for t in tokens)


def minsky_swap(truth_table: str) -> str:
    """Build a Minsky Swap template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Every
    run is ``++`` (``reg[0] = 2``) or ``**`` (swap away and back), and each
    is followed by a stage adding ``2**(n-1-i)`` to ``reg[1]``::

        $$ ~ ~ * +...+ *

    Both ``~`` target the command after the stage: a one falls through to
    the ``+`` block, a zero jumps it; either way ``reg[0]`` is zero and the
    pointer on it.  The blocks sum to ``2**n - 1`` commands.  A ``*`` then
    puts the pointer on ``reg[1]`` and ``2**n`` ``~``s route value ``v`` to
    leaf ``v``; a one leaf is ``+ * ~``, a zero leaf ``~``.  The dump reads
    ``0 {answer}``.
    """
    n = _validate_truth_table(truth_table)

    tokens: list[str] = []
    targets: list[int] = []
    pos = 0  # instantiated command index of the next command

    # load: one stage per input, MSB first.  The run is read off the
    # setters themselves, so the offsets count exactly the text the fill
    # emits; the weight is the stage's own ``+`` block.
    for i, run in enumerate(_runs(MINSKY_SWAP_PAIR, n)):
        weight = 2 ** (n - 1 - i)
        skip = pos + len(run) + 2 + 2 + weight + 1  # 1-based line after the stage
        tokens += [run, "~", "~", "*", "+" * weight, "*"]
        targets += [skip, skip]
        pos = skip - 1

    tokens.append("*")  # pointer onto reg[1], which holds the index
    pos += 1
    for _ in range(2**n):  # cascade: route the assembled value to leaf v
        tokens.append("~")
        targets.append(0)
        pos += 1
    for v in range(2**n):  # leaves: both registers are zero here
        targets[n * 2 + v] = pos + 1
        if truth_table[v] == "1":
            tokens += ["+", "*"]  # reg[1] = 1, pointer onto the zero reg[0]
            pos += 2
        tokens.append("~")  # the addressed register is zero: jump to the end
        targets.append(0)
        pos += 1

    end = pos + 1  # 1-based target just past the last command
    return (
        " ".join(tokens) + "\n" + " ".join(str(end if t == 0 else t) for t in targets)
    )


def home_row(truth_table: str) -> str:
    """Build a Home Row template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  A
    run is a two-character setter on a zero cell: ``a`` then ``s`` (clear)
    or ``j`` (a skip that does not fire).  The bits pack into one binary
    accumulator (the removed routing generator hit a wall past ``n == 2`` on
    the 5x5 grid): each packing line ``$$ l s ffff a{2**(n-1-i)} f l`` uses
    Home Row's position-stable ``l``/``s``/``l`` gate (loops cannot nest) to
    add the weight iff the bit is 1.  Then ``2**n`` lines
    ``a ffff l s f s ff l f l f <answer> k ; l f f`` fan the accumulator
    into a working copy and backup, subtract ``k``, and either print the
    baked answer and halt or restore and fall through; the last needs no restore.
    """
    n = _validate_truth_table(truth_table)
    # The leaf chain is 2**n lines whatever the table says, so dropping an
    # ignored input halves the program; its gate stays with weight zero,
    # so nothing moves and no setter changes width.
    used = essential_inputs(truth_table, n)
    # A constant table depends on nothing and reduces to a one-input table,
    # never to the length-1 table, which is not a valid shape.
    table = truth_table if len(used) == n else read_at(truth_table, used or [0], n)
    weights = {i: 2 ** (len(used) - 1 - slot) for slot, i in enumerate(used)}

    setup = "aaaaaalsffaaaaaaaaffflf"
    bit_lines = [
        run + "lsffff" + "a" * weights.get(i, 0) + "fl"
        for i, run in enumerate(_runs(HOME_ROW_PAIR, n))
    ]
    leaves = [
        "afffflsfsfflflf" + ("a" if bit == "1" else "") + "k;lff" for bit in table[:-1]
    ]
    leaves.append("f" + ("a" if table[-1] == "1" else "") + "k;")
    return setup + "".join(bit_lines) + "".join(leaves)
