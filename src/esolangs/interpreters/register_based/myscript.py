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

The interpreter runs on a :class:`_Machine`: an explicit stack of frames
stands in for Python's own, so **nesting of every kind is data rather than
Python stack**.  One statement is one ``step()`` however deep it sits --
inside a ``while``, a ``check`` arm, or a called function -- so every
intermediate state reaches :meth:`_Machine.snapshot`, and a loop inside a
called function is provable by :func:`esolangs.vm.run_until_halt_or_cycle`
rather than hanging where nothing can observe it.

There is therefore no recursion ceiling.  A program that recurses forever
grows the frame list rather than Python's stack; that class revisits no
state, so it is what ``esolangs.run``'s wall-clock ``timeout`` is for,
exactly as ``grapheme.py`` records.  ``eval.py`` says its machine and this
one are built the same way and for the same reasons, and they now are.

Evaluation is scheduled rather than recursive: a frame carries the pending
steps of the statement in progress (``todo``) and the finished operands
they have produced.  The tokens are scheduled directly rather than
pre-parsed into a tree, because MyScript's grammar is *binding-dependent* --
``add f 3`` shapes one way when ``f`` holds a one-parameter function and
another when it holds a number, so argument *N*'s start position is known
only once argument *N-1* has been evaluated.  Operands therefore carry the
position they ended at.  ``io`` is threaded through the transition rather
than lifted into the shell: a statement's expression may read and print any
number of times, at points that depend on values computed part-way through
it.
"""

import re
import sys
from dataclasses import dataclass
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
_BuiltinArity = Literal[1, 2]

# The builtin prefix functions and their fixed arities.
_ARITY: dict[_Builtin, _BuiltinArity] = {
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


#: A todo item's fields are ``object`` to the checker, since one tuple type
#: covers every continuation shape.  :func:`_typed` narrows a field back to
#: what the shape guarantees and raises if the machine ever built one wrong.
#:
#: A raise rather than an ``assert``: these hold up the whole transition, and
#: an ``assert`` disappears under ``python -O``, which would turn a broken
#: frame into a silent wrong answer instead of a stack trace.
def _typed[T](value: object, kind: type[T]) -> T:
    """Return ``value`` narrowed to ``kind``, raising if it is not one."""
    if not isinstance(value, kind):
        raise AssertionError(f"malformed frame: expected {kind.__name__}")
    return value


#: A pending evaluation step, or a continuation waiting on operands.
#:
#: ``("expr", tokens, pos)`` evaluates one prefix expression starting at
#: ``pos``; ``("apply", name, wanted, tokens)`` and ``("ucall", function,
#: wanted, tokens)`` wait until ``wanted`` operands have landed and then
#: combine them; ``("arr", wanted, tokens, closed)`` gathers an array
#: display; ``("stmt", kind, tokens, children)`` finishes a statement once
#: its expression has a value.
#:
#: Argument *N*'s start position is known only once argument *N-1* has
#: finished, because a bare name's arity comes from the value it is bound
#: to -- ``add f 3`` shapes differently when ``f`` holds a function than
#: when it holds a number.  Operands therefore carry the position they ended
#: at, and a continuation schedules the next operand from there.  That
#: binding-dependent grammar is why the tokens are scheduled directly rather
#: than pre-parsed into a tree.
type _Todo = tuple[object, ...]

#: A finished operand and the token position it ended at.
type _Operand = tuple[object, int]

#: One block on the machine's explicit frame stack.
#:
#: ``nodes``/``pos`` is the statement list and cursor a block is executing;
#: ``scope`` is the variables in effect; ``todo`` is the pending evaluation
#: steps of the statement in progress and ``operands`` the finished values
#: they have produced; ``kind`` says what finishing the block means --
#: ``None`` for a plain block, ``("while", tokens)`` to re-check a
#: condition, or ``("call",)`` for a function body whose return value lands
#: on the caller's operand stack.
#:
#: A tuple rather than a class, so the frame stack is a value the transition
#: returns rather than a list it edits.  The ``scope`` it holds is
#: deliberately *not* a value -- see :func:`_advance`.
type _Frame = tuple[
    list[Node], int, "Scope", tuple[_Todo, ...], tuple[_Operand, ...], object
]


def _frame(nodes: list[Node], scope: "Scope", kind: object = None) -> _Frame:
    """Build a fresh frame for ``nodes``, at its start."""
    return (nodes, 0, scope, (), (), kind)


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


type _Frames = tuple[_Frame, ...]


def _with(
    frames: _Frames, todo: tuple[_Todo, ...], operands: tuple[_Operand, ...]
) -> _Frames:
    """Return ``frames`` with the innermost frame's evaluation state replaced."""
    nodes, pos, scope, _, _, kind = frames[-1]
    return (*frames[:-1], (nodes, pos, scope, todo, operands, kind))


def _deliver(frames: _Frames, value: object, end: int) -> _Frames:
    """Land a finished ``value`` on the innermost frame's operand stack."""
    nodes, pos, scope, todo, operands, kind = frames[-1]
    return (*frames[:-1], (nodes, pos, scope, todo, (*operands, (value, end)), kind))


def _return_value(frames: _Frames, value: object) -> _Frames:
    """Unwind to the nearest call boundary, delivering ``value`` to its caller.

    ``return`` crosses ``step()`` boundaries now that a body is frames
    rather than Python recursion, so it cannot be an exception.  With no
    call boundary above it, a ``return`` is a top-level one and ends the
    program -- the behaviour the recursive interpreter gave it.

    A call frame's ``kind`` carries the token position its arguments ended
    at, so the value it returns resumes the caller's expression exactly
    where the call's operands stopped.
    """
    while frames:
        kind = frames[-1][5]
        frames = frames[:-1]
        if isinstance(kind, tuple) and kind and kind[0] == "call":
            end = _typed(kind[1], int)
            return _deliver(frames, value, end)
    return ()


def _schedule_expr(
    frames: _Frames, tokens: list[str], pos: int, io: IO, scope: Scope
) -> _Frames:
    """Take one evaluation step on the expression starting at ``tokens[pos]``.

    Every branch either delivers a finished operand or pushes the work that
    will produce one, so no branch recurses: the nesting lives in ``todo``.
    """
    _, _, _, todo, operands, _ = frames[-1]
    if pos >= len(tokens):
        raise ValueError("expression ended before its operands")
    tok = tokens[pos]
    if tok == "ask":
        return _deliver(frames, io.input_str(), pos + 1)
    if tok in ("yes", "no"):
        return _deliver(frames, tok == "yes", pos + 1)
    if tok[0] == '"':
        return _deliver(frames, _parse_string(tok), pos + 1)
    if tok[0].isdigit():
        return _deliver(frames, float(tok) if "." in tok else int(tok), pos + 1)
    if tok == "[":
        return _with(frames, (("arr", len(operands), tokens, pos + 1), *todo), operands)
    if tok in _BUILTINS:
        return _with(
            frames,
            (("apply", tok, len(operands), _ARITY[tok], tokens, pos + 1), *todo),
            operands,
        )
    value = scope.get(tok)
    if isinstance(value, _Function):
        return _with(
            frames,
            (
                ("ucall", value, len(operands), len(value.params), tokens, pos + 1),
                *todo,
            ),
            operands,
        )
    return _deliver(frames, value, pos + 1)


def _resume(frames: _Frames, io: IO, scope: Scope) -> _Frames:
    """Advance the innermost frame's pending evaluation by one step."""
    _, _, _, todo, operands, _ = frames[-1]
    item = todo[0]
    rest = todo[1:]
    head = item[0]

    if head == "expr":
        tokens = _typed(item[1], list)
        pos = _typed(item[2], int)
        return _schedule_expr(_with(frames, rest, operands), tokens, pos, io, scope)

    if head == "apply":
        name = _typed(item[1], str)
        base = _typed(item[2], int)
        wanted = _typed(item[3], int)
        tokens = _typed(item[4], list)
        start = _typed(item[5], int)
        # ``base`` is where this call's own operands start.  Counting the
        # whole stack instead would fold in an enclosing call's finished
        # operands and satisfy the arity early.
        if len(operands) - base < wanted:
            pos = operands[-1][1] if len(operands) > base else start
            return _with(frames, (("expr", tokens, pos), item, *rest), operands)
        args = [value for value, _ in operands[base:]]
        end = operands[-1][1] if wanted else start
        value = _apply_builtin(name, args, io)  # type: ignore[arg-type]
        return _deliver(_with(frames, rest, operands[:base]), value, end)

    if head == "ucall":
        function = _typed(item[1], _Function)
        base = _typed(item[2], int)
        wanted = _typed(item[3], int)
        tokens = _typed(item[4], list)
        start = _typed(item[5], int)
        if len(operands) - base < wanted:
            pos = operands[-1][1] if len(operands) > base else start
            return _with(frames, (("expr", tokens, pos), item, *rest), operands)
        args = [value for value, _ in operands[base:]]
        end = operands[-1][1] if wanted else start
        inner = Scope(function.outer)
        for name_, value_ in zip(function.params, args, strict=True):
            inner.declare(name_, value_)
        return (
            *_with(frames, rest, operands[:base]),
            _frame(function.body, inner, ("call", end)),
        )

    if head == "arr":
        base = _typed(item[1], int)
        tokens = _typed(item[2], list)
        pos = _typed(item[3], int)
        # ``base`` is where this display's items start on the operand stack,
        # so enclosing calls' operands below it are never miscounted.
        if len(operands) > base:
            pos = operands[-1][1]
            if pos < len(tokens) and tokens[pos] == ",":
                pos += 1
        if pos < len(tokens) and tokens[pos] != "]":
            return _with(
                frames,
                (("expr", tokens, pos), ("arr", base, tokens, pos), *rest),
                operands,
            )
        items = [value for value, _ in operands[base:]]
        return _deliver(_with(frames, rest, operands[:base]), items, pos + 1)

    return _finish_statement(frames, item, scope)


def _finish_statement(frames: _Frames, item: _Todo, scope: Scope) -> _Frames:
    """Complete a statement whose expression has produced its value."""
    kind = item[1]
    _, _, _, todo, operands, _ = frames[-1]
    value = operands[-1][0]
    kept = operands[:-1]
    base = _with(frames, todo[1:], kept)

    if kind == "declare":
        name = _typed(item[2], str)
        scope.declare(name, value)
        return base
    if kind == "assign":
        name = _typed(item[2], str)
        scope.assign(name, value)
        return base
    if kind == "return":
        return _return_value(base, value)
    if kind == "while":
        tokens = _typed(item[2], list)
        children = _typed(item[3], list)
        rearm = item[4]
        if _truthy(value):
            if rearm:
                # Re-entering from the body frame's own re-check: restart it
                # in place rather than stacking a second body frame.
                nodes, _, scope_, _, _, kind_ = base[-1]
                return (*base[:-1], (nodes, 0, scope_, (), (), kind_))
            return (*base, _frame(children, scope, ("while", tokens)))
        # The loop is over.  A re-check runs on the body frame itself, so
        # leaving means popping it; a first check runs on the enclosing
        # frame, which simply carries on.
        return base[:-1] if rearm else base
    if kind == "check":
        cases = _typed(item[2], list)
        return _check_case(base, value, cases, scope)
    if kind == "case":
        subject = item[2]
        cases = _typed(item[3], list)
        body = _typed(item[4], list)
        if subject == value:
            return (*base, _frame(body, scope))
        return _check_case(base, subject, cases, scope)
    return base  # a bare expression statement: the value is discarded


def _check_case(
    frames: _Frames, subject: object, cases: list[Node], scope: Scope
) -> _Frames:
    """Try the next ``check`` case, running the first whose value matches.

    Cases are tried in order and their expressions evaluated lazily, so a
    case after the matching one never runs -- and, now that a case value may
    contain a call, never gets stepped either.
    """
    _, _, _, todo, operands, _ = frames[-1]
    for index, case in enumerate(cases):
        case_tokens, body = case
        if case_tokens[0] == "else":
            return (*frames, _frame(body, scope))
        if case_tokens[0] != "if":
            raise ValueError("malformed check case")
        rest = cases[index + 1 :]
        item: _Todo = ("stmt", "case", subject, rest, body)
        return _with(frames, (("expr", case_tokens[1:-1], 0), item, *todo), operands)
    return frames


def _begin_statement(
    frames: _Frames, tokens: list[str], children: list[Node]
) -> _Frames:
    """Schedule the work of one statement onto the innermost frame."""
    _, _, _, todo, operands, _ = frames[-1]
    head = tokens[0]

    def sched(expr_tokens: list[str], item: _Todo) -> _Frames:
        return _with(frames, (("expr", expr_tokens, 0), item, *todo), operands)

    if head == "var":
        if len(tokens) < 3 or tokens[2] != "is":
            raise ValueError("malformed var declaration")
        name, rest = tokens[1], tokens[3:]
        if rest and rest[0] == "func":
            scope = frames[-1][2]
            scope.declare(name, _Function(rest[1:], children, scope))
            return frames
        return sched(rest, ("stmt", "declare", name))
    if head == "return":
        if len(tokens) == 1:
            return _return_value(frames, None)
        return sched(tokens[1:], ("stmt", "return"))
    if head == "while":
        return sched(tokens[1:-1], ("stmt", "while", tokens[1:-1], children, False))
    if head == "check":
        return sched(tokens[1:-1], ("stmt", "check", children))
    if head in ("if", "else"):
        raise HaltError("if/else outside a check")
    if head == "is":
        raise ValueError("malformed statement")
    if len(tokens) >= 3 and tokens[1] == "is":
        return sched(tokens[2:], ("stmt", "assign", head))
    return sched(tokens, ("stmt", "expr"))


def _advance(frames: _Frames, io: IO) -> _Frames:
    """Execute one step, returning the frame stack that follows.

    Pure in the *stack*: it returns a new tuple rather than editing the one
    it was handed.  It is deliberately not pure in the scopes, and that is a
    property of the language rather than a shortcut.  A function value
    closes over the scope object it was declared in, so a later assignment
    to that scope is visible through the closure -- ``var x is 1`` /
    ``func`` / ``var x is 9`` prints 9.  Rebuilding scopes as values per
    statement would sever exactly that aliasing, which is why
    :meth:`_Machine.snapshot` settles for a ``repr``-based view of them.

    ``io`` is threaded through rather than lifted into the shell: a
    statement's expression may read and print any number of times, at points
    that depend on values computed part-way through it.
    """
    nodes, pos, scope, todo, _, kind = frames[-1]

    if todo:
        return _resume(frames, io, scope)

    if pos >= len(nodes):
        rest = frames[:-1]
        if isinstance(kind, tuple) and kind and kind[0] == "while":
            tokens = _typed(kind[1], list)
            # Re-check the condition on the frame the body just finished on,
            # so a call inside the condition is stepped like any other.
            return (*rest, (nodes, 0, scope, _while_todo(tokens, nodes), (), kind))
        if isinstance(kind, tuple) and kind and kind[0] == "call":
            # A function body that fell off its end returns None.
            return _return_value(frames, None)
        return rest

    tokens, children = nodes[pos]
    advanced = (*frames[:-1], (nodes, pos + 1, scope, (), (), kind))
    return _begin_statement(advanced, tokens, children)


def _while_todo(tokens: list[str], nodes: list[Node]) -> tuple[_Todo, ...]:
    """Build the pending steps that re-check a ``while`` and re-enter it."""
    return (("expr", tokens, 0), ("stmt", "while", tokens, nodes, True))


@dataclass
class _State:
    """The root scope and complete call-frame stack of a MyScript run."""

    scope: Scope
    frames: _Frames


class _Machine:
    """One MyScript run: the frame stack, I/O, and the root scope."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        scope = Scope()
        self.state = _State(scope, (_frame(_block_tree(code), scope),))

    @property
    def frames(self) -> _Frames:
        return self.state.frames

    @frames.setter
    def frames(self, frames: _Frames) -> None:
        self.state.frames = frames

    @property
    def halted(self) -> bool:
        """Whether the frame stack has emptied (or a top-level return fired)."""
        return not self.frames

    # The VM's language-shaped view.  The call frames are held in
    # ``frames`` rather than ``stack``: MyScript has no operand stack for
    # the VM to show, and the old name collided with the one the VM wants.

    @property
    def ip(self) -> tuple[int, int] | None:
        """The call depth and the innermost frame's position.

        ``None`` once every frame has returned.
        """
        if not self.frames:
            return None
        return len(self.frames), self.frames[-1][1]

    @property
    def memory(self) -> list[int]:
        """The innermost scope's integer variables."""
        if not self.frames:
            return []
        return [v for v in self.frames[-1][2].vars.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        """The innermost frame's finished operands, outermost first."""
        if not self.frames:
            return []
        return [value for value, _ in self.frames[-1][4]]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Scopes and function values are not meaningfully hashable (a
        function closes over a live, mutable scope), so the snapshot
        captures each frame's position and a shallow, ``repr``-based view
        of its scope chain -- sufficient for the state-cycle detector's
        purpose, since a genuine hang re-executes the same frame position
        with the same variable bindings on every lap.

        The pending steps and finished operands are folded in too, and by
        ``repr`` for the same reason: an operand may be a list, which is not
        hashable.  Leaving them out would let two genuinely different
        mid-statement states hash alike, and the detector would call a
        program cyclic that is not.
        """
        return (
            tuple(
                (
                    id(frame[0]),
                    frame[1],
                    self._scope_key(frame[2]),
                    repr(frame[3]),
                    tuple((repr(value), end) for value, end in frame[4]),
                )
                for frame in self.frames
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
        """Execute one top-level-block statement, advancing the frame stack.

        The ports stay inside the transition rather than in this shell: a
        statement's expression may read and print any number of times, at
        points that depend on values computed part-way through it.
        """
        if self.halted:
            return
        self.frames = _advance(self.frames, self.io)


def run(code: str, io: IO) -> None:
    """Run a MyScript program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
