r"""Interpreter for Q-BAL: queues of numbers, functions and a queued program counter.

A program is one statement per line; blank lines and comments (from a
backquote to the end of the line) are not lines.  The program counter
``;`` is a queue holding a line number, ``{1}`` at the start: each step runs
the statement at the top of ``;``, then the end-of-line statement
``;+1 -> ;``.  The run halts once ``;`` is empty or its top is past the
last line.  ``F name`` through a lone ``F`` declares a function whose body
has its own line numbers and sub-program counter.  Attaching to ``f``
appends to its input queue and runs its body in a new frame after the
current line finishes; inside it ``in``, ``out`` and ``;`` are the
function's own queues and other names fall back to the main program's.  It
returns when its ``;`` empties or passes its end.  As a source, ``f`` is its
output queue.

Commands:
    ``Q x`` / ``QQ x`` / ``F f``    declare (re-executing resets); ``Q x = src``
                                    initializes as ``x = src`` would
    ``src -> dst`` / ``dst <- src`` attach: evaluate ``src``, popping each
                                    queue it names left to right, and append
                                    the value to ``dst``
    ``dst = src``                   assign: replace ``dst`` by a copy of ``src``
    ``x ->`` / ``-> f`` / ``x =``   null sides: drop x's top, run f, erase x

    Operators, loosest first: ``== != < > <= =< >= =>``, ``-``, ``+``,
    ``|`` (remainder), ``/``, ``\`` (product), ``^``; prefix ``!``.  Literals:
    ``12``, ``{1,4,9}``, ``"text"`` (its character codes).  Prefixes: ``*x``
    peeks, ``#x`` counts, ``:x`` names the main program's ``x`` from inside a
    function, ``&f``/``@f`` reach f's input/output queue without running it,
    ``$y`` moves a whole queue and ``*$y`` copies one.

Input/output:
    ``in`` reads one line holding a signed decimal integer; ``'in`` reads one
    character as its code, and ``x = 'in`` a line as a queue of codes.
    ``v -> out`` prints ``v`` in decimal and a newline; ``v -> 'out`` prints
    the character; a whole queue sent to ``'out`` (``'out = x``,
    ``$x -> 'out``) prints its characters and a newline.

Errors:
    ProgramError: a malformed statement, an unterminated or nested ``F``
    block, or a construct the page names but never exercises (see
    Decisions); raised as ValueError.
    InputExhaustedError: a read of ``in`` or ``'in`` at EOF; raised as
    EOFError.
    ArgumentError: an ``in`` line that is not a decimal integer.
    HaltError: an undeclared name, an empty queue in arithmetic, a value of
    the wrong queue type, division or remainder by zero, a negative
    exponent, writing to ``in``, reading ``out``, a line number below 1, or
    a non-character sent to ``'out``.

Decisions:
    * Declarations are lines: the queue-of-queues example's ``; - 3`` on
      line 5 returns to ``y = 'in``, line 3, after ``QQ x`` and ``Q y``.  A
      function block is one line of the program it sits in.
    * The order of operations is taken literally, "^ \ / | + -", one level
      each, so ``a - b + c`` is ``a - (b + c)``; equal operators group left.
      Comparisons bind loosest, as the relative-branch examples parenthesize
      ``(x != 0)``; ``!`` binds as a prefix.
    * ``/`` and ``|`` truncate toward zero; integers are unbounded.
    * A bare queue source that is empty attaches nothing ("the null queue
      ... is considered to have no elements"); inside arithmetic it raises.
    * EOF raises, as the page gives stdin no end value.
    * The queue-of-queues example prints each string "followed by a blank
      line", so a whole queue sent to ``'out`` ends its line.
    * Execution ends as soon as the main ``;`` is empty, even inside a
      function (":; -> is required to end execution").
    * ``'in`` and ``'out`` stay stdin and stdout inside a function; the page
      redirects only ``in`` and ``out``.
    * Raised as never exercised: directives (``.I`` needs a filesystem,
      ``.M`` and ``.P`` leave their reach unstated), the instruction queue
      (``~``, ``[...]``, ``code``), variable I/O (``?``, ``FILE``,
      ``ALLOC``), types other than Q, QQ and F, ``%``, function assignment,
      ``&``/``@`` on queues, ``#`` of stdin and multi-number ``in``/``out``
      assignment.
"""

import re
from collections import deque
from collections.abc import Mapping
from typing import Any, NamedTuple, cast

from esolangs.exceptions import ArgumentError, HaltError, ProgramError
from esolangs.languages.q_bal.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._input_retry import RejectedInput
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import format_integer, parse_integer, repr_value
from esolangs.runtime.source_hints import syntax_error

_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+)|(?P<str>\"[^\"]*\")|(?P<lit>\{[^}]*\})"
    r"|(?P<name>'?[A-Za-z_]\w*)"
    r"|(?P<op>->|<-|==|!=|<=|=<|>=|=>|[=<>!+\-/\\|^()*#:&@$;]))"
)
_DECL = re.compile(r"([QFX]+)\s+([A-Za-z_]\w*)\s*(?:=(.*))?")
_NUMBER = re.compile(r"[+-]?\d+")
#: Binary precedence, tightest highest: the page's "^ \ / | + -", then logic.
_PREC = {"^": 7, "\\": 6, "/": 5, "|": 4, "+": 3, "-": 2}
_PREC.update(dict.fromkeys(("==", "!=", "<", ">", "<=", "=<", ">=", "=>"), 1))
_PREFIXES = frozenset({"", "*", "#", "&", "@", "$", "*$"})
_UNSUPPORTED = {
    "~": "the instruction queue",
    "[": "the instruction queue",
    "?": "variable I/O",
    "%": "the diminish operator",
}
_RESERVED = {
    "code": "the instruction queue",
    "FILE": "variable I/O",
    "ALLOC": "variable I/O",
    "DELETE": "variable I/O",
}


class _Ref(NamedTuple):
    """A queue or function name, its ``:`` level and its other prefixes."""

    name: str  # a user name, ``in``, ``out``, ``'in``, ``'out`` or ``;``
    level: int
    prefix: str


class _Lit(NamedTuple):
    """A literal queue or string."""

    items: tuple[int, ...]


#: Postfix: a number, a literal, a reference, or an operator name.
type _Item = int | _Lit | _Ref | str
type _Expr = tuple[_Item, ...]


class _Stmt(NamedTuple):
    """A parsed statement; ``src``/``dst`` are None on a null side."""

    kind: str  # "decl", "attach" or "assign"
    src: "_Expr | _Ref | _Lit | None" = None
    dst: _Ref | None = None
    typ: str = ""
    name: str = ""
    body: int = -1


class _Func(NamedTuple):
    """A declared function: its input and output queue ids and its body."""

    inp: int
    out: int
    body: int


class _Queue(NamedTuple):
    """A declared queue: its type (``Q`` or ``QQ``) and heap id."""

    typ: str
    qid: int


class _Frame(NamedTuple):
    """A running body: its program counter's id, function and locals."""

    body: int
    pc: int
    func: _Func | None
    names: dict[str, "_Queue | _Func"]


class _Effect(NamedTuple):
    """What one statement does, for the machine to apply in order."""

    pops: tuple[tuple[int, int], ...]  # (queue id, count) from the top
    used: int  # stdin entries consumed
    sets: tuple[tuple[int, tuple[object, ...]], ...]  # assignments
    pushes: tuple[tuple[int, object], ...]  # appends, after the pops
    out: str
    declare: tuple[str, str, tuple[object, ...]] | None  # name, type, items
    call: _Func | None


class _NeedInputError(Exception):
    """The statement reads past the buffered stdin: fetch one ``kind``."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def _bad(text: str, hint: str) -> ValueError:
    return syntax_error(f"cannot parse {text!r}", hint, error_type=ProgramError)


def _unsupported(what: str) -> ValueError:
    return syntax_error(
        f"{what} is not implemented",
        "the page names it but no example exercises it",
        error_type=ProgramError,
    )


def _tokens(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos, end = 0, len(text.rstrip())
    while pos < end:
        m = _TOKEN.match(text, pos)
        if m is None or not m.lastgroup:
            ch = text[pos:].lstrip()[:1]
            if ch in _UNSUPPORTED:
                raise _unsupported(_UNSUPPORTED[ch])
            raise _bad(text, f"unexpected {ch!r}")
        kind, tok = m.lastgroup, m.group(m.lastgroup)
        if kind == "name":
            if tok in _RESERVED:
                raise _unsupported(_RESERVED[tok])
            if tok.startswith("'") and tok not in ("'in", "'out"):
                raise _bad(text, "only 'in and 'out take a quote")
        out.append((kind, tok))
        pos = m.end()
    return out


def _literal(kind: str, tok: str) -> _Lit:
    if kind == "str":
        return _Lit(tuple(map(ord, tok[1:-1])))
    inner = tok[1:-1].strip()
    parts = [p.strip() for p in inner.split(",")] if inner else []
    if not all(p.isdecimal() for p in parts):
        raise _bad(tok, "a literal queue holds numbers: {1,4,9}")
    return _Lit(tuple(map(parse_integer, parts)))


def _ref(toks: list[tuple[str, str]], pos: int, text: str) -> tuple[_Ref, int]:
    """Parse prefixes and a name from ``toks[pos]``; return it and the end."""
    prefix, level = "", 0
    while pos < len(toks) and toks[pos][1] in ("*", "#", ":", "&", "@", "$"):
        if toks[pos][1] == ":":
            level += 1
        else:
            prefix += toks[pos][1]
        pos += 1
    if pos >= len(toks) or not (toks[pos][0] == "name" or toks[pos][1] == ";"):
        raise _bad(text, "a prefix needs a name after it")
    if level > 1 or prefix not in _PREFIXES:
        raise _unsupported(f"the prefix {':' * level}{prefix}")
    return _Ref(toks[pos][1], level, prefix), pos + 1


def _expr(toks: list[tuple[str, str]], text: str) -> _Expr:
    """Shunting-yard to postfix, keeping operands in source (pop) order."""
    out: list[_Item] = []
    ops: list[str] = []
    want = True  # expecting an operand
    pos = 0
    while pos < len(toks):
        kind, tok = toks[pos]
        if want:
            if tok in ("!", "("):
                ops.append(tok)
                pos += 1
            elif kind == "num":
                out.append(parse_integer(tok))
                pos += 1
                want = False
            elif kind in ("str", "lit"):
                out.append(_literal(kind, tok))
                pos += 1
                want = False
            else:
                ref, pos = _ref(toks, pos, text)
                out.append(ref)
                want = False
        elif tok in _PREC:
            while (
                ops
                and ops[-1] != "("
                and (ops[-1] == "!" or _PREC[ops[-1]] >= _PREC[tok])
            ):
                out.append(ops.pop())
            ops.append(tok)
            pos += 1
            want = True
        elif tok == ")":
            while ops and ops[-1] != "(":
                out.append(ops.pop())
            if not ops:
                raise _bad(text, "unbalanced )")
            ops.pop()
            pos += 1
        else:
            raise _bad(text, f"expected an operator, got {tok!r}")
    if want:
        raise _bad(text, "an operator needs an operand after it")
    while ops:
        op = ops.pop()
        if op == "(":
            raise _bad(text, "unbalanced (")
        out.append(op)
    if len(out) > 1 and any(isinstance(i, _Ref) and "$" in i.prefix for i in out):
        raise _bad(text, "$ moves a whole queue, outside arithmetic")
    return tuple(out)


def _side(toks: list[tuple[str, str]], text: str) -> _Ref | None:
    """A destination: nothing, or one reference without arithmetic."""
    if not toks:
        return None
    ref, end = _ref(toks, 0, text)
    if end != len(toks):
        raise _bad(text, "a destination is one queue")
    return ref


def _source(toks: list[tuple[str, str]], text: str) -> _Ref | _Lit | None:
    """An assignment source: nothing, a literal, or a plain queue name."""
    if not toks:
        return None
    if len(toks) == 1 and toks[0][0] in ("str", "lit"):
        return _literal(*toks[0])
    ref = _side(toks, text)
    assert ref is not None
    if ref.prefix:
        raise _unsupported(f"the prefix {ref.prefix} in an assignment")
    return ref


def _statement(text: str, body: int = -1) -> _Stmt:
    if m := _DECL.fullmatch(text):
        typ, name, init = m.groups()
        if typ not in ("Q", "QQ", "F"):
            raise _unsupported(f"the type {typ}")
        if name in ("in", "out") or name in _RESERVED:
            raise _bad(text, f"{name} is predefined")
        if typ == "F":
            if init is not None:
                raise _bad(text, "a function's code follows on its own lines")
            return _Stmt("decl", typ=typ, name=name, body=body)
        src = None if init is None else _source(_tokens(init), text)
        return _Stmt("decl", src, typ=typ, name=name)
    toks = _tokens(text)
    depth, arrows, equals = 0, [], []
    for i, (_, tok) in enumerate(toks):
        depth += (tok == "(") - (tok == ")")
        if depth == 0 and tok in ("->", "<-"):
            arrows.append(i)
        elif depth == 0 and tok == "=":
            equals.append(i)
    if len(arrows) + len(equals) != 1:
        raise _bad(text, "a statement is one attachment (->, <-) or assignment (=)")
    at = (arrows or equals)[0]
    left, right = toks[:at], toks[at + 1 :]
    if equals:
        return _Stmt("assign", _source(right, text), _side(left, text))
    if toks[at][1] == "<-":
        left, right = right, left
    return _Stmt("attach", _expr(left, text) if left else None, _side(right, text))


def _parse(code: str) -> tuple[tuple[_Stmt, ...], ...]:
    """Split ``code`` into bodies: the main program first, then functions."""
    bodies: list[list[_Stmt]] = [[]]
    current = 0
    for raw in code.replace("\r\n", "\n").split("\n"):
        line = raw.split("`", 1)[0].strip()
        if not line:
            continue
        if line.startswith("."):
            raise _unsupported(f"the directive {line[:2]}")
        if line == "F":
            if current == 0:
                raise _bad(line, "a lone F closes a function block")
            current = 0
            continue
        m = _DECL.fullmatch(line)
        if m and m.group(1) == "F":
            if current:
                raise _unsupported("a function declared inside a function")
            bodies.append([])
            bodies[0].append(_statement(line, len(bodies) - 1))
            current = len(bodies) - 1
            continue
        bodies[current].append(_statement(line))
    if current:
        raise _bad(code, "close each function with a line holding F")
    return tuple(map(tuple, bodies))


class _Eval:
    """One statement's reads: queue offsets popped so far and stdin used."""

    def __init__(
        self,
        frame: _Frame,
        main: Mapping[str, _Queue | _Func],
        heap: Mapping[int, deque[object]],
        inbox: tuple[tuple[str, object], ...],
        main_pc: int,
    ) -> None:
        self.frame, self.main, self.heap, self.inbox = frame, main, heap, inbox
        self.main_pc = main_pc
        self.offsets: dict[int, int] = {}
        self.used = 0

    def resolve(self, ref: _Ref) -> tuple[str, object]:
        """Return ``(kind, target)``: a queue, a function or a stdio port."""
        inside = self.frame.func is not None and ref.level == 0
        if ref.level and self.frame.func is None:
            raise HaltError(f":{ref.name} is used outside a function")
        name = ref.name
        if name == ";":
            return "Q", (self.frame.pc if ref.level == 0 else self.main_pc)
        if name in ("in", "out"):
            if inside:
                assert self.frame.func is not None
                return "Q", getattr(self.frame.func, "inp" if name == "in" else "out")
            return name, None
        if name in ("'in", "'out"):
            return name, None
        obj = self.frame.names.get(name) if inside else None
        if obj is None:
            obj = self.main.get(name)
        if obj is None:
            raise HaltError(f"{name} is used before it is declared")
        if isinstance(obj, _Func):
            return "F", obj
        return obj.typ, obj.qid

    def queue(self, ref: _Ref) -> tuple[str, int]:
        """Resolve ``ref`` to a queue, mapping & and @ onto a function's."""
        kind, target = self.resolve(ref)
        if kind == "F":
            assert isinstance(target, _Func)
            return "Q", target.inp if "&" in ref.prefix else target.out
        if "&" in ref.prefix or "@" in ref.prefix:
            raise _unsupported("& and @ on a queue")
        if kind in ("in", "'in", "out", "'out"):
            return kind, -1
        assert isinstance(target, int)
        return kind, target

    def stdin(self, kind: str, *, peek: bool) -> object:
        if self.used >= len(self.inbox):
            raise _NeedInputError(kind)
        got_kind, value = self.inbox[self.used]
        if got_kind != kind:
            raise HaltError("a peeked input is read as another kind")
        if not peek:
            self.used += 1
        return value

    def take(self, ref: _Ref, *, peek: bool) -> object | None:
        """Pop (or peek) ``ref``'s top; None when the queue is empty."""
        kind, qid = self.queue(ref)
        if kind == "in":
            return self.stdin("num", peek=peek)
        if kind == "'in":
            return self.stdin("char", peek=peek)
        if kind in ("out", "'out"):
            raise HaltError(f"{ref.name} can only be a destination")
        at = self.offsets.get(qid, 0)
        q = self.heap[qid]
        if at >= len(q):
            return None
        if not peek:
            self.offsets[qid] = at + 1
        return q[at]

    def count(self, ref: _Ref) -> int:
        kind, qid = self.queue(ref)
        if kind in ("in", "'in"):
            raise _unsupported("# of stdin")
        if kind in ("out", "'out"):
            raise HaltError(f"{ref.name} can only be a destination")
        return len(self.heap[qid]) - self.offsets.get(qid, 0)

    def value(self, item: _Item) -> int:
        if isinstance(item, int):
            return item
        if isinstance(item, _Lit):
            if not item.items:
                raise HaltError("an empty literal in arithmetic")
            return item.items[0]
        assert isinstance(item, _Ref)
        if item.prefix == "#":
            return self.count(item)
        got = self.take(item, peek=item.prefix == "*")
        if got is None:
            raise HaltError(f"{item.name} is empty in arithmetic")
        if not isinstance(got, int):
            raise HaltError(f"{item.name} holds queues, not numbers")
        return got

    def arithmetic(self, expr: _Expr) -> int:
        stack: list[int] = []
        for item in expr:
            if not isinstance(item, str):
                stack.append(self.value(item))
            elif item == "!":
                stack.append(int(not stack.pop()))
            else:
                b, a = stack.pop(), stack.pop()
                stack.append(_apply(item, a, b))
        return stack[0]

    def items(self, ref: _Ref) -> tuple[str, tuple[object, ...]]:
        """A whole queue's type and items, without popping."""
        kind, qid = self.queue(ref)
        if kind == "'in":
            line = self.stdin("line", peek=False)
            assert isinstance(line, tuple)
            return "Q", line
        if kind == "in":
            raise _unsupported("multi-number input by assignment")
        if kind in ("out", "'out"):
            raise HaltError(f"{ref.name} can only be a destination")
        return kind, tuple(self.heap[qid])[self.offsets.get(qid, 0) :]


def _apply(op: str, a: int, b: int) -> int:
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "\\":
        return a * b
    if op in ("/", "|"):
        if b == 0:
            raise HaltError(f"{format_integer(a)} {op} 0 divides by zero")
        q = abs(a) // abs(b) * (1 if (a < 0) == (b < 0) else -1)
        return q if op == "/" else a - b * q
    if op == "^":
        if b < 0:
            raise HaltError(
                f"{format_integer(a)} ^ {format_integer(b)} is not an integer"
            )
        return int(a**b)
    return int(
        {
            "==": a == b,
            "!=": a != b,
            "<": a < b,
            ">": a > b,
            "<=": a <= b,
            "=<": a <= b,
            ">=": a >= b,
            "=>": a >= b,
        }[op]
    )


def _text(codes: tuple[object, ...]) -> str:
    chars = []
    for code in codes:
        if not isinstance(code, int) or not 0 <= code <= 0x10FFFF:
            number = repr_value(code, format_large_int=format_integer)
            raise HaltError(f"{number} is not a character code")
        chars.append(chr(code))
    return "".join(chars)


def _advance(
    stmt: _Stmt,
    frame: _Frame,
    main: Mapping[str, _Queue | _Func],
    heap: Mapping[int, deque[object]],
    inbox: tuple[tuple[str, object], ...],
    main_pc: int,
) -> _Effect:
    """Return one statement's effects; the end-of-line statement is the shell's.

    Pure: stdin arrives buffered in ``inbox``; reading past it raises
    ``_NeedInputError`` for the shell to fetch one entry and call again.
    """
    ev = _Eval(frame, main, heap, inbox, main_pc)
    sets: list[tuple[int, tuple[object, ...]]] = []
    pushes: list[tuple[int, object]] = []
    out, declare, call = "", None, None
    if stmt.kind == "decl":
        items: tuple[object, ...] = ()
        if stmt.src is not None:
            typ, items = _assigned(ev, stmt.src)  # type: ignore[arg-type]
            if typ != stmt.typ:
                raise HaltError(f"a {stmt.typ} cannot hold a {typ}")
        declare = (stmt.name, stmt.typ, items)
    elif stmt.kind == "assign":
        typ, items = (
            ("", ()) if stmt.src is None else _assigned(ev, stmt.src)  # type: ignore[arg-type]
        )
        if stmt.dst is not None:
            kind, qid = _destination(ev, stmt.dst, assign=True)
            if kind == "'out":
                if typ not in ("Q", ""):
                    raise HaltError("'out prints a queue of numbers")
                out = _text(items) + "\n"
            else:
                if typ and typ != kind:
                    raise HaltError(f"a {kind} cannot hold a {typ}")
                sets.append((qid, items))
    else:
        out, call = _attach(ev, stmt, pushes)
    pops = tuple(ev.offsets.items())
    return _Effect(pops, ev.used, tuple(sets), tuple(pushes), out, declare, call)


def _assigned(ev: _Eval, src: _Ref | _Lit) -> tuple[str, tuple[object, ...]]:
    if isinstance(src, _Lit):
        return "Q", src.items
    if ev.resolve(src)[0] == "F":
        raise _unsupported("function assignment")
    return ev.items(src)


def _destination(ev: _Eval, dst: _Ref, *, assign: bool) -> tuple[str, int]:
    kind, target = ev.resolve(dst)
    if kind == "F":
        if assign:
            raise _unsupported("function assignment")
        assert isinstance(target, _Func)
        return "Q", target.out if "@" in dst.prefix else target.inp
    if kind in ("in", "'in"):
        raise HaltError(f"{dst.name} can only be a source")
    if kind == "out" and assign:
        raise _unsupported("multi-number output by assignment")
    if dst.prefix:
        if "&" in dst.prefix or "@" in dst.prefix:
            raise _unsupported("& and @ on a queue")
        raise _bad(dst.name, "a destination takes no * # or $")
    return kind, (target if isinstance(target, int) else -1)


def _attach_source(ev: _Eval, src: _Expr | None) -> tuple[list[object], str, bool]:
    """Return the values an attachment moves, their queue type, and if whole."""
    if src is None:
        return [], "Q", False
    if len(src) != 1 or not isinstance(item := src[0], (_Ref, _Lit)):
        return [ev.arithmetic(src)], "Q", False
    if isinstance(item, _Lit):
        return list(item.items[:1]), "Q", False
    if "$" in item.prefix:
        typ, items = ev.items(item)
        if typ == "QQ":  # one queue of the queue of queues
            items = items[:1]
        if item.prefix == "$":  # the move empties the source
            _, qid = ev.queue(item)
            if qid >= 0:
                ev.offsets[qid] = ev.offsets.get(qid, 0) + len(items)
        return list(items), typ, True
    if item.prefix == "#":
        return [ev.count(item)], "Q", False
    kind = ev.queue(item)[0]
    got = ev.take(item, peek=item.prefix == "*")
    return [] if got is None else [got], "Q" if kind in ("in", "'in") else kind, False


def _attach(
    ev: _Eval, stmt: _Stmt, pushes: list[tuple[int, object]]
) -> tuple[str, _Func | None]:
    """Evaluate an attachment's source, then deliver it; return output and call."""
    src, dst = stmt.src, stmt.dst
    assert src is None or (isinstance(src, tuple) and not isinstance(src, _Lit))
    values, typ, whole = _attach_source(ev, src)
    if dst is None:
        return "", None
    kind, qid = _destination(ev, dst, assign=False)
    target = ev.resolve(dst)[1]
    call = target if isinstance(target, _Func) and not dst.prefix else None
    if kind == "out":
        if whole or any(not isinstance(v, int) for v in values):
            raise HaltError("out prints numbers")
        return "".join(f"{format_integer(v)}\n" for v in cast(list[int], values)), call
    if kind == "'out":
        if whole and typ == "QQ":
            return "".join(_text(v) + "\n" for v in values), call  # type: ignore[arg-type]
        return _text(tuple(values)) + "\n" * whole, call
    if whole and typ == "Q" and kind == "QQ":
        values = [tuple(values)]
    elif typ != kind and (whole or values):
        raise HaltError(f"a {kind} cannot take an element of a {typ}")
    pushes.extend((qid, v) for v in values)
    return "", call


_WORKSPACE_MODEL = WorkspaceModel(
    "q-bal-v1", ("frames", "names", "queues", "stdin_buffer", "input_cursor")
)


class _Machine:
    """A Q-BAL run: frames, declared names, the queue heap and buffered stdin."""

    ip_shape = "line"

    def __init__(self, code: str | tuple[tuple[_Stmt, ...], ...], io: IO) -> None:
        self.bodies = _parse(code) if isinstance(code, str) else code
        self.io = io
        self.heap: dict[int, deque[object]] = {0: deque([1])}
        self.main: dict[str, _Queue | _Func] = {}
        self.frames: list[_Frame] = [_Frame(0, 0, None, self.main)]
        self.inbox: deque[tuple[str, object]] = deque()
        self._next = 1
        self._writer = _BufferedOutput()
        self._rejected = RejectedInput()

    @property
    def halted(self) -> bool:
        pc = self.heap[0]
        if not pc:
            return True
        top = pc[0]
        return (
            len(self.frames) == 1 and isinstance(top, int) and top > len(self.bodies[0])
        )

    @property
    def ind(self) -> int:
        """The current body's next line, counting from 0."""
        pc = self.heap[self.frames[-1].pc]
        return pc[0] - 1 if pc and isinstance(pc[0], int) else 0

    def _queues(self) -> tuple[tuple[int, tuple[object, ...]], ...]:
        return tuple((k, tuple(v)) for k, v in sorted(self.heap.items()))

    def _frames(self) -> tuple[object, ...]:
        return tuple(
            (f.body, f.pc, f.func, tuple(sorted(f.names.items())) if f.func else ())
            for f in self.frames
        )

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of cycle grouping."""
        accepted = self._writer.accepted
        frames = self._frames()
        return _WORKSPACE_MODEL.capture(
            frames=(
                WorkspaceVariant("pending_output", (frames, accepted))
                if accepted
                else frames
            ),
            names=frozenset(self.main.items()),
            queues=self._queues(),
            stdin_buffer=tuple(self.inbox),
            input_cursor=self._rejected.cursor(self.io.progress()),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        boundary = self._rejected.snapshot(
            (
                self._frames(),
                tuple(sorted(self.main.items())),
                self._queues(),
                tuple(self.inbox),
                self.io.progress(),
            )
        )
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def _read(self, kind: str) -> tuple[str, object]:
        if kind == "char":
            return kind, self.io.input_char()
        raw = self._rejected.read(self.io, self.io.input_str).removesuffix("\r")
        if kind == "line":
            return kind, tuple(map(ord, raw))
        if _NUMBER.fullmatch(raw.strip()):
            return kind, parse_integer(raw)
        error = ArgumentError(f"in input {raw!r} is not a decimal integer")
        self._rejected.remember(error)
        raise error

    def _alloc(self, items: tuple[object, ...] = ()) -> int:
        qid = self._next
        self._next += 1
        self.heap[qid] = deque(items)
        return qid

    def _declare(
        self, frame: _Frame, body: int, name: str, typ: str, items: tuple[object, ...]
    ) -> None:
        """Bind ``name`` afresh, reusing its old queues when the kind matches."""
        old = frame.names.get(name)
        if typ == "F":
            if isinstance(old, _Func):
                self.heap[old.inp], self.heap[old.out] = deque(), deque()
                frame.names[name] = old._replace(body=body)
                return
            frame.names[name] = _Func(self._alloc(), self._alloc(), body)
        elif isinstance(old, _Queue):
            self.heap[old.qid] = deque(items)
            frame.names[name] = _Queue(typ, old.qid)
            return
        else:
            frame.names[name] = _Queue(typ, self._alloc(items))
        if isinstance(old, _Queue):
            del self.heap[old.qid]
        elif isinstance(old, _Func) and all(f.func != old for f in self.frames):
            del self.heap[old.inp], self.heap[old.out]

    def step(self) -> None:
        """Run the statement at the top of the current ``;``, then ``;+1 -> ;``."""
        if self.halted:
            return
        frame = self.frames[-1]
        line = self.heap[frame.pc][0]
        assert isinstance(line, int)
        if line < 1:
            raise HaltError(
                f"line {format_integer(line)} does not exist; lines count from 1"
            )
        stmt = self.bodies[frame.body][line - 1]
        while True:
            try:
                effect = _advance(
                    stmt, frame, self.main, self.heap, tuple(self.inbox), 0
                )
                break
            except _NeedInputError as need:
                self.inbox.append(self._read(need.kind))
        # A partial write retries the statement against the same input and queues.
        if effect.out:
            self._writer.write(self.io, effect.out)
        for _ in range(effect.used):
            self.inbox.popleft()
        for qid, count in effect.pops:
            q = self.heap[qid]
            for _ in range(count):
                q.popleft()
        for qid, items in effect.sets:
            self.heap[qid] = deque(items)
        for qid, value in effect.pushes:
            self.heap[qid].append(value)
        if effect.declare is not None:
            self._declare(frame, stmt.body, *effect.declare)
        pc = self.heap[frame.pc]
        if pc:
            top = pc.popleft()
            if not isinstance(top, int):
                raise HaltError("the program counter holds a non-number")
            pc.append(top + 1)
        if effect.call is not None:
            body = effect.call.body
            self.frames.append(_Frame(body, self._alloc((1,)), effect.call, {}))
        while len(self.frames) > 1:
            top_frame = self.frames[-1]
            pc = self.heap[top_frame.pc]
            if pc and pc[0] <= len(self.bodies[top_frame.body]):  # type: ignore[operator]
                break
            self.frames.pop()
            del self.heap[top_frame.pc]
            for obj in top_frame.names.values():
                if isinstance(obj, _Queue):
                    del self.heap[obj.qid]


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse once and allocate state per invocation."""
    if not isinstance(source, str):
        raise TypeError("Q-BAL machines require text source")
    if options:
        raise TypeError("Q-BAL machines accept no runtime options")
    bodies = _parse(source)
    return RuntimePlan(lambda io: _Machine(bodies, io), lambda io: _execute(bodies, io))


def _execute(code: str | tuple[tuple[_Stmt, ...], ...], io: IO) -> CompletionReport:
    """Run a Q-BAL program until its program counter empties or passes the end."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a Q-BAL program until its program counter empties or passes the end."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
