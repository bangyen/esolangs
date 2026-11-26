"""Parse Q-Bal source into statements and function bodies."""

import re
from typing import NamedTuple

from esolangs.exceptions import ProgramError
from esolangs.runtime.memory import parse_integer
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
