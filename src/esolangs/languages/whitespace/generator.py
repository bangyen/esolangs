"""Whitespace Boolean program generator: divide one literal by a power of two.

The stack holds the packed table and ``p = 2**index``. Each essential input
updates ``p`` to ``p*p*(1+x)``; division by p exposes the answer bit. Repeated
input steps share one subroutine; ignored inputs are read into heap 0.

Size:
    O(T) characters and O(n) commands; n=4 parity: 101 chars,
    n=8 random 1847: 357 chars. Constants: 7n+11+b chars, 2n+3 commands,
    b the answer. Workspace is O(T): heap addresses are powers of two.

Decisions:
    The earlier Horner-index reader rejected literal chunking for ``balance``: every
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
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_SPACE = " "
_TAB = "\t"
_LINE = "\n"

#: The tab/space/line tokens each command is built from, named so a run of
#: whitespace at the emission site cannot silently become another command.
_DUP = _SPACE + _LINE + _SPACE
_ADD = _TAB + _SPACE + _SPACE + _SPACE
_MUL = _TAB + _SPACE + _SPACE + _LINE
_DIV = _TAB + _SPACE + _TAB + _SPACE
_MOD = _TAB + _SPACE + _TAB + _TAB
_RETRIEVE = _TAB + _TAB + _TAB
_OUT_NUM = _TAB + _LINE + _SPACE + _TAB
_READ_NUM = _TAB + _LINE + _TAB + _TAB
_END = _LINE * 3
_CALL = _LINE + _SPACE + _TAB + _LINE
_RETURN = _LINE + _TAB + _LINE


def _push(value: int) -> str:
    """Return the push of a non-negative ``value``: a sign token, then binary."""
    digits = f"{value:b}" if value else ""
    bits = "".join(_TAB if digit == "1" else _SPACE for digit in digits)
    return _SPACE + _SPACE + _SPACE + bits + _LINE


def _mark(label: str) -> str:
    return _LINE + _SPACE + _SPACE + label + _LINE


def whitespace(truth_table: str) -> str:
    """Build a Whitespace program printing ``truth_table[row]`` for the inputs.

    A read uses the squared power as its heap address, then multiplies that
    power by 1+x. Final line feeds are command tokens and must be preserved.
    """
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    table = int(read_at(truth_table, essential, n)[::-1], 2)
    if not essential:
        parts = [_push(table), *[_DUP, _READ_NUM] * n, _OUT_NUM, _END]
        return "".join(parts)
    step = "".join([_DUP, _MUL, _DUP, _READ_NUM, _DUP, _RETRIEVE, _push(1), _ADD, _MUL])
    # [ablations.power_subroutine_20261102]: one occurrence is inline;
    # sharing m occurrences saves 29m-40 chars, positive exactly at m >= 2.
    shared = len(essential) >= 2
    parts = [_push(table), _push(1)]
    for i in range(n):
        parts += (
            [_CALL if shared else step] if i in essential else [_push(0), _READ_NUM]
        )
    parts += [_DIV, _push(2), _MOD, _OUT_NUM, _END]
    if shared:
        parts += [_mark(""), step, _RETURN]
    return "".join(parts)


LANGUAGE = Language(
    "Whitespace",
    RuntimeSpec(
        "whitespace",
        category="stack_based",
        empty_program="Whitespace program is empty",
    ),
    backend=BooleanBackend(
        generate=whitespace,
        shape=Shape.REDUCING,
        no_wrap="a line feed is a token, so a break changes the command it splits",
    ),
)
