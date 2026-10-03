"""Unified cells and independently split Collatz Multiverse instructions."""

import re


class Reference:
    def __init__(self, code, stdin):
        self.lines = []
        self.cells = {("negativeOne", 0): -1}
        self.pc = 1
        self.stdin = stdin
        self.offset = 0
        self.output = ""
        for text in code.splitlines():
            if not text.strip():
                continue

            def name(value):
                return (
                    bool(value)
                    and value.isascii()
                    and (value[0].isalpha() or value[0] == "_")
                    and all(c.isalnum() or c == "_" for c in value)
                )

            def operand(value):
                value = value.strip()
                index = None
                if "[" in value:
                    value, _, tail = value.partition("[")
                    if not tail.endswith("]"):
                        raise ValueError("bad index")
                    index = tail[:-1]
                    if not name(index):
                        raise ValueError("bad index")
                if not name(value):
                    raise ValueError("bad name")
                return value, index

            target_text, equals, rhs = text.partition("=")
            calculation, comma, printing = rhs.partition(",")
            product, plus, right_text = calculation.partition("+")
            left_text, times, remainder = product.rpartition("x")
            flag = re.fullmatch(r"(DO|NOT)\s+PRINT\.", printing.strip())
            if (
                not equals
                or not comma
                or not plus
                or not times
                or remainder.strip()
                or flag is None
            ):
                raise ValueError("bad instruction")
            target = operand(target_text)
            left = operand(left_text)
            right = operand(right_text)
            flag = flag[1]
            if target[0] == "input":
                raise ValueError("input cannot be redefined")
            self.lines.append((target, left, right, flag))

    @property
    def halted(self):
        return not 1 <= self.pc <= len(self.lines)

    def integer(self):
        token = re.search(r"\S+", self.stdin[self.offset :])
        if token is None:
            self.offset = len(self.stdin)
            raise EOFError
        self.offset += token.end()
        return int(token.group())

    def plain(self, name):
        if name == "input":
            return self.integer()
        if name == "lineNumber":
            return self.pc
        return self.cells.get((name, 0), 0)

    def operand(self, spec):
        name, index = spec
        at = self.plain(index) if index is not None else 0
        if name in ("input", "lineNumber"):
            return self.plain(name), at
        return self.cells.get((name, at), 0), at

    def step(self):
        if self.halted:
            return
        target, left, right, flag = self.lines[self.pc - 1]
        value, at = self.operand(target)
        a, _ = self.operand(left)
        b, _ = self.operand(right)
        value = value * a + b if value == 0 or value % 2 else value // 2
        if target[0] == "lineNumber":
            self.pc = value
        else:
            self.cells[target[0], at] = value
            self.pc += 1
        if flag == "DO":
            self.output += chr(value % 256)
