"""Independent mutable Eval command evaluator."""


class InvalidOperationError(Exception):
    pass


class Reference:
    def __init__(self, source):
        self.stacks = [[], []]
        self.active = 0
        self.frames = [[source, 0]] if source else []
        self.output = ""

    def state(self):
        return (
            self.active,
            tuple(tuple(stack) for stack in self.stacks),
            tuple(tuple(frame) for frame in self.frames),
            0,
        )

    @property
    def halted(self):
        return not self.frames

    def step(self):
        if self.halted:
            return
        source, index = self.frames[-1]
        if index >= len(source):
            self.frames.pop()
            return
        command = source[index]
        stack = self.stacks[self.active]
        if command in "^+-.=;?!" and not stack:
            raise InvalidOperationError
        if command in "+-" and type(stack[-1]) is not int:
            raise InvalidOperationError
        if command == "!" and type(stack[-1]) is not str:
            raise InvalidOperationError
        next_index = index + 1
        call = None
        if command == "0":
            stack.append(0)
        elif command == "`":
            stack.append(1 - self.active)
        elif command == "^":
            stack.append(stack[-1])
        elif command == "+":
            stack[-1] += 1
        elif command == "-":
            stack[-1] -= 1
        elif command == ".":
            self.output += str(stack.pop())
        elif command == "=":
            self.stacks[1 - self.active].append(stack.pop())
        elif command == ";":
            stack.pop()
        elif command == "~":
            self.active = 1 - self.active
        elif command == "*":
            stack.reverse()
        elif command == "?":
            if not stack.pop():
                next_index += 1
        elif command == "!":
            call = stack.pop()
        elif command in ('"', "'"):
            literal = []
            while next_index < len(source) and source[next_index] != '"':
                literal.append('"' if source[next_index] == "`" else source[next_index])
                next_index += 1
            value = "".join(literal)
            stack.append('"' + value + '"' if command == "'" else value)
            next_index += 1
        self.frames[-1][1] = next_index
        if call is not None:
            self.frames.append([call, 0])
