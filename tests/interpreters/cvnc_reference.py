"""Syntax-first CV(N)(C) function evaluation through Python's expression AST."""

# ruff: noqa: RUF001 -- IPA commands are the language alphabet.

import ast

from esolangs.exceptions import HaltError


def applied(accumulator: int, function: tuple[str, ...]) -> int:
    """Evaluate unsigned binary arithmetic; invalid syntax leaves the input."""
    try:
        tree = ast.parse(" ".join(function).replace("/", "//"), mode="eval")
    except (SyntaxError, ValueError):
        return accumulator
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.FloorDiv,
        ast.Constant,
        ast.Name,
        ast.Load,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            return accumulator
        if isinstance(node, ast.Name) and node.id != "a":
            return accumulator
        if isinstance(node, ast.Constant) and (
            type(node.value) is not int or node.value < 0
        ):
            return accumulator

    def evaluate(node: ast.expr) -> int:
        if isinstance(node, ast.Name):
            return accumulator
        if isinstance(node, ast.Constant):
            return int(node.value)
        assert isinstance(node, ast.BinOp)
        left = evaluate(node.left)
        right = evaluate(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return max(0, left - right)
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            raise HaltError("division by zero")
        return left // right

    return evaluate(tree.body)


class Reference:
    """Independent regex syllables and mutable command-by-command execution."""

    def __init__(self, source: str, stdin: str = "") -> None:
        import re

        self.source = source.replace("\n", "").replace("g", "ɡ")
        consonant = r"(?:ɰ̊|ɰ(?!̊)|[θfsʒpkdbtɡqʔʡcɹjʋ])"
        vowel = r"[iəæou]"
        syllable = re.compile(
            consonant + vowel + r"[mnŋɲ]?(?:" + consonant + r"(?!" + vowel + r"))?"
        )
        spans = []
        offset = 0
        while offset < len(self.source):
            match = syllable.match(self.source, offset)
            if match is None:
                raise ValueError("invalid syllable")
            spans.append(offset)
            offset = match.end()
        if not spans:
            raise ValueError("empty source")
        matches = list(re.finditer(r"ɰ̊|.", self.source))
        self.tokens = [match.group() for match in matches]
        self.offsets = [match.start() for match in matches]
        self.starts = [self.offsets.index(start) for start in spans]
        self.pairs = {}
        pending = []
        for index, token in enumerate(self.tokens):
            if token in ("ɰ", "ɰ̊"):
                pending.append(index)
            elif token == "ʋ":
                if not pending:
                    raise ValueError("unmatched end")
                opener = pending.pop()
                self.pairs[index] = opener
                self.pairs[opener] = index
        if pending:
            raise ValueError("unmatched start")
        self.accumulator = 0
        self.deque = []
        self.function = []
        self.pointer = 0
        self.stdin = stdin
        self.offset = 0
        self.output = ""

    @property
    def halted(self):
        return self.pointer >= len(self.tokens)

    def step(self):
        import bisect
        import math

        if self.halted:
            return
        token = self.tokens[self.pointer]
        self.pointer += 1
        if token in ("s", "ʒ"):
            if token == "s":
                while (
                    self.offset < len(self.stdin) and self.stdin[self.offset].isspace()
                ):
                    self.offset += 1
            if self.offset == len(self.stdin):
                raise EOFError
            start = self.offset
            self.offset += 1
            if token == "s":
                while (
                    self.offset < len(self.stdin)
                    and not self.stdin[self.offset].isspace()
                ):
                    self.offset += 1
                try:
                    value = int(self.stdin[start : self.offset])
                except ValueError:
                    value = 0
                self.accumulator = max(0, value)
            else:
                self.accumulator = ord(self.stdin[start]) % 256
        elif token == "θ":
            self.output += str(self.accumulator)
        elif token == "f":
            self.output += chr(self.accumulator % 256)
        elif token == "c":
            self.function.clear()
        elif token in "dbtɡqʔʡ":
            self.function.append(dict(zip("dbtɡqʔʡ", "a+-*/()", strict=True))[token])
        elif token in "pkŋɲ":
            if not self.deque:
                raise HaltError("empty deque")
            value = self.deque.pop(0 if token in "pŋ" else -1)
            if token in "pk":
                self.function.append(str(value))
            else:
                self.accumulator = value
        elif token == "m":
            self.deque.insert(0, self.accumulator)
        elif token == "n":
            self.deque.append(self.accumulator)
        elif token == "i":
            self.accumulator += 1
        elif token == "ə":
            self.accumulator = max(0, self.accumulator - 1)
        elif token == "æ":
            self.accumulator **= 2
        elif token == "o":
            self.accumulator = math.isqrt(self.accumulator)
        elif token == "u":
            self.accumulator = applied(self.accumulator, tuple(self.function))
        elif token == "ɹ":
            self.pointer = (
                bisect.bisect_right(self.offsets, self.accumulator) - 1
                if self.accumulator < len(self.source)
                else len(self.tokens)
            )
        elif token == "j":
            self.pointer = (
                self.starts[self.accumulator]
                if self.accumulator < len(self.starts)
                else len(self.tokens)
            )
        elif token == "ʋ":
            self.pointer = self.pairs[self.pointer - 1]
        elif (token == "ɰ̊" and self.accumulator == 0) or (
            token == "ɰ" and self.accumulator != 0
        ):
            self.pointer = self.pairs[self.pointer - 1] + 1
