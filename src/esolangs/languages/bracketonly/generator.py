"""BracketOnly Boolean generator using lazy if calls.

Each node reads the next ASCII input digit and visits only its chosen arm.
Equal arms share one reader and one child. Constant spans drain the
remaining inputs before printing their bit. The writer appends each node's fixed
syntax once and joins once. Time and emitted characters are O(T).

Size:
    O(T) characters, n=4 parity: 4,780 chars.
"""

from esolangs.generation.helpers import subtree_ids
from esolangs.generation.requests import GenerationRequest
from esolangs.languages.bracketonly._functions import Function
from esolangs.runtime._program import Program

_ONE = "()()"


def _open(function: Function) -> str:
    return "(" + _ONE * function + ")("


def _call(function: Function, *args: str) -> str:
    return _open(function) + "".join(args) + ")"


def _digit(value: int) -> str:
    return _call(Function.ADD, _ONE * value)


_ASCII_ZERO = _call(Function.MUL, _digit(6), _digit(8))
_READ = _call(Function.INPC)
_CONDITION = _open(Function.IF) + _call(Function.SUB, _READ, _ASCII_ZERO)
_SKIP = _open(Function.ADD) + _READ
_ANSWERS = (
    _call(Function.OUTC, _ASCII_ZERO),
    _call(Function.OUTC, _call(Function.ADD, _ASCII_ZERO, _ONE)),
)


def bracketonly(truth_table: str) -> str:
    """Emit a loop-less lazy tree that reads each digit once on its path."""
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    parts: list[str] = []

    def emit(level: int, block: int) -> None:
        node = ids[level][block]
        if node < 2:
            # The consumed characters contribute only to an unused return value.
            remaining = n - level
            if remaining:
                parts.append(_open(Function.ADD) + _READ * remaining)
            parts.append(_ANSWERS[node])
            if remaining:
                parts.append(")")
            return

        below = level + 1
        zero = block << 1
        if ids[below][zero] == ids[below][zero + 1]:
            parts.append(_SKIP)
            emit(below, zero)
        else:
            parts.append(_CONDITION)
            emit(below, zero + 1)
            emit(below, zero)
        parts.append(")")

    emit(0, 0)
    return "".join(parts)


def bracketonly_request(request: GenerationRequest) -> Program:
    """Emit source through the registered Boolean backend."""
    return bracketonly(request.table)
