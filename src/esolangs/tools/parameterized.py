r"""Boolean generators that embed each input once.

Each template spells input ``i`` as a run of :data:`TEMPLATE_CHAR` exactly
as wide as that input's setter, one run per input in name order; the harness
fills the runs and runs one program per input row, allowing no-input
languages to compute Boolean functions without pretending to read stdin.
Equal-width setters prevent input bits leaking through program length.

The widths are the setters' own: each generator here asks its language's
setters function (in :mod:`esolangs.tools.examples`) for the pairs and
spells a run as long as each, so the template and its fills cannot drift
apart.  That import is local to each generator because ``examples`` imports
this module.
"""

# Re-exported so this module stays the import site for the whole
# parameterized family; each of these owns a file because its
# construction (a search or a grid layout) dwarfs the others.
from esolangs.tools.a_painter_ant import a_painter_ant

# The strategies live in their own modules, but this one is the
# construction's face: the registry, the wrapper and the suite all reach
# it by this name.  Re-exported in the ``x as x`` form so a caller that
# does not care where a piece lives need not know.
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
    _instantiate_arrowqueue as _instantiate_arrowqueue,
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
    _EVAL_MAX_OPS as _EVAL_MAX_OPS,
)
from esolangs.tools.eval_lang import (
    _eval_cost as _eval_cost,
)
from esolangs.tools.eval_lang import (
    _eval_ordered as _eval_ordered,
)
from esolangs.tools.eval_lang import (
    _eval_reorders as _eval_reorders,
)
from esolangs.tools.eval_lang import (
    _eval_stack_programs as _eval_stack_programs,
)
from esolangs.tools.eval_lang import eval as eval  # noqa: A004 - named "Eval"
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    TEMPLATE_CHAR,
    Setters,
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
from esolangs.tools.nocomment import (
    _NOCOMMENT_NARROW_MAX as _NOCOMMENT_NARROW_MAX,
)
from esolangs.tools.nocomment import (
    _NOCOMMENT_SKIP_MAX as _NOCOMMENT_SKIP_MAX,
)
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


def _runs(setters: Setters) -> list[str]:
    """Each input's run of :data:`TEMPLATE_CHAR`, as wide as its setter."""
    return [TEMPLATE_CHAR * len(zero) for zero, _one in setters]


# A decision-tree node: ("leaf", leaf_id, value, None, None) or
# ("node", node_id, level, zero_subtree, one_subtree).
type _Node = tuple[str, int, int, _Node | None, _Node | None]


def bio(truth_table: str) -> str:
    """Build a BIO template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BIO has three registers (``x``, ``y``, ``z``) and no absolute jumps —
    its ``{``/``}`` loops are structurally matched — so the setter's length
    is unconstrained.  Each input is embedded once by packing it into ``x``:
    input ``i``'s run becomes ``0ox`` repeated by its binary weight (``2**w``)
    for a one bit, so ``x = sum 2**w_i * bit_i`` is the input's numeric
    index.  A zero writes the same count to ``z`` instead, which nothing
    reads, so the two bits embed at equal width rather than a zero
    embedding as nothing.

    ``y`` is initialized to the table's first entry (``table[0]``), then
    ``2**n - 1`` *nested* loops each decrement ``x`` once (``0ix{ 1ox; ... };``)
    and, on the transition ``table[j-1] -> table[j]``, adjust ``y``: ``0oy``
    for a 0-to-1 rise, ``1oy`` for a 1-to-0 fall, nothing for a flat edge.
    The j-th level fires iff ``x >= j``, so for the packed value ``V`` the
    ops telescope to ``y = table[0] + sum_{j=1}^{V} (table[j] - table[j-1]) =
    table[V]``.  The result is printed with ``1iy``.
    """
    from esolangs.tools.examples import _setters_bio

    n = _validate_truth_table(truth_table)

    def yop(a: str, b: str) -> str:
        if a == b:
            return ""
        return "0oy;" if a == "0" else "1oy;"

    pack = " ".join(_runs(_setters_bio(truth_table, n)))
    inner = ""
    for j in range(2**n - 1, 0, -1):
        body = "1ox;" + yop(truth_table[j - 1], truth_table[j]) + inner
        inner = "0ix{" + body + "};"
    init = "0oy;" if truth_table[0] == "1" else ""
    return pack + " " + init + inner + "0oy;" * _ASCII_ZERO + "1iy;"


def bfpda(truth_table: str) -> str:
    """Build a BF-PDA template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    BF-PDA has no input command, so this is a parameterized generator: the
    template's input runs become a push of the bit, four characters wide
    whichever bit it is, so the program's shape does not reveal its inputs.
    The harness instantiates one program per input combination.  Each input
    is embedded once: the load phase pushes every ``<@`` + run pair (a
    constant 1 marker, then the bit) up front, so the stack holds all ``n``
    bits and markers with ``b0`` on top.

    Every character outside ``@.<>[]`` is a comment, so the commands are
    emitted unseparated; the fragments below are spaced only to read.

    A node tests its bit and *consumes* it for the next level using a
    ``<``-break loop ``[ > one < ] > [ > zero < ] >``: ``[`` enters when the
    bit is one, ``>`` pops it, the one-branch pops the marker (to expose the
    next bit), and ``<`` pushes a fresh zero to break the loop -- which
    works because the guard was already popped, unlike ``[ sub @ ]`` where
    ``@`` needs the guard still on top.  The zero-branch is selected by the
    second loop testing the marker: when the bit is zero, ``[`` never
    entered, so the outer ``>`` pops the *bit* instead (it was never
    consumed), exposing the marker as the new top.  The marker's role is only
    to be truthy there -- its value never depends on the input, so a constant
    1 (not the input's complement) is correct, and it is embedded directly in
    the template rather than through the bit-value substitution.  A leaf pops
    the remaining pre-loaded bits (``2*(n-level)`` of them) and prints the
    constant answer.
    """
    from esolangs.tools.examples import _setters_bfpda

    n = _validate_truth_table(truth_table)

    # Load: push a constant-1 marker then the bit, in name order, so the top
    # of the stack is the *last* input and the tree tests it first.
    #
    # The load used to run reversed so the top was ``b0`` and level ``i``
    # could test input ``i``.  That is the only thing the reversal bought,
    # and testing the inputs bottom-up costs nothing: the stack is strictly
    # LIFO either way, every level still consumes exactly one bit and one
    # marker, and the tree is the same shape reflected.  Pushing in name
    # order keeps the emitted template's runs in input sequence.
    head = "".join("<@" + run for run in _runs(_setters_bfpda(truth_table, n)))

    def leaf(level: int, value: str) -> str:
        drain_preloaded_bits = ">" * (2 * (n - level))
        print_answer = ("<@" if value == "1" else "<") + ".>"
        return drain_preloaded_bits + print_answer

    # Not routed through :func:`decision_tree_tokens`: this tree is a plain
    # string with no index to thread, so the walker's token lists would have
    # to be one-element lists unwrapped at every use, which reads worse than
    # the four lines it saves.
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

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Bitdeque has no input command, so this is a parameterized generator: the
    template's input runs become a *fixed-length* two-command setter per
    bit, and the harness instantiates one program per input
    combination.  The earlier wall said the absolute ``GOTO N`` targets shift
    because the setter had variable length (``INVERT`` vs nothing); the fixed
    setter removes that: every bit is the one pair ``PUSH INVERT`` (zero)
    against ``INVERT PUSH`` (one), the register flips after every block --
    so an odd position pushes its bit complemented, which the tree's table
    absorbs (:func:`_bitdeque_ordered`) -- and the load is always ``2n``
    commands, so no absolute index moves between instantiations.

    Bits are pushed in reverse order so ``POP`` (LIFO) yields the most
    significant bit first, matching the contiguous MSB-first decision-tree
    splits.  A node pops one bit and ``GOTO``s to the one-subtree when it is
    one, with the zero-subtree falling through in place.  A leaf drains the
    deque with ``n+1`` ``POP``s (so the register is exactly zero even for a
    collapsed tree), pushes the answer, forces the register back to one with
    a trailing ``INVERT``, and uses a fixed low-address halt trampoline -- so
    every leaf always routes and the deque printed at halt holds exactly the
    answer.

    **The tree splits on its inputs in whichever order emits the shortest
    program** (:func:`~esolangs.tools.helpers.best_input_order`).
    Bitdeque is a *deque*, not a stack: ``INJECT``/``EJECT`` work the head
    where ``PUSH``/``POP`` work the tail, so a node can bring any bit to an
    end with ``EJECT PUSH`` (head to tail) or ``POP INJECT`` (tail to head)
    and is not restricted to the order the load pushed.  Rotation costs two
    commands per position, so an order pays for its folds; the search
    measures rather than models, and an order whose rotations outweigh its
    savings loses to the identity.

    The rotations happen *inside the tree*, never in the load block: what
    a position pushes depends on the register parity there, so moving the
    head would change which inputs the table must complement.  The emitted
    load is byte-identical whatever the order.
    """
    if len(truth_table) <= 16:
        return best_input_order(truth_table, _bitdeque_ordered)
    return _bitdeque_linear(truth_table)


def _bitdeque_linear(truth_table: str) -> str:
    """Push the table, then discard its prefix and suffix in O(T) text.

    Every input is the same two-command unit the tree route embeds, and the
    input's *weight* lives in the template: after the table is pushed (and
    the register zeroed, which the last table bit decides statically), each
    input's run pushes its bit onto the tail, a ``POP`` takes it back into
    the register, and a ``GOTO`` picks one of two fixed discard blocks --
    ``EJECT`` the upper half of the window off the head for a one, ``POP``
    the lower half off the tail for a zero, ``2**(n-1-i)`` commands each.
    The zero block ends by forcing the register to one and jumping over the
    one block; both meet at a three-command block that forces the register
    back to zero, which is what the next run relies on.  The last input
    skips that: the deque holds exactly the indexed entry, and nothing
    reads the register again.

    Both blocks are in the text and one runs, so the program is ``2T``
    discard commands long and executes ``T`` of them: the same growth as
    before and the same constant the execution contract measures.
    """
    from esolangs.tools.examples import _setters_bitdeque

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
    for i, run in enumerate(_runs(_setters_bitdeque("", n))):
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

    ``truth_table`` is already permuted, so the rows are in the permuted
    frame.  ``perm`` is spent on the rotations a node runs before it
    consumes its bit -- and those are a function of the *level* alone, not
    of the node: both branches of a level have rotated and consumed exactly
    the same bits on the way down, so the deque layout at a level is the
    same on every path through it.  That is what keeps a node's width
    well-defined for the walker's index arithmetic.

    Under the identity order every bit is already at the tail when it is
    wanted, so no rotation is emitted and the output is byte-identical to
    what the unordered generator produced.

    Every input is the one pair ``PUSH INVERT``/``INVERT PUSH``, and the
    register flips after every block, so the block at an odd load position
    pushes its bit *complemented*.  The tree reads the table with those
    inputs complemented back (``row ^ mask``), which is a relabelling of the
    rows and folds exactly as the table did: the flip lives in the table the
    tree walks, not in the embed and not in an extra ``INVERT`` per block.
    """
    from esolangs.tools.examples import _setters_bitdeque

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

    # Simulate the deque to find each level's rotation.  The load pushes the
    # inputs in name order, so the tail -- what ``POP`` returns -- is input
    # ``n - 1`` and the head is input 0.
    #
    # Pushing in name order rather than reversed is free.  The reversed load
    # made the first ``POP`` the *most significant* bit, which only fixes
    # which input a root-level test reaches first -- and the rotation search
    # already brings any bit to either end, so both loads reach the same set
    # of orders at the same cost.  Measured over every order at n = 2, 3 and
    # 4, the rotation-length multisets are identical.  Name order is the
    # better default: it keeps the emitted template's runs in input
    # sequence.
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
    load_block_in_name_order = _runs(_setters_bitdeque("", n))

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

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Minsky Swap has no input command, so this is a parameterized generator:
    the template's input runs become *fixed-length* setters that
    assemble the input's numeric index into ``reg[0]`` — one block per bit,
    so the inputs are embedded exactly ``n`` times.  Each non-LSB bit's block
    is as long as that bit's own weight ``2**(n-1-i)``: ``+`` repeated for
    the weight when the bit is one, ``*`` repeated for it when the bit is
    zero.  Both spellings are the same length, which is the rule -- a
    program's length must not depend on the bits it evaluates -- and both
    leave the register pointer where they found it, since a one does no
    swapping and a zero does an even number.  The LSB block is the length-4
    ``+*+*`` (adds one, and leaves ``reg[1]`` polluted with a one) or
    ``****`` (a no-op), so the setter length is fixed without an odd pad.

    The blocks therefore sum to ``2**n + 2`` commands rather than the
    ``(n-1) * 2**n`` they came to when every block was padded to the table's
    length.  That padding was this construction's whole super-linearity:
    its commands per table entry used to be the input count, 4.5 through
    10.0 at one through ten inputs, and now settle at 2.01.

    A cascade of ``2**n`` ``~``s then routes the assembled value *v* to leaf
    *v* — each ``~`` decrements a nonzero register and jumps on zero, so the
    (v+1)-th one sees the value hit zero.  A leaf flips the polluted
    ``reg[1]`` (which holds the LSB) to the answer, then ``~``s on the
    (zeroed) ``reg[0]`` to run off the program end, so the dumped registers
    read ``0 {answer}``.
    """
    from esolangs.tools.examples import _setters_minsky_swap

    n = _validate_truth_table(truth_table)

    tokens: list[str] = []
    targets: list[int] = []
    pos = 0  # instantiated command index of the next command

    # load: bits MSB first; a non-LSB setter is as long as its own bit's
    # weight, the LSB a length-4 block.  The runs are read off the setters
    # themselves, so these offsets count exactly the text the fill emits.
    for run in _runs(_setters_minsky_swap(truth_table, n)):
        tokens.append(run)
        pos += len(run)

    for _ in range(2**n):  # cascade: route the assembled value to leaf v
        tokens.append("~")
        targets.append(0)
        pos += 1
    for v in range(2**n):  # leaves: reg[1] holds the LSB; make it the answer
        targets[v] = pos + 1
        tokens.append("*")  # pointer onto reg[1]
        pos += 1
        lsb = v & 1
        if lsb == 1 and truth_table[v] == "0":
            tokens.append("~")  # reg[1] is 1 here, so it decrements, no jump
            targets.append(0)
            pos += 1
        elif lsb == 0 and truth_table[v] == "1":
            tokens.append("+")
            pos += 1
        tokens.append("*")  # pointer back onto reg[0]
        pos += 1
        tokens.append("~")  # reg[0] is 0, so this always jumps to the end
        targets.append(0)
        pos += 1

    end = pos + 1  # 1-based target just past the last command
    return (
        " ".join(tokens) + "\n" + " ".join(str(end if t == 0 else t) for t in targets)
    )


def home_row(truth_table: str) -> str:
    """Build a Home Row template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Home Row has no input command, so this is a parameterized generator:
    each input's run becomes a two-character setter at a bit cell that the
    harness fills in per instantiation.  The cell is zero when the run is
    reached, so the setter raises it with ``a`` and then
    either clears it again (``s``) or leaves it (``j``, whose skip does not
    fire on the now-nonzero cell), spending the same width either way.

    Unlike the removed ``n <= 2`` routing generator (which tried to send the
    beam to one of ``2**n`` distinct leaf cells -- a wall past ``n == 2`` on
    the fixed 5x5 grid), this closed-form construction packs the bits into a
    single binary accumulator and then walks a linear chain of leaf checks,
    so it never needs more than a handful of live cells regardless of ``n``.

    A cell holds the current value under test; the setup line seeds a
    second cell with the ASCII digit base (``48``, ``'0'``).  Each of the
    ``n`` bit-packing lines is ``$$ l s ffff a{2**(n-1-i)} f l``: the
    ``l``/``s``/``l`` triple is Home Row's position-stable "run once iff
    nonzero, consuming the guard" gate (loops cannot nest -- ``l``s pair
    strictly by order of appearance -- so this gate, not a BF-style bracket
    match, is what makes the packing safe to chain), and its body adds the
    bit's binary weight to the accumulator only when the bit is 1.  After all
    ``n`` gates the accumulator holds the combination's integer index
    ``0 .. 2**n - 1``.

    The remaining ``2**n`` lines are a linear equality chain, one per
    index ``k``: ``a ffff l s f s ff l f l f <answer> k ; l f f`` fans the
    accumulator out into a working copy and a backup (destroying the
    accumulator), subtracts ``k`` from the working copy via the leading
    ``a ffff``/``s`` structure, and the position-stable gate on that
    difference either prints the baked answer byte and halts (a match) or
    restores the accumulator from the backup and falls through to test
    ``k + 1``.  The answer byte is a literal ``a`` (or nothing) baked
    directly from ``truth_table[k]`` -- unlike the ``n`` input bits, it is
    known at generation time, not supplied by the harness, so it needs no
    input run.  The final line (index ``2**n - 1``) needs no
    restore, since every other index has already been ruled out.
    """
    from esolangs.tools.examples import _setters_home_row

    n = _validate_truth_table(truth_table)
    # A table that ignores some of its inputs is a smaller table, and the
    # leaf chain -- the whole cost here -- is 2**n lines regardless of what
    # the table says, so dropping an input halves the program.  The gates
    # stay: every input keeps its setter run and its packing line, and
    # an ignored one carries binary weight zero, so its gate runs and
    # consumes its guard exactly as before while adding nothing to the
    # accumulator.  Nothing is relocated and no setter changes width, which
    # keeps the slot-order and equal-width invariants intact.
    used = essential_inputs(truth_table, n)
    # A constant table depends on nothing and reduces to a one-input table,
    # never to the length-1 table, which is not a valid shape.
    table = truth_table if len(used) == n else read_at(truth_table, used or [0], n)
    weights = {i: 2 ** (len(used) - 1 - slot) for slot, i in enumerate(used)}

    setup = "aaaaaalsffaaaaaaaaffflf"
    bit_lines = [
        run + "lsffff" + "a" * weights.get(i, 0) + "fl"
        for i, run in enumerate(_runs(_setters_home_row(truth_table, n)))
    ]
    leaves = [
        "afffflsfsfflflf" + ("a" if bit == "1" else "") + "k;lff" for bit in table[:-1]
    ]
    leaves.append("f" + ("a" if table[-1] == "1" else "") + "k;")
    return setup + "".join(bit_lines) + "".join(leaves)
