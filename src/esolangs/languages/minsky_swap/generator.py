"""Minsky Swap Boolean program generator: weighted stages, then a ``~`` cascade.

Each input is a run (``++`` or ``**``) then a stage ``~ ~ * +...+ *`` adding
``2**(n-1-i)`` to ``reg[1]``; a ``*`` then points at ``reg[1]`` and ``2**n``
``~``s route the index to one of two shared leaves.  A row is one ``~``, so
no span shrinks.  A ``width`` the program exceeds switches to RMSN, one
command per line.

Size:
    O(T): one ``~`` per row; n=8 random 1847: 1,460 chars, n=10 random 1847:
    5,354 chars, n=12 random 1847: 20,766 chars.

Decisions:
    Every leaf target is the digit 2 or 3: a leaf per row was Theta(T log T)
    of addresses.  A zero tail stays: trimming it failed 60/134.
"""

from collections.abc import Callable
from typing import Any

from esolangs.generation.helpers import (
    TEMPLATE_CHAR,
    _validate_truth_table,
    grid_width,
    input_weights,
    same_up_to_wrapping,
)
from esolangs.generation.wrap import balance_score
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Example, Language, Shape

__all__ = ["MINSKY_SWAP_PAIR", "minsky_swap", "minsky_swap_setters"]


MINSKY_SWAP_PAIR = ("**", "++")

# Setters eight wide sharing an increment.
_MINSKY_SHORT_RMSN_PAIR = ("decnz();", "inc();  ")

_MINSKY_SMALL_RMSN_PAIR = ("decnz(2);", "inc();   ")

_RMSN = {"+": "inc();", "*": "swap();"}


def minsky_swap(truth_table: str, width: int | None = None) -> str:
    """Return a Minsky Swap template for ``truth_table`` (MSB first).

    A ``width`` the program exceeds switches to RMSN.
    """
    n = _validate_truth_table(truth_table)
    weights, table = input_weights(truth_table, n)

    # Two shared leaves sit behind a line-1 ``~`` that jumps over them at
    # start: line 2 halts (a ``~`` targeting one past the end), lines 3-5
    # (``+ * ~``) set ``reg[1]`` first.
    zero_leaf, one_leaf = 2, 3
    tokens: list[str] = ["~", "~", "+", "*", "~"]
    targets: list[int | None] = [6, None, None]  # None: one past the end
    pos = 5  # instantiated command index of the next command

    # load: one stage per input, MSB first; the run is read off the setters
    # themselves, so the offsets count exactly the text the fill emits.  A run
    # is ``++`` (``reg[0] = 2``) or ``**`` (swap away and back); the stage
    # ``~ ~ * +...+ *`` has both ``~`` target the command after it, so a one
    # falls through to the ``+`` block and a zero jumps it, and either way
    # ``reg[0]`` is zero with the pointer on it.  An ignored input's stage is
    # just ``~ ~``, so every table of one arity whose inputs all matter is
    # one length.
    run = TEMPLATE_CHAR * len(MINSKY_SWAP_PAIR[0])
    for weight in weights:
        if not weight:
            # An ignored input's two decrements drain its run, jumping nowhere
            # (target 0), so ``reg[0]`` is zero either way and nothing is added.
            tokens += [run, "~", "~"]
            targets += [0, 0]
            pos += len(run) + 2
            continue
        # run, 2 tildes, 2 stars, the + block, then +1 for the 1-based line
        skip = pos + len(run) + 2 + 2 + weight + 1
        tokens += [run, "~", "~", "*", "+" * weight, "*"]
        targets += [skip, skip]
        pos = skip - 1

    # pointer onto reg[1], which holds the index; the ``~``s route it to a leaf
    tokens.append("*")
    pos += 1
    tokens += ["~"] * len(table)
    targets += [one_leaf if bit == "1" else zero_leaf for bit in table]
    pos += len(table)

    end = pos + 1
    resolved = [end if t is None else t for t in targets]
    program = " ".join(tokens) + "\n" + " ".join(map(str, resolved))
    if width is None or grid_width(program) <= width:
        return program
    if n <= 2 and width < 10:
        return _rmsn_small(truth_table, n)
    return _rmsn_expand(tokens, resolved)


def _rmsn_small(truth_table: str, n: int) -> str:
    """Decision-chain RMSN for ``n <= 2``, whose lines stay under 10 columns.

    Nine commands at ``n = 2``; the first register is scratch, the answer
    stays in the second.
    """
    # One bit contributes 1, the other 2: common inc plus decnz/inc
    # adds 0/2 without branching. All leaves fit single-digit targets.
    slot = TEMPLATE_CHAR * len(_MINSKY_SMALL_RMSN_PAIR[0])
    lines = [slot] if n == 1 else [slot, "inc();", slot]
    one = len(lines) + len(truth_table) + 1
    for value in range(len(truth_table)):
        # the chain adds the low bit as 2 and the high bit as 1: swap them
        row = value if n == 1 else (value & 1) * 2 + (value >> 1)
        lines.append(f"decnz({one if truth_table[row] == '1' else one + 1});")
    return "\n".join([*lines, "swap();", "inc();"])


def _rmsn_expand(tokens: list[str], jumps: list[int]) -> str:
    """One RMSN command per line: short setters, ``~`` taking ``jumps`` in order."""
    lines: list[str] = []
    targets = iter(jumps)
    for token in tokens:
        if token.startswith(TEMPLATE_CHAR):
            # Both fills still execute two commands, preserving every target.
            lines.extend(("inc();", TEMPLATE_CHAR * len(_MINSKY_SHORT_RMSN_PAIR[0])))
        else:
            for command in token:
                lines.append(
                    f"decnz({next(targets)});" if command == "~" else _RMSN[command]
                )
    return "\n".join(lines)


def minsky_swap_setters(template: str, n: int) -> tuple[tuple[str, str], ...]:
    """Return the uniform pair for compact or line-oriented RMSN notation."""
    pair = MINSKY_SWAP_PAIR
    if template.startswith(TEMPLATE_CHAR * len(_MINSKY_SMALL_RMSN_PAIR[0])):
        pair = _MINSKY_SMALL_RMSN_PAIR
    elif template.startswith("decnz("):
        pair = _MINSKY_SHORT_RMSN_PAIR
    return (pair,) * n


def _balance(table: str, default: str) -> str:
    """Compare compact source and the three line-oriented setter regimes."""
    return min(default, minsky_swap(table, 1), key=balance_score)


def _same_layout(template: str, plain: str, layout: Callable[[int], Any]) -> bool:
    """Its 10- and 15-wide layouts switch representation, so match them whole."""
    return template in (layout(10), layout(15)) or same_up_to_wrapping(template, plain)


LANGUAGE = Language(
    "Minsky Swap",
    "minsky_swap",
    category="register_based",
    boolean=minsky_swap,
    same_layout=_same_layout,
    # Not a tree: each input adds its weight; a ``~`` cascade picks one of two leaves.
    shape=Shape.LOOKUP,
    contract=BooleanContract(
        answer_mode="dump",
        note="Minsky Swap has no output instruction and dumps its "
        "registers at halt; the answer is the second one",
    ),
    balance=_balance,
    no_wrap="only line 1 is code; line 2 gives its numeric jump distances",
    example=Example(setters=minsky_swap_setters, expected="1 0"),
)
