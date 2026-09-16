"""Qoibl (Qwerty oriented impractical bicharacter language) interpreter.

Qoibl is an esoteric programming language with eight instructions and a
256-variable list, using only the characters 'e', 'r', 't', 'w', 'q', 'y'
for programming constructs.  The wiki's eight are the seven dispatched
commands in :data:`INSTRUCTIONS` plus ``e``/``y`` binary literal notation,
which is a construct here rather than a command: :func:`tokenize` reads a
``[ey]+`` run as a literal, so it never reaches the instruction table.  The
four :data:`OPERATORS` (``ee``, ``ey``, ``ye``, ``yy``) are counted
separately by the wiki; they qualify the instruction they follow, reading
as ``=``, ``>``, ``<``, ``!=`` after ``yr`` and as ``+``, ``-``, ``*``,
``/`` after ``ry``.

Per the wiki, characters outside the instruction alphabet are ignored, so
spaces and newlines are optional: the statement, not the line, is the unit of
execution, and a whole program may be written as one unbroken run of
characters.  :func:`tokenize` recovers the boundaries, since a two-character
instruction butted against a variable-width ``[ey]+`` literal leaves none.

The wiki specifies a 256-entry variable list; this interpreter uses an
unbounded dictionary and does not enforce the cap.  Division by zero is an
invalid operation and halts the program with
:class:`~esolangs.exceptions.HaltError`; a comparison or arithmetic expression
with an unrecognized operator is a malformed program and is rejected with
:class:`ValueError`.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

Evaluation is a pure function over an immutable ``_Vars``: :func:`_eval`
takes an expression and the variables it sees, and returns the value with
the variables that the expression left behind.  It never reaches an
:class:`IO`.  The mutation lives in :meth:`_Machine.step`, which rebinds one
field from what the transition returned.

The ports cannot be lifted out of the recursion the way a one-command step
lifts them.  A statement is Qoibl's unit of execution -- ``rr`` runs its
body to completion inside a single ``step()`` -- so how many times a nested
``et`` reads, and what an ``rr`` prints on the way, depends on values that
only exist part-way through the evaluation.  :func:`_eval` therefore takes
the two ports as callbacks: ``read`` for ``et`` and ``emit`` for ``tt``.
That keeps the *state* threading pure and total, which is what the mutation
net tests, while leaving the effects at the one seam that has to stay
ordered.  Eval's frame stack is the other answer to this shape and does not
fit here: there a step is one command, so nesting can be unwound onto an
explicit stack; here the language defines the statement as the step.
"""

import functools
import re
import sys
from collections.abc import Callable, Mapping, Sequence

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

INSTRUCTIONS = frozenset({"tt", "we", "qe", "et", "yr", "ry", "rr"})
OPERATORS = frozenset({"ee", "ey", "ye", "yy"})


def _steal(tokens: list[str], char: str) -> list[str] | None:
    """Return ``tokens`` with a trailing ``char`` removed from the last literal.

    ``et`` and ``yr`` are spelled with a character that a preceding binary
    literal would otherwise absorb, so forming them means giving that
    character back.  Returns ``None`` when there is nothing to take.
    """
    if not tokens or tokens[-1] in INSTRUCTIONS or not tokens[-1].endswith(char):
        return None
    literal = tokens[-1]
    return tokens[:-1] if len(literal) == 1 else [*tokens[:-1], literal[:-1]]


def _scan(line: str, accept: Callable[[list[str]], bool]) -> list[str]:
    """Return the first tokenization of ``line`` that ``accept`` approves.

    Instructions are two characters and binary literals are ``[ey]+``, so a
    literal butted against ``et`` or ``yr`` has no marked boundary.  Whether
    ``r`` opens ``ry`` or closes ``yr`` depends on the surrounding grammar
    rather than on nearby characters, so the ambiguous positions are explored
    depth-first and ``accept`` decides which reading was meant.  Readings that
    consume the next character are tried before those that reach backwards.

    Whitespace is a boundary rather than a separator: it is skipped, but a
    token is never assembled from characters on both sides of it, so a spaced
    program admits exactly one tokenization.

    **The search carries its own stack.**  Written as a recursive walk it
    spent one Python frame per character -- a measured 1241 frames of the
    1315 a 3972-character program reached, against 56 for the statement
    splitter and 8 for the grammar check.  That put the whole language under
    CPython's recursion limit: a six-input majority table refused with
    ``InterpreterLimitError`` while being, as its own message said, a
    perfectly well-formed program.  A caller could lift the limit with
    ``sys.setrecursionlimit`` and it would run, which is the tell that the
    wall belonged to the interpreter and not to Qoibl.

    An explicit stack removes it rather than raising it, so nothing here
    borrows a process-global setting or has a ceiling left to document.
    Entries are pushed in reverse because a stack pops last-in first and the
    branch order is load-bearing: readings that consume the next character
    must still be tried before those that reach backwards.
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
            if nxt in "ry":
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

    The grammar below is the same one :func:`_wellformed` always used; what
    changed is what a question costs.  Asking it of a *list* meant every
    candidate prefix copied its tokens and rescanned them for markers, and
    the split search asks about a prefix per cut point -- so the two loops
    multiplied, and loading a program was cubic in its length.

    A span is a pair of indices into one immutable tuple.  ``_after`` is a
    precomputed next-occurrence table, so finding a marker is a lookup
    rather than a scan, and ``_memo`` settles a span once however many
    prefixes reach it.
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
            return self.at(lo + 1, hi - 1)
        if op in ("we", "rr"):
            # The block's own closer, which has to fall inside this span.
            ind = self._after[op][lo + 1]
            if ind >= hi:
                return False
            return self.at(lo + 1, ind) and self.at(ind + 1, hi - 1)
        for marker in ("yr", "ry"):
            beg = self._after[marker][lo]
            if beg < hi:
                # Found before the ``qe`` arm is reached, which is what keeps
                # an arithmetic value out of a ``qe`` key -- as before.
                if beg + 1 >= hi or tokens[beg + 1] not in OPERATORS:
                    return False
                if beg + 2 >= hi or tokens[beg + 2] != marker:
                    return False
                return self.at(lo, beg) and self.at(beg + 3, hi)
        if op == "qe":
            return self.at(lo + 1, hi - 1)
        if op == "et":
            return hi - lo == 1
        return bool(re.fullmatch("[ey]+", op)) and hi - lo == 1


def _wellformed(expr: list[str]) -> bool:
    """Whether ``expr`` parses, mirroring :func:`_eval` without effects.

    :func:`_eval` prints and consumes input as it goes, so it cannot be used
    to test a candidate tokenization.  The split points here are the same
    ones it uses, so a candidate accepted here is one it can run -- including
    the order of the arms: a ``ry``/``yr`` marker is found before the ``qe``
    arm is reached, so an arithmetic value inside a ``qe`` key is rejected
    here and unreachable there.

    One expression, asked once: :class:`_Reading` is what the split search
    uses, and this is the same question put the standalone way.
    """
    return _Reading(expr).at(0, len(expr))


@functools.lru_cache(maxsize=32)
def _tokenized(source: str) -> tuple[tuple[str, ...], ...]:
    """Return the reading :func:`tokenize` found, keyed by source and cached.

    The reading is a pure function of the text, and the search for it is
    what the language costs: on the six-input parity program it is 2.72s of
    a 2.72s run, essentially all of it in :func:`_wellformed`.  Nothing was
    reusing that.  ``verify`` runs one program once per row, so a six-input
    table paid the identical search 64 times -- 155s where one search and 64
    executions is about 6s.

    Immutable, so the cache cannot hand two callers the same mutable lists;
    :func:`tokenize` rebuilds fresh ones, which is O(tokens) against a search
    that is not.
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
    return (tuple(_scan(cleaned, lambda _: True)),)


def tokenize(source: str) -> list[list[str]]:
    """Split Qoibl source into statements, each a list of tokens.

    The language ignores characters that are not part of an instruction, so
    spaces and newlines are optional and a whole program may be written as one
    run of characters.  Instructions are two characters and binary literals
    are ``[ey]+``, so the boundaries are recovered by scanning: the reading
    chosen is the first one under which every statement parses.  Whitespace,
    where present, still keeps a token from spanning it, so a conventionally
    spaced program splits exactly as ``str.split`` would.

    Fresh lists on every call, as callers have always got, over a cached
    immutable reading -- see :func:`_tokenized`.
    """
    return [list(statement) for statement in _tokenized(source)]


def _split(tokens: list[str], out: list[list[str]]) -> bool:
    """Cut ``tokens`` into the shortest prefixes that each parse.

    Settled from the right.  ``cut[i]`` is the shortest statement starting at
    ``i`` whose *remainder* also splits, so by the time a position is asked,
    every position after it has already answered.  That is the cut the old
    recursive search returned too -- it also took the first prefix that
    parses and whose tail splits -- but it re-explored a failed tail once per
    earlier cut, and each trial re-sliced and rescanned its tokens.

    Still quadratic in the token count: a position in the middle of a
    statement can start nothing, and proving that means trying its ends.
    The scan itself is a list index, though, and the parse behind it is
    settled once per span, so the constant is small.
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


#: The part of a run the pure layer owns: the variable list, as a mapping
#: from number to value.  A value, not a record: :func:`_eval` returns a new
#: one rather than editing the one it was handed, so an expression that
#: assigns half-way through and then raises leaves the caller's copy intact.
type _Vars = Mapping[int, int]

#: Every value a Qoibl statement can change: the variable mapping that
#: expression evaluation returns and the top-level statement cursor.  The
#: tokenized program is fixed for a run, while ports stay in the shell.
type _State = tuple[_Vars, int]

#: What ``et`` and ``tt`` reach.  The ports stay callbacks because a
#: statement is the unit of execution: an ``rr`` body can read and print any
#: number of times inside one step, at points that depend on values computed
#: part-way through, so neither can be hoisted into the shell ahead of the
#: evaluation the way a one-command step hoists them.
type _Read = Callable[[], int]
type _Emit = Callable[[str], None]


def _eval(expr: list[str], var: _Vars, read: _Read, emit: _Emit) -> tuple[int, _Vars]:
    """Return ``expr``'s value and the variables it leaves behind.

    Pure in its state: it reads ``var`` and returns a new mapping, and never
    edits the one it was given.  ``read`` and ``emit`` are the two ports.

    ``we`` evaluates its target before its value, and ``rr`` re-evaluates
    its condition against the variables its body just returned -- the
    threading is what makes a loop terminate, so it is the part a mutant
    breaks first.
    """
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
    # ``tokenize`` only accepts a split under which every statement parses,
    # so the tokens that reach here are the keywords above, a binary
    # ``[ey]+`` literal, or ``yr``/``ry`` -- and those two are taken by the
    # ``in expr`` arms before the keyword tests run.  The fallback stays for
    # a hand-built expression list.
    if re.fullmatch("[ey]+", op):  # pragma: no branch - see above
        return int(op.replace("e", "0").replace("y", "1"), 2), var
    return 0, var


def _operands(
    expr: list[str], marker: str, var: _Vars, read: _Read, emit: _Emit
) -> tuple[str, int, int, _Vars]:
    """Return the operator and both operands around ``marker``.

    The left side is evaluated before the right, which is observable: either
    may read input or print, and swapping them reverses both.
    """
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
    """Evaluate a ``yr``-marked comparison."""
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
    """Evaluate a ``ry``-marked arithmetic expression."""
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
    """Per-run state for a Qoibl interpreter: variables and the code cursor."""

    var: dict[int, int]
    io: IO
    code: tuple[list[str], ...]
    ind: int

    def __init__(self, code: str | list[str], io: IO) -> None:
        """Build a state for ``code``, tokenized."""
        self.var = {}
        self.io = io
        self.code = tuple(tokenize(code if isinstance(code, str) else "\n".join(code)))
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the expression pointer has run off the program."""
        return self.ind >= len(self.code)

    # The VM's language-shaped view: a 256-entry variable list addressed by
    # number, so ``memory`` is that list densified -- absent keys read as
    # zero, which is what the language says an unset variable holds.

    @property
    def ip(self) -> int:
        """The expression cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The 256 variables, unset ones reading as zero."""
        return [self.var.get(k, 0) for k in range(256)]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.ind, tuple(sorted(self.var.items())), self.io.position())

    @property
    def _state(self) -> _State:
        """The complete changing state as the evaluator's value boundary."""
        return (self.var, self.ind)

    def _restore(self, state: _State) -> None:
        """Write a statement transition's result back onto the shell."""
        var, self.ind = state
        self.var = dict(var)

    def _parse(self, expr: str | list[str]) -> int:
        """Evaluate one expression, committing what it assigns.

        Kept as a method because the tokenizer's siblings and the tests
        reach it by this name.  It is now the shell around :func:`_eval`:
        the ports are bound here, and the variables the evaluation returns
        are written back in one place.
        """
        tokens = list(expr) if isinstance(expr, list) else [expr]
        value, var = _eval(
            tokens, self._state[0], self.io.input_char, self.io.print_char
        )
        _, ind = self._state
        self._restore((var, ind))
        return value

    def step(self) -> None:
        """Execute one statement, advancing the cursor."""
        if self.halted:
            return
        var, ind = self._state
        tokens = self.code[ind]
        self._restore((var, ind + 1))
        if tokens:
            self._parse(tokens)


def run(code: list[str] | str, io: IO) -> None:
    """Execute Qoibl program code.

    ``code`` may be a list of lines or one string; either way the whole
    program is one character stream, since the language draws no distinction
    between a newline and any other ignored character.
    """
    state = _Machine(code, io)

    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
