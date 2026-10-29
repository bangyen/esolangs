"""Shakespeare source to a flat list of operations.

A hand-written lexer and recursive-descent parser over ``words.toml``.
``parse`` returns the cast, the operations with goto targets resolved, and
nothing else: descriptions, titles and act/scene numbers are checked and
dropped.
"""

from __future__ import annotations

import re
import tomllib
from bisect import bisect_right
from dataclasses import dataclass, replace
from functools import cache
from importlib.resources import files
from typing import Any

from esolangs.exceptions import InterpreterLimitError
from esolangs.runtime.source_hints import syntax_error

#: An expression: ("const", n), ("me",), ("you",), ("name", cast index),
#: ("un", operator, e) or ("bin", operator, a, b); tuples so a state stays
#: immutable.
type Expr = tuple[Any, ...]

_TOKEN = re.compile(r"\w[\w'\u2019-]*|\S")
_ROMAN = re.compile(r"M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_BINARY = {
    ("the", "difference", "between"): "sub",
    ("the", "product", "of"): "mul",
    ("the", "quotient", "between"): "div",
    ("the", "remainder", "of", "the", "quotient", "between"): "mod",
    ("the", "sum", "of"): "add",
}
_UNARY = {
    ("the", "cube", "of"): "cube",
    ("the", "factorial", "of"): "factorial",
    ("the", "square", "of"): "square",
    ("the", "square", "root", "of"): "sqrt",
    ("twice",): "twice",
}
_GOTO_OPENERS = {("let", "us"), ("we", "shall"), ("we", "must")}


@dataclass(frozen=True, slots=True)
class Op:
    """One operation; ``kind`` picks which of ``a``, ``b``, ``c`` it uses."""

    kind: str
    speaker: int = -1
    cond: bool | None = None
    a: Any = None
    b: Any = None
    c: str = ""


@cache
def _words() -> dict[str, tuple[str, ...]]:
    path = files("esolangs.languages.shakespeare").joinpath("words.toml")
    return {k: tuple(v) for k, v in tomllib.loads(path.read_text("utf-8")).items()}


def _phrases(entries: tuple[str, ...]) -> dict[str, list[tuple[str, ...]]]:
    """Index multi-word entries by first word, longest first."""
    table: dict[str, list[tuple[str, ...]]] = {}
    for entry in entries:
        words = tuple(entry.split())
        table.setdefault(words[0], []).append(words)
    for options in table.values():
        options.sort(key=len, reverse=True)
    return table


def _roman(word: str) -> int | None:
    upper = word.upper()
    if not upper or not _ROMAN.fullmatch(upper):
        return None
    total = 0
    for here, after in zip(upper, upper[1:] + " ", strict=True):
        value = _ROMAN_VALUES[here]
        total += -value if _ROMAN_VALUES.get(after, 0) > value else value
    return total or None


class _Parser:
    def __init__(self, text: str) -> None:
        breaks = [m.start() for m in re.finditer("\n", text)]
        found = list(_TOKEN.finditer(text))
        self.words = [m.group().lower() for m in found]
        self.lines = [bisect_right(breaks, m.start()) + 1 for m in found]
        self.pos = 0
        w = _words()
        self.be, self.articles = set(w["be"]), set(w["article"])
        self.possessives = set(w["possessive"])
        self.first = set(w["first_person"]) | set(w["first_person_reflexive"])
        self.second = set(w["second_person"]) | set(w["second_person_reflexive"])
        self.your = set(w["second_person_possessive"])
        self.positive = set(w["positive_adjective"])
        self.negative = set(w["negative_adjective"])
        self.neutral = set(w["neutral_adjective"])
        self.nouns = {
            sign: _phrases(w[name])
            for sign, name in (
                (1, "positive_noun"),
                (0, "neutral_noun"),
                (-1, "negative_noun"),
            )
        }
        self.cast_words = _phrases(w["character"])
        self.nothing = set(w["nothing"])
        self.better = set(w["positive_comparative"])
        self.worse = set(w["negative_comparative"])
        self.cast: dict[tuple[str, ...], int] = {}
        self.ops: list[Op] = []
        self.gotos: list[tuple[int, int, int, int]] = []
        self.labels: dict[tuple[int, int], int] = {}
        self.act = 0

    # -- token helpers -------------------------------------------------

    def peek(self, ahead: int = 0) -> str:
        i = self.pos + ahead
        return self.words[i] if i < len(self.words) else ""

    def fail(self, message: str, hint: str) -> Exception:
        i = min(self.pos, len(self.words) - 1)
        line = self.lines[i] if self.words else 1
        return syntax_error(f"Shakespeare line {line}: {message}", hint)

    def expect(self, *words: str) -> None:
        for word in words:
            if self.peek() != word:
                found = self.peek() or "the end of the source"
                raise self.fail(
                    f"expected {word!r}, found {found!r}",
                    "follow the play grammar on the esolangs wiki",
                )
            self.pos += 1

    def take(self, words: tuple[str, ...]) -> bool:
        if tuple(self.words[self.pos : self.pos + len(words)]) == words:
            self.pos += len(words)
            return True
        return False

    def phrase(self, table: dict[str, list[tuple[str, ...]]]) -> tuple[str, ...] | None:
        for option in table.get(self.peek(), ()):
            if self.take(option):
                return option
        return None

    def skip_to(self, stop: str) -> int:
        """Skip to the first ``stop`` token, consume it, return the count skipped."""
        start = self.pos
        while self.peek() != stop:
            if self.pos >= len(self.words):
                raise self.fail(f"missing {stop!r}", f"end the sentence with {stop!r}")
            self.pos += 1
        self.pos += 1
        return self.pos - 1 - start

    def end_of_sentence(self) -> None:
        if self.peek() not in ("!", "."):
            raise self.fail(
                f"expected '.' or '!', found {self.peek() or 'the end'!r}",
                "end the sentence with '.' or '!'",
            )
        self.pos += 1

    # -- the play ------------------------------------------------------

    def play(self) -> None:
        if self.pos >= len(self.words):
            raise self.fail("empty play", "begin with a title ending in '.'")
        first = self.lines[self.pos]
        if not self.skip_to(".") or self.lines[self.pos - 1] != first:
            raise self.fail(
                "the title must be non-empty and end on its line",
                "write the title on one line, ending in '.'",
            )
        while self.peek() != "act":
            self.persona()
        if not self.cast:
            raise self.fail("no characters", "introduce at least one character")
        while self.pos < len(self.words):
            self.act_()
        if not self.act:
            raise self.fail("no acts", "write at least one 'Act I: ...'")
        self.resolve_gotos()

    def character(self, *, optional: bool = False) -> tuple[str, ...] | None:
        name = self.phrase(self.cast_words)
        if name is None and not optional:
            raise self.fail(
                f"{self.peek() or 'the end'!r} is not a character",
                "use a name from the Shakespeare word list",
            )
        return name

    def persona(self) -> None:
        name = self.character()
        assert name is not None
        self.expect(",")
        if not self.skip_to("."):
            raise self.fail(
                "a character description needs a word", "describe the character"
            )
        if name in self.cast:
            raise self.fail(f"{' '.join(name)!r} is introduced twice", "list it once")
        self.cast[name] = len(self.cast)

    def numeral(self, what: str) -> int:
        value = _roman(self.peek())
        if value is None:
            raise self.fail(f"{what} needs a Roman numeral", "write I, II, III ...")
        self.pos += 1
        return value

    def act_(self) -> None:
        self.expect("act")
        number = self.numeral("an act")
        if number != self.act + 1:
            raise self.fail(
                f"act {number} follows act {self.act}", "number acts from I upward"
            )
        self.act = number
        self.expect(":")
        self.skip_to(".")
        if self.peek() != "scene":
            raise self.fail("an act needs a scene", "write 'Scene I: ...'")
        while self.peek() == "scene":
            self.scene()

    def scene(self) -> None:
        self.expect("scene")
        number = self.numeral("a scene")
        if (self.act, number) in self.labels:
            raise self.fail(f"scene {number} appears twice in the act", "number once")
        self.labels[self.act, number] = len(self.ops)
        self.expect(":")
        self.skip_to(".")
        speaker = -1
        while self.peek() not in ("scene", "act", ""):
            if self.peek() == "[":
                self.stage_direction()
                speaker = -1
                continue
            start = self.pos
            name = self.character(optional=True)
            if name is not None and self.peek() == ":":
                self.pos += 1
                speaker = self.index(name)
                continue
            self.pos = start
            if speaker < 0:
                raise self.fail(
                    "a sentence needs a speaker", "put 'Name:' before the line"
                )
            self.ops.append(self.sentence(speaker))

    def index(self, name: tuple[str, ...]) -> int:
        if name not in self.cast:
            raise self.fail(
                f"{' '.join(name)!r} is not in the cast", "introduce them first"
            )
        return self.cast[name]

    def name_list(self) -> tuple[int, ...]:
        names = [self.index(self.character() or ())]
        while self.peek() in (",", "and"):
            self.pos += 1
            names.append(self.index(self.character() or ()))
        return tuple(names)

    def stage_direction(self) -> None:
        self.expect("[")
        word = self.peek()
        self.pos += 1
        if word == "enter":
            self.ops.append(Op("enter", a=self.name_list()))
        elif word == "exit":
            self.ops.append(Op("exit", a=self.index(self.character() or ())))
        elif word == "exeunt":
            names = None if self.peek() == "]" else self.name_list()
            self.ops.append(Op("exeunt", a=names))
        else:
            self.pos -= 1
            raise self.fail(
                f"unknown stage direction {word!r}", "use Enter, Exit or Exeunt"
            )
        self.expect("]")

    # -- sentences -----------------------------------------------------

    def sentence(self, speaker: int) -> Op:
        cond = None
        if self.take(("if",)):
            word = self.peek()
            if word not in ("so", "not"):
                raise self.fail("'If' needs 'so' or 'not'", "write 'If so,'")
            self.pos += 1
            cond = word == "so"
            self.expect(",")
        word = self.peek()
        if word in self.be:
            op = self.question(speaker, cond=cond)
        elif word in self.second:
            op = self.assignment(speaker, cond=cond)
        elif word in ("let", "we"):
            op = self.goto(speaker, cond=cond)
        elif word in ("open", "speak", "listen"):
            op = self.io_sentence(speaker, cond=cond)
        elif word == "remember":
            self.pos += 1
            op = Op("push", speaker, cond, self.value())
            self.end_of_sentence()
        elif word == "recall":
            self.pos += 1
            while self.peek() not in ("!", "."):
                if self.pos >= len(self.words):
                    raise self.fail("missing '!' or '.'", "end the sentence")
                self.pos += 1
            self.end_of_sentence()
            op = Op("pop", speaker, cond)
        else:
            raise self.fail(
                f"{word or 'the end'!r} starts no sentence",
                "see the esolangs wiki for the sentence forms",
            )
        return op

    def question(self, speaker: int, *, cond: bool | None) -> Op:
        self.pos += 1
        left = self.value()
        if self.take(("as",)):
            if self.peek() not in self.positive | self.negative | self.neutral:
                raise self.fail("expected an adjective", "write 'as good as'")
            self.pos += 1
            self.expect("as")
            relation = "eq"
        elif self.peek() in self.better:
            self.pos += 1
            self.expect("than")
            relation = "gt"
        elif self.peek() in self.worse:
            self.pos += 1
            self.expect("than")
            relation = "lt"
        elif self.take(("more",)):
            adjective = self.peek()
            if adjective in self.positive:
                relation = "gt"
            elif adjective in self.negative:
                relation = "lt"
            else:
                raise self.fail("'more' needs a positive or negative adjective", "")
            self.pos += 1
            self.expect("than")
        else:
            raise self.fail(
                "expected a comparison", "write 'better than' or 'as good as'"
            )
        right = self.value()
        self.expect("?")
        return Op("ask", speaker, cond, left, right, relation)

    def assignment(self, speaker: int, *, cond: bool | None) -> Op:
        self.pos += 1
        if self.peek() in self.be:
            self.pos += 1
        if self.take(("as",)):
            if self.peek() not in self.positive | self.negative | self.neutral:
                raise self.fail("expected an adjective", "write 'as good as'")
            self.pos += 1
            self.expect("as")
        value = self.value()
        self.end_of_sentence()
        return Op("set", speaker, cond, value)

    def goto(self, speaker: int, *, cond: bool | None) -> Op:
        opener = (self.peek(), self.peek(1))
        if opener not in _GOTO_OPENERS:
            raise self.fail("expected 'Let us' or 'We shall'", "write 'Let us proceed'")
        self.pos += 2
        if self.peek() not in ("proceed", "return"):
            raise self.fail("expected 'proceed' or 'return'", "write 'proceed to'")
        self.pos += 1
        self.expect("to", "scene")
        line = self.lines[min(self.pos, len(self.lines) - 1)]
        number = self.numeral("a scene")
        self.end_of_sentence()
        self.gotos.append((len(self.ops), self.act, number, line))
        return Op("goto", speaker, cond)

    def io_sentence(self, speaker: int, *, cond: bool | None) -> Op:
        verb = self.peek()
        self.pos += 1
        if verb == "listen":
            self.expect("to")
        if self.peek() not in self.your:
            raise self.fail("expected 'your'", "write 'your heart' or 'your mind'")
        self.pos += 1
        noun = self.peek()
        kinds = {("open", "heart"): "num_out", ("speak", "mind"): "chr_out"}
        kinds |= {("listen", "heart"): "num_in", ("open", "mind"): "chr_in"}
        if (verb, noun) not in kinds:
            raise self.fail(f"{verb} your {noun} is no command", "see the wiki")
        self.pos += 1
        self.end_of_sentence()
        return Op(kinds[verb, noun], speaker, cond)

    # -- values --------------------------------------------------------

    def value(self) -> Expr:
        for words, operator in _BINARY.items():
            if self.take(words):
                left = self.value()
                self.expect("and")
                return ("bin", operator, left, self.value())
        for words, operator in _UNARY.items():
            if self.take(words):
                return ("un", operator, self.value())
        word = self.peek()
        if word in self.first:
            self.pos += 1
            return ("me",)
        if word in self.second:
            self.pos += 1
            return ("you",)
        name = self.character(optional=True)
        if name is not None:
            return ("name", self.index(name))
        if word in self.nothing:
            self.pos += 1
            return ("const", 0)
        return self.noun_phrase()

    def noun_phrase(self) -> Expr:
        if self.peek() in self.articles | self.possessives:
            self.pos += 1
        adjectives = []
        while self.peek() in self.positive | self.negative | self.neutral:
            adjectives.append(self.peek())
            self.pos += 1
        sign = next((s for s, t in self.nouns.items() if self.phrase(t)), None)
        if sign is None:
            raise self.fail(
                f"{self.peek() or 'the end'!r} is not a value",
                "write a noun, a name, 'I' or 'you', or an operation",
            )
        banned = self.negative if sign >= 0 else self.positive
        if any(a in banned for a in adjectives):
            raise self.fail(
                "an adjective of the wrong sign for its noun", "match the sign"
            )
        return ("const", (sign or 1) * 2 ** len(adjectives))

    # -- gotos ---------------------------------------------------------

    def resolve_gotos(self) -> None:
        for index, act, number, line in self.gotos:
            target = self.labels.get((act, number))
            if target is None:
                raise syntax_error(
                    f"Shakespeare line {line}: act {act} has no scene {number}",
                    "a goto names a scene of its own act",
                )
            self.ops[index] = replace(self.ops[index], a=target)


def parse(text: str) -> tuple[int, list[Op]]:
    """Return the cast size and the operations of the play ``text``."""
    parser = _Parser(text)
    try:
        parser.play()
    except RecursionError:
        raise InterpreterLimitError(
            "Shakespeare expression nested too deeply",
            hint="split the expression across sentences",
        ) from None
    return len(parser.cast), parser.ops
