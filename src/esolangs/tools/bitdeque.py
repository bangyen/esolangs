"""Boolean template generator for bitdeque."""

import re

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language
from esolangs.tools.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    best_input_order,
    input_weights,
    runs,
    subtree_ids,
)
from esolangs.tools.token_balance import balanced_token_width
from esolangs.tools.wrap import _bitdeque, _bitdeque_tokens, _join_tokens, balance_score

__all__ = ["BITDEQUE_PAIR", "bitdeque", "bitdeque_setters"]


BITDEQUE_PAIR = ("PUSH INVERT", "INVERT PUSH")


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
    A constant subtree is one leaf, and a subtree repeated at its level is
    emitted once and reached by ``GOTO`` (n=4, all 65,536 tables: -49.3%, none
    longer).  Past n=4 the shorter of that tree and the linear discard lookup
    is kept (tree 0.48x to 0.29x at n=5..10, random tables; never longer).
    Width < 11 with n <= 4 loads each input via POP/EJECT on fresh zero/one
    endpoints (15 commands each); otherwise the load is the linear ``2n``.
    """
    small = len(truth_table) <= 16
    short = small and width is not None and width < len(BITDEQUE_PAIR[0])
    program = best_input_order(
        truth_table,
        lambda table, perm: _bitdeque_ordered(table, perm, short=short),
    )
    if not small:
        program = min(program, _bitdeque_linear(truth_table), key=len)
    if width is not None:
        from esolangs.tools.wrap import _bitdeque

        return _bitdeque(program, width)
    return program


_BITDEQUE_SHORT_PAIR = ("POP  ", "EJECT")
_PRELUDE_LEN = 5
_SHORT_BLOCK = 15


def _bitdeque_short_load(n: int) -> list[str]:
    """Bracket stored inputs with head one/tail zero before each setter."""
    tokens: list[str] = []
    for i in range(n):
        # The block's first command, counted from 1 as ``GOTO`` counts.
        at = _PRELUDE_LEN + 1 + _SHORT_BLOCK * i
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
    header = re.match(r"GOTO 4 INVERT GOTO 5 GOTO [0-9]+ INVERT ", normalized)
    short_count = template.count(TEMPLATE_CHAR) // 5
    short_load = " ".join(_bitdeque_short_load(short_count))
    short = header is not None and normalized[header.end() :].startswith(
        short_load + " "
    )
    pair = _BITDEQUE_SHORT_PAIR if short else BITDEQUE_PAIR
    setters = (pair,) * n
    if template.count(TEMPLATE_CHAR) == 5 * n:
        # Called only to raise if the runs do not match the setters.
        runs(template, TEMPLATE_CHAR, setters)
    return setters


def _bitdeque_linear(truth_table: str) -> str:
    """Push the table, then discard its prefix and suffix in O(T) text.

    After the table is pushed, each run pushes its bit, ``POP`` takes it into
    the register, and a ``GOTO`` picks a discard block: ``EJECT`` the upper
    half off the head for a one, ``POP`` the lower half off the tail for a
    zero, ``2**(n-1-i)`` commands each, meeting at a block that zeroes the
    register.  The last input skips that.  ``2T`` commands long, ``T`` executed.
    An ignored input's bit is popped straight back and the register zeroed,
    so the table indexes the rest.
    """
    n = _validate_truth_table(truth_table)
    weights, truth_table = input_weights(truth_table, n)
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
    # Command numbers count from 1, as ``GOTO`` does.
    at = len(tokens) + 1
    run = TEMPLATE_CHAR * len(BITDEQUE_PAIR[0])
    for i, k in enumerate(weights):
        if not k:
            # Pop the bit back; a one skips the first INVERT, zeroing it.
            tokens += [run, "POP", f"GOTO {at + 5}", "INVERT", "INVERT"]
            at += 6
            continue
        # ``run`` is one token of text but two commands once filled.
        at += 2
        # Command numbers, with ``at`` the ``POP`` that reads the bit back:
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
        out.append("GOTO 1")
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

    # Commands count from 1.  Initially command 1 falls through on zero and
    # commands 2/3 skip the trampoline.  A leaf returns with one, so ``GOTO
    # 1`` reaches command 4; only that command carries the widening end
    # address.
    prelude = ["GOTO 4", "INVERT", "GOTO 5", "GOTO@END", "INVERT"]
    # The setters read the route off the prelude's opening ``GOTO 4``.
    load = (
        _bitdeque_short_load(n)
        if short
        else [TEMPLATE_CHAR * len(BITDEQUE_PAIR[0])] * n
    )
    # Each linear run fills to two commands.
    load_len = _SHORT_BLOCK * n if short else 2 * n

    # A node spends its rotation, its pop and its ``GOTO`` before either
    # subtree.  Commands count from 1 and the load occupies ``2n`` of them
    # ahead of the tree, so the ``GOTO`` operands are right after substitution.
    # A subtree already emitted is reached by ``GOTO`` to its first copy: a
    # one-child's node operand, or ``INVERT GOTO`` where a zero-child falls in
    # (``GOTO`` is taken on a one, and the register holds the zero just popped).
    # Every subtree opens with a pop, so it ignores the register it is entered
    # with.  Equal halves drop the node's ``GOTO``: the zero subtree is the only one.
    ids = subtree_ids(seen)
    placed: dict[int, int] = {}

    def walk(level: int, block: int, at: int) -> list[str]:
        key = ids[level][block]
        if key in placed:
            return ["INVERT", f"GOTO {placed[key]}"]
        placed[key] = at
        if key < 2:
            return leaf(seen[block << (n - level)])
        zero_key, one_key = ids[level + 1][2 * block : 2 * block + 2]
        rotation = rotations[level]
        if zero_key == one_key and zero_key not in placed:
            return [*rotation, *walk(level + 1, 2 * block, at + len(rotation))]
        below = at + width(level)
        zero = walk(level + 1, 2 * block, below)
        if one_key in placed:
            return [*rotation, f"GOTO {placed[one_key]}", *zero]
        one = walk(level + 1, 2 * block + 1, below + len(zero))
        return [*rotation, f"GOTO {below + len(zero)}", *zero, *one]

    tree = walk(0, 0, len(prelude) + load_len + 1)
    end = len(prelude) + load_len + len(tree) + 1
    tokens = prelude + load + tree
    return " ".join("GOTO " + str(end) if t == "GOTO@END" else t for t in tokens)


def _balance(table: str, default: str) -> str:
    """Balance the eleven-cell and short endpoint loads in their width regimes."""
    normal = _bitdeque_tokens(default)
    short = _bitdeque_tokens(bitdeque(table, 1))
    normal_width = balanced_token_width(normal, " ", minimum=11)
    short_width = balanced_token_width(short, " ", maximum=10)
    return min(
        default,
        _join_tokens(normal, normal_width, " "),
        _join_tokens(short, short_width, " "),
        key=balance_score,
    )


LANGUAGE = Language(
    "Bitdeque",
    "queue_based.bitdeque",
    boolean=bitdeque,
    contract=BooleanContract(
        answer_mode="dump",
        note="Bitdeque has no output instruction and dumps its deque at "
        "halt; the generator leaves exactly one bit on it, so the "
        "whole dump is the answer and there is no position to name",
        parameterized=True,
    ),
    # Space-delimited, but ``GOTO`` and its target must stay on one line.
    wrap=_bitdeque,
    balance=_balance,
    example=Example(setters=bitdeque_setters),
)
