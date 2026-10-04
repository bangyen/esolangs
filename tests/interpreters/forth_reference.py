"""Independent recursive Forþ evaluator; repository integer/error profile."""


class EmptyError(Exception):
    pass


class ExhaustedError(Exception):
    pass


class LimitError(Exception):
    pass


class Reference:
    def __init__(self, text=""):
        self.stack = []
        self.functions = {}
        parts = text.split("\n")
        if text.endswith("\n"):
            parts.pop()
        self.lines = iter(parts if text else [])
        self.output = ""
        self.commands = 0
        self.reads = 0

    def top(self):
        if not self.stack:
            raise EmptyError
        return self.stack[-1]

    def execute(self, source):
        cursor = 0
        while cursor < len(source):
            self.commands += 1
            if self.commands > 10000:
                raise LimitError
            command = source[cursor]
            cursor += 1
            if command in "0123456789ABCDEF":
                self.stack.append(int(command, 16))
            elif command == ":":
                self.stack.append(self.top())
            elif command == "~":
                self.stack[-1] = ~self.top()
            elif command == ".":
                value = self.top()
                self.stack.pop()
                if value < 0 or value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                    value &= 255
                self.output += chr(value)
            elif command == ",":
                try:
                    line = next(self.lines)
                except StopIteration:
                    raise ExhaustedError from None
                self.reads += 1
                if line.endswith("\n"):
                    line = line[:-1]
                line = line.removesuffix("\r")
                self.stack.extend(map(ord, line))
            elif command == "o":
                self.stack.reverse()
            elif command == "c":
                if len(self.stack) < 3:
                    return False
                self.stack[-3:] = self.stack[-2:] + self.stack[-3:-2]
            elif command in "+-*/%v":
                if len(self.stack) < 2:
                    return False
                right = self.stack.pop()
                left = self.stack.pop()
                if command == "v":
                    self.stack.extend((right, left))
                    continue
                if command in "/%" and right == 0:
                    return False
                if command == "+":
                    value = left + right
                elif command == "-":
                    value = left - right
                elif command == "*":
                    value = left * right
                else:
                    q = abs(left) // abs(right)
                    if (left < 0) != (right < 0):
                        q = -q
                    value = q if command == "/" else left - q * right
                value &= 0xFFFFFFFF
                self.stack.append(value if value < 0x80000000 else value - 0x100000000)
            elif command == ";":
                key = self.top()
                self.stack.pop()
                self.execute(self.functions.get(key, ""))
            elif command in "([{":
                closing = dict(zip("([{", ")]}", strict=True))[command]
                depth = 1
                start = cursor
                while cursor < len(source) and depth:
                    token = source[cursor]
                    depth += (token == command) - (token == closing)
                    cursor += 1
                if depth:
                    return False
                body = source[start : cursor - 1]
                if command == "{":
                    self.functions[self.top()] = body
                elif command == "(":
                    if self.top():
                        self.execute(body)
                else:
                    while self.top():
                        self.execute(body)
        return True
