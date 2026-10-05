"""Independent recursive evaluator of Grapheme's declared repository profile."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Function:
    source: str


class InvalidError(Exception):
    pass


class BudgetError(Exception):
    pass


class Reference:
    def __init__(self, text=""):
        self.stack = []
        self.variables = {}
        self.output = ""
        self.text = text
        self.position = 0
        self.reads = 0
        self.commands = 0

    def pop(self):
        if not self.stack:
            raise InvalidError("empty")
        return self.stack.pop()

    def number(self, value):
        if isinstance(value, Function):
            raise InvalidError("function math")
        return value if isinstance(value, int) else ord(value[0]) if value else 0

    def integer(self, value):
        if isinstance(value, int):
            return value
        if isinstance(value, Function):
            return len(value.source)
        total = 0
        for token in value:
            if token == "F":
                break
            total = total * 10 + (0 if token == "Z" else ord(token) - 64)
        return total

    def string(self, value):
        if isinstance(value, str):
            return value
        if isinstance(value, Function):
            return value.source
        if value < 0:
            raise InvalidError("negative N")
        return "".join("JABCDEFGHI"[int(digit)] for digit in str(value))

    def truth(self, value):
        return bool(value.source) if isinstance(value, Function) else bool(value)

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

    def flush(self, mode, buffer):
        value = (
            buffer
            if mode == "E"
            else self.integer(buffer)
            if mode == "F"
            else Function(buffer)
        )
        self.stack.append(value)

    def execute(self, source, depth=0):
        if depth > 64:
            raise BudgetError
        cursor = 0
        mode = ""
        buffer = ""
        pending = -1
        while cursor < len(source):
            self.commands += 1
            if self.commands > 10000:
                raise BudgetError
            op = source[cursor]
            if mode:
                if op == mode:
                    self.flush(mode, buffer)
                    mode = ""
                    buffer = ""
                else:
                    buffer += op
                cursor += 1
                continue
            before = list(self.stack)
            call = None
            repeat = False
            try:
                if op in "EFH":
                    mode = op
                elif op in "ABRS":
                    a = self.number(self.pop())
                    b = self.number(self.pop())
                    if op == "R" and b == 0:
                        raise InvalidError("zero divisor")
                    self.stack.append(
                        a + b
                        if op == "A"
                        else a - b
                        if op == "B"
                        else a // b
                        if op == "R"
                        else a * b
                    )
                elif op == "C":
                    key = self.pop()
                    value = self.pop()
                    if isinstance(key, Function):
                        raise InvalidError("function variable")
                    self.variables[key] = value
                elif op == "D":
                    key = self.pop()
                    if isinstance(key, Function):
                        raise InvalidError("function variable")
                    if key not in self.variables:
                        raise InvalidError("name")
                    self.stack.append(self.variables[key])
                elif op == "G":
                    value = self.pop()
                    call = value.source if isinstance(value, Function) else value
                    if not isinstance(call, str):
                        raise InvalidError("G")
                elif op == "I":
                    value = self.pop()
                    if isinstance(value, Function):
                        call = value.source
                    else:
                        self.stack.append(value)
                elif op == "J":
                    self.stack.append(self.integer(self.pop()))
                elif op == "K":
                    value = self.pop()
                    self.stack.extend([value, value])
                elif op == "L":
                    a = self.pop()
                    b = self.pop()
                    self.stack.extend([a, b])
                elif op == "M":
                    self.pop()
                elif op == "N":
                    self.stack.append(self.string(self.pop()))
                elif op == "O":
                    value = self.pop()
                    self.stack.append(len(value) if isinstance(value, str) else value)
                elif op == "P":
                    self.stack.reverse()
                elif op == "Q":
                    function = self.pop()
                    condition = self.pop()
                    if isinstance(function, Function) and self.truth(condition):
                        call = function.source
                elif op == "T":
                    self.stack.append(int(not self.truth(self.pop())))
                elif op == "U":
                    if not self.truth(self.pop()):
                        cursor += 1
                elif op == "V":
                    condition = self.pop()
                    amount = self.pop()
                    if not self.truth(condition):
                        cursor += self.integer(amount)
                elif op == "W":
                    self.stack.append(self.read())
                elif op == "X":
                    if self.truth(self.pop()):
                        pending = cursor
                    else:
                        cursor += 1
                elif op == "Y":
                    value = self.pop()
                    if isinstance(value, Function):
                        raise InvalidError("function output")
                    self.output += str(value)
                elif op == "Z":
                    value = self.pop()
                    if isinstance(value, Function) and self.stack:
                        call = value.source
                        repeat = True
                else:
                    raise ValueError("invalid command")
            except (InvalidError, ValueError):
                self.stack = before
                raise
            cursor += 1
            if pending >= 0 and cursor == pending + 2:
                cursor += 1
                pending = -1
            if call is not None:
                self.execute(call, depth + 1)
                while repeat and self.stack:
                    self.commands += 1
                    if self.commands > 10000:
                        raise BudgetError
                    self.execute(call, depth + 1)
        if mode:
            self.flush(mode, buffer)
