"""Bitdeque Boolean template generator: a deque load, then a pop-and-GOTO tree.

The default load pushes each bit as the fixed pair ``PUSH INVERT`` / ``INVERT
PUSH`` (``2n`` commands); narrow short loads use 15n commands with jumps.
Each node pops one bit and
``GOTO``s its one-subtree, and a leaf drains the deque, pushes the answer and
halts through a low-address trampoline.  The split order is input order
(a greedy reorder saved 0.9% at n=8, 60 random tables); rotations happen
inside the tree, so the load is byte-identical under every order.  Constant
subtrees are one leaf and a repeated subtree at its level is reached by
``GOTO``.

Size:
    O(n) for parity and and, O(T) for dense tables;
    n=8 constant zero: 136 chars; n=10 parity: 580 chars,
    n=10 and: 441 chars, n=10 random 1847: 5,470 chars.

Decisions:
    A deque's ``EJECT``/``INJECT`` work the head, so any bit reaches an end at
    two commands per position: measured, not modelled.  Sharing: n=4, all
    65,536 tables, none longer ([ablations.subtree_sharing]).  A linear
    discard lookup raced the tree and won on 0 of 215 tables (random, parity,
    and, majority; n=5..9): retired.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from esolangs._bindings import TEMPLATE_CHAR, runs
from esolangs.generation.decision import DecisionLayers, decision_layers
from esolangs.generation.helpers import _validate_truth_table, same_tokens
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_tokens,
)
from esolangs.generation.token_balance import balanced_token_width

__all__ = ["BITDEQUE_PAIR", "bitdeque", "bitdeque_setters"]


BITDEQUE_PAIR = ("PUSH INVERT", "INVERT PUSH")

_BITDEQUE_SHORT_PAIR = ("POP  ", "EJECT")
_PRELUDE_LEN = 5
#: One setter run: a token of template text, two commands once filled.
_SETTER = InputSlot(len(BITDEQUE_PAIR[0]))
_SHORT_SETTER = InputSlot(5)
_SHORT_BLOCK = 15


def bitdeque(truth_table: str, width: int | None = None) -> str:
    """Build a Bitdeque template for ``truth_table`` (length ``2**n``, MSB first).

    ``width`` wraps the program; below 11 with n <= 4 it uses the short load.
    """
    return _layout(truth_table, width).source


def _layout(truth_table: str, width: int | None) -> TemplateLayout:
    small = len(truth_table) <= 16
    short = small and width is not None and width < len(BITDEQUE_PAIR[0])
    return layout_tokens(_bitdeque_ordered(truth_table, short=short), width)


def _bitdeque_short_load(n: int) -> list[TemplateToken]:
    """Bracket stored inputs with head one/tail zero before each setter.

    Loads each input via POP/EJECT on fresh zero/one endpoints, 15 commands each.
    """
    tokens: list[TemplateToken] = []
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
                _SHORT_SETTER,
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
    short_load = layout_tokens(_bitdeque_short_load(short_count)).source
    short = header is not None and normalized[header.end() :].startswith(
        short_load + " "
    )
    pair = _BITDEQUE_SHORT_PAIR if short else BITDEQUE_PAIR
    setters = (pair,) * n
    if template.count(TEMPLATE_CHAR) == 5 * n:
        # Called only to raise if the runs do not match the setters.
        runs(template, TEMPLATE_CHAR, setters)
    return setters


@dataclass
class _BitdequeTreeBuilder:
    """Emit the pop-and-GOTO tree, remembering where each subtree was placed.

    ``placed`` maps a subtree id to the command address (counted from 1) of
    its first emitted copy; a repeat is reached by ``GOTO`` to that copy
    instead of being emitted again, so the walk's address arithmetic and
    the placement table live here rather than in shared closure cells.
    """

    n: int
    diagram: DecisionLayers
    placed: dict[int, int] = field(default_factory=dict)
    #: Print the last bit itself, or its complement, at a last level whose
    #: leaves differ.  Only while at most one constant kind sits above the
    #: leaves: with both placed, a node reaches them by two ``GOTO`` stubs,
    #: which is shorter ([ablations.last_level_forms]).
    last_forms: bool = False

    def leaf(self, answer: str) -> list[str]:
        """Emit a leaf for ``answer``."""
        # Drain n+1 POPs, push the answer, INVERT restores the register, and
        # GOTO 1 halts through the low-address trampoline.
        out = ["POP"] * (self.n + 1)
        if answer == "1":
            out.append("INVERT")
        out.append("PUSH")
        if answer == "0":
            out.append("INVERT")
        out.append("GOTO 1")
        return out

    def walk(self, level: int, key: int, at: int) -> list[str]:
        """Emit the subtree ``key`` at ``level``, its first command at ``at``.

        A subtree already emitted is reached by ``GOTO`` to its first copy:
        a one-child's node operand, or ``INVERT GOTO`` where a zero-child
        falls in (``GOTO`` is taken on a one, and the register holds the
        zero just popped).  Every subtree opens with a pop, so it ignores
        the register it is entered with.  Equal halves drop the node's
        ``GOTO``: the zero subtree is the only one.
        """
        if key in self.placed:
            return ["INVERT", f"GOTO {self.placed[key]}"]
        self.placed[key] = at
        if key < 2:
            return self.leaf(str(key))
        zero_key, one_key = self.diagram.children[level][key]
        if self.last_forms and level == self.n - 1:
            flip = [] if (zero_key, one_key) == (0, 1) else ["INVERT"]
            return ["POP", *flip, "PUSH", "GOTO 1", "INVERT", "GOTO 1"]
        rotation = "POP" if level == self.n - 1 else "EJECT"
        if zero_key == one_key and zero_key not in self.placed:
            return [rotation, *self.walk(level + 1, zero_key, at + 1)]
        below = at + 2
        zero = self.walk(level + 1, zero_key, below)
        if one_key in self.placed:
            return [rotation, f"GOTO {self.placed[one_key]}", *zero]
        one = self.walk(level + 1, one_key, below + len(zero))
        return [rotation, f"GOTO {below + len(zero)}", *zero, *one]

    def build(self, start: int) -> list[str]:
        """Emit the whole tree, its first command at address ``start``."""
        return self.walk(0, self.diagram.root, start)


def _bitdeque_ordered(truth_table: str, *, short: bool = False) -> list[TemplateToken]:
    """Emit the Bitdeque template; see :func:`bitdeque`.

    Level ``i`` consumes input ``i`` from the head (``EJECT``); the last
    level's lone bit is popped.  Bits are pushed in stream order so ``EJECT``
    yields the MSB first; the register flips after every load block, so
    odd load positions push complemented;
    the tree reads the table with those inputs complemented back
    (``row ^ mask``), a relabelling that folds as the table did.
    """
    n = _validate_truth_table(truth_table)
    if not short and truth_table.count(truth_table[0]) == len(truth_table):
        # [ablations.constant_table_audit_20261101]: no branch needs a trampoline.
        tokens: list[TemplateToken] = [*[_SETTER] * n, *["POP"] * (n + 1)]
        tokens += (["INVERT"] if truth_table[0] == "1" else []) + ["PUSH"]
        return tokens
    # Level ``level`` tests input ``level``, whose load position is its name;
    # the row bit for a level is ``n - 1 - level``.
    mask = 0 if short else sum(1 << (n - 1 - level) for level in range(n) if level % 2)
    seen = "".join(truth_table[row ^ mask] for row in range(2**n))

    # Commands count from 1.  Initially command 1 falls through on zero and
    # commands 2/3 skip the trampoline.  A leaf returns with one, so ``GOTO
    # 1`` reaches command 4; only that command carries the widening end
    # address.
    prelude = ["GOTO 4", "INVERT", "GOTO 5", "GOTO@END", "INVERT"]
    # The setters read the route off the prelude's opening ``GOTO 4``.
    load = _bitdeque_short_load(n) if short else [_SETTER] * n
    # Each linear run fills to two commands.
    load_len = _SHORT_BLOCK * n if short else 2 * n

    # A node spends its EJECT/POP and its ``GOTO`` before either
    # subtree. Commands count from 1; the load occupies ``load_len`` commands
    # ahead of the tree, so the ``GOTO`` operands are right after substitution.
    diagram = decision_layers(seen)
    constants = {key for layer in diagram.children for key in layer if key < 2}
    builder = _BitdequeTreeBuilder(
        n=n,
        diagram=diagram,
        last_forms=len(constants) < 2,
    )
    tree = builder.build(len(prelude) + load_len + 1)
    end = len(prelude) + load_len + len(tree) + 1
    prelude[3] = f"GOTO {end}"
    return [*prelude, *load, *tree]


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Commands tokenize on whitespace, which its wrapper turns to newlines."""
    return same_tokens(template, layout(1)) or same_tokens(template, plain)


def _bitdeque(program: str, width: int) -> str:
    """Wrap Bitdeque, keeping each ``GOTO`` with its target operand."""
    return layout_tokens(_bitdeque_tokens(program.split()), width).source


def _bitdeque_tokens(program: Iterable[TemplateToken]) -> list[TemplateToken]:
    """Return Bitdeque commands with their attached branch operands."""
    tokens: list[TemplateToken] = []
    for token in program:
        if tokens and tokens[-1] == "GOTO" and isinstance(token, str):
            tokens[-1] = f"GOTO {token}"
        else:
            tokens.append(token)
    return tokens


def bitdeque_request(request: GenerationRequest) -> TemplateLayout:
    """Emit source through the declared generation request interface."""
    return _layout(request.table, request.width)


def bitdeque_balance_request(request: BalanceRequest) -> TemplateLayout:
    """Balance the default eleven-cell endpoint loads."""
    if not isinstance(request.source, TemplateLayout):
        raise TypeError("balancing needs a rendered template with slots")
    tokens = _bitdeque_tokens(request.source.tokens())
    widths = [token if isinstance(token, str) else "x" * len(token) for token in tokens]
    return layout_tokens(tokens, balanced_token_width(widths, " ", minimum=11))
