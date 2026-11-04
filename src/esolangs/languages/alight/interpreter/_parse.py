"""Alight expression parsing: the tokenizer and the parsed expression tree."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal, NamedTuple

from esolangs.languages.alight.interpreter._dialect import (
    expression_syntax as validate_expression_syntax,
)
from esolangs.languages.alight.interpreter._hints import Hint
from esolangs.runtime.memory import parse_integer

#: The four special values, as their own singleton type.  A special is not a
#: number -- comparing one against a number is false rather than an error --
#: so it needs to be distinguishable from ``0``, which ``nil`` is not if the
#: specials are spelled as ints.
type _Special = Literal["nil", "eof", "left", "right"]


_SPECIALS: tuple[_Special, ...] = ("nil", "eof", "left", "right")


#: A value: a number, a list of values, or one of the four specials.
type _Value = Fraction | int | list["_Value"] | _Special


class _Num(NamedTuple):
    """A number literal: the ``("num", value)`` node."""

    tag: Literal["num"]
    value: Fraction | int


class _Val(NamedTuple):
    """An already-computed value, e.g. a resolved call: the ``("val", value)`` node."""

    tag: Literal["val"]
    value: _Value


class _SpecialNode(NamedTuple):
    """One of the four special values: the ``("special", name)`` node."""

    tag: Literal["special"]
    name: _Special


class _Var(NamedTuple):
    """A variable reference: the ``("var", name)`` node."""

    tag: Literal["var"]
    name: str


class _List(NamedTuple):
    """A list literal: the ``("list", [items])`` node."""

    tag: Literal["list"]
    items: list[_Expr]


class _Not(NamedTuple):
    """Logical negation: the ``("not", operand)`` node."""

    tag: Literal["not"]
    operand: _Expr


class _Bin(NamedTuple):
    """A binary operation: the ``("bin", op, left, right)`` node."""

    tag: Literal["bin"]
    op: str
    left: _Expr
    right: _Expr


class _Call(NamedTuple):
    """A function call: the ``("call", name, [args])`` node."""

    tag: Literal["call"]
    name: str
    args: list[_Expr]


#: Typed expression nodes remain immutable tuples in snapshots.
type _Expr = _Num | _Val | _SpecialNode | _Var | _List | _Not | _Bin | _Call


#: Reserved words a variable may not be named.  The wiki says variable names
#: are alphanumeric and "not reserved words" without listing them; these are
#: every word the grammar itself gives a meaning.
_RESERVED = frozenset(
    {
        "begin",
        "end",
        "func",
        "var",
        "set",
        "skip",
        "turn",
        "inp",
        "out",
        "wait",
        "at",
        "len",
        "trunc",
        "sign",
        *_SPECIALS,
    }
)


def _valid_name(name: str) -> bool:
    """Whether ``name`` may name a variable: alphanumeric and not reserved."""
    return bool(name) and name.isalnum() and name not in _RESERVED


class _Parser:
    """Read infix (examples' ``len{l}-0.5``) or postfix (the prose's rule)."""

    def __init__(self, text: str, expression_syntax: str = "infix") -> None:
        self.expression_syntax = validate_expression_syntax(expression_syntax)
        self.text = text
        self.pos = 0

    def skip_space(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def peek(self) -> str:
        self.skip_space()
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def at_end(self) -> bool:
        return self.peek() == ""

    def word(self) -> str:
        """Read one alphanumeric identifier, or ``""`` if none is here."""
        self.skip_space()
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isalnum():
            self.pos += 1
        return self.text[start : self.pos]


# The binary operators, longest spelling first is unnecessary -- all are one
# character -- but the set is named so the parser and the evaluator cannot
# drift on which characters are operators.
_BINARY = frozenset("+-*/=<>&|^")


def _parse_expr(p: _Parser) -> _Expr:
    """Parse an expression: an operand, then ``op operand`` pairs, left to right."""
    if p.expression_syntax == "postfix":
        return _parse_postfix(p)
    node = _parse_operand(p)
    while True:
        c = p.peek()
        if c not in _BINARY:
            return node
        # A '-' directly before a digit is still an operator here, never a
        # sign: ``len{l}-0.5`` is a subtraction, and an operand position is
        # the only place a leading '-' could be a negation.  Alight has no
        # unary minus, so there is no ambiguity to resolve.
        p.pos += 1
        node = _Bin("bin", c, node, _parse_operand(p))


def _parse_postfix(p: _Parser) -> _Expr:
    """Parse one postfix expression, stopping at an argument delimiter."""
    stack: list[_Expr] = []
    while (char := p.peek()) and char not in ",}]":
        if char in _BINARY or char == "!":
            p.pos += 1
            needed = 1 if char == "!" else 2
            if len(stack) < needed:
                raise Hint.OPERAND.error("postfix operator lacks operands")
            right = stack.pop()
            stack.append(
                _Not("not", right)
                if char == "!"
                else _Bin("bin", char, stack.pop(), right)
            )
        else:
            stack.append(_parse_operand(p))
    if len(stack) != 1:
        raise Hint.EXPRESSION.error("postfix expression must leave one value")
    return stack[0]


def _parse_operand(p: _Parser) -> _Expr:
    """Parse one operand: a literal, a list, a ``!``, a call, or a variable."""
    c = p.peek()
    if c == "":
        raise Hint.OPERAND.error("expression ends early")
    if c == "!":
        p.pos += 1
        return _Not("not", _parse_operand(p))
    if c == "'":
        p.pos += 1
        if p.pos >= len(p.text):  # pragma: no cover - _scan catches it first
            # Unreachable from a real program: a trailing ``'`` shields the
            # cell after it, so the command either runs on past its
            # terminator or hits the grid edge, where ``_scan`` raises
            # "unterminated string literal".  Kept as a guard because
            # ``_parse_operand`` is also called on hand-built text.
            raise Hint.CHARACTER_LITERAL.error("character literal ends early")
        p.pos += 1
        return _Num("num", Fraction(ord(p.text[p.pos - 1])))
    if c == '"':
        p.pos += 1
        chars: list[_Expr] = []
        while p.pos < len(p.text) and p.text[p.pos] != '"':
            chars.append(_Num("num", Fraction(ord(p.text[p.pos]))))
            p.pos += 1
        if p.pos >= len(p.text):  # pragma: no cover - _scan catches it first
            # Unreachable from a real program, like the ``'`` guard above:
            # ``_scan`` tracks the same quoting, so a command whose ``"``
            # never closes runs to the grid edge and is refused there with
            # this message.  Kept because the parser is also called on
            # hand-built text, where nothing has scanned it.
            raise Hint.STRING_LITERAL.error("unterminated string literal")
        p.pos += 1
        return _List("list", chars)
    if c == "[":
        p.pos += 1
        return _List("list", _parse_args(p, "]"))
    start = p.pos
    name = p.word()
    if name and p.peek() == "{":
        p.pos += 1
        return _Call("call", name, _parse_args(p, "}"))
    p.pos = start
    if (c.isdecimal() and name.isdecimal()) or c == ".":
        return _Num("num", _parse_number(p))
    name = p.word()
    if not name:
        raise Hint.OPERAND_KIND.error(f"cannot parse operand at {p.text[p.pos :]!r}")
    if name in _SPECIALS:
        return _SpecialNode("special", name)
    return _Var("var", name)


def _parse_number(p: _Parser) -> Fraction:
    """Read a decimal literal, which may be fractional (indices are ``k+0.5``)."""
    p.skip_space()
    start = p.pos
    while p.pos < len(p.text) and (p.text[p.pos].isdecimal() or p.text[p.pos] == "."):
        p.pos += 1
    text = p.text[start : p.pos]
    whole, dot, tail = text.partition(".")
    try:
        if "." in tail:
            raise ValueError("multiple decimal points")
        return Fraction(parse_integer(whole + tail), 10 ** len(tail) if dot else 1)
    except ValueError:
        raise Hint.NUMBER.error(
            f"bad number literal {p.text[start : p.pos]!r}"
        ) from None


def _parse_args(p: _Parser, close: str) -> list[_Expr]:
    """Read a comma-separated argument or element list up to ``close``."""
    args: list[_Expr] = []
    if p.peek() == close:
        p.pos += 1
        return args
    while True:
        args.append(_parse_expr(p))
        c = p.peek()
        if c == close:
            p.pos += 1
            return args
        if c != ",":
            raise Hint.ARGUMENTS.error(f"expected {close!r} or ',' in {p.text!r}")
        p.pos += 1


def _command_expr(
    text: str, word: str, expression_syntax: str = "infix"
) -> _Expr | None:
    """Return the expression a command evaluates, or None if it has none.

    The caller passes only commands that evaluate: ``set`` names a variable
    and then evaluates; ``turn``/``skip``/``wait``/``end`` are a keyword and
    an expression; a bare call is itself the expression.
    """
    p = _Parser(text, expression_syntax)
    p.word()
    if word == "set":
        name = p.word()
        if not _valid_name(name):
            raise ValueError(f"bad variable name {name!r}")
    elif word not in ("turn", "skip", "wait", "end"):
        p = _Parser(text, expression_syntax)  # a bare call: parse the whole command
    if word == "end" and p.at_end():
        return None
    expr = _parse_expr(p)
    if not p.at_end():
        if word == "set":
            raise ValueError(f"trailing text in set: {text!r}")
        if word == "end":
            raise ValueError(f"trailing text after end value: {text!r}")
        if word in ("turn", "skip", "wait"):
            raise ValueError(f"trailing text after {word!r} expression: {text!r}")
        raise ValueError(f"unknown command {word!r} in {text!r}")
    return expr


def _replace_first(expr: _Expr, value: _Value) -> tuple[_Expr, bool]:
    """Return ``expr`` with its first call replaced, and whether one was."""
    if isinstance(expr, (_Num, _Val, _SpecialNode, _Var)):
        return expr, False
    if isinstance(expr, _Not):
        inner, done = _replace_first(expr.operand, value)
        return _Not("not", inner), done
    if isinstance(expr, _Bin):
        left, done = _replace_first(expr.left, value)
        if done:
            return _Bin("bin", expr.op, left, expr.right), True
        right, done = _replace_first(expr.right, value)
        return _Bin("bin", expr.op, left, right), done
    items = expr.items if isinstance(expr, _List) else expr.args
    # A copy: replacing in place up to the first call keeps the unprocessed
    # tail, which an early return must not drop.
    children = list(items)
    for i, child in enumerate(children):
        children[i], done = _replace_first(child, value)
        if done:
            if isinstance(expr, _List):
                return _List("list", children), True
            return _Call("call", expr.name, children), True
    if isinstance(expr, _List):
        return _List("list", children), False
    return _Val("val", value), True


def _first_call_or_none(expr: _Expr, name: str) -> _Call | None:
    """Return the leftmost ``call`` to ``name``, or None if there is none."""
    if isinstance(expr, (_Num, _Val, _SpecialNode, _Var)):
        return None
    if isinstance(expr, _Not):
        children = [expr.operand]
    elif isinstance(expr, _Bin):
        children = [expr.left, expr.right]
    else:
        children = expr.items if isinstance(expr, _List) else expr.args
    for child in children:
        found = _first_call_or_none(child, name)
        if found is not None:
            return found
    return expr if isinstance(expr, _Call) and expr.name == name else None
