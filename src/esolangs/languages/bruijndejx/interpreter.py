r"""Interpreter for Bruijndejx.

A program is ``;``-separated declarations ``Name = expression``; running it
evaluates the last one.  Expressions are postfix: ``[x]`` is a lambda, a
number a De Bruijn index, ``x y.`` applies ``y`` to ``x``, ``:`` is ``..``.
A name is replaced by its declaration's value (its free indices stay free);
``$Name`` substitutes the declaration's text, so the use site's lambdas bind
them.  The value must be an I/O action: ``/x`` writes 0 and continues with
``x``, ``\x`` writes 1, ``? a b c`` reads a bit and continues with ``a``,
``b`` or ``c`` on 0, 1 or EOF, and ``*`` halts.

Evaluation is a Krivine machine (call-by-name, one transition a step) over
hash-consed environment and argument cells, so a snapshot is five integers.

Input/output:
    One character per bit, ``0`` or ``1``, both ways.  ``?`` at EOF takes
    its third argument; nothing raises at EOF.

Errors:
    ProgramError: a character outside the syntax, a declaration with no
        name before ``=``, a duplicate or undeclared name, an unclosed or
        stray bracket, a bare expression before the last item, or no item.
    ArgumentError: an input character other than ``0`` or ``1``.
    HaltError: a value that is not an I/O action (a lambda with no
        argument, an I/O primitive with the wrong number of arguments) or
        an unbound index.

Decisions:
    * The final item may be a bare expression: the page's halting example
      is ``*`` alone, though its grammar lists only declarations.  Elsewhere
      a bare expression could never run and is refused.
    * Call-by-name: a value is fixed by beta reduction, and leftmost
      reduction finds an I/O head whenever one exists, so ``loop [*].`` with
      ``loop = loop`` halts.
    * Missing operands are index 0 on the left, as the page says (``.`` and
      empty expressions); missing ``.`` are added at the end.
    * Duplicate declarations are refused; the page gives no override rule.
    * Bits are the characters ``0`` and ``1``: the page says only "bit".
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any, NamedTuple

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.languages.bruijndejx.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime._validate import require_text_source
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import parse_integer
from esolangs.runtime.source_hints import syntax_error

_TOKEN = re.compile(r"\s+|#[^\n]*|\$?[A-Za-z_][A-Za-z_0-9']*|[0-9]+|[\[\].:;=*/\\?]")
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9']*")

# Term kinds; a term is an index into the image's parallel arrays.
_LAM, _APP, _IDX, _NAME_REF, _MACRO, _PRIM = range(6)
_ARITY = {"*": 0, "/": 1, "\\": 1, "?": 3}


class _Image(NamedTuple):
    """Compiled terms: ``kind[t]``, ``left[t]`` and ``right[t]`` per term."""

    kind: tuple[int, ...]
    left: tuple[Any, ...]
    right: tuple[int, ...]
    entry: int


def _tokens(code: str) -> list[str]:
    tokens: list[str] = []
    at = 0
    while at < len(code):
        match = _TOKEN.match(code, at)
        if match is None:
            raise syntax_error(
                f"unexpected character {code[at]!r} at position {at}",
                "use names, numbers, [ ] . : ; = * / \\ ? and # comments",
            )
        token = match.group()
        if not token.isspace() and not token.startswith("#"):
            tokens.append(token)
        at = match.end()
    return tokens


class _Builder:
    def __init__(self) -> None:
        self.kind: list[int] = []
        self.left: list[Any] = []
        self.right: list[int] = []

    def term(self, kind: int, left: Any = 0, right: int = 0) -> int:
        self.kind.append(kind)
        self.left.append(left)
        self.right.append(right)
        return len(self.kind) - 1

    def expression(self, tokens: list[str], at: int, close: str) -> tuple[int, int]:
        """Parse postfix tokens from ``at`` to ``close``; return term and end."""
        stack: list[int] = []

        def apply() -> None:
            while len(stack) < 2:
                stack.insert(0, self.term(_IDX, 0))
            function = stack.pop()
            stack.append(self.term(_APP, function, stack.pop()))

        while at < len(tokens) and tokens[at] != close:
            token = tokens[at]
            at += 1
            if token == "[":
                body, at = self.expression(tokens, at, "]")
                if at == len(tokens):
                    raise syntax_error("unclosed '['", "close each '[' with ']'")
                at += 1
                stack.append(self.term(_LAM, body))
            elif token in ".:":
                for _ in range(1 + (token == ":")):
                    apply()
            elif token.isdigit():
                stack.append(self.term(_IDX, parse_integer(token)))
            elif token in _ARITY:
                stack.append(self.term(_PRIM, token))
            elif _NAME.fullmatch(token.lstrip("$")):
                kind = _MACRO if token.startswith("$") else _NAME_REF
                stack.append(self.term(kind, token.lstrip("$")))
            else:
                raise syntax_error(
                    f"unexpected {token!r} inside an expression",
                    "write '=' only after a declaration's name; ']' closes a '['",
                )
        while len(stack) > 1:
            apply()
        return (stack[0] if stack else self.term(_IDX, 0)), at


def _parse(code: str) -> _Image:
    """Compile declarations; names resolve globally, so recursion works."""
    tokens = _tokens(code)
    builder = _Builder()
    declared: dict[str, int] = {}
    items: list[list[str]] = [[]]
    depth = 0
    for token in tokens:
        depth += (token == "[") - (token == "]")
        if token == ";" and depth == 0:
            items.append([])
        else:
            items[-1].append(token)
    items = [item for item in items if item]
    if not items:
        raise syntax_error(
            "a program needs a declaration to run",
            "write at least one declaration, for example main = *",
        )
    entry = 0
    for number, item in enumerate(items):
        named = len(item) > 1 and item[1] == "=" and _NAME.fullmatch(item[0])
        if not named and number < len(items) - 1:
            raise syntax_error(
                f"bare expression {' '.join(item)!r} before the last declaration",
                "name each declaration: Name = expression",
            )
        body = item[2:] if named else item
        term, end = builder.expression(body, 0, "")
        if end < len(body):
            raise syntax_error(
                f"stray {body[end]!r}", "pair each ']' with an earlier '['"
            )
        if named:
            if item[0] in declared:
                raise syntax_error(
                    f"duplicate declaration {item[0]!r}",
                    "give each name one definition",
                )
            declared[item[0]] = term
        entry = term
    left = list(builder.left)
    for term, kind in enumerate(builder.kind):
        if kind in (_NAME_REF, _MACRO):
            if left[term] not in declared:
                raise syntax_error(
                    f"undeclared name {left[term]!r}", "declare every name you use"
                )
            left[term] = declared[left[term]]
    return _Image(tuple(builder.kind), tuple(left), tuple(builder.right), entry)


_WORKSPACE_MODEL = WorkspaceModel(
    "bruijndejx-v1", ("term", "environment", "arguments", "input_cursor")
)

#: A cell is ``(term, environment cell, next cell)``; 0 is the empty list.
type _Cell = tuple[int, int, int]


#: ``(term, environment, arguments)``; a new list cell is spelled as its
#: ``_Cell`` tuple for the shell to intern.
type _State = tuple[int, int, int]
type _Next = tuple[int, int | _Cell, int | _Cell]


def _advance(state: _State, image: _Image, cell: Callable[[int], _Cell]) -> _Next:
    """Return the state after one Krivine transition at a non-primitive term.

    Pure: ``cell`` only reads interned cells; a cell to create is returned
    as its tuple, so the shell owns the intern table.
    """
    term, env, args = state
    kind, left = image.kind[term], image.left[term]
    if kind == _APP:
        return left, env, (image.right[term], env, args)
    if kind == _LAM:
        if not args:
            raise HaltError(
                "the program's value is a lambda, not an I/O action",
                hint="apply it, or end with /x, \\x, ?abc or *",
            )
        bound, bound_env, rest = cell(args)
        return left, (bound, bound_env, env), rest
    if kind == _IDX:
        # Stop at the environment's end: a 40-digit index walked 10^40
        # empty links in one step (the exception-leak sweep's mutant).
        for _ in range(left):
            if not env:
                break
            env = cell(env)[2]
        if not env:
            raise HaltError(
                f"index {left} is unbound", hint="bind it with an enclosing [ ]"
            )
        found = cell(env)
        return found[0], found[1], args
    if kind == _NAME_REF:
        return left, 0, args
    return left, env, args  # _MACRO: the use site's environment binds it


class _Machine:
    """Krivine machine: the current term, its environment and argument stack."""

    ip_shape = "opaque"
    eof_is_a_value = True

    def __init__(self, code: str | _Image, io: IO) -> None:
        self.image = _parse(code) if isinstance(code, str) else code
        self.io = io
        self.term = self.image.entry
        self.env = 0
        self.args = 0
        self.done = False
        # Hash-consing: equal lists share one id, so snapshots stay O(1).
        self._ids: dict[_Cell, int] = {}
        self._cells: list[_Cell] = [(0, 0, 0)]
        # The same lists as nested tuples, shared by identity, for workspace.
        self._views: list[tuple[Any, ...] | None] = [None]
        self._rejected_input: str | None = None
        self._writer = _BufferedOutput()

    @property
    def halted(self) -> bool:
        return self.done

    @property
    def ip(self) -> int:
        """The current term."""
        return self.term

    def _cons(self, term: int, env: int, rest: int) -> int:
        cell = (term, env, rest)
        found = self._ids.get(cell)
        if found is None:
            found = self._ids[cell] = len(self._cells)
            self._cells.append(cell)
            self._views.append((term, self._views[env], self._views[rest]))
        return found

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        state = (self.term, self.env, self.args, self.done, self.io.progress())
        if self._rejected_input is not None:
            return (*state, self._rejected_input)
        accepted = self._writer.accepted
        return (*state, accepted) if accepted else state

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture term, environment, arguments and the input cursor."""
        cursor = self.io.progress()
        accepted = self._writer.accepted
        term: object = (
            WorkspaceVariant("pending_output", (self.term, self.done, accepted))
            if accepted
            else (self.term, self.done)
        )
        return _WORKSPACE_MODEL.capture(
            term=term,
            environment=self._views[self.env],
            arguments=self._views[self.args],
            input_cursor=(
                cursor
                if self._rejected_input is None
                else WorkspaceVariant("rejected_input", (cursor, self._rejected_input))
            ),
        )

    def _read_bit(self) -> int | None:
        """Return 0, 1, or None at EOF; refuse other characters, keeping them."""
        char = self._rejected_input
        if char is None:
            try:
                char = chr(self.io.input_char())
            except EOFError:
                return None
        if char not in "01":
            self._rejected_input = char
            raise syntax_error(
                f"input must be bits, got {char!r}",
                "supply 0 and 1 characters only",
                error_type=ArgumentError,
            )
        self._rejected_input = None
        return int(char)

    def _perform(self, primitive: str) -> None:
        """Run an I/O action whose arguments are on the stack."""
        operands: list[_Cell] = []
        args = self.args
        while args and len(operands) <= _ARITY[primitive]:
            operands.append(self._cells[args])
            args = self._cells[args][2]
        if len(operands) != _ARITY[primitive]:
            raise HaltError(
                f"{primitive!r} has {len(operands)} argument(s), "
                f"needs {_ARITY[primitive]}",
                hint="the final value must be an I/O action: /x, \\x, ?abc or *",
            )
        if primitive == "*":
            self.done = True
            return
        if primitive == "?":
            bit = self._read_bit()
            chosen = operands[2 if bit is None else bit]
        else:
            chosen = operands[0]
            text = "0" if primitive == "/" else "1"
            self._writer.write(self.io, text, first=lambda: self.io.print_char(text))
        self.term, self.env, self.args = chosen[0], chosen[1], 0

    def step(self) -> None:
        """Make one Krivine transition, or perform the I/O action at the head."""
        if self.done:
            return
        if self.image.kind[self.term] == _PRIM:
            self._perform(self.image.left[self.term])
            return
        term, env, args = _advance(
            (self.term, self.env, self.args), self.image, self._cells.__getitem__
        )
        self.term = term
        self.env = env if isinstance(env, int) else self._cons(*env)
        self.args = args if isinstance(args, int) else self._cons(*args)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Compile once; each IO port receives fresh machine state."""
    source = require_text_source(source, options, "Bruijndejx")
    image = _parse(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run ``code`` to completion on ``io``."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
