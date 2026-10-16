"""Bitdeque Boolean template generator: a deque load, then a pop-and-GOTO tree.

The load pushes every input bit as the fixed pair ``PUSH INVERT`` / ``INVERT
PUSH`` (``2n`` commands, no absolute ``GOTO``); each node pops one bit and
``GOTO``s its one-subtree, and a leaf drains the deque, pushes the answer and
halts through a low-address trampoline.  The split order is input order
(a greedy reorder saved 0.9% at n=8, 60 random tables); rotations happen
inside the tree, so the load is byte-identical under every order.  Constant
subtrees are one leaf and a repeated subtree at its level is reached by
``GOTO``.

Size:
    O(n) for parity and and, O(T) for dense tables; n=10 parity: 682 chars,
    n=10 and: 479 chars, n=10 random 1847: 5,470 chars.

Decisions:
    A deque's ``EJECT``/``INJECT`` work the head, so any bit reaches an end at
    two commands per position: measured, not modelled.  Sharing: n=4, all
    65,536 tables, -49.3%, none longer.  A linear discard lookup raced the tree
    and won on 0 of 215 tables (random, parity, and, majority; n=5..9): retired.
"""

import re
from collections.abc import Callable
from typing import Any

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    runs,
    same_tokens,
    subtree_ids,
)
from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import _join_tokens, balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language

__all__ = ["BITDEQUE_PAIR", "bitdeque", "bitdeque_setters"]


BITDEQUE_PAIR = ("PUSH INVERT", "INVERT PUSH")

_BITDEQUE_SHORT_PAIR = ("POP  ", "EJECT")
_PRELUDE_LEN = 5
#: One setter run: a token of template text, two commands once filled.
_SETTER = TEMPLATE_CHAR * len(BITDEQUE_PAIR[0])
_SHORT_BLOCK = 15


def bitdeque(truth_table: str, width: int | None = None) -> str:
    """Build a Bitdeque template for ``truth_table`` (length ``2**n``, MSB first).

    ``width`` wraps the program; below 11 with n <= 4 it uses the short load.
    """
    small = len(truth_table) <= 16
    short = small and width is not None and width < len(BITDEQUE_PAIR[0])
    n = _validate_truth_table(truth_table)
    program = _bitdeque_ordered(truth_table, tuple(range(n)), short=short)
    if width is not None:
        return _bitdeque(program, width)
    return program


def _bitdeque_short_load(n: int) -> list[str]:
    """Bracket stored inputs with head one/tail zero before each setter.

    Loads each input via POP/EJECT on fresh zero/one endpoints, 15 commands each.
    """
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


def _bitdeque_ordered(
    truth_table: str, perm: tuple[int, ...], *, short: bool = False
) -> str:
    """Emit one input order's Bitdeque template; see :func:`bitdeque`.

    ``perm`` is spent on the rotations before a node consumes its bit, a
    function of the level alone, so a node's width is well-defined.  The
    identity order emits no rotation.  Bits are pushed in reverse so ``POP``
    yields the MSB first; the register flips after every load block, so
    odd load positions push complemented;
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
        # Drain n+1 POPs, push the answer, INVERT restores the register, and
        # GOTO 1 halts through the low-address trampoline.
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
    load = _bitdeque_short_load(n) if short else [_SETTER] * n
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


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Commands tokenize on whitespace, which its wrapper turns to newlines."""
    return same_tokens(template, layout(1)) or same_tokens(template, plain)


def _bitdeque(program: str, width: int) -> str:
    """Wrap Bitdeque, keeping each ``GOTO`` with its target operand."""
    return _join_tokens(_bitdeque_tokens(program), width, separator=" ")


def _bitdeque_tokens(program: str) -> list[str]:
    """Return Bitdeque commands with their attached branch operands."""
    tokens: list[str] = []
    for token in program.split():
        if tokens and tokens[-1] == "GOTO":
            tokens[-1] = f"GOTO {token}"
        else:
            tokens.append(token)
    return tokens


LANGUAGE = Language(
    "Bitdeque",
    "bitdeque",
    category="queue_based",
    boolean=bitdeque,
    same_layout=_same_layout,
    contract=BooleanContract(
        answer_mode="dump",
        note="Bitdeque has no output instruction and dumps its deque at "
        "halt; the generator leaves exactly one bit on it, so the "
        "whole dump is the answer and there is no position to name",
    ),
    # Space-delimited, but ``GOTO`` and its target must stay on one line.
    wrap=_bitdeque,
    balance=_balance,
    example=Example(setters=bitdeque_setters),
)
