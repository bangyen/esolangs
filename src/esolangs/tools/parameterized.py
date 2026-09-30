r"""Boolean generators that embed each input once.

Input ``i`` is a run of :data:`TEMPLATE_CHAR` as wide as its setter, in
name order; the harness fills the runs and runs one program per row.
Equal-width setters keep bits out of the program length.  Each layout uses
a uniform ``(zero, one)`` pair its generator module owns (the ``*_PAIR``
below for the five generators this module hosts); the example
in :mod:`esolangs.tools.examples` reads the same constant, so the widths
the generator lays and the text the fill substitutes cannot drift apart.
"""

import re

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
from esolangs.tools.eval_lang import (
    _eval_ordered as _eval_ordered,
)
from esolangs.tools.eval_lang import eval as eval  # noqa: A004 - named "Eval"
from esolangs.tools.helpers import (
    _ASCII_ZERO,
    TEMPLATE_CHAR,
    _validate_truth_table,
    best_input_order,
    constant_span_test,
    decision_tree_tokens,
    essential_inputs,
    read_at,
    runs,
)
from esolangs.tools.helpers import (
    permute_truth_table as permute_truth_table,
)
from esolangs.tools.minifuck import minifuck
from esolangs.tools.nocomment import nocomment as nocomment
from esolangs.tools.one_two_three import one_two_three
from esolangs.tools.ram0 import (
    _ram0_ordered as _ram0_ordered,
)
from esolangs.tools.ram0 import ram0 as ram0
from esolangs.tools.underload import underload as underload

__all__ = [
    "a_painter_ant",
    "arrowqueue",
    "back",
    "bfpda",
    "bio",
    "bitdeque",
    "eval",
    "minifuck",
    "minsky_swap",
    "nocomment",
    "one_two_three",
    "ram0",
    "underload",
]


def _runs(pair: tuple[str, str], n: int) -> list[str]:
    """Each input's run of :data:`TEMPLATE_CHAR`, as wide as its setter."""
    return [TEMPLATE_CHAR * len(pair[0])] * n


BIO_PAIR = ("0oz;", "0ox;")
#: Each bit cell is freshly pushed as zero; the marker is a separate cell.
BFPDA_PAIR = (" ", "@")
BITDEQUE_PAIR = ("PUSH INVERT", "INVERT PUSH")
#: Even widths: ``*`` swaps the pointer, so a one-wide zero would move it.
MINSKY_SWAP_PAIR = ("**", "++")
_MINSKY_RMSN_PAIR = ("swap();\nswap();", "inc(); \ninc(); ")
_MINSKY_SHORT_RMSN_PAIR = ("decnz();", "inc();  ")
_MINSKY_SMALL_RMSN_PAIR = ("decnz(2);", "inc();   ")
#: ``j`` is the pad: a gate tests this cell next, so it must leave value and pointer.
HOME_ROW_PAIR = ("s", "j")


# ("leaf", leaf_id, value, None, None) or ("node", node_id, level, zero, one).
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
    # Loop ``j`` wraps ``j + 1``: opens, then closes, joined once (O(2**n)).
    opens = [
        "0ix{1ox;" + yop(truth_table[j - 1], truth_table[j]) for j in range(1, 2**n)
    ]
    init = "0oy;" if truth_table[0] == "1" else ""
    closes = "};" * len(opens)
    return pack + init + "".join(opens) + closes + "0oy;" * _ASCII_ZERO + "1iy;"


#: ``x = 2 * x`` through ``y``: the first loop moves each unit of ``x`` into
#: ``y`` twice, the second moves ``y`` back; both registers stay non-negative,
#: so each loop terminates and ``y`` ends at zero.
_BIO_DOUBLE = "0ix{1ox;0oy;0oy;};0iy{1oy;0ox;};"


def bfpda(truth_table: str) -> str:
    """Build a BF-PDA template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Each
    run flips a fresh zero cell or leaves it alone; the load pushes
    a marker and that bit cell before every run. The stack holds all bits
    and markers with ``b0`` on top.
    Characters outside ``@.<>[]`` are comments.  A node tests and consumes
    its bit with ``[>> one ]>[> zero ]``: ``[`` enters on a one and ``>>``
    pops it and its marker; on a zero ``>`` pops the bit and the second loop
    enters on the marker, a constant 1.  A leaf empties the stack (a zero
    prints the empty stack), so each ``]`` after it exits with no zero
    pushed.  The first marker is a bare ``@``: the empty stack reads 0.
    """
    n = _validate_truth_table(truth_table)

    # Marker then bit, in name order, so the tree tests the last input
    # first (the same tree reflected; the reversed load bought nothing and
    # put the runs out of order).
    head = "".join("<@<" + run for run in _runs(BFPDA_PAIR, n))[1:]

    def leaf(level: int, value: str) -> str:
        # A one stops on the bottom entry, the first marker, and prints it.
        left = 2 * (n - level)
        if value == "0":
            return ">" * left + "."
        return ">" * (left - 1) + ".>" if left else "@.>"

    # The load pushes in name order, so the stack hands back the *last*
    # input first: level ``i`` tests input ``n - 1 - i``, row bit ``i``.
    # Through the bit-reversed index that subtree is a contiguous span.
    reflected = "".join(
        truth_table[int(f"{row:0{n}b}"[::-1], 2)] for row in range(2**n)
    )
    constant = constant_span_test(reflected)
    pieces = [head]

    # Not routed through :func:`decision_tree_tokens`: a plain string with no
    # index to thread, so its token lists would be one-element lists throughout.
    def node(i: int, lo: int, hi: int) -> None:
        if i == n or constant(lo, hi):
            pieces.append(leaf(i, reflected[lo]))
            return
        mid = (lo + hi) // 2
        # Each arm ends on an empty stack, so its ``]`` exits as it stands.
        pieces.append("[>>")
        node(i + 1, mid, hi)
        pieces.append("]>[>")
        node(i + 1, lo, mid)
        pieces.append("]")

    node(0, 0, 2**n)
    return "".join(pieces)


def bitdeque(truth_table: str, width: int | None = None) -> str:
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
    Below eleven columns, up to four inputs use POP/EJECT on fresh
    zero/one endpoints; larger tables keep the linear load.
    """
    if len(truth_table) <= 16:
        program = best_input_order(truth_table, _bitdeque_ordered)
        if width is not None and width < len(BITDEQUE_PAIR[0]):
            program = best_input_order(
                truth_table,
                lambda table, perm: _bitdeque_ordered(table, perm, short=True),
            )
    else:
        program = _bitdeque_linear(truth_table)
    if width is not None:
        from esolangs.tools.wrap import _bitdeque

        return _bitdeque(program, width)
    return program


_BITDEQUE_SHORT_PAIR = ("POP  ", "EJECT")


def _bitdeque_short_load(n: int) -> list[str]:
    """Bracket stored inputs with head one/tail zero before each setter."""
    tokens: list[str] = []
    for i in range(n):
        at = 5 + 15 * i
        # POP/EJECT selects zero/one. Both branches remove the other
        # sentinel, append the selected bit, and restore register zero.
        tokens.extend(
            [
                "INVERT",
                "INJECT",
                "INVERT",
                "PUSH",
                TEMPLATE_CHAR * 5,
                f"GOTO {at + 11}",
                "EJECT",
                "INVERT",
                "PUSH",
                "INVERT",
                f"GOTO {at + 14}",
                "POP",
                "INVERT",
                "PUSH",
                "INVERT",
            ]
        )
    return tokens


def bitdeque_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Resolve the five-character load only from its exact fixed prefix."""
    normalized = " ".join(template.split())
    header = re.match(r"GOTO 3 INVERT GOTO 4 GOTO [0-9]+ INVERT ", normalized)
    short_count = template.count(TEMPLATE_CHAR) // 5
    short_load = " ".join(_bitdeque_short_load(short_count))
    short = header is not None and normalized[header.end() :].startswith(
        short_load + " "
    )
    pair = _BITDEQUE_SHORT_PAIR if short else BITDEQUE_PAIR
    setters = (pair,) * n
    if template.count(TEMPLATE_CHAR) == 5 * n:
        runs(template, TEMPLATE_CHAR, setters)
    return setters


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


def _bitdeque_ordered(
    truth_table: str, perm: tuple[int, ...], *, short: bool = False
) -> str:
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
    mask = (
        0
        if short
        else sum(1 << (n - 1 - level) for level in range(n) if perm[level] % 2)
    )
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
    load_block_in_name_order = (
        _bitdeque_short_load(n) if short else _runs(BITDEQUE_PAIR, n)
    )

    # A node spends its rotation, its pop and its ``GOTO`` before either
    # subtree, so the walker's ``at`` lands on this node and ``at +
    # width(level)`` on the zero subtree.  The load block occupies ``2n``
    # commands ahead of the tree, which is where the indices start, so the
    # ``GOTO`` operands are right after substitution.
    def leaf_tokens(_level: int, row: int) -> list[str]:
        return leaf(seen[row])

    def node(level: int, zero: int, _one: int, at: int) -> list[str]:
        return [*rotations[level], f"GOTO {at + width(level) + zero}"]

    tree = decision_tree_tokens(
        seen,
        leaf_tokens,
        node,
        parent_width=width,
        start=len(prelude) + (15 * n if short else 2 * n),
        collapse=True,
    )
    end = len(prelude) + (15 * n if short else 2 * n) + len(tree)
    tokens = prelude + load_block_in_name_order + tree
    return " ".join("GOTO " + str(end) if t == "GOTO@END" else t for t in tokens)


def minsky_swap(truth_table: str, width: int | None = None) -> str:
    """Build a Minsky Swap template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  Every
    run is ``++`` (``reg[0] = 2``) or ``**`` (swap away and back), and each
    is followed by a stage ``~ ~ * +...+ *`` adding ``2**(n-1-i)`` to
    ``reg[1]``: both ``~`` target the command after the stage, so a one
    falls through to the ``+`` block and a zero jumps it, and either way
    ``reg[0]`` is zero with the pointer on it.  A ``*`` then puts the
    pointer on ``reg[1]`` and ``2**n`` ``~``s route value ``v`` to one of
    two shared leaves behind a line-1 ``~`` that jumps over them at start:
    line 2 halts (a ``~`` targeting one past the end), lines 3-5
    (``+ * ~``) set ``reg[1]`` first.  Every target is the digit 2 or 3 (a
    leaf per row was ``Theta(T log T)`` of addresses), every table of one
    arity is one length, and the dump reads ``0 {answer}``.  Width switches
    to RMSN, one command per line.  Below width 15 a shared increment
    leaves setters eight wide; absolute jump operands set the remaining floor.
    Below that floor, up to two inputs use a nine-command decision chain
    with the first register as scratch; the answer remains the second register.
    """
    n = _validate_truth_table(truth_table)

    zero_leaf, one_leaf = 2, 3
    tokens: list[str] = ["~", "~", "+", "*", "~"]
    targets: list[int] = [6, 0, 0]
    pos = 5  # instantiated command index of the next command

    # load: one stage per input, MSB first; the run is read off the setters
    # themselves, so the offsets count exactly the text the fill emits.
    for i, run in enumerate(_runs(MINSKY_SWAP_PAIR, n)):
        weight = 2 ** (n - 1 - i)
        skip = pos + len(run) + 2 + 2 + weight + 1  # 1-based line after the stage
        tokens += [run, "~", "~", "*", "+" * weight, "*"]
        targets += [skip, skip]
        pos = skip - 1

    tokens.append("*")  # pointer onto reg[1], which holds the index
    pos += 1
    tokens += ["~"] * 2**n
    targets += [one_leaf if bit == "1" else zero_leaf for bit in truth_table]
    pos += 2**n

    end = pos + 1
    resolved = [end if t == 0 else t for t in targets]
    program = " ".join(tokens) + "\n" + " ".join(map(str, resolved))
    if width is None or width <= 0 or max(map(len, program.splitlines())) <= width:
        return program
    if n <= 2 and width < 10:
        # One bit contributes 1, the other 2: common inc plus decnz/inc
        # adds 0/2 without branching. All leaves fit single-digit targets.
        slot = TEMPLATE_CHAR * len(_MINSKY_SMALL_RMSN_PAIR[0])
        lines = [slot] if n == 1 else [slot, "inc();", slot]
        one = len(lines) + len(truth_table) + 1
        for value in range(len(truth_table)):
            row = value if n == 1 else (value & 1) * 2 + (value >> 1)
            lines.append(f"decnz({one if truth_table[row] == '1' else one + 1});")
        return "\n".join([*lines, "swap();", "inc();"])
    lines = []
    jumps = iter(resolved)
    for token in tokens:
        if token.startswith(TEMPLATE_CHAR):
            if width < 15:
                # Both fills still execute two commands, preserving every target.
                lines.extend(
                    ("inc();", TEMPLATE_CHAR * len(_MINSKY_SHORT_RMSN_PAIR[0]))
                )
            else:
                lines.append(TEMPLATE_CHAR * len(_MINSKY_RMSN_PAIR[0]))
        else:
            for command in token:
                lines.append(
                    f"decnz({next(jumps)});"
                    if command == "~"
                    else "inc();"
                    if command == "+"
                    else "swap();"
                )
    return "\n".join(lines)


def minsky_swap_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the uniform pair for compact or line-oriented RMSN notation."""
    pair = MINSKY_SWAP_PAIR
    if template.startswith(TEMPLATE_CHAR * len(_MINSKY_SMALL_RMSN_PAIR[0])):
        pair = _MINSKY_SMALL_RMSN_PAIR
    elif template.startswith("decnz("):
        pair = (
            _MINSKY_RMSN_PAIR
            if TEMPLATE_CHAR * len(_MINSKY_RMSN_PAIR[0]) in template
            else _MINSKY_SHORT_RMSN_PAIR
        )
    return (pair,) * n


def home_row(truth_table: str) -> str:
    """Build a Home Row template for the given truth table.

    ``truth_table`` is a binary string of length ``2**n``, MSB first.  A
    run follows a fixed ``a`` on a zero cell: ``s`` clears it,
    while ``j`` is a skip that does not fire.  The bits pack into one binary
    accumulator: each packing line ``$$ l s ffff a{2**(n-1-i)} f l`` uses
    Home Row's position-stable ``l``/``s``/``l`` gate (loops cannot nest) to
    add the weight iff the bit is 1.  Then guarded leaves count it down:
    ``l s f l`` decrements a nonzero index onto the zeroed bit cell; ``ff``
    lands a zero one on the 48 (print ``<answer> k ;``), the rest on a
    blank, skipped, then back.  Rows agreeing with the last share its unguarded leaf.
    """
    n = _validate_truth_table(truth_table)
    # The leaf chain is up to 2**n leaves, so dropping an ignored input
    # halves the program; its gate stays with weight zero, so nothing moves
    # and no setter changes width.
    used = essential_inputs(truth_table, n)
    # A constant table depends on nothing and reduces to a one-input table,
    # never to the length-1 table, which is not a valid shape.
    table = truth_table if len(used) == n else read_at(truth_table, used or [0], n)
    weights = {i: 2 ** (len(used) - 1 - slot) for slot, i in enumerate(used)}

    setup = "aaaaaalsffaaaaaaaaffflf"
    bit_lines = [
        "a" + run + "lsffff" + "a" * weights.get(i, 0) + "fl"
        for i, run in enumerate(_runs(HOME_ROW_PAIR, n))
    ]
    guarded = table.rstrip(table[-1])
    # Nothing after the last guard reads the index: it need not decrement.
    leaves = [
        "l" + "s" * (row < len(guarded) - 1) + "flffl" + "a" * (bit == "1") + "k;lff"
        for row, bit in enumerate(guarded)
    ]
    # The source's end halts, so the last answer needs no ``;``.
    last = ("ff" if guarded else "f") + "a" * (table[-1] == "1") + "k"
    return setup + "".join(bit_lines) + "ffff" * bool(guarded) + "".join(leaves) + last
