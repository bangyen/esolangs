r"""Qoibl (Qwerty oriented impractical bicharacter language)."""

import re
import sys
from collections.abc import Callable, Mapping

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

INSTRUCTIONS = frozenset({"tt", "we", "qe", "et", "yr", "ry", "rr"})
OPERATORS = frozenset({"ee", "ey", "ye", "yy"})


def _steal(tokens: list[str], char: str) -> list[str] | None:
    r"""Return ``tokens`` with a trailing ``char`` removed from the last."""
    if not tokens or tokens[-1] in INSTRUCTIONS or not tokens[-1].endswith(char):
        return None
    literal = tokens[-1]
    return tokens[:-1] if len(literal) == 1 else [*tokens[:-1], literal[:-1]]


def _scan(line: str, accept: Callable[[list[str]], bool]) -> list[str]:
    r"""Return the first tokenization of ``line`` that ``accept`` approves."""
    n = len(line)
    stack: list[tuple[int, list[str], bool]] = [(0, [], False)]
    while stack:
        i, tokens, fused = stack.pop()
        while i < n and line[i].isspace():
            # A break stops `et`/`yr` from.
            i, fused = i + 1, False
        if i >= n:
            if accept(tokens):
                return tokens
            continue

        char = line[i]
        nxt = line[i + 1] if i + 1 < n else ""
        branches: list[tuple[list[str], int]] = []

        if char == "y" and nxt == "r" and not fused:
            # A marker with no literal.
            branches.append(([*tokens, "yr"], i + 2))

        if char in "wq":
            if nxt == "e":
                branches.append(([*tokens, char + "e"], i + 2))
        elif char == "t":
            if nxt == "t":
                branches.append(([*tokens, "tt"], i + 2))
            if fused and (head := _steal(tokens, "e")) is not None:
                branches.append(([*head, "et"], i + 1))
        elif char == "r":
            if nxt in "ry":
                branches.append(([*tokens, "rr" if nxt == "r" else "ry"], i + 2))
            if fused and (head := _steal(tokens, "y")) is not None:
                branches.append(([*head, "yr"], i + 1))
        else:
            # The source is filtered to.
            # loop above skipped the.
            # arms above is an ``e`` or a.
            j = i
            while j < n and line[j] in "ey":
                j += 1
            branches.append(([*tokens, line[i:j]], j))

        stack.extend((nxt_i, grown, True) for grown, nxt_i in reversed(branches))

    return []


def _wellformed(expr: list[str]) -> bool:
    r"""Whether ``expr`` parses, mirroring :func:`_eval` without effects."""
    if not expr:
        return False
    op = expr[0]
    if op == "tt":
        return _wellformed(expr[1:-1])
    if op == "we":
        try:
            ind = expr.index("we", 1)
        except ValueError:
            return False
        return _wellformed(expr[1:ind]) and _wellformed(expr[ind + 1 : -1])
    if op == "rr":
        try:
            ind = expr.index("rr", 1)
        except ValueError:
            return False
        return _wellformed(expr[1:ind]) and _wellformed(expr[ind + 1 : -1])
    for marker in ("yr", "ry"):
        if marker in expr:
            beg = expr.index(marker)
            if beg + 1 >= len(expr) or expr[beg + 1] not in OPERATORS:
                return False
            if expr[beg + 2 : beg + 3] != [marker]:
                return False
            return _wellformed(expr[:beg]) and _wellformed(expr[beg + 3 :])
    if op == "qe":
        return _wellformed(expr[1:-1])
    if op == "et":
        return len(expr) == 1
    return bool(re.fullmatch("[ey]+", op)) and len(expr) == 1


def tokenize(source: str) -> list[list[str]]:
    r"""Split Qoibl source into statements, each a list of tokens."""
    cleaned = re.sub("[^ewqtry\\s]", "", source).strip()
    if not cleaned:
        return []

    statements: list[list[str]] = []

    def accept(tokens: list[str]) -> bool:
        r"""Close the token run into statements, each of which must parse."""
        statements.clear()
        return _split(tokens, statements)

    if _scan(cleaned, accept):
        return list(statements)

    # Nothing parses; hand the.
    # program still fails there.
    return [_scan(cleaned, lambda _: True)]


def _split(tokens: list[str], out: list[list[str]]) -> bool:
    r"""Cut ``tokens`` into the shortest prefixes that each parse."""
    if not tokens:
        return True
    for end in range(1, len(tokens) + 1):
        head = tokens[:end]
        if _wellformed(head):
            out.append(head)
            if _split(tokens[end:], out):
                return True
            out.pop()
    return False


# : The part of a run the pure.
# : from number to value.
# : one rather than editing the.
# : assigns half-way through.
type _Vars = Mapping[int, int]

# : Every value a Qoibl.
# : expression evaluation.
# : tokenized program is fixed.
type _State = tuple[_Vars, int]

# : What ``et`` and ``tt``.
# : statement is the unit of.
# : number of times inside one.
# : part-way through, so.
# : evaluation the way a.
type _Read = Callable[[], int]
type _Emit = Callable[[str], None]


def _eval(expr: list[str], var: _Vars, read: _Read, emit: _Emit) -> tuple[int, _Vars]:
    r"""Return ``expr``'s value and the variables it leaves behind."""
    if not expr:
        raise ValueError("malformed expression")

    if (op := expr[0]) == "tt":
        value, var = _eval(expr[1:-1], var, read, emit)
        emit(chr(value))
        return 0, var
    if op == "we":
        ind = expr.index("we", 1)
        target, var = _eval(expr[1:ind], var, read, emit)
        value, var = _eval(expr[ind + 1 : -1], var, read, emit)
        return 0, {**var, target: value}
    if op == "rr":
        ind = expr.index("rr", 1)
        cond, var = _eval(expr[1:ind], var, read, emit)
        while cond:
            _, var = _eval(expr[ind + 1 : -1], var, read, emit)
            cond, var = _eval(expr[1:ind], var, read, emit)
        return 0, var
    if "yr" in expr:
        return _compare(expr, var, read, emit)
    if "ry" in expr:
        return _arithmetic(expr, var, read, emit)
    if op == "qe":
        key, var = _eval(expr[1:-1], var, read, emit)
        return var.get(key, 0), var
    if op == "et":
        return read(), var
    # ``tokenize`` only accepts a.
    # so the tokens that reach here.
    # ``[ey]+`` literal, or.
    # ``in expr`` arms before the.
    # a hand-built expression list.
    if re.fullmatch("[ey]+", op):  # pragma: no branch - see above
        return int(op.replace("e", "0").replace("y", "1"), 2), var
    return 0, var


def _operands(
    expr: list[str], marker: str, var: _Vars, read: _Read, emit: _Emit
) -> tuple[str, int, int, _Vars]:
    r"""Return the operator and both operands around ``marker``."""
    beg = expr.index(marker)
    if beg + 1 >= len(expr):
        raise ValueError(
            "malformed comparison" if marker == "yr" else "malformed arithmetic"
        )
    num = expr[beg + 1]
    x, var = _eval(expr[:beg], var, read, emit)
    y, var = _eval(expr[beg + 3 :], var, read, emit)
    return num, x, y, var


def _compare(
    expr: list[str], var: _Vars, read: _Read, emit: _Emit
) -> tuple[int, _Vars]:
    r"""Evaluate a ``yr``-marked comparison."""
    num, x, y, var = _operands(expr, "yr", var, read, emit)
    if num == "ee":
        return int(x == y), var
    if num == "ey":
        return int(x > y), var
    if num == "ye":
        return int(x < y), var
    if num == "yy":
        return int(x != y), var
    raise ValueError("unrecognized comparison operator")


def _arithmetic(
    expr: list[str], var: _Vars, read: _Read, emit: _Emit
) -> tuple[int, _Vars]:
    r"""Evaluate a ``ry``-marked arithmetic expression."""
    num, x, y, var = _operands(expr, "ry", var, read, emit)
    if num == "ee":
        return x + y, var
    if num == "ey":
        return x - y, var
    if num == "ye":
        return x * y, var
    if num == "yy":
        if y == 0:
            raise HaltError(f"division by zero: {x} divided by {y}")
        return x // y, var
    raise ValueError("unrecognized arithmetic operator")


class _Machine:
    r"""Per-run state for a Qoibl interpreter: variables and the code."""

    var: dict[int, int]
    io: IO
    code: tuple[list[str], ...]
    ind: int

    def __init__(self, code: str | list[str], io: IO) -> None:
        r"""Build a state for ``code``, tokenized."""
        self.var = {}
        self.io = io
        self.code = tuple(tokenize(code if isinstance(code, str) else "\n".join(code)))
        self.ind = 0

    @property
    def halted(self) -> bool:
        r"""Whether the expression pointer has run off the program."""
        return self.ind >= len(self.code)

    # The VM's language-shaped.
    # number, so ``memory`` is that.
    # zero, which is what the.

    @property
    def ip(self) -> int:
        r"""The expression cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The 256 variables, unset ones reading as zero."""
        return [self.var.get(k, 0) for k in range(256)]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (self.ind, tuple(sorted(self.var.items())), self.io.position())

    @property
    def _state(self) -> _State:
        r"""The complete changing state as the evaluator's value boundary."""
        return (self.var, self.ind)

    def _restore(self, state: _State) -> None:
        r"""Write a statement transition's result back onto the shell."""
        var, self.ind = state
        self.var = dict(var)

    def _parse(self, expr: str | list[str]) -> int:
        r"""Evaluate one expression, committing what it assigns."""
        tokens = list(expr) if isinstance(expr, list) else [expr]
        value, var = _eval(
            tokens, self._state[0], self.io.input_char, self.io.print_char
        )
        _, ind = self._state
        self._restore((var, ind))
        return value

    def step(self) -> None:
        r"""Execute one statement, advancing the cursor."""
        if self.halted:
            return
        var, ind = self._state
        tokens = self.code[ind]
        self._restore((var, ind + 1))
        if tokens:
            self._parse(tokens)


def run(code: list[str] | str, io: IO) -> None:
    r"""Execute Qoibl program code."""
    state = _Machine(code, io)

    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
