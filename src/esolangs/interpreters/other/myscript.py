r"""Interpreter for MyScript.

A JavaScript-inspired prefix language: functions are called without
parentheses (``add a b`` is ``add(a, b)``), statements are line-based, and
``while``/``check`` blocks and function bodies are introduced by an
indented block after a line ending in ``,``.  ``var x is expr`` declares a
variable, ``x is expr`` modifies one, ``return``/``return val`` leaves the
current function, ``say expr`` prints a value, ``ask`` reads a line of
input, and ``check val?`` starts an ``if``/``else`` switch.  Values are
integers, floats, strings (double quotes, escapes ``\\0 \\n \\\\ \\t \\f
\\"``), booleans ``yes``/``no``, and arrays ``[a, b, c]``.  Functions are
first-class values created with ``var f is func arg1 arg2`` whose body is
the indented block after the declaration; calling ``f x y`` binds the
parameters and runs the body.

Errors: an undefined variable, a call with the wrong number of arguments,
an ``if``/``else`` outside a ``check``, arithmetic on a non-number, and an
out-of-range ``itemat`` are invalid operations that halt the program with
:class:`~esolangs.exceptions.HaltError`; a ``while yes`` loop runs forever
unless the program ends, and ``ask`` raises :class:`EOFError` when input
runs out (the repo-wide convention).
"""

import re
import sys
from contextlib import suppress

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The builtin prefix functions and their fixed arities.
_ARITY = {
    "add": 2,
    "subtract": 2,
    "multiply": 2,
    "divide": 2,
    "equals": 2,
    "less": 2,
    "not": 1,
    "concat": 2,
    "arrlen": 1,
    "itemat": 2,
    "say": 1,
    "ask": 0,
}

_TOKEN = re.compile(
    r'"[^"\\]*(?:\\.[^"\\]*)*"'  # string literal with escapes
    r"|\d+\.\d+|\d+"  # float, then int
    r"|[A-Za-z_][A-Za-z0-9_]*"
    r"|[,\?\[\]]"
)
_ESCAPES = {"0": "\0", "n": "\n", "\\": "\\", "t": "\t", "f": "\f", '"': '"'}

# An indentation block: a list of ``(tokens, children)`` statement nodes.
Node = tuple[list[str], list["Node"]]


def _parse_string(raw: str) -> str:
    """Decode a MyScript string literal (including its surrounding quotes)."""
    body = raw[1:-1]
    out: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            out.append(_ESCAPES[body[i + 1]])
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _tokenize(line: str) -> list[str]:
    """Split one stripped line into tokens."""
    return _TOKEN.findall(line)


def _block_tree(code: str) -> list[Node]:
    """Build the indentation tree of ``(tokens, children)`` nodes."""
    root: list[Node] = []
    stack: list[tuple[int, list[Node]]] = [(0, root)]
    for raw in code.split("\n"):
        stripped = raw.strip()
        if not stripped:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        node: Node = (_tokenize(stripped), [])
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        stack[-1][1].append(node)
        stack.append((indent, node[1]))
    return root


def _truthy(value: object) -> bool:
    """MyScript's boolean coercion."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return True


def _as_str(value: object) -> str:
    """Render a value the way MyScript prints or concatenates it."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _num(value: object) -> int | float:
    """Require ``value`` to be a number, halting otherwise."""
    if not isinstance(value, (int, float)):
        raise HaltError("expected a number")
    return value


def _as_list(value: object) -> list[object]:
    """Require ``value`` to be an array, halting otherwise."""
    if not isinstance(value, list):
        raise HaltError("expected an array")
    return value


class _ReturnError(Exception):
    """The value a ``return`` statement carries out of a function."""

    def __init__(self, value: object) -> None:
        """Build the return with ``value``."""
        super().__init__()
        self.value = value


class _Function:
    """A user-defined function value: parameters, body, and defining scope."""

    def __init__(self, params: list[str], body: list[Node], outer: "Scope") -> None:
        """Bind ``params`` to a ``body`` tree that runs against ``outer``."""
        self.params = params
        self.body = body
        self.outer = outer


class Scope:
    """A variable scope chaining to its defining scope."""

    def __init__(self, parent: "Scope | None" = None) -> None:
        """Start empty, falling back to ``parent`` for lookups."""
        self.vars: dict[str, object] = {}
        self.parent = parent

    def get(self, name: str) -> object:
        """Return ``name``'s value, walking the scope chain."""
        scope: Scope | None = self
        while scope is not None:
            if name in scope.vars:
                return scope.vars[name]
            scope = scope.parent
        raise HaltError(f"undefined variable: {name}")

    def declare(self, name: str, value: object) -> None:
        """Bind ``name`` in this scope."""
        self.vars[name] = value

    def assign(self, name: str, value: object) -> None:
        """Rebind ``name`` where it already exists, else error."""
        scope: Scope | None = self
        while scope is not None:
            if name in scope.vars:
                scope.vars[name] = value
                return
            scope = scope.parent
        raise HaltError(f"assignment to undefined variable: {name}")


def _run_block(nodes: list[Node], io: IO, scope: Scope) -> None:
    """Execute every statement in an indentation block."""
    for tokens, children in nodes:
        _run_statement(tokens, children, io, scope)


def _parse_expr(
    tokens: list[str], pos: int, io: IO, scope: Scope
) -> tuple[object, int]:
    """Parse one prefix expression from ``tokens[pos:]``, returning (value, pos)."""
    tok = tokens[pos]
    if tok == "ask":
        return io.input_str(), pos + 1
    if tok in ("yes", "no"):
        return tok == "yes", pos + 1
    if tok[0] == '"':
        return _parse_string(tok), pos + 1
    if tok[0].isdigit():
        return float(tok) if "." in tok else int(tok), pos + 1
    if tok == "[":
        return _parse_array(tokens, pos + 1, io, scope)
    arity = _ARITY.get(tok)
    if arity is not None:
        pos += 1
        args: list[object] = []
        for _ in range(arity):
            value, pos = _parse_expr(tokens, pos, io, scope)
            args.append(value)
        return _apply_builtin(tok, args, io), pos
    value = scope.get(tok)
    if isinstance(value, _Function):
        pos += 1
        args = []
        for _ in range(len(value.params)):
            arg, pos = _parse_expr(tokens, pos, io, scope)
            args.append(arg)
        return _call_function(value, args, io), pos
    return value, pos + 1


def _parse_array(
    tokens: list[str], pos: int, io: IO, scope: Scope
) -> tuple[list[object], int]:
    """Parse ``[v1, v2, ...]`` starting just after the ``[``."""
    items: list[object] = []
    while pos < len(tokens) and tokens[pos] != "]":
        value, pos = _parse_expr(tokens, pos, io, scope)
        items.append(value)
        if pos < len(tokens) and tokens[pos] == ",":
            pos += 1
    return items, pos + 1


def _apply_builtin(name: str, args: list[object], io: IO) -> object:
    """Apply a builtin function to its already-evaluated arguments."""
    if name == "add":
        return _num(args[0]) + _num(args[1])
    if name == "subtract":
        return _num(args[0]) - _num(args[1])
    if name == "multiply":
        return _num(args[0]) * _num(args[1])
    if name == "divide":
        return _num(args[0]) / _num(args[1])
    if name == "equals":
        return args[0] == args[1]
    if name == "less":
        return _num(args[0]) < _num(args[1])
    if name == "not":
        return not _truthy(args[0])
    if name == "concat":
        return _as_str(args[0]) + _as_str(args[1])
    if name == "arrlen":
        return len(_as_list(args[0]))
    if name == "itemat":
        index = _num(args[1])
        array = _as_list(args[0])
        if not 0 <= index < len(array):
            raise HaltError("itemat index out of range")
        return array[int(index)]
    if name == "say":
        io.print_value(_as_str(args[0]))
        return None
    raise AssertionError(f"unknown builtin: {name}")


def _call_function(function: _Function, args: list[object], io: IO) -> object:
    """Call a user function with ``args``, running its body in a child scope."""
    scope = Scope(function.outer)
    for name, value in zip(function.params, args, strict=True):
        scope.declare(name, value)
    try:
        _run_block(function.body, io, scope)
    except _ReturnError as ret:
        return ret.value
    return None


def _run_statement(
    tokens: list[str], children: list[Node], io: IO, scope: Scope
) -> None:
    """Execute one statement (a line's tokens and its indented block)."""
    head = tokens[0]
    if head == "var":
        name = tokens[1]
        if tokens[2] != "is":
            raise HaltError("malformed var declaration")
        rest = tokens[3:]
        if rest and rest[0] == "func":
            scope.declare(name, _Function(rest[1:], children, scope))
            return
        value, _ = _parse_expr(rest, 0, io, scope)
        scope.declare(name, value)
        return
    if head == "return":
        if len(tokens) == 1:
            raise _ReturnError(None)
        value, _ = _parse_expr(tokens[1:], 0, io, scope)
        raise _ReturnError(value)
    if head == "while":
        cond, _ = _parse_expr(tokens[1:-1], 0, io, scope)
        while _truthy(cond):
            _run_block(children, io, scope)
            cond, _ = _parse_expr(tokens[1:-1], 0, io, scope)
        return
    if head == "check":
        value, _ = _parse_expr(tokens[1:-1], 0, io, scope)
        for case in children:
            case_tokens = case[0]
            if case_tokens[0] == "else":
                _run_block(case[1], io, scope)
                return
            if case_tokens[0] != "if":
                raise HaltError("malformed check case")
            case_value, _ = _parse_expr(case_tokens[1:-1], 0, io, scope)
            if value == case_value:
                _run_block(case[1], io, scope)
                return
        return
    if head in ("if", "else"):
        raise HaltError("if/else outside a check")
    if head == "is":
        raise HaltError("malformed statement")
    if len(tokens) >= 3 and tokens[1] == "is":
        scope.assign(head, _parse_expr(tokens[2:], 0, io, scope)[0])
        return
    _parse_expr(tokens, 0, io, scope)


def run(code: str, io: IO) -> None:
    """Run a MyScript program."""
    with suppress(_ReturnError):  # a top-level return ends the program
        _run_block(_block_tree(code), io, Scope())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
