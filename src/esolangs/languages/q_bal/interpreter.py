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
    * A ``.P`` directive sets the end statement for following lines in its
      body. Functions inherit it at declaration and can override it locally.
    * Raised as never exercised: directives ``.I`` and ``.M``, variable I/O
      (``?``, ``FILE``, ``ALLOC``), types other than Q, QQ and F, ``%``,
      ``&``/``@`` on queues, ``#`` of stdin and multi-number ``in``/``out``
      assignment.
"""

import re
from collections import deque
from collections.abc import Mapping, Sequence
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
from esolangs.runtime._validate import require_text_source
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import format_integer, parse_integer, repr_value
from esolangs.runtime.source_hints import syntax_error

_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+)|(?P<str>\"[^\"]*\")|(?P<lit>\{[^}]*\})"
    r"|(?P<name>'?[A-Za-z_]\w*)"
    r"|(?P<op>->|<-|==|!=|<=|=<|>=|=>|[=<>!+\-/\\|^()*#:&@$;~\[\]]))"
)
_DECL = re.compile(r"([QFX]+)\s+([A-Za-z_]\w*)\s*(?:=(.*))?")
_NUMBER = re.compile(r"[+-]?\d+")
#: Binary precedence, tightest highest: the page's "^ \ / | + -", then logic.
_PREC = {"^": 7, "\\": 6, "/": 5, "|": 4, "+": 3, "-": 2}
_PREC.update(dict.fromkeys(("==", "!=", "<", ">", "<=", "=<", ">=", "=>"), 1))
_PREFIXES = frozenset({"", "*", "#", "&", "@", "$", "*$", "~", "*~", "#~", "$~", "*$~"})
_UNSUPPORTED = {
    "?": "variable I/O",
    "%": "the diminish operator",
}
_RESERVED = {
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
type _Item = int | _Lit | _Ref | _Stmt | str
type _Expr = tuple[_Item, ...]


class _Stmt(NamedTuple):
    """A parsed statement; ``src``/``dst`` are None on a null side."""

    kind: str  # "decl", "attach" or "assign"
    src: "_Expr | _Ref | _Lit | _Stmt | None" = None
    dst: _Ref | None = None
    typ: str = ""
    name: str = ""
    body: int = -1
    end: "_Stmt | None" = None


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
    function_copy: tuple[_Ref, _Func] | None = None


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
    brackets: list[int] = []
    while pos < end:
        m = _TOKEN.match(text, pos)
        if m is None or not m.lastgroup:
            ch = text[pos:].lstrip()[:1]
            if ch in _UNSUPPORTED:
                raise _unsupported(_UNSUPPORTED[ch])
            raise _bad(text, f"unexpected {ch!r}")
        kind, tok = m.lastgroup, m.group(m.lastgroup)
        if brackets or tok in ("[", "]"):
            if tok == "[":
                brackets.append(m.start(kind))
            elif tok == "]":
                if not brackets:
                    raise _bad(text, "unexpected ]")
                start = brackets.pop()
                if not brackets:
                    out.append(("stmt", text[start : m.end()]))
        else:
            if kind == "name":
                if tok in _RESERVED:
                    raise _unsupported(_RESERVED[tok])
                if tok.startswith("'") and tok not in ("'in", "'out"):
                    raise _bad(text, "only 'in and 'out take a quote")
            out.append((kind, tok))
        pos = m.end()
    if brackets:
        raise _bad(text, "close the bracketed statement")
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
    while pos < len(toks) and toks[pos][1] in ("*", "#", ":", "&", "@", "$", "~"):
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
            elif kind == "stmt":
                out.append(_quoted_statement(tok))
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


def _source(toks: list[tuple[str, str]], text: str) -> _Ref | _Lit | _Stmt | None:
    """An assignment source: nothing, a literal, or a plain queue name."""
    if not toks:
        return None
    if len(toks) == 1 and toks[0][0] in ("str", "lit"):
        return _literal(*toks[0])
    if len(toks) == 1 and toks[0][0] == "stmt":
        return _quoted_statement(toks[0][1])
    ref = _side(toks, text)
    assert ref is not None
    if ref.prefix not in ("", "~"):
        raise _unsupported(f"the prefix {ref.prefix} in an assignment")
    return ref


def _statement(text: str, body: int = -1) -> _Stmt:
    if m := _DECL.fullmatch(text):
        typ, name, init = m.groups()
        if typ not in ("Q", "QQ", "F"):
            raise _unsupported(f"the type {typ}")
        if name in ("in", "out", "code") or name in _RESERVED:
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


def _quoted_statement(text: str) -> _Stmt:
    stmt = _statement(text[1:-1].strip())
    if stmt.typ == "F":
        raise _bad(text, "a function block is not a single statement")
    return stmt


def _code_id(body: int) -> int:
    return -2 - body


def _parse(code: str) -> tuple[tuple[_Stmt, ...], ...]:
    """Split ``code`` into bodies: the main program first, then functions."""
    bodies: list[list[_Stmt]] = [[]]
    ends: list[_Stmt | None] = [None]
    current = 0
    for raw in code.replace("\r\n", "\n").split("\n"):
        line = raw.split("`", 1)[0].strip()
        if not line:
            continue
        if line.startswith("."):
            directive, *args = line.split(maxsplit=1)
            if directive != ".P":
                raise _unsupported(f"the directive {line[:2]}")
            if not args:
                raise _bad(line, ".P requires an end statement")
            end = _statement(args[0])
            if end.typ == "F":
                raise _bad(line, ".P cannot declare a function block")
            ends[current] = end
            continue
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
            ends.append(ends[0])
            stmt = _statement(line, len(bodies) - 1)
            bodies[0].append(stmt if ends[0] is None else stmt._replace(end=ends[0]))
            current = len(bodies) - 1
            continue
        stmt = _statement(line)
        current_end = ends[current]
        bodies[current].append(
            stmt if current_end is None else stmt._replace(end=current_end)
        )
    if current:
        raise _bad(code, "close each function with a line holding F")
    return tuple(map(tuple, bodies))


class _Eval:
    """One statement's reads: queue offsets popped so far and stdin used."""

    __slots__ = (
        "bodies",
        "frame",
        "heap",
        "inbox",
        "main",
        "main_pc",
        "offsets",
        "used",
    )

    def __init__(
        self,
        frame: _Frame,
        main: Mapping[str, _Queue | _Func],
        heap: Mapping[int, deque[object]],
        inbox: tuple[tuple[str, object], ...],
        main_pc: int,
        bodies: Mapping[int, Sequence[object]],
    ) -> None:
        self.frame, self.main, self.heap, self.inbox = frame, main, heap, inbox
        self.main_pc = main_pc
        self.bodies = bodies
        self.offsets: dict[int, int] = {}
        self.used = 0

    def resolve(self, ref: _Ref) -> tuple[str, object]:
        """Return ``(kind, target)``: a queue, a function or a stdio port."""
        inside = self.frame.func is not None and ref.level == 0
        if ref.level and self.frame.func is None:
            raise HaltError(f":{ref.name} is used outside a function")
        name = ref.name
        if "~" in ref.prefix and name in ("code", ";", "in", "out", "'in", "'out"):
            raise HaltError("~ requires a function")
        if name == "code":
            return "code", _code_id(self.frame.body if ref.level == 0 else 0)
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
            if "~" in ref.prefix:
                return "code", _code_id(obj.body)
            return "F", obj
        if "~" in ref.prefix:
            raise HaltError("~ requires a function")
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

    def contents(self, qid: int) -> Sequence[object]:
        if qid <= -2:
            return self.bodies[-2 - qid]
        # deque supports the size and index operations used here.
        return self.heap[qid]

    def take(
        self, ref: _Ref, *, peek: bool, queue: tuple[str, int] | None = None
    ) -> object | None:
        """Pop (or peek) ``ref``'s top; None when the queue is empty."""
        kind, qid = self.queue(ref) if queue is None else queue
        if kind == "in":
            return self.stdin("num", peek=peek)
        if kind == "'in":
            return self.stdin("char", peek=peek)
        if kind in ("out", "'out"):
            raise HaltError(f"{ref.name} can only be a destination")
        at = self.offsets.get(qid, 0)
        q = self.heap[qid] if qid >= 0 else self.bodies[-2 - qid]
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
        return len(self.contents(qid)) - self.offsets.get(qid, 0)

    def value(self, item: _Item) -> int:
        if isinstance(item, int):
            return item
        if isinstance(item, _Lit):
            if not item.items:
                raise HaltError("an empty literal in arithmetic")
            return item.items[0]
        if isinstance(item, _Stmt):
            raise HaltError("an instruction cannot be used in arithmetic")
        assert isinstance(item, _Ref)
        if item.prefix.startswith("#"):
            return self.count(item)
        got = self.take(item, peek=item.prefix.startswith("*"))
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
        return kind, tuple(self.contents(qid))[self.offsets.get(qid, 0) :]


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
    bodies: Mapping[int, Sequence[object]],
) -> _Effect:
    """Return one statement's effects; the end-of-line statement is the shell's.

    Pure: stdin arrives buffered in ``inbox``; reading past it raises
    ``_NeedInputError`` for the shell to fetch one entry and call again.
    """
    ev = _Eval(frame, main, heap, inbox, main_pc, bodies)
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
        return _assignment(ev, stmt)
    else:
        out, call = _attach(ev, stmt, pushes)
    pops = tuple(ev.offsets.items())
    return _Effect(pops, ev.used, (), tuple(pushes), out, declare, call)


def _assignment(ev: _Eval, stmt: _Stmt) -> _Effect:
    """Evaluate an assignment without changing its source."""
    src, dst = stmt.src, stmt.dst
    assert src is None or isinstance(src, (_Ref, _Lit, _Stmt))
    if isinstance(src, _Ref):
        _, origin = ev.resolve(src)
        if isinstance(origin, _Func):
            if dst is None:
                return _Effect((), 0, (), (), "", None, None)
            _, target = ev.resolve(dst)
            if not isinstance(target, _Func) or dst.prefix:
                raise HaltError("a function can only be assigned to a function")
            copies = (
                (target.inp, tuple(ev.heap[origin.inp])),
                (target.out, tuple(ev.heap[origin.out])),
            )
            copy = (dst, target._replace(body=origin.body))
            return _Effect((), 0, copies, (), "", None, None, copy)
    typ, items = ("", ()) if src is None else _assigned(ev, src)
    sets: tuple[tuple[int, tuple[object, ...]], ...] = ()
    out = ""
    if dst is not None:
        kind, qid = _destination(dst, ev.resolve(dst), assign=True)
        if kind == "'out":
            if typ not in ("Q", ""):
                raise HaltError("'out prints a queue of numbers")
            out = _text(items) + "\n"
        else:
            if typ and typ != kind:
                raise HaltError(f"a {kind} cannot hold a {typ}")
            sets = ((qid, items),)
    return _Effect(tuple(ev.offsets.items()), ev.used, sets, (), out, None, None)


def _assigned(ev: _Eval, src: _Ref | _Lit | _Stmt) -> tuple[str, tuple[object, ...]]:
    if isinstance(src, _Lit):
        return "Q", src.items
    if isinstance(src, _Stmt):
        return "code", (src,)
    if ev.resolve(src)[0] == "F":
        return "F", ()
    return ev.items(src)


def _destination(
    dst: _Ref, resolved: tuple[str, object], *, assign: bool
) -> tuple[str, int]:
    kind, target = resolved
    if kind == "F":
        if assign:
            raise HaltError("a function must be assigned another function")
        assert isinstance(target, _Func)
        return "Q", target.out if "@" in dst.prefix else target.inp
    if kind in ("in", "'in"):
        raise HaltError(f"{dst.name} can only be a source")
    if kind == "out" and assign:
        raise _unsupported("multi-number output by assignment")
    if dst.prefix and dst.prefix != "~":
        if "&" in dst.prefix or "@" in dst.prefix:
            raise _unsupported("& and @ on a queue")
        raise _bad(dst.name, "a destination takes no * # or $")
    return kind, (target if isinstance(target, int) else -1)


def _attach_source(ev: _Eval, src: _Expr | None) -> tuple[list[object], str, bool]:
    """Return the values an attachment moves, their queue type, and if whole."""
    if src is None:
        return [], "Q", False
    if len(src) != 1 or not isinstance(item := src[0], (_Ref, _Lit, _Stmt)):
        return [ev.arithmetic(src)], "Q", False
    if isinstance(item, _Lit):
        return list(item.items[:1]), "Q", False
    if isinstance(item, _Stmt):
        return [item], "code", False
    if "$" in item.prefix:
        typ, items = ev.items(item)
        if typ == "QQ":  # one queue of the queue of queues
            items = items[:1]
        if not item.prefix.startswith("*"):  # the move empties the source
            _, qid = ev.queue(item)
            if qid != -1:
                ev.offsets[qid] = ev.offsets.get(qid, 0) + len(items)
        return list(items), typ, True
    if item.prefix.startswith("#"):
        return [ev.count(item)], "Q", False
    queue = ev.queue(item)
    kind = queue[0]
    got = ev.take(item, peek=item.prefix.startswith("*"), queue=queue)
    return [] if got is None else [got], "Q" if kind in ("in", "'in") else kind, False


def _attach(
    ev: _Eval, stmt: _Stmt, pushes: list[tuple[int, object]]
) -> tuple[str, _Func | None]:
    """Evaluate an attachment's source, then deliver it; return output and call."""
    src, dst = stmt.src, stmt.dst
    assert src is None or (
        isinstance(src, tuple) and not isinstance(src, (_Lit, _Stmt))
    )
    values, typ, whole = _attach_source(ev, src)
    if dst is None:
        return "", None
    resolved = ev.resolve(dst)
    kind, qid = _destination(dst, resolved, assign=False)
    target = resolved[1]
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
        self.templates = _parse(code) if isinstance(code, str) else code
        self.bodies: dict[int, Sequence[object]] = dict(enumerate(self.templates))
        self._next_body = len(self.templates)
        self.io = io
        self.heap: dict[int, deque[object]] = {0: deque([1])}
        self.main: dict[str, _Queue | _Func] = {}
        self.frames: list[_Frame] = [_Frame(0, 0, None, self.main)]
        self.inbox: deque[tuple[str, object]] = deque()
        self._pending_ends: dict[int, tuple[int, _Stmt]] = {}
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
            len(self.frames) == 1
            and 0 not in self._pending_ends
            and isinstance(top, int)
            and top > len(self.bodies[0])
        )

    @property
    def ind(self) -> int:
        """The current body's next line, counting from 0."""
        qid = self.frames[-1].pc
        pending = self._pending_ends.get(qid)
        if pending is not None:
            return pending[0] - 1
        pc = self.heap[qid]
        return pc[0] - 1 if pc and isinstance(pc[0], int) else 0

    def _set_queue(self, qid: int, items: Sequence[object]) -> deque[object]:
        queue = deque(items)
        self.heap[qid] = queue
        if qid <= -2:
            self.bodies[-2 - qid] = queue
        return queue

    def _writable(self, qid: int) -> deque[object]:
        queue = self.heap.get(qid)
        if queue is None:
            queue = self._set_queue(qid, self.bodies[-2 - qid])
        return queue

    def _queues(self) -> tuple[tuple[int, tuple[object, ...]], ...]:
        return tuple((k, tuple(v)) for k, v in sorted(self.heap.items()))

    def _frames(self) -> tuple[object, ...]:
        return tuple(
            (
                f.body,
                f.pc,
                f.func,
                tuple(sorted(f.names.items())) if f.func else (),
                *((self._pending_ends[f.pc],) if f.pc in self._pending_ends else ()),
            )
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
        raw = self._rejected.read(self.io, self.io.input_str)
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

    def _discard_body(self, body: int) -> None:
        """Release an edited body once its last binding and active call are gone."""
        if _code_id(body) not in self.heap:
            return
        if any(frame.body == body for frame in self.frames) or any(
            isinstance(obj, _Func) and obj.body == body for obj in self.main.values()
        ):
            return
        del self.heap[_code_id(body)]
        if body >= len(self.templates):
            del self.bodies[body]
        else:
            self.bodies[body] = self.templates[body]

    def _declare(
        self, frame: _Frame, body: int, name: str, typ: str, items: tuple[object, ...]
    ) -> None:
        """Bind ``name`` afresh, reusing its old queues when the kind matches."""
        old = frame.names.get(name)
        if typ == "F":
            if frame.func is not None:
                raise HaltError("a function cannot declare another function")
            if self.heap.pop(_code_id(body), None) is not None:
                self.bodies[body] = self.templates[body]
            if isinstance(old, _Func):
                self.heap[old.inp], self.heap[old.out] = deque(), deque()
                frame.names[name] = old._replace(body=body)
                self._discard_body(old.body)
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
            self._discard_body(old.body)

    def _apply(self, frame: _Frame, stmt: _Stmt) -> _Func | None:
        """Commit one statement, preserving the input and output retry boundary."""
        while True:
            try:
                effect = _advance(
                    stmt, frame, self.main, self.heap, tuple(self.inbox), 0, self.bodies
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
            q = self.heap[qid] if qid >= 0 else self._writable(qid)
            for _ in range(count):
                q.popleft()
        for qid, items in effect.sets:
            self._set_queue(qid, items)
        for qid, value in effect.pushes:
            queue = self.heap[qid] if qid >= 0 else self._writable(qid)
            queue.append(value)
        if effect.declare is not None:
            self._declare(frame, stmt.body, *effect.declare)
        if effect.function_copy is not None:
            dst, function = effect.function_copy
            names = (
                frame.names if dst.level == 0 and dst.name in frame.names else self.main
            )
            old = names[dst.name]
            assert isinstance(old, _Func)
            if old.body != function.body:
                instructions = self.bodies[function.body]
                body = old.body
                if any(active.body == body for active in self.frames):
                    body = self._next_body
                    self._next_body += 1
                    self.bodies[body] = ()
                self._set_queue(_code_id(body), instructions)
                names[dst.name] = function._replace(body=body)
        return effect.call

    def step(self) -> None:
        """Run a line or its pending custom end statement."""
        if self.halted:
            return
        frame = self.frames[-1]
        pending = self._pending_ends.get(frame.pc)
        if pending is not None:
            call = self._apply(frame, pending[1])
            del self._pending_ends[frame.pc]
        else:
            line = self.heap[frame.pc][0]
            assert isinstance(line, int)
            if line < 1:
                raise HaltError(
                    f"line {format_integer(line)} does not exist; lines count from 1"
                )
            stmt = self.bodies[frame.body][line - 1]
            assert isinstance(stmt, _Stmt)
            call = self._apply(frame, stmt)
            pc = self.heap[frame.pc]
            if pc and stmt.end is not None:
                self._pending_ends[frame.pc] = (line, stmt.end)
            elif pc:
                top = pc.popleft()
                if not isinstance(top, int):
                    raise HaltError("the program counter holds a non-number")
                pc.append(top + 1)
        if call is not None:
            self.frames.append(_Frame(call.body, self._alloc((1,)), call, {}))
        while len(self.frames) > 1:
            top_frame = self.frames[-1]
            pc = self.heap[top_frame.pc]
            if pc and (
                top_frame.pc in self._pending_ends
                or pc[0] <= len(self.bodies[top_frame.body])  # type: ignore[operator]
            ):
                break
            self.frames.pop()
            self._discard_body(top_frame.body)
            self._pending_ends.pop(top_frame.pc, None)
            del self.heap[top_frame.pc]
            for obj in top_frame.names.values():
                if isinstance(obj, _Queue):
                    del self.heap[obj.qid]


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse once and allocate state per invocation."""
    source = require_text_source(source, options, "Q-BAL")
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
