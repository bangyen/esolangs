"""Independent token grammar for finite Forbin fixtures; never imports native code."""
# Source-only draft API: concise names are shared with the root price driver.

from dataclasses import dataclass


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Function:
    name: str
    args: tuple[str, ...]
    site: int
    body: tuple
    nested: tuple


@dataclass(frozen=True)
class Program:
    source: str
    functions: tuple[Function, ...]
    initializers: tuple


def tokens(source):
    result = []
    index = 0
    while index < len(source):
        char = source[index]
        if char in " \t\r\n":
            index += 1
        elif source.startswith("//", index):
            while index < len(source) and source[index] not in "\r\n":
                index += 1
        elif char.isalpha() or char == "_":
            end = index + 1
            while end < len(source) and (source[end].isalnum() or source[end] == "_"):
                end += 1
            result.append(Token(source[index:end], index, end))
            index = end
        elif source.startswith("..", index):
            result.append(Token("..", index, index + 2))
            index += 2
        elif char in "01!{}(),;:=@*":
            result.append(Token(char, index, index + 1))
            index += 1
        else:
            raise ValueError(("character", index, char))
    result.append(Token("", len(source), len(source)))
    return result


class Reader:
    def __init__(self, source):
        self.source = source
        self.items = tokens(source)
        self.index = 0
        self.definitions = []

    def peek(self):
        return self.items[self.index].text

    def take(self, wanted=None):
        item = self.items[self.index]
        if wanted is not None and item.text != wanted:
            raise ValueError(("expected", wanted, item.start))
        self.index += 1
        return item

    def name(self):
        text = self.peek()
        if not text or not (text[0].isalpha() or text[0] == "_"):
            raise ValueError(("identifier", self.items[self.index].start))
        return self.take().text

    def definition_ahead(self):
        cursor = self.index
        if not self.peek() or not (self.peek()[0].isalpha() or self.peek()[0] == "_"):
            return False
        cursor += 1
        while True:
            text = self.items[cursor].text
            if text == "{":
                return True
            if text == ",":
                cursor += 1
                text = self.items[cursor].text
                if text == "{":
                    return True
            if text and (text[0].isalpha() or text[0] == "_"):
                cursor += 1
            else:
                return False

    def function(self, name, args, site=None):
        # Named/bare definitions use the brace; parameter literals use after @.
        if site is None:
            site = self.items[self.index].start
        body, nested = self.block()
        return Function(name, tuple(args), site, body, nested)

    def named(self):
        name = self.name()
        args = []
        while self.peek() != "{":
            if self.peek() == ",":
                self.take()
                if self.peek() == "{":
                    break
            args.append(self.name())
        return self.function(name, args)

    def block(self):
        self.take("{")
        nested = {}
        statements = []
        self.definitions.append(nested)
        while self.peek() != "}":
            if not self.peek():
                raise ValueError("unterminated block")
            if self.definition_ahead():
                fn = self.named()
                nested[fn.name] = fn
            else:
                statements.append(self.statement())
        self.take("}")
        self.definitions.pop()
        return tuple(statements), tuple(nested.items())

    def separated(self, read):
        result = []
        if self.peek() != ")":
            result.append(read())
            while self.peek() == ",":
                self.take()
                result.append(read())
        self.take(")")
        return tuple(result)

    def value(self):
        symbol = self.peek()
        if symbol in ("0", "1"):
            return ("bit", int(self.take().text))
        if symbol == "!":
            self.take()
            return ("not", self.value())
        if symbol == "{":
            return ("function", self.function("", ()))
        if symbol == "(":
            self.take()
            saved = self.index
            names = [self.name()]
            while self.peek() == ",":
                self.take()
                names.append(self.name())
            if self.peek() == "@":
                marker = self.take()
                fn = self.function("", names, marker.end)
                self.take(")")
                return ("function", fn)
            self.index = saved
            callee = ("name", self.name())
            return ("call", callee, self.separated(self.value))
        return ("name", self.name())

    def values(self):
        result = [self.value()]
        while self.peek() == ",":
            self.take()
            result.append(self.value())
        return tuple(result)

    def pattern(self):
        if self.peek() == "*":
            self.take()
            return None
        return self.value()

    def spec(self):
        if self.peek() == "(":
            self.take()
            names = self.separated(self.name)
        else:
            names = (self.name(),)
        self.take(":")
        if self.peek() != "(":
            start = self.value()
            self.take("..")
            return ("range", names[0], start, self.value())
        self.take()
        if len(names) > 1 and self.peek() != "(":
            groups = (self.separated(self.pattern),)
        elif len(names) == 1:
            groups = tuple((item,) for item in self.separated(self.pattern))
        else:

            def group():
                self.take("(")
                return self.separated(self.pattern)

            groups = self.separated(group)
        return ("rows", names, groups)

    def statement(self):
        if self.peek() == "return":
            self.take()
            result = ("return", self.value())
        elif self.peek() == "for":
            self.take()
            spec = self.spec()
            body, definitions = self.block()
            self.definitions[-1].update(definitions)
            result = ("for", spec, body)
        else:
            first = self.value()
            if self.peek() in ("=", ","):
                targets = [first]
                while self.peek() == ",":
                    self.take()
                    targets.append(self.value())
                self.take("=")
                if any(item[0] != "name" for item in targets):
                    raise ValueError("assignment target")
                result = ("assign", tuple(item[1] for item in targets), self.values())
            else:
                if first[0] not in ("name", "call", "function"):
                    raise ValueError("statement")
                symbol = self.peek()
                args = (
                    self.values()
                    if symbol
                    and (symbol[0].isalpha() or symbol[0] == "_" or symbol in "01!(_")
                    else ()
                )
                result = ("call", first, args)
        if self.peek() == ";":
            self.take()
        return result

    def program(self):
        functions = {}
        initializers = []
        while self.peek():
            if self.definition_ahead():
                fn = self.named()
                functions[fn.name] = fn
            else:
                initializers.append(self.statement())
                if initializers[-1][0] != "assign":
                    raise ValueError("top-level assignment")
        if "main" not in functions:
            raise ValueError("missing main")
        return Program(self.source, tuple(functions.values()), tuple(initializers))
