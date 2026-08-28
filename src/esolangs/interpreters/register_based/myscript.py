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

Errors: a ``var`` declaration missing ``is``, an unrecognized ``check``
case, and a bare ``is`` at statement position are malformed programs and
raise :class:`ValueError`; an undefined variable, a call with the wrong
number of arguments, an ``if``/``else`` outside a ``check``, arithmetic on
a non-number, and an out-of-range ``itemat`` are invalid operations that
halt the program with :class:`~esolangs.exceptions.HaltError`; a
``while yes`` loop runs forever unless the program ends, and ``ask``
raises :class:`EOFError` when input runs out (the repo-wide convention).

The interpreter runs on a :class:`_Machine`: an explicit stack of
``_Frame``s (a block's statement list, cursor, and scope) stands in for
top-level block sequencing, so a top-level ``while`` -- the common case,
and the one the wiki's truth-machine example uses -- is resumed one pass
through its body at a time instead of looping natively in Python.  This
makes ``step()`` interruptible between top-level statements and between
passes of a top-level ``while``.  A statement nested inside a function
call still runs to completion inside the ``step()`` that invokes the
call (through the original recursive ``_call_function``/``_run_block``),
since that nesting is bounded by the call depth in a working program;
only a top-level ``while`` is unbounded by construction, and that is
the one the frame stack unrolls.
"""

import re
import sys
from typing import Literal, get_args

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The builtin prefix functions _apply_builtin dispatches on.  ``ask`` is
# not among them: it is answered in _parse_expr before the arity lookup,
# so naming the eleven that do arrive lets the checker see the dispatch is
# exhaustive.
_Builtin = Literal[
    "add",
    "subtract",
    "multiply",
    "divide",
    "equals",
    "less",
    "not",
    "concat",
    "arrlen",
    "itemat",
    "say",
]

# The builtin prefix functions and their fixed arities.
_ARITY: dict[str, int] = {
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

# The arity table minus ``ask``, typed: _parse_expr answers ``ask`` before
# the lookup, so membership here is exactly "is a _Builtin" and narrows the
# token to the type _apply_builtin dispatches on.
_BUILTINS: frozenset[_Builtin] = frozenset(get_args(_Builtin))

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
        toks = _tokenize(stripped)
        if not toks:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        node: Node = (toks, [])
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


class _Frame:
    """One block on the machine's explicit call stack.

    ``nodes``/``pos`` is the statement list and cursor a block is
    executing; ``scope`` is the variables in effect; ``while_head`` is the
    condition tokens to re-check when a ``while`` body's frame finishes
    (``None`` for a plain block or function body).
    """

    __slots__ = ("nodes", "pos", "scope", "while_head")

    def __init__(
        self,
        nodes: list[Node],
        scope: "Scope",
        while_head: list[str] | None = None,
    ) -> None:
        self.nodes = nodes
        self.pos = 0
        self.scope = scope
        self.while_head = while_head


def _run_block(nodes: list[Node], io: IO, scope: Scope) -> None:
    """Execute every statement in an indentation block."""
    for tokens, children in nodes:
        _run_statement(tokens, children, io, scope)


def _parse_expr(
    tokens: list[str], pos: int, io: IO, scope: Scope
) -> tuple[object, int]:
    """Parse one prefix expression from ``tokens[pos:]``, returning (value, pos).

    A prefix call consumes exactly as many expressions as its operator's
    arity, so a line that ends early (``say`` with nothing to say) is a
    malformed program rather than a bad value, and is rejected the same
    way as the other malformed forms here.
    """
    if pos >= len(tokens):
        raise ValueError("expression ended before its operands")
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
    # ``ask`` is answered above, so every other arity hit is a _Builtin;
    # testing the typed set is what lets the token reach _apply_builtin at
    # that type rather than as a bare str.
    if tok in _BUILTINS:
        arity = _ARITY[tok]
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


def _apply_builtin(name: _Builtin, args: list[object], io: IO) -> object:
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
    io.print_value(_as_str(args[0]))
    return None


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
        if len(tokens) < 3 or tokens[2] != "is":
            raise ValueError("malformed var declaration")
        name = tokens[1]
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
                raise ValueError("malformed check case")
            case_value, _ = _parse_expr(case_tokens[1:-1], 0, io, scope)
            if value == case_value:
                _run_block(case[1], io, scope)
                return
        return
    if head in ("if", "else"):
        raise HaltError("if/else outside a check")
    if head == "is":
        raise ValueError("malformed statement")
    if len(tokens) >= 3 and tokens[1] == "is":
        scope.assign(head, _parse_expr(tokens[2:], 0, io, scope)[0])
        return
    _parse_expr(tokens, 0, io, scope)


class _Machine:
    """One MyScript run: the frame stack, I/O, and the root scope."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.scope = Scope()
        self.stack: list[_Frame] = [_Frame(_block_tree(code), self.scope)]

    @property
    def halted(self) -> bool:
        """Whether the frame stack has emptied (or a top-level return fired)."""
        return not self.stack

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Scopes and function values are not meaningfully hashable (a
        function closes over a live, mutable scope), so the snapshot
        captures each frame's position and a shallow, ``repr``-based view
        of its scope chain -- sufficient for the state-cycle detector's
        purpose, since a genuine hang re-executes the same frame position
        with the same variable bindings on every lap.
        """
        return (
            tuple(
                (id(frame.nodes), frame.pos, self._scope_key(frame.scope))
                for frame in self.stack
            ),
            self.io.position(),
        )

    @staticmethod
    def _scope_key(scope: "Scope | None") -> tuple[object, ...]:
        chain = []
        while scope is not None:
            chain.append(tuple(sorted((k, repr(v)) for k, v in scope.vars.items())))
            scope = scope.parent
        return tuple(chain)

    def step(self) -> None:
        """Execute one top-level-block statement, advancing the frame stack."""
        if self.halted:
            return
        frame = self.stack[-1]
        if frame.pos >= len(frame.nodes):
            self.stack.pop()
            if frame.while_head is not None:
                cond, _ = _parse_expr(frame.while_head, 0, self.io, frame.scope)
                if _truthy(cond):
                    while_head = frame.while_head
                    self.stack.append(_Frame(frame.nodes, frame.scope, while_head))
            return

        tokens, children = frame.nodes[frame.pos]
        frame.pos += 1
        head = tokens[0]
        if head == "while":
            cond, _ = _parse_expr(tokens[1:-1], 0, self.io, frame.scope)
            if _truthy(cond):
                self.stack.append(_Frame(children, frame.scope, tokens[1:-1]))
            return
        try:
            _run_statement(tokens, children, self.io, frame.scope)
        except _ReturnError:
            self.stack.clear()  # a top-level return ends the program


def run(code: str, io: IO) -> None:
    """Run a MyScript program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
