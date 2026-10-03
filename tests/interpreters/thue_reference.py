"""Independent Thue rule parsing, occurrence enumeration and substitution."""

import re


class Reference:
    def __init__(self, source, stdin=""):
        separator = re.search(r"(?m)^[^\S\n]*::=[^\S\n]*(?:\n|$)", source)
        if separator is None:
            raise ValueError("missing separator")
        self.rules = []
        prefix = source[: separator.start()]
        for match in re.finditer(r"([^\n]*)\n", prefix):
            line = match.group(1)
            delimiter = line.find("::=")
            if delimiter <= 0:
                raise ValueError("invalid rule")
            self.rules.append((line[:delimiter], line[delimiter + 3 :]))
        self.by_first = {}
        for index, (left, _) in enumerate(self.rules):
            self.by_first.setdefault(left[0], []).append((index, left))
        self.state = source[separator.end() :]
        self.stdin = stdin
        self.offset = 0
        self.output = ""
        self.reads = 0

    def matches(self, state=None):
        text = self.state if state is None else state
        found = []
        for position, character in enumerate(text):
            for rule, left in self.by_first.get(character, ()):
                if text.startswith(left, position):
                    found.append((rule, position))
        return sorted(found)

    def replacement(self, match, line=None):
        rule, position = match
        left, right = self.rules[rule]
        if right == ":::":
            replacement = line
        elif right[:1] == "~":
            replacement = ""
        else:
            replacement = right
        characters = list(self.state)
        characters[position : position + len(left)] = replacement
        return "".join(characters)

    def step(self, choice):
        available = self.matches()
        if not available:
            return
        match = available[choice]
        right = self.rules[match[0]][1]
        line = None
        if right == ":::":
            if self.offset == len(self.stdin):
                raise EOFError
            start = self.offset
            while self.offset < len(self.stdin) and self.stdin[self.offset] != "\n":
                self.offset += 1
            line = self.stdin[start : self.offset]
            if self.offset < len(self.stdin):
                self.offset += 1
            line = line[:-1] if line.endswith("\r") else line
            self.reads += 1
        self.state = self.replacement(match, line)
        if right[:1] == "~":
            self.output += right[1:] or "\n"

    def successors(self):
        available = self.matches()
        if any(self.rules[index][1] == ":::" for index, _ in available):
            return None
        return tuple(self.replacement(match) for match in available)
