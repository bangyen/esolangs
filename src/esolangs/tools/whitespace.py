"""Whitespace boolean program builder: one literal, halved per index step.

``whitespace(truth_table)`` reads one ``0``/``1`` line per input, folds them
into a row index with Horner's rule, and pushes the whole table as a single
binary number whose bit ``r`` is ``table[r]``.  Halving that number once per
index step leaves the answer in the low bit, so no per-row address is ever
spelled: O(T) characters of source and O(T) executed commands.
"""

from __future__ import annotations

from esolangs.tools.helpers import _validate_truth_table

_SPACE = " "
_TAB = "\t"
_LINE = "\n"

#: The tab/space/line tokens each command is built from, named so a run of
#: whitespace at the emission site cannot silently become another command.
_SWAP = _SPACE + _LINE + _TAB
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
    """Return a Whitespace program computing ``truth_table``.

    Address 0 is the read scratch, address 1 the index and address 2 the
    table.  The loop halves the table and decrements the index; at zero it
    takes the low bit.  The trailing ``swap`` is dead code past ``end``: the
    example writer strips trailing newlines, and ``end`` is three of them.
    """
    n = _validate_truth_table(truth_table)
    table = int(truth_table[::-1], 2)
    loop, done = _SPACE, _TAB

    parts = [_push(0)]
    for _ in range(n):
        parts += [
            _push(0),
            _READ_NUM,
            _push(0),
            _RETRIEVE,
            _SWAP,
            _push(2),
            _MUL,
            _ADD,
        ]
    parts += [_push(1), _SWAP, _STORE]
    parts += [_push(table), _push(2), _SWAP, _STORE]
    parts += [
        _mark(loop),
        _push(1),
        _RETRIEVE,
        _jz(done),
        _push(2),
        _RETRIEVE,
        _push(2),
        _DIV,
        _push(2),
        _SWAP,
        _STORE,
        _push(1),
        _RETRIEVE,
        _push(1),
        _SUB,
        _push(1),
        _SWAP,
        _STORE,
        _jump(loop),
        _mark(done),
        _push(2),
        _RETRIEVE,
        _push(2),
        _MOD,
        _OUT_NUM,
        _END,
        _SWAP,
    ]
    return "".join(parts)
