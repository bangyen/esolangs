r"""Interpreter for DINAC.

A strongly typed, indentation-structured language of three datatypes: the
wrapping unsigned byte (``wubyte``, a 2-char hex literal ``[0-9A-F]{2}``),
the ASCII character (``aschar``, ``'`` plus a character or a ``\0 \n \t \r
\\`` escape), and the null ``snuval`` (``$``).  ``SET n:v`` declares,
``n . v`` assigns (one space each side of the period), ``OUT v`` prints,
``IN n`` reads a line into an already-declared variable, ``IF``/``ELSE``
and ``WHILE`` take a 4-space-indented body, and ``DEF/<type> f p:v``
declares a function returning via ``GIVE``.  Overloading is by parameter
type tuple.  ``+``/``-`` are postfix successor/predecessor (wrapping mod
256 for a wubyte, mod 128 for an aschar), ``=``/``!`` compare, ``~``
negates, and parentheses group.  A wubyte prints as its two hex digits, an
aschar as its character.

``_Machine`` steps one statement at a time over an explicit frame stack, so
a top-level loop is provable by state-cycle detection.  Function calls
appear *inside* expressions (``OUT add1(x)``, ``WHILE and(a,b)``), which a
frame stack cannot suspend, so a call is evaluated inline by a recursive
evaluator bounded by an explicit depth counter checked at call entry;
runaway recursion is a :class:`~esolangs.exceptions.HaltError` rather than
a Python ``RecursionError``.

Decisions for gaps in the wiki spec (documented):
- EOF: the wiki defines only *empty* input (``\n`` for an aschar, ``00``
  for a wubyte) and is silent on input running out.  Reading past the end
  yields ``\0`` for an aschar and ``00`` for a wubyte rather than raising
  :class:`EOFError`.  That is the only reading under which the wiki's own
  cat program terminates: ``WHILE c`` exits exactly when ``IN`` can produce
  a falsy value, and the spec's empty-line ``\n`` is truthy;
- an empty line reads as the wiki says (``\n`` / ``00``), so EOF and a
  blank line are distinguishable, and one ``IN`` consumes one line;
- ``OUT`` of a wubyte prints its two hex digits (the wiki: "printed as
  their 2-char literals"), so the truth machine prints ``00``, not ``0``;
- ``=`` and ``!`` across two different types compare false and true
  respectively rather than raising -- the types are disjoint value sets, so
  no cross-type pair can be equal.  A snuval equals only a snuval;
- the wiki bans "null statements" in a branch.  Detecting them needs
  whole-program effect analysis, no example relies on the ban, and a
  rejected program is worse than an accepted no-op, so it is not enforced;
- ``ValueError`` for a malformed program: an indent that is not a multiple
  of four or jumps more than one level, an ``IF`` without its ``ELSE`` (the
  wiki: "always come in pairs"), an ``ELSE`` without an ``IF``, an empty
  block where one is required, a nested ``DEF``, a bad literal, a
  redeclared or keyword name, or an unparsable statement;
- :class:`~esolangs.exceptions.HaltError` for an invalid runtime operation:
  assigning across types, using an undeclared name, calling an overload
  that does not exist, a non-snuval function that returns nothing or the
  wrong type, ``GIVE`` outside a function, and exceeding the call-depth
  cap;
- ``SET x:$`` is refused (the wiki requires a non-snuval initial value so a
  variable has a type); ``x . $`` is allowed and stores the snuval, which
  is always false.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

_KEYWORDS = frozenset(("DEF", "ELSE", "GIVE", "IF", "IN", "OUT", "SET", "WHILE"))
# Named because a bare "'" comparison reads to bandit as a hardcoded secret.
_QUOTE = "'"
_HEX = "0123456789ABCDEF"
_ESCAPES = {"0": "\0", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
_INDENT = 4

# Depth cap for the inline call evaluator.  An explicit counter rather than
# a caught RecursionError: partial effects survive a raise, and Python's
# own limit would land at an arbitrary point inside an expression.
_MAX_DEPTH = 200

_Kind = Literal["wubyte", "aschar", "snuval"]


@dataclass(frozen=True)
class _Value:
    """A DINAC value: its type tag and its integer code (0 for a snuval)."""

    kind: _Kind
    code: int = 0

    def truthy(self) -> bool:
        """Return the truth value: a snuval is always false, else nonzero."""
        return self.kind != "snuval" and self.code != 0

    def render(self) -> str:
        """Render for ``OUT``: a wubyte as two hex digits, an aschar as itself."""
        if self.kind == "wubyte":
            return f"{self.code:02X}"
        if self.kind == "aschar":
            return chr(self.code)
        return "$"


_SNUVAL = _Value("snuval")


# -- expressions -----------------------------------------------------------

# Discriminated by the first element, like the statement tuples below.
_Lit = tuple[Literal["lit"], _Value]
_Name = tuple[Literal["name"], str]
_Not = tuple[Literal["not"], "_Expr"]
_Step = tuple[Literal["step"], str, "_Expr"]  # postfix + / -
_Cmp = tuple[Literal["cmp"], str, "_Expr", "_Expr"]  # = / !
_Call = tuple[Literal["call"], str, tuple["_Expr", ...]]
_Expr = _Lit | _Name | _Not | _Step | _Cmp | _Call


def _parse_literal(text: str) -> _Value | None:
    """Return the value of a whole-token literal, or None if it is not one."""
    if text == "$":
        return _SNUVAL
    if len(text) == 2 and text[0] in _HEX and text[1] in _HEX:
        return _Value("wubyte", int(text, 16))
    if text.startswith("'"):
        return _parse_aschar(text[1:])
    # A bare escape: the wiki's prose spells an aschar ``'`` + char, but its
    # examples write ``SET c:\0``, ``OUT \n`` and ``DEF/\0`` unquoted.  The
    # examples are ground truth, so both spellings are accepted.
    if text.startswith("\\"):
        return _parse_aschar(text)
    return None


def _parse_aschar(body: str) -> _Value | None:
    """Return the aschar named by ``body`` (a char or a 2-char escape)."""
    if body.startswith("\\") and len(body) == 2:
        escape = _ESCAPES.get(body[1])
        return None if escape is None else _Value("aschar", ord(escape))
    if len(body) == 1 and ord(body) < 128:
        return _Value("aschar", ord(body))
    return None


def _is_name(text: str) -> bool:
    """Whether ``text`` matches the identifier regex ``[a-z][A-Za-z0-9]*``."""
    return bool(text) and text[0].islower() and text[0].isalpha() and text.isalnum()


class _Reader:
    """A cursor over one statement's text, used by the expression parser.

    Kept as a small object rather than threaded indices because every
    ``_parse_*`` helper below needs both the text and the position, and the
    grammar backtracks in exactly one place (``_parse_compare``).
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] == " ":
            self.pos += 1

    def done(self) -> bool:
        self.skip()
        return self.pos >= len(self.text)

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""


def _parse_expr(reader: _Reader) -> _Expr:
    """Parse one expression: a comparison, the loosest binding form."""
    return _parse_compare(reader)


def _parse_compare(reader: _Reader) -> _Expr:
    """Parse ``a = b`` / ``a ! b``, or just the left operand.

    ``=`` and ``!`` are the only infix operators and they do not chain, so
    one optional right-hand side is the whole rule.
    """
    left = _parse_unary(reader)
    reader.skip()
    if reader.peek() in ("=", "!"):
        op = reader.peek()
        reader.pos += 1
        return ("cmp", op, left, _parse_unary(reader))
    return left


def _parse_unary(reader: _Reader) -> _Expr:
    """Parse ``~``-prefixed operands, which stack (the wiki's ``~~b``)."""
    reader.skip()
    if reader.peek() == "~":
        reader.pos += 1
        return ("not", _parse_unary(reader))
    return _parse_postfix(reader)


def _parse_postfix(reader: _Reader) -> _Expr:
    """Parse a primary followed by any run of ``+``/``-`` successors.

    No space is allowed before the operator (the wiki: ``N+``, no space),
    which is what keeps ``a - b`` from parsing: there is no binary minus,
    and a spaced ``-`` is simply not part of the grammar.
    """
    expr = _parse_primary(reader)
    while reader.peek() in ("+", "-"):
        expr = ("step", reader.peek(), expr)
        reader.pos += 1
    return expr


def _parse_primary(reader: _Reader) -> _Expr:
    """Parse a parenthesized group, a call, a name, or a literal."""
    reader.skip()
    if reader.peek() == "(":
        reader.pos += 1
        inner = _parse_expr(reader)
        reader.skip()
        if reader.peek() != ")":
            raise ValueError("unclosed parenthesis")
        reader.pos += 1
        return inner
    start = reader.pos
    while reader.pos < len(reader.text) and reader.text[reader.pos] not in " ()~=!,+-":
        reader.pos += 1
    token = reader.text[start : reader.pos]
    if not token:
        # An aschar literal may *be* one of the delimiters (``' ``, ``'(``,
        # ``'+``), so a quote is re-read here taking the next character raw.
        raise ValueError(f"expected a value at position {start}")
    # A lone quote means the character it introduces is one of the
    # delimiters the scan above stopped on (``' ``, ``'(``, ``'+``), so it
    # is taken raw here rather than tokenized.
    if len(token) == 1 and token == _QUOTE:
        if reader.pos < len(reader.text):
            char = reader.text[reader.pos]
            reader.pos += 1
            value = _parse_aschar(char)
            if value is not None:
                return ("lit", value)
        raise ValueError("malformed aschar literal")
    if reader.peek() == "(":
        if not _is_name(token):
            raise ValueError(f"{token!r} is not a valid function name")
        return ("call", token, _parse_args(reader))
    literal = _parse_literal(token)
    if literal is not None:
        return ("lit", literal)
    if _is_name(token) and token not in _KEYWORDS:
        return ("name", token)
    raise ValueError(f"malformed value {token!r}")


def _parse_args(reader: _Reader) -> tuple[_Expr, ...]:
    """Parse a call's parenthesized, comma-separated argument list."""
    reader.pos += 1  # the "("
    args: list[_Expr] = []
    reader.skip()
    if reader.peek() == ")":
        reader.pos += 1
        return ()
    while True:
        args.append(_parse_expr(reader))
        reader.skip()
        if reader.peek() == ",":
            reader.pos += 1
            continue
        if reader.peek() == ")":
            reader.pos += 1
            return tuple(args)
        raise ValueError("malformed argument list")


def _parse_whole(text: str) -> _Expr:
    """Parse ``text`` as a complete expression, rejecting a trailing tail.

    Trailing spaces are allowed: the wiki's Hello World writes ``OUT 'r ``
    with one, so a statement is complete once the cursor reaches only
    blanks.
    """
    reader = _Reader(text)
    expr = _parse_expr(reader)
    if not reader.done():
        raise ValueError(f"trailing text in expression {text!r}")
    return expr


# -- statements ------------------------------------------------------------

_Out = tuple[Literal["out"], _Expr]
_In = tuple[Literal["in"], str]
_Set = tuple[Literal["set"], str, _Expr]
_Assign = tuple[Literal["assign"], str, _Expr]
_Give = tuple[Literal["give"], _Expr]
_CallStmt = tuple[Literal["callstmt"], _Expr]
_If = tuple[Literal["if"], _Expr, tuple["_Stmt", ...], tuple["_Stmt", ...]]
_While = tuple[Literal["while"], _Expr, tuple["_Stmt", ...]]
_Stmt = _Out | _In | _Set | _Assign | _Give | _CallStmt | _If | _While


@dataclass(frozen=True)
class _Function:
    """One overload: its return type, parameter names/types, and body."""

    name: str
    returns: _Kind
    params: tuple[tuple[str, _Kind], ...]
    body: tuple[_Stmt, ...]

    @property
    def signature(self) -> tuple[str, tuple[_Kind, ...]]:
        """The overload key: the name plus the parameter *types*."""
        return (self.name, tuple(kind for _, kind in self.params))


def _strip_comment(line: str) -> str:
    r"""Remove a ``#`` comment, respecting an aschar literal.

    ``OUT '#`` is a character literal, not a comment, so the scan tracks
    whether the ``#`` is the character a quote just introduced.
    """
    out = []
    i = 0
    while i < len(line):
        char = line[i]
        if char == "#":
            break
        out.append(char)
        if char == "'" and i + 1 < len(line):
            # The quoted character is taken raw, escape included.
            nxt = line[i + 1]
            out.append(nxt)
            i += 2
            if nxt == "\\" and i < len(line):
                out.append(line[i])
                i += 1
            continue
        i += 1
    return "".join(out)


def _indent_of(line: str) -> int:
    """Return a line's indent level, rejecting a non-multiple of four."""
    spaces = len(line) - len(line.lstrip(" "))
    if spaces % _INDENT:
        raise ValueError(f"indent of {spaces} spaces is not a multiple of {_INDENT}")
    return spaces // _INDENT


def _split_lines(code: str) -> list[tuple[int, str]]:
    """Return ``(level, text)`` for every non-blank, non-comment line.

    Only the *leading* indent is removed.  A trailing space can be the
    statement's own value -- the wiki's Hello World prints one with
    ``OUT ' `` -- so stripping the right-hand side would delete the
    literal; ``_parse_whole`` tolerates a trailing run of blanks instead
    (the same example's ``OUT 'r `` has one that is not a literal).
    """
    result = []
    for raw in code.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        result.append((_indent_of(line), line.lstrip(" ")))
    return result


def _parse_typed(token: str) -> _Kind:
    """Return the type a ``DEF/<v>`` or a parameter's sample value names."""
    value = _parse_literal(token)
    if value is None:
        raise ValueError(f"{token!r} does not name a type")
    return value.kind


class _Parser:
    """Folds the indented lines into functions and a top-level body."""

    def __init__(self, lines: list[tuple[int, str]]) -> None:
        self.lines = lines
        self.pos = 0
        self.functions: dict[tuple[str, tuple[_Kind, ...]], _Function] = {}

    def parse(self) -> tuple[_Stmt, ...]:
        """Parse the whole program, returning its top-level body.

        Functions are hoisted into ``self.functions`` as they are met, so a
        call may name an overload defined further down the file.
        """
        top: list[_Stmt] = []
        while self.pos < len(self.lines):
            level, text = self.lines[self.pos]
            if level != 0:
                raise ValueError(f"unexpected indent before {text!r}")
            if text.startswith("DEF"):
                self._parse_def()
            else:
                top.append(self._parse_statement(0))
        return tuple(top)

    def _block(self, level: int, owner: str) -> tuple[_Stmt, ...]:
        """Parse the statements indented one level below ``level``."""
        body: list[_Stmt] = []
        while self.pos < len(self.lines):
            here, text = self.lines[self.pos]
            if here <= level:
                break
            if here != level + 1:
                raise ValueError(f"indent jumps to {here} before {text!r}")
            body.append(self._parse_statement(here))
        if not body:
            raise ValueError(f"{owner} needs an indented body")
        return tuple(body)

    def _parse_def(self) -> None:
        """Parse one ``DEF/<type> name p:v ...`` and register the overload."""
        level, text = self.lines[self.pos]
        self.pos += 1
        head, _, rest = text.partition(" ")
        if not head.startswith("DEF/"):
            raise ValueError(f"malformed DEF header {text!r}")
        returns = _parse_typed(head[4:])
        parts = rest.split()
        if not parts or not _is_name(parts[0]) or parts[0] in _KEYWORDS:
            raise ValueError(f"malformed DEF name in {text!r}")
        name = parts[0]
        params: list[tuple[str, _Kind]] = []
        seen: set[str] = set()
        for part in parts[1:]:
            pname, sep, sample = part.partition(":")
            if not sep or not _is_name(pname) or pname in _KEYWORDS or pname in seen:
                raise ValueError(f"malformed parameter {part!r}")
            seen.add(pname)
            params.append((pname, _parse_typed(sample)))
        body = self._block(level, f"DEF {name}")
        # The wiki: a non-snuval function that never returns "will raise an
        # error".  A body with no GIVE anywhere cannot return, so it is
        # refused at parse time; a GIVE that is merely unreachable at
        # runtime is the HaltError in ``_checked`` instead.
        if returns != "snuval" and not any(s[0] == "give" for s in _walk(body)):
            raise ValueError(f"function {name!r} returns {returns} but never GIVEs")
        function = _Function(name, returns, tuple(params), body)
        if function.signature in self.functions:
            raise ValueError(f"duplicate overload for {name!r}")
        self.functions[function.signature] = function

    def _parse_statement(self, level: int) -> _Stmt:
        """Parse the statement at the cursor, consuming any indented body."""
        _, text = self.lines[self.pos]
        self.pos += 1
        if text.startswith("DEF/") or text.startswith("DEF "):
            raise ValueError("a DEF may not be nested")
        if text.startswith("IF "):
            return self._parse_if(level, text)
        if text.startswith("WHILE "):
            condition = _parse_whole(text[6:])
            return ("while", condition, self._block(level, "WHILE"))
        if text.rstrip() == "ELSE":
            raise ValueError("ELSE without a matching IF")
        if text.startswith("OUT "):
            return ("out", _parse_whole(text[4:]))
        if text.startswith("IN "):
            name = text[3:].strip()
            if not _is_name(name) or name in _KEYWORDS:
                raise ValueError(f"IN needs a variable name, got {name!r}")
            return ("in", name)
        if text.startswith("GIVE "):
            return ("give", _parse_whole(text[5:]))
        if text.startswith("SET "):
            name, sep, value = text[4:].partition(":")
            if not sep or not _is_name(name) or name in _KEYWORDS:
                raise ValueError(f"malformed SET in {text!r}")
            return ("set", name, _parse_whole(value))
        head, sep, value = text.partition(" . ")
        if sep and _is_name(head) and head not in _KEYWORDS:
            return ("assign", head, _parse_whole(value))
        # A bare call is a statement of its own: the wiki's way to invoke a
        # DEF/$ function, whose value there is nothing to bind.
        if text.rstrip().endswith(")"):
            expr = _parse_whole(text)
            if expr[0] == "call":
                return ("callstmt", expr)
        raise ValueError(f"malformed statement {text!r}")

    def _parse_if(self, level: int, text: str) -> _If:
        """Parse ``IF``, its body, the mandatory ``ELSE``, and that body."""
        condition = _parse_whole(text[3:])
        then = self._block(level, "IF")
        if self.pos >= len(self.lines):
            raise ValueError("IF without its ELSE")
        here, next_text = self.lines[self.pos]
        if here != level or next_text.rstrip() != "ELSE":
            raise ValueError("IF without its ELSE")
        self.pos += 1
        return ("if", condition, then, self._block(level, "ELSE"))


def _walk(body: tuple[_Stmt, ...]) -> list[_Stmt]:
    """Return every statement in ``body``, descending into nested blocks."""
    found: list[_Stmt] = []
    for stmt in body:
        found.append(stmt)
        if stmt[0] == "if":
            found.extend(_walk(stmt[2]))
            found.extend(_walk(stmt[3]))
        elif stmt[0] == "while":
            found.extend(_walk(stmt[2]))
    return found


_Overloads = dict[tuple[str, tuple[_Kind, ...]], _Function]


def _parse(code: str) -> tuple[_Overloads, tuple[_Stmt, ...]]:
    """Parse a whole program into its overload table and top-level body."""
    parser = _Parser(_split_lines(code))
    top = parser.parse()
    return parser.functions, top


# -- evaluation ------------------------------------------------------------


class _Return(Exception):  # noqa: N818 - a control-flow signal, not an error
    """Carries a ``GIVE``'s value out of the inline call evaluator."""

    def __init__(self, value: _Value) -> None:
        super().__init__()
        self.value = value


def _step_value(value: _Value, op: str) -> _Value:
    """Apply postfix ``+``/``-``, wrapping at 256 (wubyte) or 128 (aschar)."""
    if value.kind == "snuval":
        raise HaltError("cannot apply + or - to a snuval")
    modulus = 256 if value.kind == "wubyte" else 128
    delta = 1 if op == "+" else -1
    return _Value(value.kind, (value.code + delta) % modulus)


def _compare(left: _Value, right: _Value) -> bool:
    """Whether two values are equal; different types are never equal."""
    return left.kind == right.kind and left.code == right.code


def _bit(*, flag: bool) -> _Value:
    """Return the wubyte ``01``/``00`` a comparison or ``~`` yields."""
    return _Value("wubyte", 1 if flag else 0)


# -- the machine -----------------------------------------------------------


@dataclass
class _Frame:
    """One executing block: its statements, cursor, and variable scope.

    ``scope`` is shared with the enclosing frames of the same call (a
    ``WHILE`` body sees the enclosing locals), so it is a reference rather
    than a copy.  A loop needs no marker here: ``step`` rewinds the
    *parent's* cursor onto the ``WHILE`` before pushing the body, so the
    condition is re-tested when this frame runs out.
    """

    body: tuple[_Stmt, ...]
    scope: dict[str, _Value]
    ind: int = 0


#: The whole run state as a value: the frame stack (each frame's block
#: identity, its cursor, and the bindings it can see) and the input cursor.
#: This is what :meth:`_Machine.snapshot` hands the cycle detector, and it
#: is complete -- the overload table and the parsed bodies are fixed at
#: parse time, so nothing outside these fields can change during a run.
type _State = tuple[tuple[tuple[int, int, tuple[tuple[str, str, int], ...]], ...], int]


class _Machine:
    """One DINAC run: the parsed program, the frame stack, and the ports.

    ``step()`` executes one statement of the innermost frame.  A ``WHILE``
    pushes a frame carrying its condition, so a top-level loop is stepped
    rather than recursed and :func:`esolangs.vm.run_until_halt_or_cycle`
    can prove the truth machine's hang.  Calls inside expressions are
    evaluated inline instead, bounded by ``_MAX_DEPTH``.
    """

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.functions, top = _parse(code)
        self.globals: dict[str, _Value] = {}
        self.frames: list[_Frame] = [_Frame(top, self.globals)]
        self.depth = 0
        self._pending: list[str] = []

    @property
    def halted(self) -> bool:
        """Whether every frame has run to its end."""
        return not self.frames

    def snapshot(self) -> _State:
        """Return the complete internal state, hashable for cycle detection."""
        # Every frame's cursor and every binding it can see, plus the input
        # cursor: a lap that consumed a line is not a repeat.  A body is
        # identified by ``id``, which is stable for the run because every
        # block tuple is built once at parse time and never rebuilt.
        return (
            tuple(
                (
                    id(frame.body),
                    frame.ind,
                    tuple(sorted((k, v.kind, v.code) for k, v in frame.scope.items())),
                )
                for frame in self.frames
            ),
            self.io.position(),
        )

    @property
    def ip(self) -> int:
        """The innermost frame's statement cursor."""
        return self.frames[-1].ind if self.frames else 0

    @property
    def memory(self) -> list[int]:
        """The global scope's values, in declaration order."""
        return [v.code for v in self.globals.values()]

    @property
    def stack(self) -> list[object]:
        """The frame stack's depth exposed as the VM's stack view."""
        return [frame.ind for frame in self.frames]

    # -- expression evaluation, the one place that recurses ---------------

    def _eval(self, expr: _Expr, scope: dict[str, _Value]) -> _Value:
        """Evaluate an expression in ``scope``, running any calls inline."""
        if expr[0] == "lit":
            return expr[1]
        if expr[0] == "name":
            value = scope.get(expr[1])
            if value is None:
                raise HaltError(f"undeclared name {expr[1]!r}")
            return value
        if expr[0] == "not":
            return _bit(flag=not self._eval(expr[1], scope).truthy())
        if expr[0] == "step":
            return _step_value(self._eval(expr[2], scope), expr[1])
        if expr[0] == "cmp":
            left = self._eval(expr[2], scope)
            right = self._eval(expr[3], scope)
            same = _compare(left, right)
            return _bit(flag=same if expr[1] == "=" else not same)
        return self._call(expr[1], expr[2], scope)

    def _call(
        self, name: str, args: tuple[_Expr, ...], scope: dict[str, _Value]
    ) -> _Value:
        """Run one call to completion and return its value.

        Inline rather than frame-suspended: a call can sit inside an
        expression (``WHILE and(a,b)``), and suspending mid-expression
        would need continuations the frame stack does not model.
        """
        values = [self._eval(arg, scope) for arg in args]
        key = (name, tuple(v.kind for v in values))
        function = self.functions.get(key)
        if function is None:
            raise HaltError(f"no overload of {name!r} takes {list(key[1])}")
        if self.depth >= _MAX_DEPTH:
            raise HaltError(f"call depth exceeded {_MAX_DEPTH} in {name!r}")
        # strict: the overload was selected by its parameter *types*, so the
        # two sequences are the same length by construction.
        local = {
            pname: value
            for (pname, _), value in zip(function.params, values, strict=True)
        }
        self.depth += 1
        try:
            self._run_body(function.body, local)
        except _Return as give:
            return self._checked(function, give.value)
        finally:
            self.depth -= 1
        return self._checked(function, _SNUVAL)

    def _checked(self, function: _Function, value: _Value) -> _Value:
        """Validate a call's result against the overload's declared type."""
        if function.returns == "snuval":
            return value
        if value.kind != function.returns:
            raise HaltError(
                f"{function.name!r} declares {function.returns} but gave {value.kind}"
            )
        return value

    def _run_body(self, body: tuple[_Stmt, ...], scope: dict[str, _Value]) -> None:
        """Execute a function body to completion, inside one ``step``."""
        for stmt in body:
            self._exec(stmt, scope)

    def _exec(self, stmt: _Stmt, scope: dict[str, _Value]) -> None:
        """Execute one statement inside a called function (not stepped)."""
        if stmt[0] == "if":
            branch = stmt[2] if self._eval(stmt[1], scope).truthy() else stmt[3]
            self._run_body(branch, scope)
        elif stmt[0] == "while":
            while self._eval(stmt[1], scope).truthy():
                self._run_body(stmt[2], scope)
        elif stmt[0] == "give":
            raise _Return(self._eval(stmt[1], scope))
        else:
            self._simple(stmt, scope)

    # -- the simple statements, shared by both execution paths -------------

    def _simple(self, stmt: _Stmt, scope: dict[str, _Value]) -> None:
        """Execute a statement with no body: OUT, IN, SET, or an assignment."""
        if stmt[0] == "out":
            self.io.print_str(self._eval(stmt[1], scope).render())
        elif stmt[0] == "callstmt":
            self._eval(stmt[1], scope)  # run for its effects; the value is dropped
        elif stmt[0] == "in":
            self._read(stmt[1], scope)
        elif stmt[0] == "set":
            if stmt[1] in scope:
                raise HaltError(f"{stmt[1]!r} is already declared")
            value = self._eval(stmt[2], scope)
            if value.kind == "snuval":
                raise HaltError(f"SET {stmt[1]!r} needs a typed initial value")
            scope[stmt[1]] = value
        elif stmt[0] == "assign":
            current = scope.get(stmt[1])
            if current is None:
                raise HaltError(f"undeclared name {stmt[1]!r}")
            value = self._eval(stmt[2], scope)
            if value.kind != "snuval" and value.kind != current.kind:
                raise HaltError(
                    f"{stmt[1]!r} is {current.kind}, cannot take a {value.kind}"
                )
            scope[stmt[1]] = value
        else:
            raise HaltError("GIVE outside a function")

    def _read(self, name: str, scope: dict[str, _Value]) -> None:
        r"""Read one line into ``name``, per its declared type.

        The wiki fixes the *empty line* conventions (``\n`` for an aschar,
        ``00`` for a wubyte) and is silent on input running out; EOF gives
        ``\0``/``00`` so the wiki's cat program terminates.
        """
        current = scope.get(name)
        if current is None:
            raise HaltError(f"undeclared name {name!r}")
        if current.kind == "snuval":
            raise HaltError(f"{name!r} has no type to read into")
        try:
            line = self.io.input_str()
        except EOFError:
            scope[name] = _Value(current.kind, 0)
            return
        if current.kind == "aschar":
            # An empty line is legal and has no character to take, so the
            # wiki's newline convention applies rather than an IndexError.
            code = ord(line[0]) if line else ord("\n")
            scope[name] = _Value("aschar", code if code < 128 else 0)
            return
        scope[name] = _Value("wubyte", _wubyte_of(line))

    # -- the stepped shell -------------------------------------------------

    def step(self) -> None:
        """Execute one statement of the innermost frame."""
        if not self.frames:
            return
        frame = self.frames[-1]
        if frame.ind >= len(frame.body):
            self.frames.pop()
            return
        stmt = frame.body[frame.ind]
        frame.ind += 1
        if stmt[0] == "if":
            branch = stmt[2] if self._eval(stmt[1], frame.scope).truthy() else stmt[3]
            self.frames.append(_Frame(branch, frame.scope))
        elif stmt[0] == "while":
            if self._eval(stmt[1], frame.scope).truthy():
                # Rewind onto the WHILE itself, so finishing the body
                # re-tests the condition rather than falling past it.
                frame.ind -= 1
                self.frames.append(_Frame(stmt[2], frame.scope))
        else:
            self._simple(stmt, frame.scope)


def _wubyte_of(line: str) -> int:
    """Parse a 1-3 digit decimal wubyte, per the wiki's ``IN`` convention.

    Empty input or an invalid/out-of-range value reads as ``00``.
    """
    text = line.strip()
    if not text.isdigit() or len(text) > 3:
        return 0
    value = int(text)
    return value if 0 <= value <= 255 else 0


def run(code: str, io: IO) -> None:
    """Run a DINAC program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
