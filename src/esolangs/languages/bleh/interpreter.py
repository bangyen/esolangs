r"""Interpreter for Bleh.

Ashli Katt's 2024 lazy functional language over bitstrings.  A program is
functions, each a name, branches ``: patterns = expression`` and ``;``; the
run calls ``main`` with no arguments and ends when it returns.  A call tries
its function's branches in order and evaluates the first whose patterns all
match the arguments; none matching crashes.

Commands:
    Expressions: ``1011`` bits; ``"s"`` or ``'s'`` the UTF-8 bits of ``s``;
    ``x`` a variable; ``[a, b]`` concatenation; ``{a; b}`` each in turn,
    giving the last; ``f(a, b)`` a call, ``f a`` the call ``f(a)``.
    Patterns: a literal matches equal bits; ``_`` anything; ``x`` binds, or
    when bound matches its value; ``x[p, ...]`` and ``[p, ...]`` match the
    bits one each, binding the whole to ``x``; ``x..`` and ``..`` match any
    run (of arguments at the top, of bits inside brackets), at most one a
    level.
    ``^: std::io;`` imports ``io``; ``^: std::io = name;`` renames it.
    ``//`` and ``/* */`` are comments; ``::`` before a function is ignored.

Input/output:
    ``io::print`` writes its arguments' bits as UTF-8, ``io::debug`` as
    ``0``/``1`` characters or ``[]``; both return the empty bitstring.
    ``io::next()`` returns the next character's UTF-8 bits, empty at EOF;
    ``io::hasNext()`` returns ``1`` while a character is left, else ``0``.

Errors:
    ProgramError: a token or construct outside the grammar, a call to an
    undefined function, an unbound variable, a second function of one name,
    an import other than ``std::io``, and a program with no ``main``.
    HaltError: a call no branch matches, ``io::print`` of bits that are not
    UTF-8 bytes, and ``io::next`` or ``io::hasNext`` given an argument.

Decisions:
    * Call by need: an argument is evaluated once, when first forced, which
      is when a literal, bracket or repeated-variable pattern inspects it;
      ``_``, ``..`` and a first ``x`` bind without forcing, so the page's
      ``AND`` and ``OR`` short-circuit.  ``x..`` binds lazily too.
    * ``{a; b}`` forces each element in order, as statements; a block
      passed as an argument runs only if the argument is forced.
    * A string escape is one of ``\n \t \r \0 \\ \" \'``.
    * A qualified name with no argument (``io::next``) is refused: it is no
      variable, and the page writes every zero-argument call with ``()``.
    * Modules other than ``std::io`` are refused: one source has no other
      files to import.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


@dataclass(frozen=True, slots=True)
class _Bits:
    value: str


@dataclass(frozen=True, slots=True)
class _Ref:
    name: str


@dataclass(frozen=True, slots=True)
class _Join:
    parts: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True)
class _Seq:
    parts: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True)
class _Call:
    #: A function's name, or ``io.<builtin>``.
    func: str
    args: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True)
class _Slot:
    """A bound value in an expression's place: a lazy join's part."""

    val: _Val


@dataclass(frozen=True, slots=True)
class _Lazy:
    """An unforced ``x..`` binding: the arguments it spans, joined."""

    parts: tuple[_Val, ...]


type _Expr = _Bits | _Ref | _Join | _Seq | _Call | _Slot
#: A bound value: a heap address, known bits, or a lazy join.
type _Val = int | str | _Lazy


@dataclass(frozen=True, slots=True)
class _PLit:
    value: str


@dataclass(frozen=True, slots=True)
class _PAny:
    pass


@dataclass(frozen=True, slots=True)
class _PVar:
    name: str


@dataclass(frozen=True, slots=True)
class _PRest:
    name: str | None


@dataclass(frozen=True, slots=True)
class _PSplit:
    name: str | None
    subs: tuple[_Pattern, ...]


type _Pattern = _PLit | _PAny | _PVar | _PRest | _PSplit
#: One branch: its patterns and its expression.
type _Branch = tuple[tuple[_Pattern, ...], _Expr]
type _Funcs = Mapping[str, tuple[_Branch, ...]]

_BUILTINS = ("print", "debug", "next", "hasNext")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'"}
_TOKEN = re.compile(
    r"""\s+|//[^\n]*|/\*.*?\*/|(::|\.\.|[:=;,()\[\]{}^])|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\w+)|(.)""",
    re.S | re.A,
)


def _utf8_bits(text: str) -> str:
    return "".join(format(byte, "08b") for byte in text.encode())


def _string(token: str) -> str:
    """Return the bits of a quoted string token."""
    out, chars = [], iter(token[1:-1])
    for char in chars:
        if char == "\\":
            escaped = next(chars)
            if escaped not in _ESCAPES:
                raise syntax_error(
                    f"\\{escaped} is not a Bleh string escape",
                    "use \\n \\t \\r \\0 \\\\ \\\" or \\'",
                )
            char = _ESCAPES[escaped]
        out.append(char)
    return _utf8_bits("".join(out))


def _tokens(code: str) -> list[str]:
    out = []
    for match in _TOKEN.finditer(code):
        punct, string, word, stray = match.groups()
        if stray is not None:
            raise syntax_error(
                f"{stray!r} is not part of Bleh's syntax",
                "check for an unterminated string or /* comment",
            )
        token = punct or string or word
        if token:
            out.append(token)
    return out


def _is_bits(token: str) -> bool:
    return not token.strip("01")


def _is_name(token: str) -> bool:
    return bool(re.fullmatch(r"\w+", token, re.A)) and not _is_bits(token)


class _Parser:
    """Recursive descent: Bleh source nests only as deep as it is written."""

    def __init__(self, code: str) -> None:
        self.tokens = _tokens(code)
        self.pos = 0
        self.aliases: dict[str, str] = {}

    def peek(self, ahead: int = 0) -> str | None:
        at = self.pos + ahead
        return self.tokens[at] if at < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            want = repr(expected) if expected else "more source"
            raise syntax_error(
                f"Bleh expected {want}, got {token or 'the end'!r}",
                "write functions as `name: patterns = expression;`",
            )
        self.pos += 1
        return token

    def name(self) -> str:
        token = self.take()
        if not _is_name(token) or token == "_":
            raise syntax_error(
                f"{token!r} is not a Bleh name",
                "use letters, digits and _, not only 0s and 1s",
            )
        return token

    def program(self) -> dict[str, tuple[_Branch, ...]]:
        funcs: dict[str, tuple[_Branch, ...]] = {}
        while self.peek() is not None:
            if self.peek() == "^":
                self.imports()
                continue
            if self.peek() == "::":
                self.take()
            name = self.name()
            if name in funcs:
                raise syntax_error(
                    f"Bleh function {name!r} is defined twice", "merge its branches"
                )
            branches = []
            while self.peek() == ":":
                self.take()
                branches.append(self.branch())
            self.take(";")
            funcs[name] = tuple(branches)
        return funcs

    def imports(self) -> None:
        self.take("^")
        while self.peek() == ":":
            self.take()
            path = [self.name()]
            while self.peek() == "::":
                self.take()
                path.append(self.name())
            if path != ["std", "io"]:
                raise syntax_error(
                    f"Bleh module {'::'.join(path)!r} is unavailable",
                    "import std::io; a single source has no other modules",
                )
            alias = path[-1]
            if self.peek() == "=":
                self.take()
                alias = self.name()
            self.aliases[alias] = "io"
        self.take(";")

    def branch(self) -> _Branch:
        patterns = self.patterns("=")
        self.take("=")
        return patterns, self.expr()

    def patterns(self, end: str) -> tuple[_Pattern, ...]:
        out: list[_Pattern] = []
        while self.peek() != end:
            out.append(self.pattern())
            if self.peek() != end:
                self.take(",")
        if sum(isinstance(p, _PRest) for p in out) > 1:
            raise syntax_error(
                "two .. patterns at one Bleh pattern level are ambiguous",
                "keep at most one .. a level",
            )
        return tuple(out)

    def pattern(self) -> _Pattern:
        token = self.take()
        if token == "..":
            return _PRest(None)
        if token == "[":
            subs = self.patterns("]")
            self.take("]")
            return _PSplit(None, subs)
        if token[0] in "\"'":
            return _PLit(_string(token))
        if _is_bits(token):
            return _PLit(token)
        if token == "_":
            return _PAny()
        self.pos -= 1
        name = self.name()
        if self.peek() == "..":
            self.take()
            return _PRest(name)
        if self.peek() == "[":
            self.take()
            subs = self.patterns("]")
            self.take("]")
            return _PSplit(name, subs)
        return _PVar(name)

    def _starts_expr(self) -> bool:
        token = self.peek()
        return token is not None and (
            token in "[{" or token[0] in "\"'" or bool(re.match(r"\w", token, re.A))
        )

    def expr(self) -> _Expr:
        token = self.take()
        if token == "[":
            return _Join(self.items("]", ","))
        if token == "{":
            parts = self.items("}", ";")
            if not parts:
                raise syntax_error("Bleh {} needs an expression", "write {a; b}")
            return _Seq(parts)
        if token[0] in "\"'":
            return _Bits(_string(token))
        if _is_bits(token):
            return _Bits(token)
        self.pos -= 1
        func = self.name()
        qualified = self.peek() == "::"
        if qualified:
            self.take()
            func = f"{func}::{self.name()}"
        if self.peek() == "(":
            self.take()
            return _Call(func, self.items(")", ","))
        if self._starts_expr():
            return _Call(func, (self.expr(),))
        if qualified:
            raise syntax_error(
                f"Bleh {func} is a function, not a variable", f"call it: {func}()"
            )
        return _Ref(func)

    def items(self, end: str, sep: str) -> tuple[_Expr, ...]:
        out = []
        while self.peek() != end:
            out.append(self.expr())
            if self.peek() != end:
                self.take(sep)
        self.take(end)
        return tuple(out)


def _pattern_names(patterns: tuple[_Pattern, ...]) -> set[str]:
    names: set[str] = set()
    for p in patterns:
        if isinstance(p, (_PVar, _PRest, _PSplit)) and p.name:
            names.add(p.name)
        if isinstance(p, _PSplit):
            names |= _pattern_names(p.subs)
    return names


def _resolve(
    expr: _Expr, bound: set[str], funcs: Mapping[str, object], aliases: dict[str, str]
) -> _Expr:
    """Return ``expr`` with builtins resolved; check names and variables."""
    if isinstance(expr, _Ref):
        if expr.name not in bound:
            raise syntax_error(
                f"Bleh variable {expr.name!r} is not bound by its branch",
                "bind it in a pattern, or call a function with ()",
            )
        return expr
    if isinstance(expr, (_Bits, _Slot)):
        return expr
    parts = tuple(_resolve(p, bound, funcs, aliases) for p in _children(expr))
    if isinstance(expr, _Join):
        return _Join(parts)
    if isinstance(expr, _Seq):
        return _Seq(parts)
    module, _, name = expr.func.rpartition("::")
    if module:
        if aliases.get(module) != "io" or name not in _BUILTINS:
            raise syntax_error(
                f"Bleh has no function {expr.func!r}", "import std::io for io::print"
            )
        return _Call(f"io.{name}", parts)
    if name not in funcs:
        raise syntax_error(f"Bleh has no function {name!r}", "define it")
    return _Call(name, parts)


def _children(expr: _Expr) -> tuple[_Expr, ...]:
    if isinstance(expr, (_Join, _Seq)):
        return expr.parts
    assert isinstance(expr, _Call)
    return expr.args


def _parse(code: str) -> dict[str, tuple[_Branch, ...]]:
    parser = _Parser(code)
    if parser.peek() is None:
        raise syntax_error("a Bleh program needs a main function", "write main := ...;")
    funcs = parser.program()
    if "main" not in funcs:
        raise syntax_error("a Bleh program needs a main function", "write main := ...;")
    return {
        name: tuple(
            (patterns, _resolve(body, _pattern_names(patterns), funcs, parser.aliases))
            for patterns, body in branches
        )
        for name, branches in funcs.items()
    }


class _Need(Exception):  # noqa: N818 - a request, not an error
    """Matching needs the heap address ``at`` forced first."""

    def __init__(self, at: int) -> None:
        self.at = at


#: A branch's bindings, in binding order.
type _Env = tuple[tuple[str, _Val], ...]
#: A heap cell: bits once forced, else the expression and its bindings.
type _Cell = str | tuple[_Expr, _Env]
type _Heap = Mapping[int, _Cell]


def _lookup(env: _Env, name: str) -> _Val:
    return next(value for key, value in env if key == name)


def _value(val: _Val, heap: _Heap) -> str:
    """Return ``val``'s bits, raising :class:`_Need` for an unforced address."""
    if isinstance(val, str):
        return val
    if isinstance(val, _Lazy):
        return "".join(_value(part, heap) for part in val.parts)
    cell = heap[val]
    if isinstance(cell, str):
        return cell
    raise _Need(val)


def _align[T](
    patterns: tuple[_Pattern, ...], items: tuple[T, ...]
) -> (
    tuple[
        list[tuple[_Pattern, T]], _PRest | None, tuple[T, ...], list[tuple[_Pattern, T]]
    ]
    | None
):
    """Pair patterns with items around the one rest pattern and its run."""
    rest = next((i for i, p in enumerate(patterns) if isinstance(p, _PRest)), None)
    if rest is None:
        if len(patterns) != len(items):
            return None
        return list(zip(patterns, items, strict=True)), None, (), []
    tail = len(patterns) - rest - 1
    if len(items) < rest + tail:
        return None
    cut = len(items) - tail
    rest_pattern = patterns[rest]
    assert isinstance(rest_pattern, _PRest)
    return (
        list(zip(patterns[:rest], items[:rest], strict=True)),
        rest_pattern,
        items[rest:cut],
        list(zip(patterns[rest + 1 :], items[cut:], strict=True)),
    )


class _Matcher:
    """One branch's match, left to right, forcing values only on demand."""

    def __init__(self, heap: _Heap) -> None:
        self.heap = heap
        self.bound: dict[str, _Val] = {}

    def bind(self, name: str, val: _Val) -> bool:
        if name not in self.bound:
            self.bound[name] = val
            return True
        return _value(self.bound[name], self.heap) == _value(val, self.heap)

    def level[T: _Val](
        self,
        patterns: tuple[_Pattern, ...],
        items: tuple[T, ...],
        run: Callable[[tuple[T, ...]], _Val],
    ) -> bool:
        aligned = _align(patterns, items)
        if aligned is None:
            return False
        head, rest, span, tail = aligned
        if not all(self.one(p, item) for p, item in head):
            return False
        if rest is not None and rest.name and not self.bind(rest.name, run(span)):
            return False
        return all(self.one(p, item) for p, item in tail)

    def one(self, pattern: _Pattern, val: _Val) -> bool:
        if isinstance(pattern, _PAny):
            return True
        if isinstance(pattern, _PVar):
            return self.bind(pattern.name, val)
        bits = _value(val, self.heap)
        if isinstance(pattern, _PLit):
            return bits == pattern.value
        assert isinstance(pattern, _PSplit)
        if pattern.name and not self.bind(pattern.name, bits):
            return False
        return self.level(pattern.subs, tuple(bits), "".join)


def _match(
    patterns: tuple[_Pattern, ...], args: tuple[_Val, ...], heap: _Heap
) -> _Env | None:
    """Return the branch's bindings, None on a mismatch; may raise _Need."""
    matcher = _Matcher(heap)
    if not matcher.level(patterns, args, _Lazy):
        return None
    return tuple(matcher.bound.items())


@dataclass(frozen=True, slots=True)
class _Eval:
    expr: _Expr
    env: _Env


@dataclass(frozen=True, slots=True)
class _Ret:
    value: str


@dataclass(frozen=True, slots=True)
class _Try:
    """Match ``func``'s branch ``branch``; as a frame, retry it."""

    func: str
    args: tuple[_Val, ...]
    branch: int


@dataclass(frozen=True, slots=True)
class _Do:
    """Run a builtin: the shell's job, since it is IO."""

    builtin: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Update:
    at: int


@dataclass(frozen=True, slots=True)
class _Part:
    """Part ``at`` of a join or block is running; ``acc`` is the join so far."""

    expr: _Join | _Seq
    at: int
    env: _Env
    acc: str


@dataclass(frozen=True, slots=True)
class _Arg:
    """Argument ``at`` of a builtin is running; ``values`` precede it."""

    builtin: str
    args: tuple[_Expr, ...]
    at: int
    env: _Env
    values: tuple[str, ...]


type _Control = _Eval | _Ret | _Try | _Do
type _Frame = _Update | _Part | _Arg | _Try
#: Continuation frames, innermost first.
type _Kont = tuple[_Frame, _Kont] | None
#: Heap writes a transition makes: addresses and their new cells.
type _Writes = tuple[tuple[int, _Cell], ...]


class _State(NamedTuple):
    control: _Control
    kont: _Kont
    #: The next free heap address.
    fresh: int


def _force(at: int, heap: _Heap, kont: _Kont, fresh: int) -> _State:
    cell = heap[at]
    if isinstance(cell, str):
        return _State(_Ret(cell), kont, fresh)
    expr, env = cell
    return _State(_Eval(expr, env), (_Update(at), kont), fresh)


def _advance(state: _State, heap: _Heap, funcs: _Funcs) -> tuple[_State, _Writes]:
    """Return the state after one transition, and the heap writes it makes.

    Pure: ``heap`` is read, never written; a builtin is the shell's.
    """
    control, kont, fresh = state
    if isinstance(control, _Eval):
        return _eval(control.expr, control.env, heap, kont, fresh)
    if isinstance(control, _Ret):
        assert kont is not None
        if isinstance(kont[0], _Update):
            # A forced thunk keeps its bits: call by need.
            return _State(control, kont[1], fresh), ((kont[0].at, control.value),)
        return _return(control.value, kont, fresh), ()
    assert isinstance(control, _Try)
    branches = funcs[control.func]
    patterns, body = branches[control.branch]
    try:
        env = _match(patterns, control.args, heap)
    except _Need as need:
        return _force(need.at, heap, (control, kont), fresh), ()
    if env is not None:
        return _State(_Eval(body, env), kont, fresh), ()
    if control.branch + 1 == len(branches):
        raise HaltError(f"no branch of Bleh function {control.func} matches")
    retry = _Try(control.func, control.args, control.branch + 1)
    return _State(retry, kont, fresh), ()


def _eval(
    expr: _Expr, env: _Env, heap: _Heap, kont: _Kont, fresh: int
) -> tuple[_State, _Writes]:
    if isinstance(expr, _Ref):
        expr = _Slot(_lookup(env, expr.name))
    if isinstance(expr, _Slot):
        val = expr.val
        if isinstance(val, int):
            return _force(val, heap, kont, fresh), ()
        if isinstance(val, str):
            return _State(_Ret(val), kont, fresh), ()
        expr = _Join(tuple(_Slot(part) for part in val.parts))
    if isinstance(expr, _Bits):
        return _State(_Ret(expr.value), kont, fresh), ()
    if isinstance(expr, (_Join, _Seq)):
        if not expr.parts:
            return _State(_Ret(""), kont, fresh), ()
        return _part(expr, 0, env, "", kont, fresh), ()
    if expr.func.startswith("io."):
        builtin = expr.func[3:]
        if not expr.args:
            return _State(_Do(builtin, ()), kont, fresh), ()
        frame = _Arg(builtin, expr.args, 0, env, ())
        return _State(_Eval(expr.args[0], env), (frame, kont), fresh), ()
    args: list[_Val] = []
    writes: list[tuple[int, _Cell]] = []
    for arg in expr.args:
        if isinstance(arg, _Bits):
            args.append(arg.value)
        elif isinstance(arg, (_Ref, _Slot)):
            # A variable passes its binding on: the callee shares the thunk.
            args.append(_lookup(env, arg.name) if isinstance(arg, _Ref) else arg.val)
        else:
            writes.append((fresh, (arg, env)))
            args.append(fresh)
            fresh += 1
    return _State(_Try(expr.func, tuple(args), 0), kont, fresh), tuple(writes)


def _part(
    expr: _Join | _Seq, at: int, env: _Env, acc: str, kont: _Kont, fresh: int
) -> _State:
    """Start part ``at`` of a join or block; a block's last runs as a tail."""
    if isinstance(expr, _Seq) and at == len(expr.parts) - 1:
        return _State(_Eval(expr.parts[at], env), kont, fresh)
    frame = _Part(expr, at, env, acc)
    return _State(_Eval(expr.parts[at], env), (frame, kont), fresh)


def _return(value: str, kont: _Kont, fresh: int) -> _State:
    assert kont is not None
    frame, rest = kont
    if isinstance(frame, _Part):
        acc = frame.acc + value if isinstance(frame.expr, _Join) else ""
        if frame.at + 1 == len(frame.expr.parts):
            return _State(_Ret(acc), rest, fresh)
        return _part(frame.expr, frame.at + 1, frame.env, acc, rest, fresh)
    if isinstance(frame, _Arg):
        values = (*frame.values, value)
        if frame.at + 1 == len(frame.args):
            return _State(_Do(frame.builtin, values), rest, fresh)
        nxt = _Arg(frame.builtin, frame.args, frame.at + 1, frame.env, values)
        return _State(_Eval(frame.args[frame.at + 1], frame.env), (nxt, rest), fresh)
    assert isinstance(frame, _Try)  # ``_advance`` pops updates itself
    return _State(frame, rest, fresh)  # retry the branch


class _Machine:
    """The functions, the control and continuation, the heap, and lookahead."""

    #: A frame stack, not a place in the source; ``ip`` is its depth.
    ip_shape = "opaque"
    #: ``io::next()`` past EOF is the empty bitstring, not a raise.
    eof_is_a_value = True

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.funcs = _parse(code)
        self.state = _State(_Try("main", (), 0), None, 0)
        self.heap: dict[int, _Cell] = {}
        #: A character ``io::hasNext`` read ahead, ``""`` past EOF, or None.
        self.ahead: str | None = None

    @property
    def halted(self) -> bool:
        return self.state.kont is None and isinstance(self.state.control, _Ret)

    @property
    def ip(self) -> tuple[int, ...]:
        """The continuation's depth."""
        depth, kont = 0, self.state.kont
        while kont is not None:
            depth, kont = depth + 1, kont[1]
        return (depth,)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            *self.state,
            frozenset(self.heap.items()),
            self.ahead,
            self.io.progress(),
        )

    def _char(self) -> str:
        """Return the next input character, or ``""`` at EOF."""
        if self.ahead is not None:
            char = self.ahead
            self.ahead = None if char else ""
            return char
        try:
            return chr(self.io.input_char())
        except EOFError:
            self.ahead = ""
            return ""

    def _builtin(self, name: str, values: tuple[str, ...]) -> str:
        bits = "".join(values)
        if name in ("next", "hasNext") and values:
            raise HaltError(f"Bleh io::{name} takes no arguments")
        if name == "print":
            data = bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))
            try:
                if len(bits) % 8:
                    raise ValueError(len(bits))
                self.io.print_str(data.decode())
            except ValueError as exc:
                raise HaltError(f"Bleh io::print got non-UTF-8 bits {bits}") from exc
        elif name == "debug":
            self.io.print_str(bits or "[]")
        elif name == "next":
            return _utf8_bits(self._char())
        else:
            if self.ahead is None:
                self.ahead = self._char()
            return "1" if self.ahead else "0"
        return ""

    def step(self) -> None:
        if self.halted:
            return
        control = self.state.control
        if isinstance(control, _Do):
            value = self._builtin(control.builtin, control.values)
            self.state = self.state._replace(control=_Ret(value))
            return
        self.state, writes = _advance(self.state, self.heap, self.funcs)
        self.heap.update(writes)


def run(code: str, io: IO) -> None:
    """Run a Bleh program from its ``main``."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
