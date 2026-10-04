"""Independent delimiter-object Inject model, wiki156916 and declared profile."""

import re
from dataclasses import dataclass


class InvalidError(Exception):
    pass


@dataclass(eq=False)
class Line:
    text: str


def label(text):
    text = text.strip()
    if not text.endswith(";"):
        return None
    name = text[:-1]
    return name if name and all(c.isalnum() or c == "_" for c in name) else None


class Reference:
    def __init__(self, source, text=""):
        values = source.split("\n") if isinstance(source, str) else list(source)
        self.lines = [Line(value) for value in values]
        occurrences = {}
        for node in self.lines:
            name = label(node.text)
            if name is not None:
                occurrences.setdefault(name, []).append(node)
        if any(len(nodes) != 2 for nodes in occurrences.values()):
            raise ValueError("label multiplicity")
        # Closing order defines ties between equally short overlapping spans.
        self.blocks = dict(
            sorted(occurrences.items(), key=lambda item: self.lines.index(item[1][1]))
        )
        self.indices = {node: index for index, node in enumerate(self.lines)}
        self.cursor = 0
        self.done = False
        self.text = text
        self.position = 0
        self.reads = 0
        self.output = ""

    def span(self, name):
        if name not in self.blocks:
            raise ValueError("unknown label")
        opening, closing = self.blocks[name]
        return self.indices[opening], self.indices[closing]

    def contents(self, name):
        opening, closing = self.span(name)
        return [node.text for node in self.lines[opening + 1 : closing]]

    def read(self):
        if self.position == len(self.text):
            raise EOFError
        end = self.text.find("\n", self.position)
        if end < 0:
            end = len(self.text)
            stop = end
        else:
            stop = end + 1
        value = self.text[self.position : end].removesuffix("\r")
        self.position = stop
        self.reads += 1
        return value

    def overwrite(self, name, values):
        opening, closing = self.span(name)
        removed = self.lines[opening + 1 : closing]
        delta = len(values) - len(removed)
        if delta:
            anchors = {node for pair in self.blocks.values() for node in pair}
            if any(node in anchors for node in removed):
                raise InvalidError("deleted delimiter")
            if self.cursor > opening:
                new_cursor = self.cursor + delta
                if new_cursor + 1 < 0:
                    raise InvalidError("negative cursor")
                self.cursor = new_cursor
            self.lines[opening + 1 : closing] = [Line(value) for value in values]
            self.indices = {node: index for index, node in enumerate(self.lines)}
        else:
            for node, value in zip(removed, values, strict=True):
                node.text = value

    def skip(self):
        ahead = self.cursor + 1
        if ahead < len(self.lines):
            name = label(self.lines[ahead].text)
            if name in self.blocks and self.span(name)[0] == ahead:
                self.cursor = self.span(name)[1] + 1
                return
        containing = [
            name
            for name in self.blocks
            if self.span(name)[0] < self.cursor < self.span(name)[1]
        ]
        if containing:
            name = min(
                containing, key=lambda name: self.span(name)[1] - self.span(name)[0]
            )
            self.cursor = self.span(name)[0]
        else:
            self.done = True

    @property
    def halted(self):
        return self.done or self.cursor >= len(self.lines)

    def step(self):
        if self.halted:
            return
        raw = self.lines[self.cursor].text.strip()
        op, _separator, args = raw.partition(" ")
        args = args.strip()
        if not raw or label(raw) is not None:
            self.cursor += 1
            return
        if op == "send":
            self.output += "".join(line + "\n" for line in self.contents(args))
        elif op == "readto":
            value = self.read()
            self.overwrite(args, [value] if value else [])
        elif op == "inject":
            name, equals, expression = args.partition("=")
            if not equals:
                raise ValueError("inject syntax")
            pattern, slash, replacement = expression.partition("/")
            if not slash:
                raise ValueError("replacement syntax")
            try:
                compiled = re.compile(pattern)
            except re.error:
                raise InvalidError("regex") from None
            try:
                values = [
                    compiled.sub(replacement, line) for line in self.contents(name)
                ]
            except (re.error, IndexError):
                raise InvalidError("replacement") from None
            self.overwrite(name, values)
        elif op == "skip":
            if args:
                raise ValueError("skip syntax")
            self.skip()
            return
        elif op == "skipif":
            if self.contents(args):
                self.skip()
                return
        elif op == "skipq":
            left, _space, right = args.partition(" ")
            right = right.strip()
            if not left or not right:
                raise ValueError("skipq syntax")
            if self.contents(left) == self.contents(right):
                self.skip()
                return
        self.cursor += 1
