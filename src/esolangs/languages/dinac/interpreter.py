r"""Interpreter for DINAC.

A strongly typed, indentation-structured language of three datatypes: the
wrapping unsigned byte (``wubyte``, a 2-char literal ``[0-9A-F]{2}``), the
ASCII character (``aschar``, ``'`` plus a character, or an escape ``\0 \n
\t \r \\``) and the null ``snuval`` (``$``).  ``SET n:v`` declares, ``n . v``
assigns, ``OUT v`` prints, ``IN n`` reads into a declared variable, ``IF``
(always with its ``ELSE``) and ``WHILE`` take a 4-space-indented body, and
``DEF/<type> f p:v`` declares a function returning by ``GIVE``; overloads
differ by parameter types.  ``+``/``-`` are postfix successor and
predecessor (mod 256 for a wubyte, mod 128 for an aschar), ``=``/``!``
compare, ``~`` negates, parentheses group.  A call is a frame: a call inside
an expression (``OUT add1(x)``, ``WHILE and(a,b)``) suspends its statement,
which is re-entered once per call with the returned value rewritten in as a
literal, so a loop inside a function body is stepped like any other.

Input/output:
    ``IN`` of an aschar takes the next character; of a wubyte, one line read
    as 1-3 decimal digits (empty or invalid reads ``00``).  ``OUT`` prints a
    wubyte as two hex digits, an aschar as its character, a snuval as ``$``.
    At EOF an ``IN`` reads ``\0`` / ``00``.

Errors:
    ProgramError: an indent that is not a multiple of four or that jumps a
    level, an ``IF`` without its ``ELSE`` or an ``ELSE`` without an ``IF``,
    an empty block, a nested ``DEF``, a bad literal, a keyword or reused
    name, a function that never ``GIVE``s but declares a type, a duplicate
    overload, an unparsable statement.
    HaltError: assigning across types, an undeclared name, ``SET`` of a
    snuval, a call with no matching overload, a function returning the wrong
    type, ``GIVE`` outside a function, ``+``/``-`` on a snuval.

Decisions:
    The page contradicts itself; examples outrank prose.
    * Wubyte literals are uppercase hex, as the regex says "case-sensitive"
      and the examples write ``FF``, ``0F``.  The prose claim that a
      wubyte's first character may be "lowercase alphabetical" cannot hold
      beside identifiers starting lowercase, so ``ff`` is a variable name.
    * ``\0``, ``\n`` and the other escapes are accepted bare as aschar
      literals, in ``SET``, ``OUT``, ``DEF/\0`` and parameters: the
      examples write them unquoted, the prose says ``'`` plus an escape.
    * ``add1(1)`` raises ``ValueError``: ``1`` is neither a wubyte nor a
      name.  The repairs ``add1(01)`` (prints ``02``) and ``add1('1)``
      (through the aschar overload, prints ``2``) both fit; "should output
      2" fits only the second, so the repair is not unique and not made.
    * The cat program reads before it prints, so it drops its first
      character and prints a final ``\0`` when ``IN`` yields it.  Run as
      written; the repair (``OUT c`` before ``IN c``) is the intended cat.
    * The truth machine prints ``00``, not ``0``: wubytes print as their
      2-char literals.  Input 1 loops printing ``1``.
    * The Deadfish interpreter indents ``add`` and ``mul`` by three
      spaces (the page marks it "maybe"); the 4-space rule rejects it.
    * ``IN`` of an aschar consumes one character (the PlusOrMinus and cat
      examples read "1 char at a time"), so an empty line reads ``\n``
      ("Empty input returns \n").  Input running out is unspecified; ``\0``
      / ``00`` is chosen so the cat's ``WHILE c`` can end.  A non-ASCII
      character reads ``\0``, as an invalid wubyte reads ``00``.
    * ``=`` and ``!`` across types are false and true.  A snuval equals only
      a snuval and is always falsy; ``x . $`` stores it, ``SET x:$`` is
      refused (a variable's type comes from its initial value).
    * A function sees only its parameters and locals: the page never reads
      a global inside a function.  A variable may not share a function's
      name.
    * The ban on null statements in a branch is not enforced: detecting
      them needs effect analysis and no example relies on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

_KEYWORDS = frozenset(("DEF", "ELSE", "GIVE", "IF", "IN", "OUT", "SET", "WHILE"))
# Named because a bare "'" comparison reads to bandit as a hardcoded secret.
_QUOTE = "'"
_HEX = "0123456789ABCDEF"
_ESCAPES = {"0": "\0", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
_INDENT = 4

type _Kind = Literal["wubyte", "aschar", "snuval"]


class _Value(NamedTuple):
    """A DINAC value: its type tag and its integer code (0 for a snuval)."""

    kind: _Kind
    code: int = 0

    def truthy(self) -> bool:
        """A snuval is always false, anything else is false iff its code is 0."""
        return self.kind != "snuval" and self.code != 0

    def render(self) -> str:
        """The ``OUT`` text: two hex digits, the character, or ``$``."""
        if self.kind == "wubyte":
            return f"{self.code:02X}"
        return chr(self.code) if self.kind == "aschar" else "$"


_SNUVAL = _Value("snuval")

# Discriminated by the first element.  A name is its slot in the function's
# scope tuple, so a store is a tuple edit rather than a dict rebuild.
type _Expr = tuple[Any, ...]
# Statements hold block ids into ``_Program.bodies``.
type _Stmt = tuple[Any, ...]

#: Where each statement kind keeps the expression it evaluates; ``in`` has none.
_EXPR_SLOT = {
    "out": 1,
    "give": 1,
    "call": 1,
    "if": 1,
    "while": 1,
    "set": 2,
    "assign": 2,
}


@dataclass(frozen=True)
class _Fn:
    """One overload: return type, parameter types, slot names, body block."""

    name: str
    returns: _Kind
    params: tuple[_Kind, ...]
    names: tuple[str, ...]
    body: int


@dataclass(frozen=True)
class _Program:
    """Parsed program: function 0 is the top level; blocks are ids."""

    fns: tuple[_Fn, ...]
    overloads: dict[tuple[str, tuple[_Kind, ...]], int]
    bodies: tuple[tuple[_Stmt, ...], ...]


class _Frame(NamedTuple):
    """One call: its scope, its block cursors, and a suspended statement.

    ``pending`` is the statement's expression with the calls already
    returned rewritten in as literals; ``returned`` is the value a
    just-finished call is handing back.
    """

    fn: int
    scope: tuple[_Value | None, ...]
    blocks: tuple[tuple[int, int], ...]
    pending: _Expr | None = None
    returned: _Value | None = None


#: The call stack as a linked pair, so a call and a return are O(1).
type _State = tuple[_Frame, _State] | None


def _bad(message: str, hint: str) -> ValueError:
    return syntax_error(message, hint)


def _parse_aschar(body: str) -> _Value | None:
    """The aschar named by ``body`` (a character or a 2-char escape)."""
    if body.startswith("\\") and len(body) == 2:
        escape = _ESCAPES.get(body[1])
        return None if escape is None else _Value("aschar", ord(escape))
    if len(body) == 1 and ord(body) < 128:
        return _Value("aschar", ord(body))
    return None


def _parse_literal(text: str) -> _Value | None:
    """The value of a whole-token literal, or None if it is not one."""
    if text == "$":
        return _SNUVAL
    if len(text) == 2 and text[0] in _HEX and text[1] in _HEX:
        return _Value("wubyte", int(text, 16))
    if text.startswith(_QUOTE):
        return _parse_aschar(text[1:])
    # A bare escape: the examples write ``SET c:\0`` and ``OUT \n`` unquoted.
    return _parse_aschar(text) if text.startswith("\\") else None


def _is_name(text: str) -> bool:
    """Whether ``text`` matches ``[a-z][A-Za-z0-9]*``."""
    return bool(text) and text[0].islower() and text[0].isalpha() and text.isalnum()


class _Slots:
    """The names of one function body, numbered in order of first mention."""

    def __init__(self) -> None:
        self.names: list[str] = []

    def slot(self, name: str) -> int:
        if name not in self.names:
            self.names.append(name)
        return self.names.index(name)


class _Reader:
    """A cursor over one statement's text, for the expression parser."""

    def __init__(self, text: str, slots: _Slots) -> None:
        self.text = text
        self.slots = slots
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
    """``a = b`` / ``a ! b`` (infix, unchained) or just the left operand."""
    left = _parse_unary(reader)
    reader.skip()
    if reader.peek() in ("=", "!"):
        op = reader.peek()
        reader.pos += 1
        return ("cmp", op, left, _parse_unary(reader))
    return left


def _parse_unary(reader: _Reader) -> _Expr:
    """``~``-prefixed operands, which stack (``~~b``)."""
    reader.skip()
    if reader.peek() == "~":
        reader.pos += 1
        return ("not", _parse_unary(reader))
    expr = _parse_primary(reader)
    # No space before ``+``/``-`` (``N+``), so a spaced ``-`` is no operator.
    while reader.peek() in ("+", "-"):
        expr = ("step", reader.peek(), expr)
        reader.pos += 1
    return expr


def _parse_primary(reader: _Reader) -> _Expr:
    """A parenthesized group, a call, a name, or a literal."""
    reader.skip()
    if reader.peek() == "(":
        reader.pos += 1
        inner = _parse_expr(reader)
        reader.skip()
        if reader.peek() != ")":
            raise _bad("unclosed parenthesis", "close the group with )")
        reader.pos += 1
        return inner
    start = reader.pos
    while reader.pos < len(reader.text) and reader.text[reader.pos] not in " ()~=!,+-":
        reader.pos += 1
    token = reader.text[start : reader.pos]
    if not token:
        raise _bad(f"expected a value at position {start}", "write a value here")
    # A lone quote introduces a delimiter character (``' ``, ``'(``, ``'+``),
    # taken raw rather than tokenized.
    if token == _QUOTE:
        if reader.pos < len(reader.text):
            char = reader.text[reader.pos]
            reader.pos += 1
            value = _parse_aschar(char)
            if value is not None:  # pragma: no branch
                return ("lit", value)
        raise _bad("malformed aschar literal", "follow ' with one ASCII character")
    if reader.peek() == "(":
        if not _is_name(token):
            raise _bad(f"{token!r} is not a function name", "use [a-z][A-Za-z0-9]*")
        return ("call", token, _parse_args(reader))
    literal = _parse_literal(token)
    if literal is not None:
        return ("lit", literal)
    if _is_name(token) and token not in _KEYWORDS:
        return ("name", reader.slots.slot(token))
    raise _bad(
        f"malformed value {token!r}",
        "a wubyte is two hex digits 00-FF, an aschar ' and a character",
    )


def _parse_args(reader: _Reader) -> tuple[_Expr, ...]:
    """A call's parenthesized, comma-separated argument list."""
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
        elif reader.peek() == ")":
            reader.pos += 1
            return tuple(args)
        else:
            raise _bad("malformed argument list", "separate arguments with commas")


def _parse_whole(text: str, slots: _Slots) -> _Expr:
    """``text`` as a complete expression; trailing blanks are tolerated.

    The Hello World writes ``OUT 'r `` with a stray trailing space.
    """
    reader = _Reader(text, slots)
    expr = _parse_expr(reader)
    if not reader.done():
        raise _bad(f"trailing text in expression {text!r}", "one expression per line")
    return expr


def _strip_comment(line: str) -> str:
    r"""Remove a ``#`` comment, keeping ``'#`` (a character literal)."""
    out = []
    i = 0
    while i < len(line):
        char = line[i]
        if char == "#":
            break
        out.append(char)
        if char == _QUOTE and i + 1 < len(line):
            out.append(line[i + 1])
            i += 2
            if out[-1] == "\\" and i < len(line):
                out.append(line[i])
                i += 1
            continue
        i += 1
    return "".join(out)


def _split_lines(code: str) -> list[tuple[int, str]]:
    """``(level, text)`` for every non-blank, non-comment line.

    Only the leading indent goes: ``OUT ' `` ends in the literal space.
    """
    result = []
    for raw in code.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        spaces = len(line) - len(line.lstrip(" "))
        if spaces % _INDENT:
            raise _bad(
                f"indent of {spaces} spaces is not a multiple of {_INDENT}",
                "indent each level by exactly 4 spaces",
            )
        result.append((spaces // _INDENT, line.lstrip(" ")))
    return result


def _parse_type(token: str) -> _Kind:
    """The type a ``DEF/<v>`` or a parameter's sample value names."""
    value = _parse_literal(token)
    if value is None:
        raise _bad(f"{token!r} does not name a type", "use 00, \\0 or $")
    return value.kind


def _walk(bodies: list[tuple[_Stmt, ...]], block: int) -> list[_Stmt]:
    """Every statement under ``block``, descending into nested blocks."""
    found: list[_Stmt] = []
    for stmt in bodies[block]:
        found.append(stmt)
        if stmt[0] == "if":
            found += _walk(bodies, stmt[2])
            found += _walk(bodies, stmt[3])
        elif stmt[0] == "while":
            found += _walk(bodies, stmt[2])
    return found


class _Parser:
    """Folds the indented lines into functions and a top-level body."""

    def __init__(self, lines: list[tuple[int, str]]) -> None:
        self.lines = lines
        self.pos = 0
        self.fns: list[_Fn] = []
        self.overloads: dict[tuple[str, tuple[_Kind, ...]], int] = {}
        self.bodies: list[tuple[_Stmt, ...]] = []
        self.slots = _Slots()
        self.reserved: set[str] = set()

    def parse(self) -> _Program:
        """Parse the whole program; function 0 is the top level.

        Functions are hoisted, so a call may name an overload further down.
        """
        self.fns.append(_Fn("", "snuval", (), (), 0))  # placeholder for the top
        top: list[_Stmt] = []
        top_slots = self.slots
        while self.pos < len(self.lines):
            level, text = self.lines[self.pos]
            if level != 0:
                raise _bad(f"unexpected indent before {text!r}", "dedent to column 0")
            if text.startswith("DEF"):
                self.slots = _Slots()
                self._parse_def()
                self.slots = top_slots
            else:
                top.append(self._statement(0))
        self.bodies.append(tuple(top))
        self.fns[0] = _Fn(
            "", "snuval", (), tuple(top_slots.names), len(self.bodies) - 1
        )
        for fn in self.fns:
            clash = self.reserved & set(fn.names)
            if clash:
                raise _bad(
                    f"{sorted(clash)[0]!r} names both a function and a variable",
                    "give the variable another name",
                )
        return _Program(tuple(self.fns), self.overloads, tuple(self.bodies))

    def _block(self, level: int, owner: str) -> int:
        """Parse the statements one level below ``level``; return the block id."""
        body: list[_Stmt] = []
        while self.pos < len(self.lines):
            here, text = self.lines[self.pos]
            if here <= level:
                break
            if here != level + 1:
                raise _bad(
                    f"indent jumps to {here} before {text!r}", "indent one level"
                )
            body.append(self._statement(here))
        if not body:
            raise _bad(f"{owner} needs an indented body", "indent the body 4 spaces")
        self.bodies.append(tuple(body))
        return len(self.bodies) - 1

    def _parse_def(self) -> None:
        """Parse one ``DEF/<type> name p:v ...`` and register the overload."""
        level, text = self.lines[self.pos]
        self.pos += 1
        head, _, rest = text.partition(" ")
        if not head.startswith("DEF/"):
            raise _bad(f"malformed DEF header {text!r}", "write DEF/<type> name")
        returns = _parse_type(head[4:])
        parts = rest.split()
        if not parts or not _is_name(parts[0]) or parts[0] in _KEYWORDS:
            raise _bad(f"malformed DEF name in {text!r}", "use [a-z][A-Za-z0-9]*")
        name = parts[0]
        kinds: list[_Kind] = []
        for part in parts[1:]:
            pname, sep, sample = part.partition(":")
            if (
                not sep
                or not _is_name(pname)
                or pname in _KEYWORDS
                or pname in self.slots.names
            ):
                raise _bad(f"malformed parameter {part!r}", "write name:sample")
            self.slots.slot(pname)
            kinds.append(_parse_type(sample))
        body = self._block(level, f"DEF {name}")
        # A body with no GIVE cannot return; a GIVE merely unreachable is
        # the HaltError in ``_leave``.
        if returns != "snuval" and not any(
            s[0] == "give" for s in _walk(self.bodies, body)
        ):
            raise _bad(f"function {name!r} returns {returns} but never GIVEs", "GIVE")
        key = (name, tuple(kinds))
        if key in self.overloads:
            raise _bad(f"duplicate overload for {name!r}", "differ by parameter types")
        self.reserved.add(name)
        self.overloads[key] = len(self.fns)
        self.fns.append(_Fn(name, returns, key[1], tuple(self.slots.names), body))

    def _statement(self, level: int) -> _Stmt:
        """Parse the statement at the cursor, consuming any indented body."""
        _, text = self.lines[self.pos]
        self.pos += 1
        slots = self.slots
        if text.startswith(("DEF/", "DEF ")):
            raise _bad("a DEF may not be nested", "declare functions at column 0")
        if text.startswith("IF "):
            condition = _parse_whole(text[3:], slots)
            then = self._block(level, "IF")
            if self.pos >= len(self.lines):
                raise _bad("IF without its ELSE", "follow every IF body with ELSE")
            here, nxt = self.lines[self.pos]
            if here != level or nxt.rstrip() != "ELSE":
                raise _bad("IF without its ELSE", "follow every IF body with ELSE")
            self.pos += 1
            return ("if", condition, then, self._block(level, "ELSE"))
        if text.startswith("WHILE "):
            return ("while", _parse_whole(text[6:], slots), self._block(level, "WHILE"))
        if text.rstrip() == "ELSE":
            raise _bad("ELSE without a matching IF", "ELSE follows an IF body")
        if text.startswith("OUT "):
            return ("out", _parse_whole(text[4:], slots))
        if text.startswith("IN "):
            name = text[3:].strip()
            if not _is_name(name) or name in _KEYWORDS:
                raise _bad(f"IN needs a variable name, got {name!r}", "IN <name>")
            return ("in", slots.slot(name))
        if text.startswith("GIVE "):
            return ("give", _parse_whole(text[5:], slots))
        if text.startswith("SET "):
            name, sep, value = text[4:].partition(":")
            if not sep or not _is_name(name) or name in _KEYWORDS:
                raise _bad(f"malformed SET in {text!r}", "write SET name:value")
            return ("set", slots.slot(name), _parse_whole(value, slots))
        head, sep, value = text.partition(" . ")
        if sep and _is_name(head) and head not in _KEYWORDS:
            return ("assign", slots.slot(head), _parse_whole(value, slots))
        # A bare call is a statement of its own: how a DEF/$ is invoked.
        if text.rstrip().endswith(")"):
            expr = _parse_whole(text, slots)
            if expr[0] == "call":
                return ("call", expr)
        raise _bad(f"malformed statement {text!r}", "see the statement forms")


def _step_value(value: _Value, op: str) -> _Value:
    """Postfix ``+``/``-``, wrapping at 256 (wubyte) or 128 (aschar)."""
    if value.kind == "snuval":
        raise HaltError("cannot apply + or - to a snuval")
    modulus = 256 if value.kind == "wubyte" else 128
    return _Value(value.kind, (value.code + (1 if op == "+" else -1)) % modulus)


def _bit(*, flag: bool) -> _Value:
    """The wubyte ``01``/``00`` a comparison or ``~`` yields."""
    return _Value("wubyte", 1 if flag else 0)


def _eval(
    expr: _Expr, scope: tuple[_Value | None, ...], names: tuple[str, ...]
) -> _Value:
    """Evaluate a call-free expression."""
    if expr[0] == "lit":
        literal: _Value = expr[1]
        return literal
    if expr[0] == "name":
        value = scope[expr[1]]
        if value is None:
            raise HaltError(f"undeclared name {names[expr[1]]!r}")
        return value
    if expr[0] == "not":
        return _bit(flag=not _eval(expr[1], scope, names).truthy())
    if expr[0] == "step":
        return _step_value(_eval(expr[2], scope, names), expr[1])
    if expr[0] == "cmp":
        same = _eval(expr[2], scope, names) == _eval(expr[3], scope, names)
        return _bit(flag=same if expr[1] == "=" else not same)
    # Unreachable: every call is pushed and rewritten in before evaluating.
    raise HaltError(f"unresolved call to {expr[1]!r}")  # pragma: no cover


def _pending_call(expr: _Expr) -> _Expr | None:
    """The call evaluation would reach first (leftmost-innermost), or None."""
    if expr[0] in ("lit", "name"):
        return None
    if expr[0] == "not":
        return _pending_call(expr[1])
    if expr[0] == "step":
        return _pending_call(expr[2])
    if expr[0] == "cmp":
        return _pending_call(expr[2]) or _pending_call(expr[3])
    for arg in expr[2]:
        found = _pending_call(arg)
        if found is not None:
            return found
    return expr


def _substitute(expr: _Expr, target: _Expr, value: _Value) -> _Expr:
    """A copy of ``expr`` with the call ``target`` replaced by a literal."""
    if expr is target:
        return ("lit", value)
    if expr[0] in ("lit", "name"):
        return expr
    if expr[0] == "not":
        return ("not", _substitute(expr[1], target, value))
    if expr[0] == "step":
        return ("step", expr[1], _substitute(expr[2], target, value))
    if expr[0] == "cmp":
        return (
            "cmp",
            expr[1],
            _substitute(expr[2], target, value),
            _substitute(expr[3], target, value),
        )
    return ("call", expr[1], tuple(_substitute(a, target, value) for a in expr[2]))


def _wanted_read(state: _State, prog: _Program) -> _Kind | None:
    """The type the next statement reads, if it is an ``IN`` that can run."""
    if state is None:
        return None
    frame = state[0]
    block, ind = frame.blocks[-1]
    body = prog.bodies[block]
    if ind >= len(body) or body[ind][0] != "in":
        return None
    current = frame.scope[body[ind][1]]
    return None if current is None or current.kind == "snuval" else current.kind


def _leave(
    state: tuple[_Frame, _State], prog: _Program, value: _Value, *, gave: bool
) -> _State:
    """Return from the innermost call with ``value``, checked against its type."""
    frame, parent = state
    fn = prog.fns[frame.fn]
    if parent is None:
        if gave:
            raise HaltError("GIVE outside a function")
        return None
    if fn.returns != "snuval" and value.kind != fn.returns:
        raise HaltError(f"{fn.name!r} declares {fn.returns} but gave {value.kind}")
    return (parent[0]._replace(returned=value), parent[1])


def _push_call(
    state: tuple[_Frame, _State], prog: _Program, call: _Expr
) -> tuple[_Frame, _State]:
    """Start ``call``: select its overload and push its body as a frame."""
    frame = state[0]
    names = prog.fns[frame.fn].names
    # The arguments are call-free here: the innermost call is resolved first.
    values = [_eval(arg, frame.scope, names) for arg in call[2]]
    kinds = tuple(v.kind for v in values)
    index = prog.overloads.get((call[1], kinds))
    if index is None:
        raise HaltError(f"no overload of {call[1]!r} takes {list(kinds)}")
    fn = prog.fns[index]
    scope = (*values, *([None] * (len(fn.names) - len(values))))
    return (_Frame(index, scope, ((fn.body, 0),)), state)


def _simple(
    frame: _Frame, stmt: _Stmt, names: tuple[str, ...], byte: int | None
) -> tuple[_Frame, str | None]:
    """Run a body-less statement (OUT, bare call, IN, SET, assignment)."""
    kind, scope = stmt[0], frame.scope
    if kind == "out":
        return frame, _eval(stmt[1], scope, names).render()
    if kind == "call":
        _eval(stmt[1], scope, names)
        return frame, None
    current = scope[stmt[1]]
    if kind == "in":
        if current is None or current.kind == "snuval" or byte is None:
            raise HaltError(f"{names[stmt[1]]!r} has no type to read into")
        value = _Value(current.kind, byte)
    else:
        value = _eval(stmt[2], scope, names)
        if kind == "set":
            if current is not None:
                raise HaltError(f"{names[stmt[1]]!r} is already declared")
            if value.kind == "snuval":
                raise HaltError(f"SET {names[stmt[1]]!r} needs a typed initial value")
        elif current is None:
            raise HaltError(f"undeclared name {names[stmt[1]]!r}")
        elif value.kind != "snuval" and value.kind != current.kind:
            raise HaltError(
                f"{names[stmt[1]]!r} is {current.kind}, cannot take a {value.kind}"
            )
    return frame._replace(scope=_store(scope, stmt[1], value)), None


def _advance(
    state: _State, prog: _Program, byte: int | None = None
) -> tuple[_State, str | None]:
    """Return the state after one statement step, and the text to print.

    Pure: an ``IN`` arrives as ``byte`` (the shell reads it by the target's
    type); a statement holding calls takes one step per call.
    """
    if state is None:
        return None, None
    frame, parent = state
    fn = prog.fns[frame.fn]
    block, ind = frame.blocks[-1]
    body = prog.bodies[block]
    if ind >= len(body):
        if len(frame.blocks) > 1:
            return (frame._replace(blocks=frame.blocks[:-1]), parent), None
        # A body that runs out without GIVE returns the snuval.
        return _leave(state, prog, _SNUVAL, gave=False), None
    stmt = body[ind]
    kind = stmt[0]
    names = fn.names
    slot = _EXPR_SLOT.get(kind)
    if slot is not None:
        working: _Expr = frame.pending if frame.pending is not None else stmt[slot]
        if frame.returned is not None:
            done = _pending_call(working)
            if done is not None:  # pragma: no branch
                working = _substitute(working, done, frame.returned)
            frame = frame._replace(returned=None)
        call = _pending_call(working)
        if call is not None:
            frame = frame._replace(pending=working)
            return _push_call((frame, parent), prog, call), None
        frame = frame._replace(pending=None)
        parts = list(stmt)
        parts[slot] = working
        stmt = tuple(parts)

    cursor = (*frame.blocks[:-1], (block, ind + 1))
    out = None
    scope = frame.scope
    if kind == "if":
        taken = stmt[2] if _eval(stmt[1], scope, names).truthy() else stmt[3]
        frame = frame._replace(blocks=(*cursor, (taken, 0)))
    elif kind == "while":
        if _eval(stmt[1], scope, names).truthy():
            # The cursor stays on the WHILE, so the body's end re-tests it.
            frame = frame._replace(blocks=(*frame.blocks, (stmt[2], 0)))
        else:
            frame = frame._replace(blocks=cursor)
    elif kind == "give":
        return _leave(
            (frame, parent), prog, _eval(stmt[1], scope, names), gave=True
        ), None
    else:
        frame, out = _simple(frame._replace(blocks=cursor), stmt, names, byte)
    return (frame, parent), out


def _store(
    scope: tuple[_Value | None, ...], slot: int, value: _Value
) -> tuple[_Value | None, ...]:
    """``scope`` with ``slot`` replaced."""
    return (*scope[:slot], value, *scope[slot + 1 :])


def _parse(code: str) -> _Program:
    """Parse a whole program."""
    return _Parser(_split_lines(code)).parse()


def _wubyte_of(line: str) -> int:
    """A 1-3 digit decimal wubyte; empty or invalid or out of range is 0."""
    text = line.strip()
    if not text.isascii() or not text.isdigit() or len(text) > 3:
        return 0
    value = int(text)
    return value if value <= 255 else 0


class _Machine:
    """A DINAC run: the call stack as an immutable linked pair."""

    # ``ind`` is the innermost block's statement cursor, not a character.
    ip_shape = "opaque"

    #: The page gives running out no value; \0 / 00 lets its cat end.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.prog = _parse(code)
        top = self.prog.fns[0]
        self.state: _State = (
            _Frame(0, (None,) * len(top.names), ((top.body, 0),)),
            None,
        )

    @property
    def halted(self) -> bool:
        return self.state is None

    @property
    def ind(self) -> int:
        """The innermost block's statement cursor."""
        return self.state[0].blocks[-1][1] if self.state else 0

    @property
    def memory(self) -> list[int]:
        """The top-level variables' codes, in order of first mention."""
        frame = self.state
        while frame is not None and frame[1] is not None:
            frame = frame[1]
        return [v.code for v in frame[0].scope if v] if frame else []

    @property
    def stack(self) -> list[object]:
        """The called functions' names, outermost first."""
        names: list[object] = []
        frame = self.state
        while frame is not None:
            names.append(self.prog.fns[frame[0].fn].name or "<top>")
            frame = frame[1]
        return names[::-1]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.state, self.io.progress())

    def _read(self, kind: _Kind) -> int:
        r"""Read the value an ``IN`` stores: \0 / 00 once input runs out."""
        try:
            if kind == "wubyte":
                return _wubyte_of(self.io.input_str())
            code = self.io.input_char()
        except EOFError:
            return 0
        return code if code < 128 else 0

    def step(self) -> None:
        """Execute one statement step; the reads and the write happen here."""
        if self.halted:
            return
        kind = _wanted_read(self.state, self.prog)
        byte = None if kind is None else self._read(kind)
        self.state, out = _advance(self.state, self.prog, byte)
        if out is not None:
            self.io.print_str(out)


def run(code: str, io: IO) -> None:
    """Run a DINAC program until its top level ends."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
