"""Interpreter for Stisp.

Tanner Swett's 2022 rewriting language.  A program is equations, then one
closed stack expression: an S-expression (the head) followed by frames
``-> block[arg, ...]``.  A step takes the head and the first frame, finds
the first equation whose left side ``head -> block[args]`` matches them under
one consistent substitution of its variables, and replaces the two with the
right side, substituted the same way.  The run halts when no frame is left.

Commands:
    ``ATOM`` (an identifier not starting with a lowercase letter) is an atom,
    ``var`` (one starting with one) a variable, ``()`` the empty list,
    ``(h . t)`` a cons cell and ``(x1 ... xn)`` the list
    ``(x1 . (... (xn . ())))``.
    ``lhs -> block[args] = rhs -> f[...] ...;`` is an equation.
    ``#`` starts a line comment; identifiers are letters, digits, ``-`` and
    ``_``.

Input/output:
    Stisp has no input.  At halt the result, the head, is printed: lists in
    the list syntax, a cons whose tail ends in an atom as ``(h . t)``.

Errors:
    ProgramError: a token or construct outside the grammar, an equation
    whose left side has other than one frame or whose right side uses a
    variable its left side does not, a final stack with a variable, and a
    program with no final stack.
    HaltError: a step that no equation matches, whose outcome the page
    leaves undefined.

Decisions:
    * ``-`` followed by ``>`` ends an identifier, so ``x->f[]`` is ``x``,
      the arrow and ``f``: identifiers may contain ``-``, and the page only
      requires whitespace between two identifiers.
    * ``(a b . c)`` is refused: the grammar dots only a single head.
    * A trailing comma in a frame is allowed, as ``{<expr> ","} [<expr>]``
      reads.
    * The result prints at halt, the only output a program has; a cons
      whose tail ends in an atom prints in nested pairs, ``(a . (b . c))``,
      which the grammar reads back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error


@dataclass(frozen=True, slots=True)
class _Var:
    """A variable: an lword in an S-expression position."""

    name: str


#: An atom is its name, ``()`` the empty list, a 2-tuple a cons cell.
type _Expr = str | _Var | tuple[()] | tuple[_Expr, _Expr]
#: A frame: its block name and arguments.
type _Frame = tuple[str, tuple[_Expr, ...]]
#: The call stack, first frame on top: persistent, so a step is O(rhs).
type _Frames = tuple[_Frame, _Frames] | None


@dataclass(frozen=True, slots=True)
class _Equation:
    head: _Expr
    block: str
    args: tuple[_Expr, ...]
    rhs: _Expr
    frames: tuple[_Frame, ...]


_TOKEN = re.compile(
    r"\s+|#[^\n]*|(->)|([()\.\[\],=;])|((?:[A-Za-z0-9_]|-(?!>))+)|(.)", re.S
)
_NIL: tuple[()] = ()


@dataclass(slots=True)
class _Open:
    """An open parenthesis: the items read so far, and whether a dot was."""

    items: list[_Expr]
    dotted: bool = False


def _tokens(code: str) -> list[str]:
    """Return the tokens of ``code``, comments and whitespace dropped."""
    out = []
    for match in _TOKEN.finditer(code):
        arrow, punct, word, stray = match.groups()
        if stray is not None:
            raise syntax_error(
                f"{stray!r} is not part of Stisp's syntax",
                "use identifiers, ( ) . [ ] , = ; and ->",
            )
        token = arrow or punct or word
        if token:
            out.append(token)
    return out


def _is_word(token: str) -> bool:
    return token[0].isalnum() or token[0] in "-_"


class _Parser:
    """Recursive-descent over tokens; S-expressions are built iteratively."""

    def __init__(self, code: str) -> None:
        self.tokens = _tokens(code)
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            want = repr(expected) if expected else "a token"
            raise syntax_error(
                f"Stisp expected {want}, got {token or 'the end'!r}",
                "write equations `e -> f[...] = stack;`, then one stack",
            )
        self.pos += 1
        return token

    def expr(self) -> _Expr:
        """Parse one S-expression, without recursion: data nests deep."""
        opened: list[_Open] = []
        while True:
            token = self.take()
            if token == "(" and self.peek() == ")":
                self.take(")")
                value: _Expr = _NIL
            elif token == "(":
                opened.append(_Open([]))
                continue
            elif _is_word(token):
                value = _Var(token) if token[0].islower() else token
            else:
                raise syntax_error(
                    f"Stisp expected an S-expression, got {token!r}",
                    "write an identifier, () or a parenthesized list",
                )
            while opened:
                top = opened[-1]
                if top.dotted:
                    self.take(")")
                    opened.pop()
                    value = (top.items[0], value)
                    continue
                top.items.append(value)
                if self.peek() == ".":
                    if len(top.items) != 1:
                        raise syntax_error(
                            "a Stisp dot follows exactly one expression",
                            "write (a . b), or (a . (b . c)) for more",
                        )
                    self.take(".")
                    top.dotted = True
                elif self.peek() == ")":
                    self.take(")")
                    opened.pop()
                    value = _NIL
                    for item in reversed(top.items):
                        value = (item, value)
                    continue
                break
            else:
                return value

    def frame(self) -> _Frame:
        self.take("->")
        name = self.take()
        if not (_is_word(name) and name[0].islower()):
            raise syntax_error(
                f"a Stisp block name must start lowercase, got {name!r}",
                "write -> name[...]",
            )
        self.take("[")
        args: list[_Expr] = []
        while self.peek() != "]":
            args.append(self.expr())
            if self.peek() != "]":
                self.take(",")
        self.take("]")
        return name, tuple(args)

    def stack(self) -> tuple[_Expr, tuple[_Frame, ...]]:
        head = self.expr()
        frames = []
        while self.peek() == "->":
            frames.append(self.frame())
        return head, tuple(frames)


def _variables(*exprs: _Expr) -> set[str]:
    """Return the variable names in ``exprs``."""
    names, todo = set(), list(exprs)
    while todo:
        expr = todo.pop()
        if isinstance(expr, _Var):
            names.add(expr.name)
        elif isinstance(expr, tuple) and expr:
            todo.extend(expr)
    return names


def _frame_variables(frames: tuple[_Frame, ...]) -> set[str]:
    return _variables(*(arg for _, args in frames for arg in args))


def _parse(code: str) -> tuple[list[_Equation], _Expr, tuple[_Frame, ...]]:
    """Return the equations and the initial stack of ``code``."""
    parser = _Parser(code)
    if parser.peek() is None:
        raise syntax_error(
            "a Stisp program needs a stack expression", "end it with, e.g., A -> f[]"
        )
    equations = []
    while True:
        head, frames = parser.stack()
        if parser.peek() is None:
            break
        parser.take("=")
        if len(frames) != 1:
            raise syntax_error(
                f"a Stisp equation's left side takes one frame, not {len(frames)}",
                "write `expr -> block[args] = ...;`",
            )
        rhs, rhs_frames = parser.stack()
        parser.take(";")
        (block, args), bound = frames[0], _variables(head, *frames[0][1])
        loose = (_variables(rhs) | _frame_variables(rhs_frames)) - bound
        if loose:
            raise syntax_error(
                f"Stisp variable {min(loose)!r} is on the right side only",
                "bind every right-side variable on the left side",
            )
        equations.append(_Equation(head, block, args, rhs, rhs_frames))
    if _variables(head) or _frame_variables(frames):
        raise syntax_error(
            "the final Stisp stack must be closed",
            "use atoms, not variables, outside equations",
        )
    return equations, head, frames


def _key(expr: _Expr) -> str | None:
    """Return what an equation's head must equal, or None for a variable."""
    if isinstance(expr, _Var):
        return None
    if isinstance(expr, str):
        return expr
    return "(.)" if expr else "()"


def _index(equations: list[_Equation]) -> dict[tuple[str, int], _Bucket]:
    """Group equations by block and arity, then by their head's constructor.

    First-match order survives: each head's list merges in the equations
    whose head is a variable.  A step looks at one list, not the program.
    """
    groups: dict[tuple[str, int], list[_Equation]] = {}
    for eq in equations:
        groups.setdefault((eq.block, len(eq.args)), []).append(eq)
    index = {}
    for group, eqs in groups.items():
        keys = {_key(eq.head) for eq in eqs} - {None}
        by_key = {
            key: [eq for eq in eqs if _key(eq.head) in (key, None)] for key in keys
        }
        index[group] = _Bucket(by_key, [eq for eq in eqs if _key(eq.head) is None])
    return index


@dataclass(frozen=True, slots=True)
class _Bucket:
    by_key: dict[str | None, list[_Equation]]
    default: list[_Equation]


def _match(
    patterns: tuple[_Expr, ...], values: tuple[_Expr, ...]
) -> dict[str, _Expr] | None:
    """Return the substitution taking ``patterns`` to ``values``, if any."""
    bound: dict[str, _Expr] = {}
    todo = list(zip(reversed(patterns), reversed(values), strict=True))
    while todo:
        pattern, value = todo.pop()
        if isinstance(pattern, _Var):
            if bound.setdefault(pattern.name, value) != value:
                return None
        elif isinstance(pattern, str) or not pattern:
            if pattern != value:
                return None
        elif isinstance(value, tuple) and value:
            todo.append((pattern[1], value[1]))
            todo.append((pattern[0], value[0]))
        else:
            return None
    return bound


def _substitute(expr: _Expr, bound: dict[str, _Expr]) -> _Expr:
    """Return ``expr`` with its variables replaced; it nests as deep as source."""
    if isinstance(expr, _Var):
        return bound[expr.name]
    if isinstance(expr, str) or not expr:
        return expr
    return (_substitute(expr[0], bound), _substitute(expr[1], bound))


def _render(expr: _Expr) -> str:
    """Return ``expr`` in list syntax, without recursion."""
    out: list[str] = []
    #: Pending output: an expression to render, or text already rendered.
    todo: list[tuple[bool, _Expr]] = [(False, expr)]
    while todo:
        is_text, item = todo.pop()
        if is_text or isinstance(item, str):
            assert isinstance(item, str)
            out.append(item)
            continue
        assert not isinstance(item, _Var)
        if not item:
            out.append("()")
            continue
        items: list[_Expr] = []
        tail: _Expr = item
        while isinstance(tail, tuple) and tail:
            items.append(tail[0])
            tail = tail[1]
        if tail != _NIL:
            # A tail ending in an atom: one pair, its own tail nested.
            parts = [item[0], " . ", item[1]]
        else:
            parts = [part for value in items for part in (" ", value)][1:]
        todo.append((True, ")"))
        for at, part in reversed(list(enumerate(parts))):
            todo.append((at % 2 == 1, part))
        todo.append((True, "("))
    return "".join(out)


def _advance(
    index: dict[tuple[str, int], _Bucket], head: _Expr, frames: _Frames
) -> tuple[_Expr, _Frames]:
    """Return the head and frames after rewriting the head and first frame."""
    assert frames is not None
    (block, args), rest = frames
    bucket = index.get((block, len(args)))
    candidates = [] if bucket is None else bucket.by_key.get(_key(head), bucket.default)
    for eq in candidates:
        bound = _match((eq.head, *eq.args), (head, *args))
        if bound is not None:
            break
    else:
        raise HaltError(f"no Stisp equation matches {_render(head)} -> {block}[...]")
    for name, rhs_args in reversed(eq.frames):
        rest = ((name, tuple(_substitute(arg, bound) for arg in rhs_args)), rest)
    return _substitute(eq.rhs, bound), rest


class _Machine:
    """The equations, the head, and the frames left."""

    dumps_on_the_post_halt_step = True
    #: The state is an expression and a frame stack; ``ip`` is the depth.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        equations, head, frames = _parse(code)
        self.index = _index(equations)
        stack: _Frames = None
        for frame in reversed(frames):
            stack = (frame, stack)
        self.head: _Expr = head
        self.frames = stack
        self.rendered = False

    @property
    def halted(self) -> bool:
        return self.frames is None

    def _blocks(self) -> list[str]:
        names, frames = [], self.frames
        while frames is not None:
            names.append(frames[0][0])
            frames = frames[1]
        return names

    @property
    def ip(self) -> tuple[int, ...]:
        """The number of frames left."""
        return (len(self._blocks()),)

    @property
    def stack(self) -> list[str]:
        """The head, then each frame's block name, first frame first."""
        return [_render(self.head), *self._blocks()]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.head, self.frames, self.rendered)

    def step(self) -> None:
        """Rewrite once; past the last frame, print the result once."""
        if self.frames is not None:
            self.head, self.frames = _advance(self.index, self.head, self.frames)
        elif not self.rendered:
            self.io.print_str(_render(self.head))
            self.rendered = True


def run(code: str, io: IO) -> None:
    """Run a Stisp program and print its result."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
