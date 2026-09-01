"""Qoibl (Qwerty oriented impractical bicharacter language) interpreter.

Qoibl is an esoteric programming language with 8 instructions and a 256-variable list.
It uses only the characters 'e', 'r', 't', 'w', 'q', 'y' for programming constructs.

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
"""

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

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
    """
    n = len(line)

    def walk(i: int, tokens: list[str], *, fused: bool) -> list[str] | None:
        while i < n and line[i].isspace():
            # A break stops `et`/`yr` from reaching back into the last run.
            i, fused = i + 1, False
        if i >= n:
            return tokens if accept(tokens) else None

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

        for grown, nxt_i in branches:
            if (found := walk(nxt_i, grown, fused=True)) is not None:
                return found
        return None

    return walk(0, [], fused=False) or []


def _wellformed(expr: list[str]) -> bool:
    """Whether ``expr`` parses, mirroring :meth:`State._parse` without effects.

    :meth:`State._parse` prints and consumes input as it goes, so it cannot be
    used to test a candidate tokenization.  The split points here are the same
    ones it uses, so a candidate accepted here is one it can run.
    """
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
    """Split Qoibl source into statements, each a list of tokens.

    The language ignores characters that are not part of an instruction, so
    spaces and newlines are optional and a whole program may be written as one
    run of characters.  Instructions are two characters and binary literals
    are ``[ey]+``, so the boundaries are recovered by scanning: the reading
    chosen is the first one under which every statement parses.  Whitespace,
    where present, still keeps a token from spanning it, so a conventionally
    spaced program splits exactly as ``str.split`` would.
    """
    cleaned = re.sub("[^ewqtry\\s]", "", source).strip()
    if not cleaned:
        return []

    statements: list[list[str]] = []

    def accept(tokens: list[str]) -> bool:
        """Close the token run into statements, each of which must parse."""
        statements.clear()
        return _split(tokens, statements)

    if _scan(cleaned, accept):
        return list(statements)

    # Nothing parses; hand the greedy reading to `_parse` so a malformed
    # program still fails there with its usual diagnostics.
    return [_scan(cleaned, lambda _: True)]


def _split(tokens: list[str], out: list[list[str]]) -> bool:
    """Cut ``tokens`` into the shortest prefixes that each parse."""
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


@dataclass
class State:
    """Per-run state for a Qoibl interpreter: variables and the code cursor."""

    var: dict[int, int] = field(default_factory=dict)
    io: IO = field(default_factory=IO)
    code: list[list[str]] = field(default_factory=list, init=False)
    ind: int = 0

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

    def _parse(self, expr: str | list[str]) -> int:
        """Parse and execute a single Qoibl expression."""
        if not expr:
            raise ValueError("malformed expression")
        if (op := expr[0]) == "tt":
            self.io.print_char(chr(self._parse(expr[1:-1])))
        elif op == "we":
            ind = expr.index("we", 1)
            self.var[self._parse(expr[1:ind])] = self._parse(expr[ind + 1 : -1])
        elif op == "rr":
            ind = expr.index("rr", 1)
            while self._parse(expr[1:ind]):
                self._parse(expr[ind + 1 : -1])
        elif "yr" in expr:
            beg = expr.index("yr")
            if beg + 1 >= len(expr):
                raise ValueError("malformed comparison")
            num = expr[beg + 1]
            x = self._parse(expr[:beg])
            y = self._parse(expr[beg + 3 :])

            if num == "ee":
                return x == y
            if num == "ey":
                return x > y
            if num == "ye":
                return x < y
            if num == "yy":
                return x != y
            raise ValueError("unrecognized comparison operator")
        elif "ry" in expr:
            beg = expr.index("ry")
            if beg + 1 >= len(expr):
                raise ValueError("malformed arithmetic")
            num = expr[beg + 1]
            x = self._parse(expr[:beg])
            y = self._parse(expr[beg + 3 :])

            if num == "ee":
                return x + y
            if num == "ey":
                return x - y
            if num == "ye":
                return x * y
            if num == "yy":
                if y == 0:
                    raise HaltError
                return x // y
            raise ValueError("unrecognized arithmetic operator")
        elif op == "qe":
            return self.var.get(self._parse(expr[1:-1]), 0)
        elif op == "et":
            return self.io.input_char()
        # ``tokenize`` only accepts a split under which every statement
        # parses, so the tokens that reach here are the keywords above, a
        # binary ``[ey]+`` literal, or ``yr``/``ry`` -- and those two are
        # taken by the ``in expr`` arms before the keyword tests run.  The
        # fallback stays for a hand-built expression list.
        elif re.fullmatch("[ey]+", op):  # pragma: no branch - see above
            op = op.replace("e", "0").replace("y", "1")
            return int(op, 2)
        return 0

    def step(self) -> None:
        """Execute one statement, advancing the cursor."""
        if self.halted:
            return
        tokens = self.code[self.ind]
        self.ind += 1
        if tokens:
            self._parse(tokens)


def run(code: list[str] | str, io: IO) -> None:
    """Execute Qoibl program code.

    ``code`` may be a list of lines or one string; either way the whole
    program is one character stream, since the language draws no distinction
    between a newline and any other ignored character.
    """
    state = State(io=io)
    state.code = tokenize(code if isinstance(code, str) else "\n".join(code))

    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
