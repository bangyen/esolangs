"""Independent mutable scope scheduler, using recursive primitive evaluator."""

from tests.interpreters.forth_reference import Reference


class Stepped:
    def __init__(self, source, text=""):
        self.evaluator = Reference(text)
        self.frames = [[source, 0, False]]
        self.error = False
        self.text = text
        self.position = 0

    def finish(self):
        while self.frames and self.frames[-1][1] == len(self.frames[-1][0]):
            _source, _cursor, repeat = self.frames[-1]
            if repeat and self.evaluator.top():
                self.frames[-1][1] = 0
                return
            self.frames.pop()

    def abort(self):
        top_level = len(self.frames) == 1
        self.frames[-1][1] = len(self.frames[-1][0])
        self.finish()
        self.error |= top_level

    def step(self):
        if not self.frames:
            return
        self.finish()
        if not self.frames:
            return
        frame = self.frames[-1]
        source, cursor, _repeat = frame
        if cursor == len(source):
            return
        op = source[cursor]
        frame[1] += 1
        if op in "([{":
            closer = {"(": ")", "[": "]", "{": "}"}[op]
            depth = 1
            end = cursor + 1
            while end < len(source) and depth:
                depth += (source[end] == op) - (source[end] == closer)
                end += 1
            frame[1] = end
            if depth:
                self.abort()
                return
            body = source[cursor + 1 : end - 1]
            if op == "{":
                self.evaluator.functions[self.evaluator.top()] = body
            elif self.evaluator.top():
                self.frames.append([body, 0, op == "["])
        elif op == ";":
            key = self.evaluator.top()
            self.evaluator.stack.pop()
            self.frames.append([self.evaluator.functions.get(key, ""), 0, False])
        else:
            okay = self.evaluator.execute(op)
            if op == ",":
                end = self.text.find("\n", self.position)
                self.position = len(self.text) if end == -1 else end + 1
            if not okay:
                self.abort()
