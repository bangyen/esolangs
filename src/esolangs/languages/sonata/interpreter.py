"""Interpreter for Sonata.

Afarnen's 2010 string-rewriting language.  A program is rules ``lhs->rhs``,
one a line.  The state is one string, initially the input; a step rewrites
it by the first rule, top to bottom, whose left side matches the *whole*
string, and the run halts when no rule matches.  The final string is the
output.

Commands:
    A caret, then a character naming it, is an s-var: any one character.
    An underscore, then a name character, is an m-var: any substring,
    possibly empty.
    Any other character is itself.  M-vars bind left to right, each to the
    shortest substring that still lets the whole left side match.

Input/output:
    The input, less one trailing newline, is the initial string; the final
    string prints at halt.

Errors:
    ProgramError: a nonblank line with no ``->``, a ``^`` or ``_`` with no
    name after it, a name bound twice on one left side, and a right side
    naming a variable its left side does not bind.

Decisions:
    * A name bound twice on one left side is refused: the page never says
      whether the two must match equal text.
    * A right side may write a variable with either prefix: ``^A`` and
      ``_A`` both copy what ``A`` bound.
    * A side has no escape, so ``^`` and ``_`` cannot be literal; the first
      ``->`` outside a variable ends the left side, and later ones are
      literal.  Whitespace is literal and blank lines are skipped.
    * A step matches the whole string afresh: the page's whole-string match
      leaves no rewrite site to remember.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

#: ``(kind, text)``: kind ``"="`` a literal character, ``"^"``/``"_"`` a
#: variable named ``text``.
type _Token = tuple[str, str]


@dataclass(frozen=True, slots=True)
class _Rule:
    pattern: re.Pattern[str]
    #: Literal runs and variable names, in order: ``(is_variable, text)``.
    rhs: tuple[tuple[bool, str], ...]


def _side(text: str, line: str, *, stop_at_arrow: bool) -> tuple[list[_Token], int]:
    """Return a side's tokens and where it ended in ``text``."""
    tokens: list[_Token] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char in "^_":
            if i + 1 >= len(text):
                raise syntax_error(
                    f"Sonata {char!r} names no variable in {line!r}",
                    "write the variable's name after it, for example ^A",
                )
            tokens.append((char, text[i + 1]))
            i += 2
        elif stop_at_arrow and text.startswith("->", i):
            return tokens, i
        else:
            tokens.append(("=", char))
            i += 1
    return tokens, i


def _rule(line: str) -> _Rule:
    """Compile one ``lhs->rhs`` line."""
    lhs, end = _side(line, line, stop_at_arrow=True)
    if end >= len(line):
        raise syntax_error(
            f"a Sonata rule needs '->': {line!r}", "write rules as lhs->rhs"
        )
    rhs, _ = _side(line[end + 2 :], line, stop_at_arrow=False)
    names: dict[str, int] = {}
    parts: list[str] = []
    for kind, text in lhs:
        if kind == "=":
            parts.append(re.escape(text))
            continue
        if text in names:
            raise syntax_error(
                f"Sonata variable {text!r} is bound twice in {line!r}",
                "give each variable on a left side its own name",
            )
        names[text] = len(names) + 1
        parts.append("(.)" if kind == "^" else "(.*?)")
    out: list[tuple[bool, str]] = []
    for kind, text in rhs:
        if kind == "=":
            out.append((False, text))
        elif text in names:
            out.append((True, str(names[text])))
        else:
            raise syntax_error(
                f"Sonata variable {text!r} is not bound on the left of {line!r}",
                "use only variables the left side binds",
            )
    return _Rule(re.compile("".join(parts), re.S), tuple(out))


def _parse(code: str) -> tuple[_Rule, ...]:
    return tuple(_rule(line) for line in code.split("\n") if line.strip())


def _advance(rules: tuple[_Rule, ...], text: str) -> str | None:
    """Return the string after one rewrite, or ``None`` when none applies."""
    for rule in rules:
        match = rule.pattern.fullmatch(text)
        if match is not None:
            return "".join(
                match.group(int(part)) if variable else part
                for variable, part in rule.rhs
            )
    return None


class _Machine:
    """The rules, the string, and whether the run is over."""

    #: The state is a string; ``ip`` is its length.
    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.rules = _parse(code)
        text = io.input_all()
        self.text = text.removesuffix("\n")
        self.halted = False
        self.rendered = False

    @property
    def ip(self) -> tuple[int, ...]:
        """The string's length."""
        return (len(self.text),)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (self.text, self.halted, self.rendered)

    def step(self) -> None:
        """Rewrite once; the step that finds no rule halts and prints."""
        if not self.halted:
            text = _advance(self.rules, self.text)
            if text is None:
                self.halted = True
            else:
                self.text = text
        if self.halted and not self.rendered:
            self.io.print_str(self.text)
            self.rendered = True


def run(code: str, io: IO) -> None:
    """Run a Sonata program on its input and print the final string."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
