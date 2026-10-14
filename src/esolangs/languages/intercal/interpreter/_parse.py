"""INTERCAL parsing: statement splitting, headers, commands and expressions."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from itertools import pairwise
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError


class _Node(NamedTuple):
    """A parse-tree node: ``tag`` names the form, ``arg1``-``arg3`` its parts.

    The parts' meaning depends on ``tag``:

    - ``("#", value)``: a 16-bit constant.
    - ``(".", number)`` / ``(":", number)``: a scalar variable.
    - ``("u", operator, child)``: a unary ``&``/``V``/``?`` application.
    - ``("$", left, right)`` / ``("~", left, right)``: mingle / select.
    - ``("sub", sigil, number, subscripts)``: an array element.
    - ``("array", sigil, number)``: a whole array (an I/O item).
    - ``("calculate", target, expression)``;
      ``("dimension", key, sizes)``: a DIMENSION command, where ``key`` is
      a ``_DimensionKey`` (``sigil`` and ``number`` fields naming the array)
      and ``sizes`` is a tuple of dimension expressions.
    - ``("next", label)``; ``("forget" | "resume", expression)``;
      ``("stash" | "retrieve" | "ignore" | "remember", keys)``;
      ``("abstain", target, count)``; ``("reinstate", target)``;
      ``("read" | "write", items)``; ``("give up",)``; ``("try again",)``;
      ``("come from" | "next from", target)``; ``("error", message)``.
    """

    tag: str
    arg1: Any = None
    arg2: Any = None
    arg3: Any = None


type _Key = tuple[str, int]


class _DimensionKey(NamedTuple):
    """A ``("dimension", key, sizes)`` node's key: the array's sigil and number.

    Hashable, so it serves as a dict key in ``_dimension``; it
    compares equal to the plain ``(sigil, number)`` tuple other nodes use.
    """

    sigil: str
    number: int


_MINGLES = "$¢£¤€"
_UNARIES = "&V?"

# Gerund spellings, longest first, and the statement kind each names.
_GERUNDS = (
    ("NEXTING FROM", "next from"),
    ("COMING FROM", "come from"),
    ("CALCULATING", "calculate"),
    ("NEXTING", "next"),
    ("FORGETTING", "forget"),
    ("RESUMING", "resume"),
    ("STASHING", "stash"),
    ("RETRIEVING", "retrieve"),
    ("IGNORING", "ignore"),
    ("REMEMBERING", "remember"),
    ("ABSTAINING", "abstain"),
    ("REINSTATING", "reinstate"),
    ("READING OUT", "read"),
    ("WRITING IN", "write"),
    ("TRYING AGAIN", "try again"),
    ("COMMENTING", "error"),
    ("COMMENTS", "error"),
    ("COMMENT", "error"),
)


class _SelfAbstain(IntEnum):
    """A statement's ONCE/AGAIN outcome once the statement is reached.

    ``ABSTAIN``: the statement abstains itself when reached (``ONCE``, or
    ``AGAIN`` on a ``DO NOT`` statement).  ``REINSTATE``: the statement
    reinstates itself when reached (``AGAIN``, or ``ONCE`` on a ``DO NOT``
    statement).
    """

    ABSTAIN = 1
    REINSTATE = 2


def _fail(code: str, message: str, hint: str | None = None) -> HaltError:
    """Build a ``HaltError`` whose message names the manual's E-number."""
    return HaltError(f"{message} ({code})", hint=hint)


def _unary(value: int, width: int, operator: str) -> int:
    mask = (1 << width) - 1
    rotated = ((value >> 1) | (value << (width - 1))) & mask
    if operator == "&":
        return value & rotated
    if operator == "V":
        return value | rotated
    return value ^ rotated


def _number(digits: str, low: int, high: int, code: str, what: str) -> int:
    digits = re.sub(r"\s", "", digits).lstrip("0") or "0"
    if len(digits) > 10 or not low <= int(digits) <= high:
        raise _fail(code, what)
    return int(digits)


# C-INTERCAL's lexer skips whitespace between tokens and inside numbers.
_LITERAL = re.compile(r"([.:#,;])\s*([&V?]?)\s*([0-9][0-9\s]*)")
_LABEL = re.compile(r"\(\s*(\d[\d\s]*)\)")
_KEYWORDS: dict[str, re.Pattern[str]] = {}


class _Parser:
    """Recursive descent over one statement body; whitespace separates tokens."""

    def __init__(self, text: str, at: int = 0) -> None:
        self.text = text
        self.at = at
        self.groups: list[str] = []

    def peek(self) -> str:
        while self.at < len(self.text) and self.text[self.at].isspace():
            self.at += 1
        return self.text[self.at] if self.at < len(self.text) else ""

    def keyword(self, word: str) -> bool:
        """Consume ``word``; its own spaces may be any (or no) whitespace."""
        pattern = _KEYWORDS.get(word)
        if pattern is None:
            pattern = _KEYWORDS[word] = re.compile(
                r"\s*".join(map(re.escape, word.split()))
            )
        self.peek()
        found = pattern.match(self.text, self.at)
        if found is None:
            return False
        self.at = found.end()
        return True

    def label(self) -> int | None:
        self.peek()
        found = _LABEL.match(self.text, self.at)
        if found is None:
            return None
        self.at = found.end()
        return _number(found[1], 1, 65535, "E197", "invalid INTERCAL label number")

    def literal(self, sigils: str) -> tuple[str, str, int] | None:
        """Consume a constant or variable whose sigil is in ``sigils``."""
        self.peek()
        found = _LITERAL.match(self.text, self.at)
        if found is None or found[1] not in sigils:
            return None
        self.at = found.end()
        sigil, unary, digits = found.groups()
        if sigil == "#":
            return (
                sigil,
                unary,
                _number(digits, 0, 65535, "E017", "INTERCAL constant out of range"),
            )
        return (
            sigil,
            unary,
            _number(digits, 1, 65535, "E200", "invalid INTERCAL variable number"),
        )

    def operand_follows(self) -> bool:
        """Whether a subscript list continues with another operand."""
        char = self.peek()
        if not char:
            return False
        if char in "'\"":
            return not self.groups or char != self.groups[-1]
        return char in ".:#,;&V?"

    def unambiguous(self) -> _Node:
        char = self.peek()
        if not char:
            raise _fail(
                "E000",
                "incomplete INTERCAL expression",
                hint="supply a complete INTERCAL operand or expression",
            )
        if char in "'\"":
            return self.group(char)
        if char in _UNARIES:
            self.at += 1
            return _Node("u", char, self.unambiguous())
        found = self.literal(".:#,;")
        if found is None:
            raise _fail(
                "E000",
                "invalid INTERCAL operand",
                hint="use an INTERCAL constant, variable or grouped expression",
            )
        sigil, unary, number = found
        node: _Node
        if sigil == "#":
            node = _Node("#", _unary(number, 16, unary) if unary else number)
            return node
        if sigil in ",;":
            if not self.keyword("SUB"):
                raise _fail("E000", "an INTERCAL array needs SUB in an expression")
            node = _Node("sub", sigil, number, self.subscripts())
        else:
            node = _Node(sigil, number)
        return _Node("u", unary, node) if unary else node

    def subscripts(self) -> tuple[_Node, ...]:
        items = [self.unambiguous()]
        while items[-1].tag != "sub" and self.operand_follows():
            items.append(self.unambiguous())
        return tuple(items)

    def group(self, delimiter: str) -> _Node:
        self.at += 1
        self.groups.append(delimiter)
        char = self.peek()
        unary = char if char in _UNARIES else ""
        self.at += bool(unary)
        inner = self.expression()
        if self.peek() != delimiter:
            raise _fail(
                "E000",
                "unbalanced INTERCAL expression group",
                hint="balance the expression grouping marks",
            )
        self.at += 1
        self.groups.pop()
        return _Node("u", unary, inner) if unary else inner

    def expression(self) -> _Node:
        """Parse an expression; binary operators right-associate (0.26+)."""
        left = self.unambiguous()
        char = self.peek()
        if char and char in _MINGLES + "~":
            self.at += 1
            return _Node("$" if char in _MINGLES else "~", left, self.expression())
        return left

    def separated[T](self, item: Callable[[], T]) -> tuple[T, ...]:
        items = [item()]
        while self.peek() == "+":
            self.at += 1
            items.append(item())
        return tuple(items)

    def variable(self) -> _Key:
        found = self.literal(".:,;")
        if found is None or found[1]:
            raise _fail("E000", "invalid INTERCAL variable list")
        return found[0], found[2]

    def gerunds(self) -> frozenset[str] | None:
        start = self.at
        found: list[str] = []
        while True:
            kind = next((k for word, k in _GERUNDS if self.keyword(word)), None)
            if kind is None:
                self.at = start
                return None
            found.append(kind)
            if self.peek() != "+":
                return frozenset(found)
            self.at += 1

    def target(self) -> int | frozenset[str] | None:
        label = self.label()
        return label if label is not None else self.gerunds()

    def io_item(self, *, output: bool) -> _Node:
        start = self.at
        found = self.literal(",;")
        if found is not None and not found[1] and not self.keyword("SUB"):
            return _Node("array", found[0], found[2])
        self.at = start
        if output:
            return self.expression()
        found = self.literal(".:")
        if found is not None:
            if found[1]:
                raise _fail("E000", "invalid INTERCAL variable")
            return _Node(found[0], found[2])
        node = self.unambiguous()
        if node.tag != "sub":
            raise _fail("E000", "invalid INTERCAL variable")
        return node

    def lvalue_assignment(self) -> _Node:
        found = self.literal(".:,;")
        if found is None or found[1]:
            raise _fail(
                "E000",
                "unrecognized INTERCAL statement",
                hint="use statements supported by esolangs describe --spec INTERCAL",
            )
        sigil, _unary_mark, number = found
        target: _Node = _Node(sigil, number)
        if sigil in ",;" and self.keyword("SUB"):
            target = _Node("sub", sigil, number, self.subscripts())
        if not self.keyword("<-"):
            raise _fail("E000", "invalid INTERCAL calculation")
        if target.tag in ",;":
            dimensions = [self.expression()]
            while self.keyword("BY"):
                dimensions.append(self.expression())
            return _Node("dimension", _DimensionKey(sigil, number), tuple(dimensions))
        return _Node("calculate", target, self.expression())

    def command(self) -> _Node:
        label = self.label()
        if label is not None:
            if not self.keyword("NEXT"):
                raise _fail("E000", "a label in a statement body must precede NEXT")
            return _Node("next", label)
        for word in ("FORGET", "RESUME"):
            if self.keyword(word):
                return _Node(word.lower(), self.expression())
        for word in ("STASH", "RETRIEVE", "IGNORE", "REMEMBER"):
            if self.keyword(word):
                return _Node(word.lower(), self.separated(self.variable))
        if self.keyword("ABSTAIN"):
            count = None if self.keyword("FROM") else self.expression()
            if count is not None and not self.keyword("FROM"):
                raise _fail("E000", "computed ABSTAIN needs FROM")
            return _Node("abstain", self.required_target(), count)
        if self.keyword("REINSTATE"):
            return _Node("reinstate", self.required_target())
        if self.keyword("READ OUT"):
            return _Node("read", self.separated(lambda: self.io_item(output=True)))
        if self.keyword("WRITE IN"):
            return _Node("write", self.separated(lambda: self.io_item(output=False)))
        if self.keyword("GIVE UP"):
            return _Node("give up")
        if self.keyword("TRY AGAIN"):
            return _Node("try again")
        for word in ("COME FROM", "NEXT FROM"):
            if self.keyword(word):
                found = self.target()
                kind = word.lower()
                return (
                    _Node(kind, found)
                    if found is not None
                    else _Node(kind, self.expression())
                )
        return self.lvalue_assignment()

    def required_target(self) -> int | frozenset[str]:
        found = self.target()
        if found is None:
            raise _fail("E000", "ABSTAIN and REINSTATE need a label or gerunds")
        return found


def _parse_expression(text: str, at: int = 0) -> tuple[_Node, int]:
    parser = _Parser(text, at)
    return parser.expression(), parser.at


_START = re.compile(
    r"(?:\(\s*\d[\d\s]*\)\s*)?(?P<id>PLEASE(?:\s*DO)?|DO)(?:\s*(?:NOT|N'T))?"
)
# A label after these words is the command's target, not the next statement's;
# not after the gerunds COMING FROM and NEXTING FROM, which take none.
_TARGETING = ("FROM", "REINSTATE")
_GERUND_FROM = re.compile(r"(?:COMING|NEXTING)\s*FROM\Z")
_HEADER = re.compile(
    r"\s*(?:\(\s*(\d[\d\s]*)\)\s*)?(?:(PLEASE)(?:\s*DO)?|DO)(\s*(?:NOT|N'T))?"
    r"(?:\s*%\s*(\d[\d\s]*))?"
)
_BARE = re.compile(
    r"(?:\.\d+\s*<-|READ\s+OUT|WRITE\s+IN|GIVE\s+UP|RESUME\b|FORGET\b|\(\s*\d[\d\s]*\)\s+NEXT)"
)


def _statements(code: str) -> list[str]:
    """Assemble statements at identifiers, retaining bare core fixtures."""
    starts = []
    for match in _START.finditer(code):
        before = code[: match.start()].rstrip()
        targeted = before.endswith(_TARGETING) and not _GERUND_FROM.search(before)
        starts.append(match.start("id") if targeted else match.start())
    bounds = [0, *starts, len(code)]
    statements: list[str] = []
    for left, right in pairwise(bounds):
        fragments: list[str] = []
        for line in code[left:right].splitlines():
            line = line.strip()
            if not line:
                continue
            # Bare complete commands remain physical-line statements; a
            # command after only an identifier completes that identifier.
            if fragments and _BARE.match(line):
                prefix = " ".join(fragments)
                if _START.fullmatch(prefix) is None:
                    statements.append(prefix)
                    fragments = []
            fragments.append(line)
        if fragments:
            statements.append(" ".join(fragments))
    return statements


_KIND = {
    "calculate": "calculate",
    "dimension": "calculate",
    "next": "next",
    "forget": "forget",
    "resume": "resume",
    "stash": "stash",
    "retrieve": "retrieve",
    "ignore": "ignore",
    "remember": "remember",
    "abstain": "abstain",
    "reinstate": "reinstate",
    "read": "read",
    "write": "write",
    "come from": "come from",
    "next from": "next from",
    "try again": "try again",
    "error": "error",
}


@dataclass(frozen=True, slots=True)
class _Statement:
    """One parsed statement: its header fields and its command."""

    text: str
    label: int | None
    polite: bool
    abstained: bool
    chance: int
    command: _Node
    after: int

    @property
    def kind(self) -> str | None:
        """The gerund kind, or ``None`` for ``GIVE UP``, which has none."""
        return _KIND.get(self.command.tag)


def _load(text: str) -> _Statement:
    header = _HEADER.match(text)
    label = polite = None
    abstained = False
    chance = 100
    body = text
    if header is not None:
        if header[1] is not None:
            label = _number(
                header[1], 1, 65535, "E197", "invalid INTERCAL label number"
            )
        polite = header[2]
        abstained = header[3] is not None
        if header[4] is not None:
            chance = int(re.sub(r"\s", "", header[4]))
        body = text[header.end() :]
    after = 0
    try:
        parser = _Parser(body.replace("!", "'."))
        command = parser.command()
        if parser.keyword("ONCE"):
            after = _SelfAbstain.REINSTATE if abstained else _SelfAbstain.ABSTAIN
        elif parser.keyword("AGAIN"):
            after = _SelfAbstain.ABSTAIN if abstained else _SelfAbstain.REINSTATE
        if parser.peek():
            listed = command.tag in ("write", "stash", "retrieve", "ignore", "remember")
            raise _fail(
                "E000",
                "invalid INTERCAL variable list"
                if listed
                else "unrecognized INTERCAL statement",
            )
    except HaltError as error:
        command = _Node("error", str(error))
    return _Statement(text, label, bool(polite), abstained, chance, command, after)
