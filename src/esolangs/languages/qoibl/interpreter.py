"""Interpreter for Qoibl (Qwerty oriented impractical bicharacter language).

Eight instructions and a 256-variable list over ``e r t w q y``: seven
dispatched commands (:data:`INSTRUCTIONS`) plus ``[ey]+`` binary
literals, and the four :data:`OPERATORS` (``ee``, ``ey``, ``ye``, ``yy``)
reading as ``= > < !=`` after ``yr`` and ``+ - * /`` after ``ry``.
Other characters are ignored, so the statement, not the line, is the
unit and :func:`tokenize` recovers boundaries.

Input/output:
    Output printed before a failed read or a halt is kept.

Errors:
    ProgramError: Unrecognized operator, or a malformed expression.
    InputExhaustedError: A read at EOF.
    HaltError: A variable index outside 0..255; division by zero.

Decisions:
    * The wiki fixes no precedence: a chain splits at its first ``yr``
      (else ``ry``) and the right side is evaluated whole.  Generated
      programs do not depend on it: each chain is a pure product or a
      plus-first ``+``/``-``, equal under either association.
    * "``rr x rr y rr``" is read literally, a loop body being one statement.
"""

import functools
import re
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._fault import _Fault
from esolangs.runtime.io import IO
from esolangs.runtime.memory import format_integer
from esolangs.runtime.source_hints import syntax_error

INSTRUCTIONS = frozenset({"tt", "we", "qe", "et", "yr", "ry", "rr"})
OPERATORS = frozenset({"ee", "ey", "ye", "yy"})
_VARIABLES = 256


def _variable(index: int) -> int:
    """Return a valid Qoibl variable index, rejecting an out-of-range one."""
    if not 0 <= index < _VARIABLES:
        raise HaltError(
            f"variable index {format_integer(index)} is outside 0..{_VARIABLES - 1}",
            hint="keep the index within the bounds stated in the diagnostic",
        )
    return index


def _steal(tokens: list[str], char: str) -> list[str] | None:
    """Return ``tokens`` with a trailing ``char`` removed from the last literal.

    ``et`` and ``yr`` end in a character a preceding literal would absorb.
    """
    if not tokens or tokens[-1] in INSTRUCTIONS or not tokens[-1].endswith(char):
        return None
    literal = tokens[-1]
    return tokens[:-1] if len(literal) == 1 else [*tokens[:-1], literal[:-1]]


def _scan(line: str, accept: Callable[[list[str]], bool]) -> list[str]:
    """Return the first tokenization of ``line`` that ``accept`` approves.

    Whether ``r`` opens ``ry`` or closes ``yr`` depends on the grammar, so
    ambiguous positions are explored depth-first, consuming-next before
    reaching-back; whitespace is a boundary.  The search carries its own
    stack: a recursive walk spent one frame per character (1241 of 1315 on a
    3972-character program) and refused a six-input majority table with
    ``InterpreterLimitError``.
    """
    n = len(line)
    stack: list[tuple[int, list[str], bool]] = [(0, [], False)]
    while stack:
        i, tokens, fused = stack.pop()
        while i < n and line[i].isspace():
            # A break stops `et`/`yr` from reaching back into the last run.
            i, fused = i + 1, False
        if i >= n:
            if accept(tokens):
                return tokens
            continue

        char = line[i]
        nxt = line[i + 1] if i + 1 < n else ""
        branches: list[tuple[list[str], int]] = []

        if char == "y" and nxt == "r" and not fused:
            # A marker with no literal behind it to lend the `y`.
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
            if nxt and nxt in "ry":
                branches.append(([*tokens, "rr" if nxt == "r" else "ry"], i + 2))
            if fused and (head := _steal(tokens, "y")) is not None:
                branches.append(([*head, "yr"], i + 1))
        else:
            # The source is filtered to ``ewqtry`` and whitespace, and the
            # loop above skipped the whitespace, so what is left after the
            # arms above is an ``e`` or a ``y`` opening a binary literal.
            j = i
            while j < n and line[j] in "ey":
                j += 1
            branches.append(([*tokens, line[i:j]], j))

        stack.extend((nxt_i, grown, True) for grown, nxt_i in reversed(branches))

    return []


class _Reading:
    """One token run, asked about by index rather than by slice.

    Asking of a list copied and rescanned per candidate prefix, making
    loading cubic; ``_after`` is a next-occurrence table and ``_memo``
    settles a span once.
    """

    __slots__ = ("_after", "_memo", "_tokens")

    #: The tokens whose position the grammar asks after.  ``we`` and ``rr``
    #: close their own block; ``yr`` and ``ry`` bracket an operator.
    _MARKERS = ("we", "rr", "yr", "ry")

    def __init__(self, tokens: Sequence[str]) -> None:
        self._tokens = tuple(tokens)
        size = len(self._tokens)
        self._after: dict[str, list[int]] = {}
        for marker in self._MARKERS:
            # ``found[i]`` is the first index at or after ``i`` holding
            # ``marker``, or ``size`` when there is none.
            found = [size] * (size + 1)
            for i in range(size - 1, -1, -1):
                found[i] = i if self._tokens[i] == marker else found[i + 1]
            self._after[marker] = found
        self._memo: dict[tuple[int, int], bool] = {}

    def at(self, lo: int, hi: int) -> bool:
        """Whether ``tokens[lo:hi]`` parses, by the rules :func:`_eval` runs."""
        key = (lo, hi)
        settled = self._memo.get(key)
        if settled is None:
            settled = self._memo[key] = self._decide(lo, hi)
        return settled

    def _decide(self, lo: int, hi: int) -> bool:
        """``at`` without the memo: the grammar itself, on one span."""
        if hi <= lo:
            return False
        tokens = self._tokens
        op = tokens[lo]
        if op == "tt":
            return tokens[hi - 1] == op and self.at(lo + 1, hi - 1)
        if op in ("we", "rr"):
            if tokens[hi - 1] != op:
                return False
            # The block's own closer, which has to fall inside this span.
            ind = self._after[op][lo + 1]
            if ind >= hi:
                return False
            return self.at(lo + 1, ind) and self.at(ind + 1, hi - 1)
        for marker in ("yr", "ry"):
            beg = self._after[marker][lo]
            if beg < hi:
                # Found before the ``qe`` arm is reached, which is what keeps
                # an arithmetic value out of a ``qe`` key.
                if beg + 1 >= hi or tokens[beg + 1] not in OPERATORS:
                    return False
                if beg + 2 >= hi or tokens[beg + 2] != marker:
                    return False
                return self.at(lo, beg) and self.at(beg + 3, hi)
        if op == "qe":
            return tokens[hi - 1] == op and self.at(lo + 1, hi - 1)
        if op == "et":
            return hi - lo == 1
        return bool(re.fullmatch("[ey]+", op)) and hi - lo == 1


@functools.lru_cache(maxsize=32)
def _tokenized(source: str) -> tuple[tuple[str, ...], ...]:
    """Return the reading :func:`tokenize` found, keyed by source and cached.

    The search was 2.72s of a 2.72s six-input parity run, paid once per
    row by ``verify``: 155s for 64 rows where one search is about 6s.
    """
    cleaned = re.sub("[^ewqtry\\s]", "", source).strip()
    if not cleaned:
        return ()

    statements: list[list[str]] = []

    def accept(tokens: list[str]) -> bool:
        """Close the token run into statements, each of which must parse."""
        statements.clear()
        return _split(tokens, statements)

    if _scan(cleaned, accept):
        return tuple(tuple(statement) for statement in statements)

    # Nothing parses; hand the greedy reading to `_parse` so a malformed
    # program still fails there with its usual diagnostics.
    reading = _scan(cleaned, lambda _: True)
    if not reading and (
        any(char in "ey" for char in cleaned)
        or any(marker in cleaned for marker in INSTRUCTIONS)
    ):
        # A failed scan must not erase a complete statement ("tt y tt w").
        raise ValueError("malformed Qoibl expression")
    return (tuple(reading),)


def tokenize(source: str) -> list[list[str]]:
    """Split Qoibl source into statements, each a list of tokens.

    The first reading under which every statement parses; whitespace still
    keeps a token from spanning it.  Fresh lists over a cached reading.
    """
    return [list(statement) for statement in _tokenized(source)]


def _split(tokens: list[str], out: list[list[str]]) -> bool:
    """Cut ``tokens`` into the shortest prefixes that each parse.

    Settled from the right: ``cut[i]`` is the shortest statement at ``i``
    whose remainder also splits.
    Still quadratic in tokens, with a small constant.
    """
    size = len(tokens)
    reading = _Reading(tokens)
    #: ``size + 1`` marks a position that cannot start a run of statements.
    cut = [size + 1] * (size + 2)
    cut[size] = size
    for lo in range(size - 1, -1, -1):
        for end in range(lo + 1, size + 1):
            # The tail test is a lookup and the prefix test is not, so it
            # goes first: only a cut the remainder can live with is worth
            # parsing a prefix for.
            if cut[end] <= size and reading.at(lo, end):
                cut[lo] = end
                break
    if cut[0] > size:
        return False
    lo = 0
    while lo < size:
        end = cut[lo]
        out.append(tokens[lo:end])
        lo = end
    return True


#: The part of a run the pure layer owns: the variable list, as an immutable
#: mapping from number to value.  A value, not a record: :func:`_eval` returns
#: a new one rather than editing the one it was handed, so an expression that
#: assigns half-way through and then raises leaves the caller's copy intact.
type _Vars = Mapping[int, int]

#: Every value a Qoibl statement can change: the variable mapping that
#: expression evaluation returns and the top-level statement cursor.  The
#: tokenized program is fixed for a run; input values and output characters
#: are explicit, not ports.
type _State = tuple[_Vars, int]

#: What a statement asks the shell to print, in order.
type _Effects = tuple[str, ...]


def _frozen(var: Mapping[int, int]) -> _Vars:
    """Return ``var`` as an immutable mapping, sharing an existing freeze."""
    return var if isinstance(var, MappingProxyType) else MappingProxyType(var)


class _NeedInput(Exception):  # noqa: N818 - an internal resumption signal
    """Signals that a statement needs one more input value than supplied.

    Raised by :func:`_eval` when an ``et`` finds the explicit input tuple
    exhausted.  ``effects`` is the output already computed before the read,
    so the shell can flush it before reading.  The shell reads one more
    value and retries; the transition is deterministic, so the retry reaches
    the same point with the new value.
    """

    def __init__(self, effects: _Effects = ()) -> None:
        super().__init__()
        self.effects = effects


def _eval(
    expr: list[str],
    var: _Vars,
    inputs: Sequence[int],
    pos: int,
    out: list[str],
) -> tuple[int, _Vars, int]:
    """Return a validated expression's value, variables, and input cursor.

    ``we`` evaluates its target before its value; ``rr`` re-evaluates its
    condition against the variables its body returned.  Output is appended to
    ``out`` as it is computed, so a later read or fault still sees the prefix;
    ``inputs`` is the explicit input the shell has supplied.
    """
    if not expr:
        raise syntax_error(
            "malformed expression", "provide a nonempty Qoibl expression"
        )

    if (op := expr[0]) == "tt":
        value, var, pos = _eval(expr[1:-1], var, inputs, pos, out)
        out.append(chr(value))
        return 0, var, pos
    if op == "we":
        ind = expr.index("we", 1)
        target, var, pos = _eval(expr[1:ind], var, inputs, pos, out)
        value, var, pos = _eval(expr[ind + 1 : -1], var, inputs, pos, out)
        return 0, _frozen({**var, _variable(target): value}), pos
    if op == "rr":
        ind = expr.index("rr", 1)
        cond, var, pos = _eval(expr[1:ind], var, inputs, pos, out)
        while cond:
            _, var, pos = _eval(expr[ind + 1 : -1], var, inputs, pos, out)
            cond, var, pos = _eval(expr[1:ind], var, inputs, pos, out)
        return 0, var, pos
    if "yr" in expr:
        return _compare(expr, var, inputs, pos, out)
    if "ry" in expr:
        return _arithmetic(expr, var, inputs, pos, out)
    if op == "qe":
        key, var, pos = _eval(expr[1:-1], var, inputs, pos, out)
        return var.get(_variable(key), 0), var, pos
    if op == "et":
        if pos >= len(inputs):
            raise _NeedInput
        return inputs[pos], var, pos + 1
    # Loading validates literals; unreachable hand-built tokens need no arm.
    return int(op.replace("e", "0").replace("y", "1"), 2), var, pos


def _operands(
    expr: list[str],
    marker: str,
    var: _Vars,
    inputs: Sequence[int],
    pos: int,
    out: list[str],
) -> tuple[str, int, int, _Vars, int]:
    """Return the operator and both operands around ``marker``.

    Left before right, which is observable through the requested output.
    """
    beg = expr.index(marker)
    if beg + 1 >= len(expr):
        raise syntax_error(
            "malformed comparison" if marker == "yr" else "malformed arithmetic",
            (
                "put an ee/ey/ye/yy operator and an operand on each side of "
                "the yr or ry form"
            ),
        )
    num = expr[beg + 1]
    x, var, pos = _eval(expr[:beg], var, inputs, pos, out)
    y, var, pos = _eval(expr[beg + 3 :], var, inputs, pos, out)
    return num, x, y, var, pos


_COMPARISONS: dict[str, Callable[[int, int], bool]] = {
    "ee": lambda x, y: x == y,
    "ey": lambda x, y: x > y,
    "ye": lambda x, y: x < y,
    "yy": lambda x, y: x != y,
}

_ARITHMETIC: dict[str, Callable[[int, int], int]] = {
    "ee": lambda x, y: x + y,
    "ey": lambda x, y: x - y,
    "ye": lambda x, y: x * y,
}


def _compare(
    expr: list[str], var: _Vars, inputs: Sequence[int], pos: int, out: list[str]
) -> tuple[int, _Vars, int]:
    """Evaluate a ``yr``-marked comparison."""
    num, x, y, var, pos = _operands(expr, "yr", var, inputs, pos, out)
    if num not in _COMPARISONS:
        raise syntax_error(
            "unrecognized comparison operator", "use ee, ey, ye or yy after yr"
        )
    return int(_COMPARISONS[num](x, y)), var, pos


def _arithmetic(
    expr: list[str], var: _Vars, inputs: Sequence[int], pos: int, out: list[str]
) -> tuple[int, _Vars, int]:
    """Evaluate a ``ry``-marked arithmetic expression."""
    num, x, y, var, pos = _operands(expr, "ry", var, inputs, pos, out)
    if num in _ARITHMETIC:
        return _ARITHMETIC[num](x, y), var, pos
    if num != "yy":
        raise syntax_error(
            "unrecognized arithmetic operator", "use ee, ey, ye or yy after ry"
        )
    if y == 0:
        raise HaltError(
            f"division by zero: {format_integer(x)} divided by {format_integer(y)}",
            hint="ensure the divisor is nonzero before dividing",
        )
    return x // y, var, pos


# The semantics are a pure transition: :func:`_advance` maps an immutable ``_State``
# (the variable mapping and the statement cursor) plus the input values the statement
# may read to a new ``_State`` and the characters it asks to print.  :func:`_eval`
# appends output to an internal accumulator as it is computed, so a ``tt`` records
# output and an ``et`` reads the next explicit input value.  A statement may read any
# number of times (an ``rr`` body loops), so the shell cannot hoist one read: it calls
# :func:`_advance` with the values it has read, and when the statement asks for one more
# than that -- raising :data:`_NeedInput` with the output prefix already computed -- the
# shell flushes that prefix, reads one character, and retries.  A fault raises
# :data:`_Fault` with the same prefix, which the shell flushes before re-raising, so
# output written before a later read fails or an operation halts is never dropped.  The
# transition is deterministic, so the retry lands on the same state; the shell is the
# only place that touches ``io``.
def _advance(
    state: _State, code: Sequence[list[str]], inputs: Sequence[int] = ()
) -> tuple[_State, _Effects]:
    """Return the state after one statement, and the characters to print.

    Pure: the tokenized ``code`` is a parameter, a read arrives in
    ``inputs``, and a write leaves in the returned effects.  An ``et`` that
    needs a value ``inputs`` does not hold raises :data:`_NeedInput` carrying
    the output prefix computed before it; any other fault raises
    :data:`_Fault` carrying the same prefix, so the shell can flush output
    before re-raising.
    """
    var, ind = state
    out: list[str] = []
    try:
        if ind >= len(code):
            return state, ()
        tokens = code[ind]
        if tokens:
            _value, var, _pos = _eval(tokens, var, inputs, 0, out)
        new_state: _State = (_frozen(var), ind + 1)
    except _NeedInput:
        raise _NeedInput(tuple(out)) from None
    except _Fault:
        raise
    except BaseException as exc:
        raise _Fault(tuple(out), exc) from None
    return new_state, tuple(out)


class _Machine:
    """Per-run state for a Qoibl interpreter: variables and the code cursor."""

    var: _Vars
    io: IO
    code: tuple[list[str], ...]
    ind: int

    def __init__(self, code: str | list[str], io: IO) -> None:
        """Build a state for ``code``, tokenized."""
        self.var = MappingProxyType({})
        self.io = io
        self.code = tuple(tokenize(code if isinstance(code, str) else "\n".join(code)))
        for statement in self.code:
            if statement and not _Reading(statement).at(0, len(statement)):
                kind = (
                    "comparison operator"
                    if "yr" in statement
                    else "arithmetic operator"
                    if "ry" in statement
                    else "expression"
                )
                raise syntax_error(
                    f"malformed Qoibl {kind}",
                    (
                        "complete each expression and pair its delimiters; "
                        "comparison and arithmetic use ee/ey/ye/yy operators"
                    ),
                )
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the expression pointer has run off the program."""
        return self.ind >= len(self.code)

    # The VM's language-shaped view: a 256-entry variable list addressed by
    # number, so ``memory`` is that list densified -- absent keys read as
    # zero, which is what the language says an unset variable holds.

    @property
    def memory(self) -> list[int]:
        """The 256 variables, unset ones reading as zero."""
        return [self.var.get(k, 0) for k in range(_VARIABLES)]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, tuple(sorted(self.var.items())), self.io.progress())

    @property
    def _state(self) -> _State:
        """The complete changing state as the evaluator's value boundary."""
        return (self.var, self.ind)

    def _restore(self, state: _State) -> None:
        """Write a statement transition's result back onto the shell."""
        self.var, self.ind = state

    def _flush(self, effects: _Effects, flushed: int) -> int:
        """Print ``effects`` past ``flushed``; return the new flush count."""
        for char in effects[flushed:]:
            self.io.print_char(char)
        return len(effects)

    def step(self) -> None:
        """Execute one statement, advancing the cursor.

        The shell: it reads the values the statement asks for and prints the
        characters it asks to print, then commits the transition's state.  A
        statement may read any number of times, so the reads cannot be
        hoisted; each :data:`_NeedInput` flushes the output computed before
        it, reads one more value, and retries.  A fault flushes the same
        prefix before it is re-raised, matching the original output order.
        """
        if self.halted:
            return
        inputs: list[int] = []
        flushed = 0
        while True:
            try:
                state, effects = _advance(self._state, self.code, tuple(inputs))
            except _NeedInput as need:
                flushed = self._flush(need.effects, flushed)
                inputs.append(self.io.input_char())
                continue
            except _Fault as fault:
                self._flush(fault.effects, flushed)
                raise fault.error from None
            break
        self._restore(state)
        self._flush(effects, flushed)


def run(code: list[str] | str, io: IO) -> None:
    """Execute Qoibl program code.

    Lines or one string; the program is one character stream.
    """
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run, shape="keep")
