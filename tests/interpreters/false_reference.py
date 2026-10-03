"""Independent parsed FALSE functions and recursive stack evaluation."""


class InvalidOperationError(Exception):
    pass


class Function:
    def __init__(self, tokens, start, end):
        self.tokens = tokens
        self.start = start
        self.end = end


def signed(value):
    value = value & 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def parse(source):
    def sequence(index, *, nested=False):
        tokens = []
        while index < len(source):
            start = index
            char = source[index]
            index += 1
            if char == "]":
                if not nested:
                    raise ValueError("unmatched lambda end")
                return tokens, index
            if char == "[":
                body, index = sequence(index, nested=True)
                tokens.append(("value", Function(body, start + 1, index - 1)))
                continue
            if char in '{"':
                closer = "}" if char == "{" else '"'
                characters = []
                while index < len(source) and source[index] != closer:
                    characters.append(source[index])
                    index += 1
                if index == len(source):
                    raise ValueError("unterminated quoted span")
                index += 1
                if char == '"':
                    tokens.append(("text", "".join(characters)))
                continue
            if char == "'":
                if index == len(source):
                    raise ValueError("unterminated character")
                tokens.append(("value", ord(source[index])))
                index += 1
                continue
            if char in "0123456789":
                value = ord(char) - 48
                while index < len(source) and source[index] in "0123456789":
                    value = (value * 10 + ord(source[index]) - 48) & 0xFFFFFFFF
                    index += 1
                tokens.append(("value", signed(value)))
                continue
            if "a" <= char <= "z":
                tokens.append(("value", ord(char) - 97))
            else:
                tokens.append(("command", char))
        if nested:
            raise ValueError("unterminated lambda")
        return tokens, index

    return sequence(0)[0]


class Reference:
    def __init__(self, source, stdin=""):
        self.tokens = parse(source)
        self.stdin = stdin
        self.offset = 0
        self.past_end = 0
        self.stack = []
        self.variables = [None] * 26
        self.output = ""
        self.commands = 0

    def require(self, count):
        if len(self.stack) < count:
            raise InvalidOperationError("empty stack")

    def number(self, value):
        if type(value) is not int:
            raise InvalidOperationError("not a number")
        return value

    def function(self, value):
        if not isinstance(value, Function):
            raise InvalidOperationError("not a function")
        return value

    def reference(self, value):
        value = self.number(value)
        if not 0 <= value < 26:
            raise InvalidOperationError("not a variable")
        return value

    def execute(self, tokens=None, limit=10000):
        for kind, value in self.tokens if tokens is None else tokens:
            self.commands += 1
            if self.commands > limit:
                raise AssertionError("bounded FALSE reference exceeded")
            if kind == "value":
                self.stack.append(value)
                continue
            if kind == "text":
                self.output += value
                continue
            command = value
            if command in "$%\\@øO_~+-*/&|>=:;!?.,":
                count = 3 if command == "@" else 2 if command in "\\+-*/&|>=:?" else 1
                self.require(count)
            if command == "$":
                self.stack.append(self.stack[-1])
            elif command == "%":
                self.stack.pop()
            elif command == "\\":
                self.stack[-2:] = self.stack[-2:][::-1]
            elif command == "@":
                self.stack[-3:] = [*self.stack[-2:], self.stack[-3]]
            elif command in "øO":
                depth = self.number(self.stack[-1])
                if not 0 <= depth < len(self.stack) - 1:
                    raise InvalidOperationError("invalid pick")
                self.stack[-1] = self.stack[-2 - depth]
            elif command in "_~":
                top = self.number(self.stack[-1])
                self.stack[-1] = signed(-top if command == "_" else ~top)
            elif command in "+-*/&|>=":
                left, right = map(self.number, self.stack[-2:])
                if command == "/":
                    if not right:
                        raise InvalidOperationError("divide by zero")
                    result = (abs(left) // abs(right)) * (
                        -1 if (left < 0) != (right < 0) else 1
                    )
                else:
                    result = {
                        "+": left + right,
                        "-": left - right,
                        "*": left * right,
                        "&": left & right,
                        "|": left | right,
                        ">": -int(left > right),
                        "=": -int(left == right),
                    }[command]
                self.stack[-2:] = [signed(result)]
            elif command == ":":
                index = self.reference(self.stack[-1])
                self.variables[index] = self.stack[-2]
                del self.stack[-2:]
            elif command == ";":
                index = self.reference(self.stack[-1])
                stored = self.variables[index]
                if stored is None:
                    raise InvalidOperationError("unset variable")
                self.stack[-1] = stored
            elif command == "!":
                function = self.function(self.stack[-1])
                self.stack.pop()
                self.execute(function.tokens, limit)
            elif command == "?":
                function = self.function(self.stack[-1])
                flag = self.number(self.stack[-2])
                del self.stack[-2:]
                if flag:
                    self.execute(function.tokens, limit)
            elif command == "#":
                self.require(2)
                condition = self.function(self.stack[-2])
                body = self.function(self.stack[-1])
                del self.stack[-2:]
                while True:
                    self.execute(condition.tokens, limit)
                    self.require(1)
                    flag = self.number(self.stack[-1])
                    self.stack.pop()
                    if not flag:
                        break
                    self.execute(body.tokens, limit)
            elif command in ".,":
                top = self.number(self.stack[-1])
                self.stack.pop()
                self.output += str(top) if command == "." else chr(top & 255)
            elif command == "^":
                if self.offset == len(self.stdin):
                    self.stack.append(-1)
                    self.past_end += 1
                else:
                    self.stack.append(ord(self.stdin[self.offset]))
                    self.offset += 1
