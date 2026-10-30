"""Whitespace Boolean program generator: one literal, halved per index step.

The program pushes the whole table as a single binary number whose bit ``r``
is ``table[r]``, then reads one number per input and folds them into a row
index with Horner's rule on top of it.  A loop halves the table once per index
step and leaves the answer in the low bit, so no per-row address is ever
spelled.  An
ignored input is read and dropped, and the literal covers only the essential
inputs.

Size:
    O(T) characters and O(T) commands; n=4 parity: 176 chars,
    n=8 random 1847: 512 chars.

Decisions:
    Horner-chunking the literal to a width was rejected for ``balance``: every
    chunk adds a multiply, an add and a separator line, so a 256-bit table at
    width 80 renders 838 on the squarest-side score against 263 for the one
    literal.
"""

from __future__ import annotations

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.registry._language import Language, Shape

_SPACE = " "
_TAB = "\t"
_LINE = "\n"

#: The tab/space/line tokens each command is built from, named so a run of
#: whitespace at the emission site cannot silently become another command.
_DUP = _SPACE + _LINE + _SPACE
_SWAP = _SPACE + _LINE + _TAB
_DROP = _SPACE + _LINE + _LINE
_ADD = _TAB + _SPACE + _SPACE + _SPACE
_SUB = _TAB + _SPACE + _SPACE + _TAB
_MUL = _TAB + _SPACE + _SPACE + _LINE
_DIV = _TAB + _SPACE + _TAB + _SPACE
_MOD = _TAB + _SPACE + _TAB + _TAB
_STORE = _TAB + _TAB + _SPACE
_RETRIEVE = _TAB + _TAB + _TAB
_OUT_NUM = _TAB + _LINE + _SPACE + _TAB
_READ_NUM = _TAB + _LINE + _TAB + _TAB
_END = _LINE * 3


def _push(value: int) -> str:
    """Return the push of a non-negative ``value``: a sign token, then binary."""
    digits = bin(value)[2:] if value else ""
    bits = "".join(_TAB if digit == "1" else _SPACE for digit in digits)
    return _SPACE + _SPACE + _SPACE + bits + _LINE


def _mark(label: str) -> str:
    return _LINE + _SPACE + _SPACE + label + _LINE


def _jump(label: str) -> str:
    return _LINE + _SPACE + _LINE + label + _LINE


def _jz(label: str) -> str:
    return _LINE + _TAB + _SPACE + label + _LINE


def whitespace(truth_table: str) -> str:
    """Build a Whitespace program printing ``truth_table[row]`` for the inputs.

    The stack holds ``[table, index]`` throughout; a read lands in the heap
    cell the running index addresses (heap 0 for the first and for an ignored
    input, which is dropped); a constant table prints its bit.
    The trailing ``swap`` is dead code past ``end``: the example writer strips
    trailing newlines, and ``end`` is three of them.
    """
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = int(read_at(truth_table, essential, n)[::-1], 2)
    loop, done = _SPACE, _TAB
    if not essential:
        parts = [_push(0), _READ_NUM] * n
        return "".join([*parts, _push(table), _OUT_NUM, _END])
    # Stack [table, index]: Horner doubles the index, reads into the heap cell
    # the index itself addresses, and adds that cell back.
    parts = [_push(table)]
    first = True
    for i in range(n):
        if i not in essential:
            parts += [_push(0), _READ_NUM]
        elif first:
            parts += [_push(0), _DUP, _READ_NUM, _RETRIEVE]
            first = False
        else:
            parts += [_DUP, _ADD, _DUP, _READ_NUM, _DUP, _RETRIEVE, _ADD]
    parts += [
        _mark(loop),
        _DUP,
        _jz(done),
        _SWAP,
        _push(2),
        _DIV,
        _SWAP,
        _push(1),
        _SUB,
        _jump(loop),
        _mark(done),
        _DROP,
        _push(2),
        _MOD,
        _OUT_NUM,
        _END,
        _SWAP,
    ]
    return "".join(parts)


LANGUAGE = Language(
    "Whitespace",
    "whitespace",
    category="stack_based",
    boolean=whitespace,
    shape=Shape.REDUCING,
    empty_program="Whitespace program is empty",
    no_wrap="a line feed is a token, so a break changes the command it splits",
)
