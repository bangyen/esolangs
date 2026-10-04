"""Independent token-tree Forbin parser and bounded evaluator, wiki159753."""

import itertools
import re
from dataclasses import dataclass

LEXER = re.compile("//[^\\r\\n]*|\\s+|[^\\W\\d]\\w*|[01]|\\.\\.|[{}(),;@!:*=]")


def tokens(source):
    result = []
    position = 0
    for match in LEXER.finditer(source):
        if match.start() != position:
            raise ValueError("token")
        value = match.group()
        position = match.end()
        if not value.isspace() and (not value.startswith("//")):
            result.append(value)
    if position != len(source):
        raise ValueError("token")
    return result


def identifier(value):
    return (
        value
        and (value[0].isalpha() or value[0] == "_")
        and all(c.isalnum() or c == "_" for c in value)
    )


def close(items, start):
    stack = []
    for index in range(start, len(items)):
        value = items[index]
        if value in ("{", "("):
            stack.append(value)
        elif value in ("}", ")"):
            if not stack or {"}": "{", ")": "("}[value] != stack.pop():
                raise ValueError("delimiter")
            if not stack:
                return index
    raise ValueError("delimiter")


def split(items, separator):
    pieces = []
    start = 0
    index = 0
    while index < len(items):
        if items[index] in ("{", "("):
            index = close(items, index) + 1
            continue
        if items[index] == separator:
            pieces.append(items[start:index])
            start = index + 1
        index += 1
    return [*pieces, items[start:]]


def names(items):
    if not items:
        return []
    result = [value for value in items if value != ","]
    if not all(identifier(value) for value in result):
        raise ValueError("identifier")
    return result


@dataclass(eq=False)
class Function:
    name: str
    parameters: list
    statements: list
    children: dict


def expression(items):
    if not items:
        raise ValueError("expression")
    if items[0] == "!":
        return ("negate", expression(items[1:]))
    if len(items) == 1:
        if items[0] in ("0", "1"):
            return int(items[0])
        if identifier(items[0]):
            return ("name", items[0])
    if items[0] == "{" and close(items, 0) == len(items) - 1:
        statements, children = block(items[1:-1])
        return Function("", [], statements, children)
    if items[0] == "(" and close(items, 0) == len(items) - 1:
        inside = items[1:-1]
        sections = split(inside, "@")
        if len(sections) == 2:
            parameters = names(sections[0])
            body = sections[1]
            if (
                not parameters
                or not body
                or body[0] != "{"
                or (close(body, 0) != len(body) - 1)
            ):
                raise ValueError("literal")
            statements, children = block(body[1:-1])
            return Function("", parameters, statements, children)
        if not inside or not identifier(inside[0]):
            raise ValueError("callee")
        arguments = (
            [expression(part) for part in split(inside[1:], ",")] if inside[1:] else []
        )
        return ("invoke", ("name", inside[0]), arguments)
    raise ValueError("expression")


def loop_header(items):
    sections = split(items, ":")
    if len(sections) != 2:
        raise ValueError("loop")
    head, tail = sections
    variables = names(head[1:-1] if head and head[0] == "(" else head)
    if not variables:
        raise ValueError("loop variable")
    bounds = split(tail, "..")
    if len(bounds) == 2:
        return ("range", variables[:1], [expression(value) for value in bounds])
    if not tail or tail[0] != "(" or close(tail, 0) != len(tail) - 1:
        raise ValueError("iteration")
    parts = split(tail[1:-1], ",") if tail[1:-1] else []
    if len(variables) > 1 and parts and (parts[0][0] != "("):
        parts = [tail[1:-1]]
    patterns = []
    for part in parts:
        fields = (
            [part]
            if len(variables) == 1
            else split(part[1:-1], ",")
            if part and part[0] == "("
            else split(part, ",")
        )
        patterns.append(
            [None if field == ["*"] else expression(field) for field in fields]
        )
    return ("iteration", variables, patterns)


def statement(items):
    if not items:
        raise ValueError("statement")
    if items[0] == "return":
        return ("return", expression(items[1:]))
    pieces = split(items, "=")
    if len(pieces) == 2:
        return (
            "bind",
            names(pieces[0]),
            [expression(part) for part in split(pieces[1], ",")],
        )
    end = close(items, 0) + 1 if items[0] in ("{", "(") else 1
    callee = expression(items[:end])
    arguments = (
        [expression(part) for part in split(items[end:], ",")] if items[end:] else []
    )
    if isinstance(callee, int) or (isinstance(callee, tuple) and callee[0] == "negate"):
        raise ValueError("statement")
    return ("invoke", callee, arguments)


def block(items):
    statements = []
    children = {}
    index = 0
    while index < len(items):
        if items[index] == ";":
            index += 1
            continue
        if items[index] == "for":
            cursor = index + 1
            while cursor < len(items) and items[cursor] != "{":
                cursor = (
                    close(items, cursor) + 1 if items[cursor] == "(" else cursor + 1
                )
            if cursor == len(items):
                raise ValueError("loop body")
            end = close(items, cursor)
            body, nested = block(items[cursor + 1 : end])
            children.update(nested)
            statements.append(("loop", loop_header(items[index + 1 : cursor]), body))
            index = end + 1
            continue
        cursor = index
        while cursor < len(items) and items[cursor] not in ("{", ";", "}", "=", "("):
            cursor += 1
        prefix = items[index:cursor]
        if (
            cursor < len(items)
            and items[cursor] == "{"
            and prefix
            and (prefix[0] != "return")
            and all(value == "," or identifier(value) for value in prefix)
        ):
            end = close(items, cursor)
            body, nested = block(items[cursor + 1 : end])
            function = Function(prefix[0], names(prefix[1:]), body, nested)
            children[function.name] = function
            index = end + 1
            continue
        cursor = index
        while cursor < len(items) and items[cursor] != ";":
            cursor = (
                close(items, cursor) + 1 if items[cursor] in ("{", "(") else cursor + 1
            )
        statements.append(statement(items[index:cursor]))
        index = cursor + 1
    return (statements, children)


def parse_program(source):
    statements, functions = block(tokens(source))
    if (
        any(statement[0] != "bind" for statement in statements)
        or "main" not in functions
    ):
        raise ValueError("entry")
    return (functions, statements)


def parse(source):
    return parse_program(source)[0]


@dataclass
class Scope:
    function: Function
    parent: object
    values: dict


class InvalidError(Exception):
    pass


class BudgetError(Exception):
    pass


class ReturnedError(Exception):
    def __init__(self, value):
        self.value = value


class Reference:
    """Caller lookup and discard/uneven binding follow the existing repo profile."""

    def __init__(self, source, stdin="", limit=100000):
        self.functions, self.initializers = parse_program(source)
        self.stdin = stdin
        self.offset = 0
        self.bit_index = 8
        self.byte = 0
        self.reads = 0
        self.past_end = 0
        self.bit_reads = 0
        self.output = ""
        self.limit = limit
        self.events = []
        self.global_scope = Scope(Function("$globals", [], [], {}), None, {})
        self.execute(self.initializers, self.global_scope)

    def tick(self, event):
        self.events.append(event)
        if len(self.events) > self.limit:
            raise BudgetError("execution")

    def lookup(self, scope, name):
        while scope:
            if name in scope.values:
                return scope.values[name]
            if name in scope.function.children:
                return scope.function.children[name]
            scope = scope.parent
        if name in ("in", "out"):
            return name
        if name in self.functions:
            return self.functions[name]
        raise InvalidError("identifier")

    def value(self, node, scope):
        if isinstance(node, (int, Function)):
            return node
        if node[0] == "name":
            return self.lookup(scope, node[1])
        if node[0] == "negate":
            value = self.value(node[1], scope)
            if type(value) is not int or value not in (0, 1):
                raise InvalidError("bit")
            return int(value == 0)
        return self.call(
            self.value(node[1], scope),
            [self.value(arg, scope) for arg in node[2]],
            scope,
        )

    def call(self, function, arguments, parent):
        self.tick(
            ("call", function.name if isinstance(function, Function) else function)
        )
        if function == "in":
            if self.bit_index == 8:
                if self.offset == len(self.stdin):
                    self.past_end += 1
                    raise EOFError
                self.byte = ord(self.stdin[self.offset])
                self.offset += 1
                self.reads += 1
                self.bit_index = 0
            bit = int(bool(self.byte & 128 >> self.bit_index))
            self.bit_index += 1
            self.bit_reads += 1
            return bit
        if function == "out":
            if len(arguments) != 8 or any(
                type(value) is not int or value not in (0, 1) for value in arguments
            ):
                raise InvalidError("output")
            self.output += chr(
                sum((bit << 7 - index for index, bit in enumerate(arguments)))
            )
            return 0
        if not isinstance(function, Function):
            raise InvalidError("function")
        bindings = dict.fromkeys(function.parameters, 0)
        bindings.update(zip(function.parameters, arguments, strict=False))
        scope = Scope(function, parent, bindings)
        try:
            self.execute(function.statements, scope)
        except ReturnedError as returned:
            return returned.value
        return 0

    def rows(self, header, scope):
        kind, variables, values = header
        if kind == "range":
            low, high = [self.value(value, scope) for value in values]
            if type(low) is not int or type(high) is not int:
                raise InvalidError("bound")
            return (variables, [[value] for value in range(low, high + 1)])
        rows = []
        for pattern in values:
            choices = [(0, 1) if value is None else (value,) for value in pattern]
            for choice in itertools.product(*choices):
                rows.append(
                    [
                        value if original is None else self.value(value, scope)
                        for value, original in zip(choice, pattern, strict=False)
                    ]
                )
        return (variables, rows)

    def execute(self, statements, scope):
        for node in statements:
            self.tick(("statement", node[0]))
            if node[0] == "return":
                raise ReturnedError(self.value(node[1], scope))
            if node[0] == "bind":
                targets, rhs = node[1:]
                pairs = zip(
                    targets,
                    [rhs[0]] * len(targets) if len(rhs) == 1 else rhs,
                    strict=False,
                )
                bindings = [
                    (name, self.value(value, scope))
                    for name, value in pairs
                    if name != "_"
                ]
                scope.values.update(bindings)
            elif node[0] == "invoke":
                self.call(
                    self.value(node[1], scope),
                    [self.value(value, scope) for value in node[2]],
                    scope,
                )
            else:
                variables, rows = self.rows(node[1], scope)
                for row in rows:
                    scope.values.update(
                        (
                            (name, value)
                            for name, value in zip(variables, row, strict=False)
                            if name != "_"
                        )
                    )
                    self.execute(node[2], scope)

    def run(self):
        return self.call(self.functions["main"], [0], self.global_scope)
