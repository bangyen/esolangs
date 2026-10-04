"""Independent statement scheduler for the supported scalar INTERCAL core."""

import re

from tests.interpreters.intercal_expression import InvalidError, expression

WORDS = {
    name: str(n)
    for n, name in enumerate(
        ("ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE")
    )
} | {"OH": "0", "NINER": "9"}


def roman(number):
    if not 0 <= number < 2**32:
        raise InvalidError("output range")

    def digit(n, one, five, ten):
        if n < 4:
            return one * n
        if n == 4:
            return one + five
        if n < 9:
            return five + one * (n - 5)
        return one + ten

    glyphs = []
    bars = []
    for place, char in reversed(list(enumerate(str(number)[::-1]))):
        n = int(char)
        group, column = divmod(place, 3)
        if column == 0 and group and n < 4:
            text = "M" * n
            group -= 1
        else:
            one, five, ten = ("IVX", "XLC", "CDM")[column]
            text = digit(n, one, five, ten)
        if group >= 2:
            text = text.lower()
        glyphs.append(text)
        bars.append(("_" if group % 2 else " ") * len(text))
    head = "".join(bars)
    body = "".join(glyphs)
    return head + "\n" + body if "_" in head else body


def statements(source):
    matches = list(
        re.finditer(r"\([0-9]+\)|DON'T|[A-Z]+|[.#][&V?]?[0-9]+|<-|[^\s]", source)
    )
    result = []
    current = []
    i = 0
    identifiers = (["PLEASE"], ["PLEASE", "DO"], ["DO"], ["DO", "NOT"], ["DON'T"])
    while i < len(matches):
        match = matches[i]
        token = match[0]
        line_start = source.rfind("\n", 0, match.start()) + 1
        physical_start = not source[line_start : match.start()].strip()
        line_end = source.find("\n", match.start())
        if line_end < 0:
            line_end = len(source)
        physical_line = source[match.start() : line_end]
        command_start = bool(
            re.match(
                r"(?:\.[0-9]+\s*<-|READ\s+OUT|WRITE\s+IN|GIVE\s+UP|RESUME\b|FORGET\b|\([0-9]+\)\s+NEXT)",
                physical_line,
            )
        )
        prefix = current[1:] if current and current[0].startswith("(") else current
        if physical_start and command_start and current and prefix not in identifiers:
            result.append(current)
            current = []
        if token in ("PLEASE", "DO", "DON'T"):
            label = None
            if current and current[-1].startswith("("):
                label = current.pop()
            if current:
                result.append(current)
            current = [] if label is None else [label]
            current.append(token)
            i += 1
            if token == "PLEASE" and i < len(matches) and matches[i][0] == "DO":
                current.append(matches[i][0])
                i += 1
            if token == "DO" and i < len(matches) and matches[i][0] == "NOT":
                current.append(matches[i][0])
                i += 1
        else:
            current.append(token)
            i += 1
    if current:
        result.append(current)
    return result


class Reference:
    def __init__(self, source, text=""):
        self.program = statements(source)
        self.labels = {}
        self.instructions = []
        polite = 0
        for row, tokens in enumerate(self.program):
            tokens = list(tokens)
            if tokens and tokens[0].startswith("("):
                label = int(tokens.pop(0)[1:-1])
                if not 1 <= label <= 65535 or label in self.labels:
                    raise InvalidError("label")
                self.labels[label] = row
            if not tokens:
                raise InvalidError("statement")
            prefix = tokens.pop(0)
            inactive = prefix == "DON'T"
            if prefix == "PLEASE":
                polite += 1
                if tokens and tokens[0] == "DO":
                    tokens.pop(0)
            elif prefix == "DO":
                if tokens and tokens[0] == "NOT":
                    tokens.pop(0)
                    inactive = True
            elif prefix != "DON'T":
                tokens.insert(0, prefix)
            self.instructions.append((inactive, tokens))
        if (
            not self.instructions
            or not len(self.instructions) <= polite * 5
            or polite * 3 > len(self.instructions)
        ):
            raise InvalidError("politeness")
        self.cursor = 0
        self.variables = {}
        self.calls = []
        self.text = text
        self.position = 0
        self.reads = 0
        self.output = ""

    @property
    def halted(self):
        return self.cursor >= len(self.instructions)

    def read(self):
        if self.position == len(self.text):
            raise EOFError
        end = self.text.find("\n", self.position)
        if end < 0:
            end = len(self.text)
            stop = end
        else:
            stop = end + 1
        text = self.text[self.position : end].removesuffix("\r")
        self.position = stop
        self.reads += 1
        words = text.upper().split()
        if not words or any(word not in WORDS for word in words):
            raise InvalidError("numeric input")
        value = 0
        for word in words:
            value = 10 * value + int(WORDS[word])
            if value > 65535:
                raise InvalidError("input range")
        return value

    def variable(self, token):
        if not re.fullmatch(r"\.[0-9]+", token):
            raise InvalidError("target")
        name = int(token[1:])
        if not 1 <= name <= 65535:
            raise InvalidError("target range")
        return name

    def step(self):
        if self.halted:
            return
        inactive, tokens = self.instructions[self.cursor]
        next_cursor = self.cursor + 1
        variables = dict(self.variables)
        calls = list(self.calls)
        if not inactive:
            if len(tokens) >= 3 and tokens[1] == "<-":
                target = self.variable(tokens[0])
                result, _width = expression(" ".join(tokens[2:]), variables)
                if result > 65535:
                    raise InvalidError("assignment range")
                variables[target] = result
            elif tokens[:2] == ["READ", "OUT"]:
                result, _width = expression(" ".join(tokens[2:]), variables)
                self.output += roman(result) + "\n"
            elif tokens[:2] == ["WRITE", "IN"]:
                if len(tokens) != 3:
                    raise InvalidError("input syntax")
                target = self.variable(tokens[2])
                variables[target] = self.read()
            elif len(tokens) == 2 and tokens[0].startswith("(") and tokens[1] == "NEXT":
                label = int(tokens[0][1:-1])
                if label not in self.labels or len(calls) == 80:
                    raise InvalidError("NEXT")
                calls.append(next_cursor)
                next_cursor = self.labels[label]
            elif tokens and tokens[0] in ("RESUME", "FORGET"):
                count, _width = expression(" ".join(tokens[1:]), variables)
                if tokens[0] == "RESUME":
                    if not 1 <= count <= len(calls):
                        raise InvalidError("RESUME")
                    next_cursor = calls[-count]
                if count:
                    calls = calls[: max(0, len(calls) - count)]
            elif tokens == ["GIVE", "UP"]:
                next_cursor = len(self.instructions)
            else:
                raise InvalidError("unsupported")
        self.cursor = next_cursor
        self.variables = variables
        self.calls = calls
