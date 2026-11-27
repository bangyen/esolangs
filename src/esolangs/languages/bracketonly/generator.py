"""BracketOnly Boolean generator using lazy if calls.

Each test reduces the next ASCII input digit modulo two and visits only
its chosen arm. Equal arms share one child. Discarded reads contribute
zero to the result. The tree returns a bit to one enclosing output call.
Each source fragment is appended once and generation takes O(T).

Size:
    O(T) characters, n=4 parity: 1,932 chars.
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


_ZERO = _call(Function.ADD)
_TWO = _call(Function.ADD, _ONE, _ONE)
_READ = _call(Function.INPC)
_CONDITION = _open(Function.IF) + _call(Function.MOD, _READ, _TWO)
_SKIP = _open(Function.ADD) + _call(Function.MUL, _ZERO, _READ)
_BITS = (_ZERO, _ONE)


def bracketonly(truth_table: str) -> str:
    """Emit a loop-less lazy tree that reads each digit once on its path."""
    ids = subtree_ids(truth_table)
    n = len(ids) - 1
    parts = [_open(Function.OUT)]

    def emit(level: int, block: int) -> None:
        node = ids[level][block]
        if node < 2:
            remaining = n - level
            bit = _BITS[node]
            if remaining:
                # Multiplication evaluates the reads even with a zero factor.
                drained = _call(Function.MUL, _ZERO, _READ * remaining)
                bit = _call(Function.ADD, drained, bit)
            parts.append(bit)
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
    parts.append(")")
    return "".join(parts)


def bracketonly_request(request: GenerationRequest) -> Program:
    """Emit source through the registered Boolean backend."""
    return bracketonly(request.table)
