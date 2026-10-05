"""Independent bracket lexer and mutable Modulous scheduler."""


class InvalidError(Exception):
    pass


def modules(source):
    result = []
    position = 0
    while position < len(source):
        if source[position].isspace():
            position += 1
            continue
        if source[position] != "[":
            raise ValueError("stray text")
        position += 1
        start = position
        quoted = False
        closed = False
        while position < len(source):
            char = source[position]
            if char == '"':
                if closed:
                    raise ValueError("multiple quoted payloads")
                quoted = not quoted
                if not quoted:
                    closed = True
            elif closed and char != "]" and not char.isspace():
                raise ValueError("text after quoted payload")
            elif not quoted and char == "[":
                raise ValueError("nested module")
            elif not quoted and char == "]":
                break
            position += 1
        if position == len(source):
            raise ValueError("unclosed module")
        result.append(source[start:position])
        position += 1
    return tuple(result)


class Reference:
    def __init__(self, source, text=""):
        self.program = modules(source)
        self.stack = []
        self.variables = {f"VAR{i}": 0 for i in range(1, 5)}
        self.cursor = 0
        self.done = False
        self.text = text
        self.position = 0
        self.reads = 0
        self.draws = 0
        self.output = ""

    @property
    def halted(self):
        return self.done or self.cursor >= len(self.program)

    def top(self):
        if not self.stack:
            raise InvalidError("empty stack")
        return self.stack[-1]

    def named(self, name):
        if name not in self.variables:
            raise InvalidError("variable")
        return self.variables[name]

    def operand(self, words, index):
        try:
            return words[index]
        except IndexError:
            raise ValueError("operand") from None

    def read(self, numeric):
        if numeric:
            while self.position < len(self.text) and self.text[self.position].isspace():
                self.position += 1
            start = self.position
            while (
                self.position < len(self.text)
                and not self.text[self.position].isspace()
            ):
                self.position += 1
            if start == self.position:
                raise EOFError
            result = self.text[start : self.position]
        else:
            if self.position == len(self.text):
                raise EOFError
            start = self.position
            end = self.text.find("\n", start)
            if end < 0:
                end = len(self.text)
                self.position = end
            else:
                self.position = end + 1
            result = self.text[start:end].removesuffix("\r")
        self.reads += 1
        return result

    def step(self, draw=0):
        if self.halted:
            return
        if self.cursor < 0:
            self.cursor %= len(self.program)
        origin = self.cursor
        module = self.program[origin]
        self.cursor += 1
        words = module.split()
        if not words:
            return
        op = words[0]
        if op == "PSH":
            kind = self.operand(words, 1)
            if kind == "INT":
                self.stack.append(int(self.operand(words, 2)))
            elif kind == "STR":
                first = module.find('"')
                last = module.rfind('"')
                if first < 0 or first == last:
                    raise ValueError("string")
                self.stack.extend(ord(c) for c in reversed(module[first + 1 : last]))
            elif kind.startswith("VAR"):
                self.named(kind)
                self.variables[kind] = self.top()
            else:
                raise ValueError("push kind")
        elif op in ("ADD", "SUB"):
            amount = int(self.operand(words, 1))
            value = self.top()
            self.stack[-1] = value + amount if op == "ADD" else value - amount
        elif op == "POP":
            self.top()
            self.stack.pop()
        elif op == "DUP":
            self.stack.append(self.top())
        elif op == "SWP":
            if len(self.stack) < 2:
                raise InvalidError("swap")
            self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
        elif op == "PRT":
            variable = len(words) > 1 and words[1].startswith("VAR")
            value = self.named(words[1]) if variable else self.top()
            self.output += str(value) if "INT" in words else chr(value)
            if not variable:
                self.stack.pop()
        elif op == "INP":
            numeric = "INT" in words
            value = self.read(numeric)
            if numeric:
                self.stack.append(int(value))
            else:
                self.stack.extend(ord(c) for c in reversed(value))
        elif op == "JMP":
            condition = True
            value = self.stack[-1] if self.stack else 0
            if "NIF" in words:
                condition = value != int(words[-1])
            elif "IF" in words:
                condition = value == int(words[-1])
            if condition:
                direction = self.operand(words, 1)
                distance = int(self.operand(words, 2))
                self.cursor = origin + (distance if direction == "F" else -distance)
        elif op == "RST":
            self.cursor = 0
        elif op == "END":
            self.done = True
        elif op == "RND":
            bound = int(self.operand(words, 1))
            if bound < 1:
                raise InvalidError("random bound")
            assert 0 <= draw < bound
            self.draws += 1
            self.stack.append(draw)
        else:
            point = next((i for i, c in enumerate(module) if c in "+-"), None)
            if point is None:
                raise ValueError("unknown command")
            name = module[:point]
            amount = int(module[point + 1 :])
            before = self.named(name)
            self.variables[name] = (
                before + amount if module[point] == "+" else before - amount
            )
