"""Pratt parser and flat bytecode evaluator for the declared APL profile."""

import math
import re
from dataclasses import dataclass, field
from typing import ClassVar


class RuntimeFaultError(Exception):
    pass


class ReturnedError(Exception):
    def __init__(self, value):
        self.value = value


@dataclass(eq=False)
class Function:
    name: str
    arguments: tuple[str, ...]
    statements: list = field(default_factory=list)
    pattern: tuple[str | None, ...] | None = None


def number(token):
    if "." in token:
        result = float(token)
        if not math.isfinite(result):
            raise RuntimeFaultError("nonfinite number")
        return result
    sign = -1 if token.startswith("-") else 1
    digits = token.lstrip("+-")
    if not digits or any(char not in "0123456789" for char in digits):
        raise RuntimeFaultError("not a number")
    result = 0
    for char in digits:
        result = 10 * result + ord(char) - ord("0")
    return sign * result


def render(value):
    if isinstance(value, Function):
        raise RuntimeFaultError("not a number")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeFaultError("nonfinite result")
        return render(int(value)) if value.is_integer() else str(value)
    if not value:
        return "0"
    sign = "-" if value < 0 else ""
    digits = []
    value = abs(value)
    while value:
        value, digit = divmod(value, 10)
        digits.append(chr(ord("0") + digit))
    return sign + "".join(reversed(digits))


class Parser:
    levels: ClassVar = {"|": 1, "&": 2, "+": 3, "-": 3, "*": 4, "/": 4, "%": 4, "**": 6}

    def __init__(self, source, functions):
        self.tokens = re.findall(r"[0-9]+(?:\.[0-9]+)?|\*\*|[^\s]", source)
        self.cursor = 0
        self.functions = functions

    def peek(self):
        return self.tokens[self.cursor] if self.cursor < len(self.tokens) else None

    def take(self, token=None):
        actual = self.peek()
        if actual is None or (token is not None and actual != token):
            raise ValueError("unexpected token")
        self.cursor += 1
        return actual

    def whole(self):
        result = self.expression()
        if self.peek() is not None:
            raise ValueError("trailing tokens")
        return result

    def custom(self, left):
        functions = sorted(
            (fn for fn in self.functions.values() if fn.pattern is not None),
            key=lambda fn: -len(fn.pattern),
        )
        for fn in functions:
            if (fn.pattern[0] is None) != (left is not None):
                continue
            saved = self.cursor
            args = [] if left is None else [left]
            pattern = fn.pattern if left is None else fn.pattern[1:]
            try:
                for part in pattern:
                    if part is None:
                        args.append(self.expression(7))
                    else:
                        self.take(part)
                return ("invoke", fn.name, tuple(args))
            except ValueError:
                self.cursor = saved
        return None

    def expression(self, minimum=0):
        token = self.peek()
        if token in ("-", "$"):
            self.take()
            left = ("minus" if token == "-" else "return", self.expression(5))
        else:
            left = self.custom(None)
            if left is None:
                left = self.atom()
        while True:
            if minimum <= 7 and (custom := self.custom(left)) is not None:
                left = custom
                continue
            token = self.peek()
            if (
                token is not None
                and token.isalpha()
                and token.islower()
                and self.cursor > 0
                and self.tokens[self.cursor - 1].isalpha()
                and self.tokens[self.cursor - 1].islower()
            ):
                # Juxtaposition has multiplication's ordinary precedence.
                if minimum > 4:
                    return left
                right = self.expression(5)
                left = ("binary", "*", left, right)
                continue
            level = self.levels.get(token, -1)
            if level < minimum:
                return left
            self.take()
            right = self.expression(level if token == "**" else level + 1)
            left = ("binary", token, left, right)

    def atom(self):
        token = self.take()
        if token[0] in "0123456789":
            if self.peek() == "(":
                raise ValueError("bracket multiplication")
            return ("constant", number(token))
        if token == "(":
            value = self.expression()
            self.take(")")
            return value
        if token.isalpha() and token.islower():
            return self.arguments(token) if self.peek() == "(" else ("variable", token)
        if token.isalpha() and token.isupper():
            name = token
            while (
                self.peek() is not None
                and self.peek().isalpha()
                and self.peek().isupper()
            ):
                name += self.take()
            return self.arguments(name) if self.peek() == "(" else ("function", name)
        raise ValueError("invalid operand")

    def arguments(self, name):
        self.take("(")
        args = []
        if self.peek() != ")":
            args.append(self.expression())
            while self.peek() == ",":
                self.take(",")
                args.append(self.expression())
        self.take(")")
        return ("invoke", name, tuple(args))


def body(rhs, functions):
    text = rhs.strip()
    if text.startswith("{"):
        if not text.endswith("}"):
            raise ValueError("malformed body")
        sources = [line.strip() for line in text[1:-1].splitlines() if line.strip()]
    else:
        sources = [text]
    if not sources:
        raise ValueError("empty body")
    return [Parser(source, functions).whole() for source in sources]


def contains_return(node):
    pending = [node]
    while pending:
        node = pending.pop()
        if node[0] == "return":
            return True
        if node[0] == "minus":
            pending.append(node[1])
        elif node[0] == "binary":
            pending.extend((node[2], node[3]))
        elif node[0] == "invoke":
            pending.extend(node[2])
    return False


def append_expression(tape, node):
    pending = [("node", node)]
    while pending:
        action, item = pending.pop()
        if action == "instruction":
            tape.append(item)
            continue
        if action == "jump":
            item.append(len(tape))
            tape.append(("jump-" + item[0], None))
            continue
        if action == "patch":
            tape[item[1]] = ("jump-" + item[0], len(tape))
            continue
        tag = item[0]
        if tag in ("constant", "variable", "function"):
            tape.append(
                (
                    {"constant": "push", "variable": "load", "function": "reference"}[
                        tag
                    ],
                    item[1],
                )
            )
        elif tag in ("minus", "return"):
            pending.extend(
                [
                    ("instruction", ("negate" if tag == "minus" else "exit", None)),
                    ("node", item[1]),
                ]
            )
        elif tag == "binary":
            if item[1] in ("&", "|"):
                label = ["false" if item[1] == "&" else "true"]
                pending.extend(
                    [
                        ("patch", label),
                        ("node", item[3]),
                        ("jump", label),
                        ("node", item[2]),
                    ]
                )
            else:
                pending.extend(
                    [
                        ("instruction", ("arithmetic", item[1])),
                        ("node", item[3]),
                        ("node", item[2]),
                    ]
                )
        else:
            pending.append(("instruction", ("call", (item[1], len(item[2])))))
            pending.extend(("node", argument) for argument in reversed(item[2]))


def variables(node):
    out = []
    pending = [node]
    while pending:
        current = pending.pop()
        if current[0] == "variable":
            if current[1] not in out:
                out.append(current[1])
        elif current[0] in ("minus", "return"):
            pending.append(current[1])
        elif current[0] == "binary":
            pending.extend([current[3], current[2]])
        elif current[0] == "invoke":
            pending.extend(reversed(current[2]))
    return out


class Reference:
    def __init__(self, source, stdin=""):
        self.functions = {}
        self.globals = {}
        self.stdout = ""
        self.stdin = stdin
        self.offset = 0
        self.past_end = 0
        self.calls = []
        self.lines = []
        start = 0
        braces = 0
        for i, char in enumerate(source):
            if char == "{":
                braces += 1
            elif char == "}":
                braces -= 1
                if braces < 0:
                    raise ValueError("unbalanced brace")
            elif char == "\n" and not braces:
                if source[start:i].strip():
                    self.lines.append(source[start:i].strip())
                start = i + 1
        if braces:
            raise ValueError("unbalanced brace")
        if source[start:].strip():
            self.lines.append(source[start:].strip())
        self.line = 0
        self.done = False

    def input(self):
        found = re.search(r"\S+", self.stdin[self.offset :])
        if found is None:
            self.offset = len(self.stdin)
            self.past_end += 1
            raise EOFError()
        start = self.offset + found.start()
        end = self.offset + found.end()
        self.offset = end
        return number(self.stdin[start:end])

    def emit(self, value):
        self.stdout += render(value) + "\n"

    def evaluate(self, node, bindings):
        tape = []
        append_expression(tape, node)
        tape.append(("finish", None))
        frames = [[tape, 0, bindings, []]]
        cache = getattr(self, "compiled", {})
        self.compiled = cache
        while frames:
            tape, position, bindings, stack = frame = frames[-1]
            operation, argument = tape[position]
            frame[1] += 1
            if operation == "push":
                stack.append(argument)
            elif operation == "load":
                if argument in bindings:
                    stack.append(bindings[argument])
                elif argument in self.globals:
                    stack.append(self.globals[argument])
                else:
                    raise ValueError("unknown variable")
            elif operation == "reference":
                if argument not in self.functions:
                    raise ValueError("unknown function")
                stack.append(self.functions[argument])
            elif operation == "negate":
                value = stack.pop()
                if isinstance(value, Function):
                    raise RuntimeFaultError("not a number")
                stack.append(-value)
            elif operation == "arithmetic":
                right, left = stack.pop(), stack.pop()
                stack.append(self.arithmetic(argument, left, right))
            elif operation.startswith("jump-"):
                value = stack[-1]
                if operation == "jump-true" and value:
                    frame[1] = argument
                elif operation == "jump-false" and not value:
                    stack[-1] = 0
                    frame[1] = argument
                else:
                    stack.pop()
            elif operation == "print":
                self.emit(stack.pop())
            elif operation == "discard":
                stack.pop()
            elif operation in ("finish", "exit", "return"):
                value = stack.pop()
                frames.pop()
                if frames:
                    frames[-1][3].append(value)
                elif operation == "exit":
                    raise ReturnedError(value)
                else:
                    return value
            else:
                name, count = argument
                arguments = stack[-count:] if count else []
                if count:
                    del stack[-count:]
                target = bindings.get(name)
                if not isinstance(target, Function):
                    target = self.functions.get(name)
                if target is None:
                    raise ValueError("unknown function")
                if len(arguments) != len(target.arguments):
                    raise ValueError("bad arity")

                def roots(value):
                    return tuple(
                        (scope, key)
                        for scope, mapping in (
                            ("definition", self.functions),
                            ("global", self.globals),
                        )
                        for key, item in sorted(mapping.items())
                        if item is value
                    )

                self.calls.append(
                    (
                        target,
                        tuple(arguments),
                        self.offset,
                        roots(target),
                        tuple(
                            roots(value) if isinstance(value, Function) else None
                            for value in arguments
                        ),
                    )
                )
                key = (target, id(target.statements))
                if key not in cache:
                    body = []
                    for i, statement in enumerate(target.statements):
                        append_expression(body, statement)
                        if i == len(target.statements) - 1:
                            body.append(("return", None))
                        else:
                            body.append(
                                (
                                    "discard"
                                    if contains_return(statement)
                                    else "print",
                                    None,
                                )
                            )
                    cache[key] = body
                frames.append(
                    [
                        cache[key],
                        0,
                        dict(zip(target.arguments, arguments, strict=True)),
                        [],
                    ]
                )

        raise AssertionError("evaluation ended without a result")

    def arithmetic(self, op, left, right):
        if isinstance(left, Function) or isinstance(right, Function):
            raise RuntimeFaultError("not a number")
        try:
            if op == "+":
                result = left + right
            elif op == "-":
                result = left - right
            elif op == "*":
                result = left * right
            elif op == "%":
                result = left % right
            elif op == "**":
                result = left**right
            else:
                if isinstance(left, int) and isinstance(right, int):
                    q, r = divmod(left, right)
                    if not r:
                        return q
                result = left / right
                if result.is_integer():
                    result = int(result)
        except (ZeroDivisionError, OverflowError) as error:
            raise RuntimeFaultError("arithmetic failure") from error
        if isinstance(result, complex) or (
            isinstance(result, float) and not math.isfinite(result)
        ):
            raise RuntimeFaultError("nonreal or nonfinite result")
        return result

    def step_line(self):
        if self.line == len(self.lines):
            self.done = True
            return
        source = self.lines[self.line]
        self.line += 1
        if "=" not in source:
            expression = Parser(source, self.functions).whole()
            for name in variables(expression):
                if name not in self.globals:
                    self.globals[name] = self.input()
            try:
                result = self.evaluate(expression, {})
            except ReturnedError as returned:
                result = returned.value
            self.emit(result)
            return
        lhs, rhs = source.split("=", 1)
        lhs = "".join(lhs.split())
        if len(lhs) == 1 and lhs.isalpha() and lhs.islower():
            statements = body(rhs, self.functions)
            try:
                for i, statement in enumerate(statements):
                    result = self.evaluate(statement, {})
                    if i != len(statements) - 1 and not contains_return(statement):
                        self.emit(result)
            except ReturnedError as returned:
                result = returned.value
            self.globals[lhs] = result
            return
        head = lhs.split("(", 1)[0]
        if head and all(char.isalpha() and char.isupper() for char in head):
            if "(" not in lhs:
                args = ()
            else:
                if not lhs.endswith(")"):
                    raise ValueError("bad header")
                text = lhs[len(head) + 1 : -1]
                args = tuple(text.split(",")) if text else ()
                if any(
                    len(arg) != 1 or not arg.isalpha() or not arg.islower()
                    for arg in args
                ):
                    raise ValueError("bad header")
            if len(set(args)) != len(args):
                raise ValueError("duplicate argument")
            fn = Function(head, args)
        else:
            args = tuple(char for char in lhs if char.isalpha() and char.islower())
            if not args or len(set(args)) != len(args):
                raise ValueError("bad operator arguments")
            pattern = tuple(
                None if char.isalpha() and char.islower() else char for char in lhs
            )
            if any(
                char is not None and (char.isalnum() or char in "+-*/%&|()={}$,")
                for char in pattern
            ):
                raise ValueError("bad operator")
            name = "".join("\0" if char is None else char for char in pattern)
            fn = Function(name, args, pattern=pattern)
        self.functions[fn.name] = fn
        fn.statements = body(rhs, self.functions)

    def run(self):
        while not self.done:
            self.step_line()
        return self.stdout
