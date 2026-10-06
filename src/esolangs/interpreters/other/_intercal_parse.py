"""INTERCAL parsing: statement splitting, headers, commands and expressions."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from esolangs.exceptions import HaltError

type _Node = tuple[Any, ...]
type _Key = tuple[str, int]

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

# A ONCE/AGAIN outcome once the statement is reached.
_SELF_ABSTAIN, _SELF_REINSTATE = 1, 2


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
            return ("u", char, self.unambiguous())
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
            node = ("#", _unary(number, 16, unary) if unary else number)
            return node
        if sigil in ",;":
            if not self.keyword("SUB"):
                raise _fail("E000", "an INTERCAL array needs SUB in an expression")
            node = ("sub", sigil, number, self.subscripts())
        else:
            node = (sigil, number)
        return ("u", unary, node) if unary else node

    def subscripts(self) -> tuple[_Node, ...]:
        items = [self.unambiguous()]
        while items[-1][0] != "sub" and self.operand_follows():
            items.append(self.unambiguous())
        return tuple(items)

    def group(self, delimiter: str) -> _Node:
        self.at += 1
        self.groups.append(delimiter)
        char = self.peek()
        if not char:
            raise _fail(
                "E000",
                "incomplete INTERCAL expression",
                hint="supply a complete INTERCAL operand or expression",
            )
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
        return ("u", unary, inner) if unary else inner

    def expression(self) -> _Node:
        """Parse an expression; binary operators right-associate (0.26+)."""
        left = self.unambiguous()
        char = self.peek()
        if char and char in _MINGLES + "~":
            self.at += 1
            return ("$" if char in _MINGLES else "~", left, self.expression())
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
            return ("array", found[0], found[2])
        self.at = start
        if output:
            return self.expression()
        found = self.literal(".:")
        if found is not None:
            if found[1]:
                raise _fail("E000", "invalid INTERCAL variable")
            return (found[0], found[2])
        node = self.unambiguous()
        if node[0] != "sub":
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
        target: _Node = (sigil, number)
        if sigil in ",;" and self.keyword("SUB"):
            target = ("sub", sigil, number, self.subscripts())
        if not self.keyword("<-"):
            raise _fail("E000", "invalid INTERCAL calculation")
        if target[0] in ",;":
            dimensions = [self.expression()]
            while self.keyword("BY"):
                dimensions.append(self.expression())
            return ("dimension", (sigil, number), tuple(dimensions))
        return ("calculate", target, self.expression())

    def command(self) -> _Node:
        label = self.label()
        if label is not None:
            if not self.keyword("NEXT"):
                raise _fail("E000", "a label in a statement body must precede NEXT")
            return ("next", label)
        for word in ("FORGET", "RESUME"):
            if self.keyword(word):
                return (word.lower(), self.expression())
        for word in ("STASH", "RETRIEVE", "IGNORE", "REMEMBER"):
            if self.keyword(word):
                return (word.lower(), self.separated(self.variable))
        if self.keyword("ABSTAIN"):
            count = None if self.keyword("FROM") else self.expression()
            if count is not None and not self.keyword("FROM"):
                raise _fail("E000", "computed ABSTAIN needs FROM")
            return ("abstain", self.required_target(), count)
        if self.keyword("REINSTATE"):
            return ("reinstate", self.required_target())
        if self.keyword("READ OUT"):
            return ("read", self.separated(lambda: self.io_item(output=True)))
        if self.keyword("WRITE IN"):
            return ("write", self.separated(lambda: self.io_item(output=False)))
        if self.keyword("GIVE UP"):
            return ("give up",)
        if self.keyword("TRY AGAIN"):
            return ("try again",)
        for word in ("COME FROM", "NEXT FROM"):
            if self.keyword(word):
                found = self.target()
                kind = word.lower()
                return (kind, found) if found is not None else (kind, self.expression())
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
# A label after these words is the command's target, not the next statement's.
_TARGETING = ("FROM", "REINSTATE")
_HEADER = re.compile(
    r"\s*(?:\(\s*(\d[\d\s]*)\)\s*)?(?:(PLEASE)(?:\s*DO)?|DO)(\s*(?:NOT|N'T))?"
    r"(?:\s*%\s*(\d[\d\s]*))?"
)
_BARE = re.compile(
    r"(?:\.\d+\s*<-|READ\s+OUT|WRITE\s+IN|GIVE\s+UP|RESUME\b|FORGET\b|\(\s*\d[\d\s]*\)\s+NEXT)"
)


def _statements(code: str) -> list[str]:
    """Assemble statements at identifiers, retaining bare core fixtures."""
    starts = [
        match.start("id")
        if code[: match.start()].rstrip().endswith(_TARGETING)
        else match.start()
        for match in _START.finditer(code)
    ]
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
        return _KIND.get(str(self.command[0]))


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
            after = _SELF_REINSTATE if abstained else _SELF_ABSTAIN
        elif parser.keyword("AGAIN"):
            after = _SELF_ABSTAIN if abstained else _SELF_REINSTATE
        if parser.peek():
            listed = command[0] in ("write", "stash", "retrieve", "ignore", "remember")
            raise _fail(
                "E000",
                "invalid INTERCAL variable list"
                if listed
                else "unrecognized INTERCAL statement",
            )
    except HaltError as error:
        command = ("error", str(error))
    return _Statement(text, label, bool(polite), abstained, chance, command, after)
