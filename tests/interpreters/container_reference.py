"""Synchronous nonnegative rule equations from Container revision135848."""

import re
from collections import deque
from unicodedata import decimal


def integer(text):
    sign = -1 if text.startswith("-") else 1
    digits = text[1:] if text[:1] in "+-" else text
    if not digits:
        raise ValueError("empty integer")
    value = 0
    for char in digits:
        value = 10 * value + decimal(char)
    return sign * value


class Reference:
    def __init__(self, lines, stdin=""):
        self.values = {}
        self.rules = {}
        current = None
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.endswith(":"):
                head = line[:-1]
                name, separator, initial = head.partition("=")
                if name in self.values:
                    raise ValueError("duplicate container")
                value = integer(initial) if separator else 0
                if value < 0:
                    raise ValueError("initial value must be nonnegative")
                self.values[name] = value
                self.rules[name] = []
                current = name
            else:
                if current is None:
                    raise ValueError("rule before declaration")
                match = re.fullmatch(r"([+-]?\d+)\s+(.*?)\s*(<=|>=)\s*(.*?)", line)
                if match is None:
                    raise ValueError("invalid rule")
                delta, left, operation, right = match.groups()
                self.rules[current].append((integer(delta), left, operation, right))
        self.stdin = stdin
        self.offset = 0
        self.reads = 0
        self.past_end = 0
        self.queue = deque()
        self.output = ""
        self.exit_code = None
        self.tick = 0

    @property
    def halted(self):
        return self.exit_code is not None or not self.rules

    def step(self):
        if self.halted:
            return
        old = self.values

        def term(text):
            return old[text] if text in old else integer(text)

        updated = {}
        for name, rules in self.rules.items():
            delta = sum(
                amount
                for amount, left, operation, right in rules
                if (
                    term(left) <= term(right)
                    if operation == "<="
                    else term(left) >= term(right)
                )
            )
            updated[name] = max(0, old[name] + delta)
        if old.get("PRINT") == 0 and updated["PRINT"] > 0 and "OUT" in old:
            self.output += chr(updated["OUT"] % 128)
        if old.get("") == 0 and updated[""] > 0:
            if self.queue:
                char = self.queue.popleft()
                value = ord(char)
            elif self.offset < len(self.stdin):
                value = ord(self.stdin[self.offset])
                self.offset += 1
                self.reads += 1
            else:
                value = 0
                self.past_end += 1
            updated["IN"] = value
        if "EXIT" in old and updated["EXIT"] != old["EXIT"]:
            self.exit_code = updated["EXIT"]
        self.values = updated
        self.tick += 1

    def snapshot(self):
        return (
            tuple(sorted(self.values.items())),
            tuple(self.queue),
            self.exit_code,
            self.offset,
            self.reads,
        )
