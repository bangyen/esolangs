"""Independent prefix reduction and callback-based Unlambda evaluation."""


def parse(source):
    tokens = []
    index = 0
    while index < len(source):
        char = source[index]
        index += 1
        if char.isspace():
            continue
        if char == "#":
            while index < len(source) and source[index] != "\n":
                index += 1
            continue
        if char in ".?":
            if index == len(source):
                raise ValueError("missing character")
            tokens.append(("print" if char == "." else "query", source[index]))
            index += 1
        elif char == "`":
            tokens.append(None)
        elif char == "r":
            tokens.append(("print", "\n"))
        elif char in "skivcde@|":
            tokens.append(("atom", char))
        else:
            raise ValueError("unknown command")
    stack = []
    for token in reversed(tokens):
        if token is None:
            if len(stack) < 2:
                raise ValueError("incomplete application")
            left = stack.pop()
            right = stack.pop()
            stack.append(("app", left, right))
        else:
            stack.append(token)
    if len(stack) != 1:
        raise ValueError("not exactly one expression")
    return stack[0]


class Reference:
    def __init__(self, source, stdin=""):
        self.term = parse(source)
        self.stdin = stdin
        self.offset = 0
        self.past_end = 0
        self.current = None
        self.output = ""
        self.result = None
        self.actions = 0

        def done(value):
            return self.finish(value)

        done.context = ()
        self.done = done
        self.action = (self.evaluate, (self.term, done))

    def finish(self, value):
        self.result = value
        return

    def evaluate(self, term, continuation):
        if term[0] == "value":
            return continuation, (term[1],)
        if term[0] != "app":
            return continuation, (term,)
        left, right = term[1:]

        def got_function(function):
            if function == ("atom", "d"):
                return continuation, (("promise", right),)

            def got_argument(argument):
                return self.apply, (function, argument, continuation)

            got_argument.context = (
                *continuation.context,
                ("waiting_argument", function),
            )
            return self.evaluate, (right, got_argument)

        got_function.context = (*continuation.context, ("waiting_function", right))
        return self.evaluate, (left, got_function)

    def apply(self, function, argument, continuation):
        kind = function[0]
        if kind == "print":
            self.output += function[1]
            return continuation, (argument,)
        if kind == "query":
            return self.apply, (
                argument,
                ("atom", "i" if self.current == function[1] else "v"),
                continuation,
            )
        if kind == "promise":
            return self.evaluate, (
                ("app", function[1], ("value", argument)),
                continuation,
            )
        if kind == "continuation":
            return function[1], (argument,)
        if kind == "k1":
            return continuation, (function[1],)
        if kind == "s1":
            return continuation, (("s2", function[1], argument),)
        if kind == "s2":
            x, y = function[1:]
            z = ("value", argument)
            return self.evaluate, (
                ("app", ("app", ("value", x), z), ("app", ("value", y), z)),
                continuation,
            )
        name = function[1]
        if name == "i":
            return continuation, (argument,)
        if name == "v":
            return continuation, (("atom", "v"),)
        if name in "ks":
            return continuation, ((name + "1", argument),)
        if name == "c":
            return self.apply, (argument, ("continuation", continuation), continuation)
        if name == "d":
            return continuation, (("promise", ("value", argument)),)
        if name == "e":
            return self.finish(argument)
        if name == "@":
            if self.offset < len(self.stdin):
                self.current = self.stdin[self.offset]
                self.offset += 1
                flag = "i"
            else:
                self.current = None
                self.past_end += 1
                flag = "v"
            return self.apply, (argument, ("atom", flag), continuation)
        if name == "|":
            supplied = (
                ("atom", "v") if self.current is None else ("print", self.current)
            )
            return self.apply, (argument, supplied, continuation)
        raise AssertionError("unknown independent value")

    def step(self):
        if self.action is None:
            return
        function, arguments = self.action
        self.action = function(*arguments)
        self.actions += 1

    def run(self, limit=10000):
        while self.action is not None:
            if self.actions == limit:
                raise RuntimeError("independent action bound")
            self.step()
        return self.result

    def view(self):
        if self.action is None:
            return (("return", self.result), (), self.current, True)
        function, arguments = self.action
        if function == self.evaluate:
            term, callback = arguments
            return (("evaluate", term), callback.context, self.current, False)
        if function == self.apply:
            first, second, callback = arguments
            return (("apply", first, second), callback.context, self.current, False)
        return (("return", arguments[0]), function.context, self.current, False)


def normalize(value):
    kind = value[0]
    if kind in ("atom", "print", "query"):
        return value
    if kind == "continuation":
        return (kind, tuple((tag, normalize(term)) for tag, term in value[1].context))
    if kind in ("app", "s2"):
        return (kind, *(normalize(item) for item in value[1:]))
    if kind in ("value", "promise", "k1", "s1"):
        return (kind, normalize(value[1]))
    raise AssertionError(kind)
