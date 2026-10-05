"""Alight's geometric reader, independently tokenized along complex headings."""

import operator as operations
import re


class Grid:
    def __init__(self, rows):
        self.width = max(map(len, rows), default=0)
        self.height = len(rows)
        self.cells = "".join(row.ljust(self.width) for row in rows)

    def contains(self, position):
        return 0 <= position.real < self.width and 0 <= position.imag < self.height

    def read(self, position, direction):
        path = []
        while self.contains(position):
            path.append(position)
            position += direction
        stream = "".join(
            self.cells[int(p.imag) * self.width + int(p.real)] for p in path
        )
        consumed = 0
        for token in re.finditer(r""""[^"]*"|'[\s\S]|[^;'"]+|;""", stream):
            if token.start() != consumed:
                raise ValueError("unclosed literal")
            if token.group() == ";":
                return stream[: token.start()], path[token.start()]
            consumed = token.end()
        if consumed != len(stream):
            raise ValueError("unclosed literal")
        return stream, path[-1] if path else position - direction


class AlightFaultError(Exception):
    pass


def compile_expression(text):
    """Compile the declared infix profile to postfix with an operator stack."""
    from fractions import Fraction

    tokens = []
    consumed = 0
    pattern = (
        r"""('[\s\S]|"[^"]*"|[^\W_]+(?=\s*\{)|"""
        r"""[^\W_]*[^\W\d_][^\W_]*|\d+(?:\.\d*)?|\.\d+|"""
        r"""[^\W_]+|[+*/=<>&|^!{},\[\]-])"""
    )
    for match in re.finditer(pattern, text):
        if text[consumed : match.start()].strip():
            raise ValueError("invalid expression token")
        tokens.append(match.group())
        consumed = match.end()
    if text[consumed:].strip():
        raise ValueError("invalid expression suffix")
    output = []
    operators = []
    expecting = True
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "!" and expecting:
            operators.append(token)
        elif token in "+-*/=<>&|^" and len(token) == 1:
            if expecting:
                raise ValueError("missing left operand")
            while operators and isinstance(operators[-1], str):
                output.append(("operator", operators.pop()))
            operators.append(token)
            expecting = True
        elif token == "," or token in ("]", "}"):
            if expecting and operators and isinstance(operators[-1], str):
                raise ValueError("missing operand before delimiter")
            while operators and isinstance(operators[-1], str):
                output.append(("operator", operators.pop()))
            if not operators:
                raise ValueError("unexpected delimiter")
            kind, name, count = operators.pop()
            if token == ",":
                if expecting:
                    raise ValueError("missing argument")
                operators.append((kind, name, count + 1))
                expecting = True
            else:
                if token != ("]" if kind == "list" else "}") or (expecting and count):
                    raise ValueError("mismatched delimiter")
                output.append((kind, name, count + int(not expecting)))
                expecting = False
        elif token == "[" or (
            token.isalnum() and index + 1 < len(tokens) and tokens[index + 1] == "{"
        ):
            if not expecting:
                raise ValueError("adjacent operands")
            operators.append(("list", None, 0) if token == "[" else ("call", token, 0))
            if token != "[":
                index += 1
        else:
            if not expecting:
                raise ValueError("adjacent operands")
            if token.startswith('"'):
                output.append(("literal", list(map(ord, token[1:-1]))))
            elif token.startswith("'"):
                output.append(("literal", Fraction(ord(token[1]))))
            elif (
                token.isdecimal()
                or token.startswith(".")
                or (token[0].isdecimal() and "." in token)
            ):
                digits = token.replace(".", "")
                numerator = 0
                for digit in digits:
                    numerator = numerator * 10 + int(digit)
                places = len(token.partition(".")[2])
                output.append(("literal", Fraction(numerator, 10**places)))
            elif token in ("nil", "eof", "left", "right"):
                output.append(("literal", token))
            elif token.isalnum():
                output.append(("variable", token))
            else:
                raise ValueError("unexpected token")
            expecting = False
        index += 1
    if expecting:
        raise ValueError("missing operand")
    while operators:
        operator = operators.pop()
        if not isinstance(operator, str):
            raise ValueError("unclosed delimiter")
        output.append(("operator", operator))
    return tuple(output)


def homogeneous(values):
    if any(isinstance(value, list) for value in values) and any(
        not isinstance(value, list | str) for value in values
    ):
        raise AlightFaultError("heterogeneous list")
    return values


def truth(value):
    if value not in ("left", "right"):
        raise AlightFaultError("nonboolean guard")
    return value == "left"


class Evaluation:
    def __init__(self, text, variables):
        self.tape = compile_expression(text)
        self.variables = variables
        self.values = []
        self.offset = 0
        self.waiting = None

    def resume(self):
        from fractions import Fraction

        while self.offset < len(self.tape):
            instruction = self.tape[self.offset]
            self.offset += 1
            kind = instruction[0]
            if kind == "literal":
                value = instruction[1]
                self.values.append(value.copy() if isinstance(value, list) else value)
            elif kind == "variable":
                if instruction[1] not in self.variables:
                    raise AlightFaultError("unknown variable")
                self.values.append(self.variables[instruction[1]])
            elif kind in ("call", "list"):
                _, name, count = instruction
                args = self.values[-count:] if count else []
                if count:
                    del self.values[-count:]
                if kind == "list":
                    self.values.append(homogeneous(args))
                    continue
                if name not in ("sign", "trunc", "len", "at"):
                    self.waiting = (name, args)
                    return "call", name, args
                if name in ("sign", "trunc"):
                    if len(args) != 1 or isinstance(args[0], list | str):
                        raise AlightFaultError("invalid numeric arguments")
                    value = args[0]
                    self.values.append(
                        Fraction(int(value))
                        if name == "trunc"
                        else Fraction((value > 0) - (value < 0))
                    )
                    continue
                if (
                    name not in ("len", "at")
                    or not args
                    or not isinstance(args[0], list)
                ):
                    raise AlightFaultError("invalid list arguments")
                sequence = args[0]
                if name == "len":
                    if len(args) == 1:
                        self.values.append(Fraction(len(sequence)))
                    elif (
                        len(args) == 2
                        and not isinstance(args[1], list | str)
                        and args[1] >= 0
                        and args[1].denominator == 1
                    ):
                        self.values.append(sequence + ["nil"] * int(args[1]))
                    else:
                        raise AlightFaultError("invalid padding")
                    continue
                if len(args) not in (2, 3) or isinstance(args[1], list | str):
                    raise AlightFaultError("invalid index arguments")
                slot = args[1] - Fraction(1, 2)
                if slot < 0 or slot.denominator != 1:
                    raise AlightFaultError("invalid index")
                slot = int(slot)
                if len(args) == 2:
                    self.values.append(
                        sequence[slot] if slot < len(sequence) else "nil"
                    )
                else:
                    if slot >= len(sequence):
                        raise AlightFaultError("setter bounds")
                    homogeneous([*sequence, args[2]])
                    copied = list(sequence)
                    copied[slot] = args[2]
                    self.values.append(copied)
            else:
                operator = instruction[1]
                b = self.values.pop()
                if operator == "!":
                    self.values.append("right" if truth(b) else "left")
                    continue
                a = self.values.pop()
                if operator in "=<>&|^":
                    if operator == "=":
                        result = structural_equal(a, b)
                    elif operator in "<>":
                        result = (
                            False
                            if isinstance(a, list | str) or isinstance(b, list | str)
                            else (a < b if operator == "<" else a > b)
                        )
                    else:
                        left, right = truth(a), truth(b)
                        result = (
                            (left and right)
                            if operator == "&"
                            else (left or right)
                            if operator == "|"
                            else left != right
                        )
                    self.values.append("left" if result else "right")
                elif isinstance(a, list) or isinstance(b, list):
                    if isinstance(a, list) and isinstance(b, list) and operator == "+":
                        self.values.append(homogeneous(a + b))
                    elif operator == "*" and isinstance(a, list) != isinstance(b, list):
                        sequence, count = (a, b) if isinstance(a, list) else (b, a)
                        if (
                            isinstance(count, str)
                            or count < 0
                            or count.denominator != 1
                        ):
                            raise AlightFaultError("invalid repeat")
                        self.values.append(sequence * int(count))
                    else:
                        raise AlightFaultError("invalid list operator")
                elif (
                    isinstance(a, str)
                    or isinstance(b, str)
                    or (operator == "/" and b == 0)
                ):
                    raise AlightFaultError("invalid arithmetic")
                else:
                    self.values.append(
                        {
                            "+": operations.add,
                            "-": operations.sub,
                            "*": operations.mul,
                            "/": operations.truediv,
                        }[operator](Fraction(a), Fraction(b))
                    )
        if len(self.values) != 1:
            raise ValueError("invalid postfix tape")
        return "done", self.values[0]


def evaluate_expression(text, variables=None):
    evaluation = Evaluation(text, {} if variables is None else variables)
    result = evaluation.resume()
    if result[0] != "done":
        raise AlightFaultError("unknown function")
    return result[1]


class Frame:
    def __init__(self, position, direction, variables):
        self.position = position
        self.direction = direction
        self.variables = variables
        self.evaluation = None


class Reference:
    def __init__(self, rows, stdin=""):
        self.grid = Grid(rows)
        start = self.find_word("begin")
        if start is None:
            raise ValueError("no begin")
        position, direction = start
        self.frames = [Frame(position + 5 * direction, direction, {})]
        self.done = False
        self.stdin = stdin
        self.offset = 0
        self.past_end = 0
        self.output = ""

    def find_word(self, word):
        for cell in range(len(self.grid.cells)):
            position = complex(cell % self.grid.width, cell // self.grid.width)
            for direction in (1, 1j, -1, -1j):
                locations = [
                    position + direction * offset for offset in range(len(word))
                ]
                if all(self.grid.contains(point) for point in locations):
                    spelling = "".join(
                        self.grid.cells[
                            int(point.imag) * self.grid.width + int(point.real)
                        ]
                        for point in locations
                    )
                    if spelling == word:
                        return position, direction
        return None

    def function(self, name):
        for cell in range(len(self.grid.cells)):
            point = complex(cell % self.grid.width, cell // self.grid.width)
            for direction in (1, 1j, -1, -1j):
                locations = [point + direction * offset for offset in range(4)]
                if not all(self.grid.contains(location) for location in locations):
                    continue
                spelling = "".join(
                    self.grid.cells[
                        int(location.imag) * self.grid.width + int(location.real)
                    ]
                    for location in locations
                )
                if spelling != "func":
                    continue
                text, pivot = self.grid.read(point, direction)
                match = re.fullmatch(r"\s*func\s+([^\W_]+)\s*\{([^{}]*)\}\s*", text)
                if match and match[1] == name:
                    parameters = (
                        [value.strip() for value in match[2].split(",")]
                        if match[2].strip()
                        else []
                    )
                    if all(
                        value.isalnum() and value not in RESERVED
                        for value in parameters
                    ):
                        return pivot + direction, direction, parameters
        raise AlightFaultError("unknown function")

    def step(self):
        if self.done:
            return
        frame = self.frames[-1]
        text, pivot = self.grid.read(frame.position, frame.direction)
        match = re.fullmatch(r"\s*([^\W_]+)(.*)", text, flags=re.DOTALL)
        if match:
            command, rest = match[1], match[2].strip()
        elif text.strip():
            raise ValueError("invalid command")
        else:
            command, rest = "", ""
        expression = None
        target = None
        if command == "set":
            match = re.fullmatch(r"([^\W_]+)\s+(.*)", rest, flags=re.DOTALL)
            if not match:
                raise ValueError("invalid assignment")
            target, expression = match[1], match[2]
        elif command in ("skip", "turn", "wait"):
            expression = rest
        elif command == "end":
            expression = rest if rest else None
        elif rest.startswith("{") and (
            command not in RESERVED
            or command in ("at", "len", "trunc", "sign", "nil", "eof", "left", "right")
        ):
            expression = command + rest
        value = None
        if expression is not None:
            if frame.evaluation is None:
                evaluation = Evaluation(expression, frame.variables)
                if target is not None:
                    if not target.isalnum() or target in RESERVED:
                        raise ValueError("invalid assignment target")
                    if target not in frame.variables:
                        raise AlightFaultError("unknown assignment target")
                frame.evaluation = evaluation
            result = frame.evaluation.resume()
            if result[0] == "call":
                _, name, args = result
                position, direction, parameters = self.function(name)
                if len(parameters) != len(args):
                    raise AlightFaultError("argument count")
                self.frames.append(
                    Frame(position, direction, dict(zip(parameters, args, strict=True)))
                )
                return
            value = result[1]
        if command == "end":
            if expression is None:
                value = "nil"
            if len(self.frames) == 1:
                self.done = True
            else:
                self.frames.pop()
                self.frames[-1].evaluation.values.append(value)
                self.frames[-1].evaluation.waiting = None
            return
        if command == "turn":
            frame.direction *= -1j if truth(value) else 1j
        elif command == "skip":
            if truth(value):
                _, pivot = self.grid.read(pivot + frame.direction, frame.direction)
        elif command in ("var", "inp", "out"):
            if not rest.isalnum() or rest in RESERVED:
                raise ValueError("invalid variable")
            if command == "var":
                if rest in frame.variables:
                    raise AlightFaultError("redeclaration")
                frame.variables[rest] = "nil"
            elif rest not in frame.variables:
                raise AlightFaultError("unknown variable")
            elif command == "inp":
                if self.offset == len(self.stdin):
                    self.past_end += 1
                    frame.variables[rest] = "eof"
                else:
                    frame.variables[rest] = ord(self.stdin[self.offset])
                    self.offset += 1
            else:
                value = frame.variables[rest]
                if (
                    isinstance(value, str | list)
                    or value != int(value)
                    or not 0 <= value < 0x110000
                ):
                    raise AlightFaultError("invalid output")
                self.output += chr(int(value))
        elif command == "set":
            if not target.isalnum() or target in RESERVED:
                raise ValueError("invalid variable")
            if target not in frame.variables:
                raise AlightFaultError("unknown variable")
            frame.variables[target] = value
        elif command not in ("wait", "") and expression is None:
            raise ValueError("unknown command")
        frame.evaluation = None
        frame.position = pivot + frame.direction
        if not self.grid.contains(frame.position):
            raise AlightFaultError("off grid")


RESERVED = frozenset(
    [
        "begin",
        "end",
        "func",
        "var",
        "set",
        "skip",
        "turn",
        "inp",
        "out",
        "wait",
        "at",
        "len",
        "trunc",
        "sign",
        "nil",
        "eof",
        "left",
        "right",
    ]
)


def structural_equal(left, right):
    """Compare cyclic lists by refining a finite labelled-graph partition."""
    if not isinstance(left, list) or not isinstance(right, list):
        return not (isinstance(left, list) or isinstance(right, list)) and left == right
    nodes = []
    indices = {}

    def register(value):
        if id(value) not in indices:
            indices[id(value)] = len(nodes)
            nodes.append(value)
        return indices[id(value)]

    roots = register(left), register(right)
    edges = []
    cursor = 0
    while cursor < len(nodes):
        edges.append(
            tuple(
                ("edge", register(value))
                if isinstance(value, list)
                else ("atom", value)
                for value in nodes[cursor]
            )
        )
        cursor += 1
    classes = [0] * len(nodes)
    while True:
        signatures = {}
        refined = []
        for node in edges:
            signature = tuple(
                (kind, classes[value]) if kind == "edge" else (kind, value)
                for kind, value in node
            )
            if signature not in signatures:
                signatures[signature] = len(signatures)
            refined.append(signatures[signature])
        if refined == classes:
            return classes[roots[0]] == classes[roots[1]]
        classes = refined


def pending_expression(evaluation):
    if evaluation is None:
        return None
    stack = [("value", value) for value in evaluation.values]
    if evaluation.waiting is not None:
        name, args = evaluation.waiting
        stack.append(("call", name, tuple(("value", value) for value in args)))
    for instruction in evaluation.tape[evaluation.offset :]:
        kind = instruction[0]
        if kind == "literal":
            value = instruction[1]
            stack.append(
                ("list", tuple(("value", item) for item in value))
                if isinstance(value, list)
                else ("value", value)
            )
        elif kind == "variable":
            stack.append(("variable", instruction[1]))
        elif kind == "operator":
            right = stack.pop()
            if instruction[1] == "!":
                stack.append(("not", right))
            else:
                stack.append(("binary", instruction[1], stack.pop(), right))
        else:
            _, name, count = instruction
            args = tuple(stack[-count:]) if count else ()
            if count:
                del stack[-count:]
            stack.append(("list", args) if kind == "list" else ("call", name, args))
    if len(stack) != 1:
        raise AssertionError("incomplete evaluator representation")
    return stack[0]


def graph_key(value):
    """Canonical ordered list graph; immutable expression tuples are structural."""
    nodes = []
    indices = {}

    def edge(item):
        if isinstance(item, list):
            if id(item) not in indices:
                indices[id(item)] = len(nodes)
                nodes.append(item)
            return "list", indices[id(item)]
        if isinstance(item, dict):
            return "mapping", tuple(
                (key, edge(val)) for key, val in sorted(item.items())
            )
        if isinstance(item, tuple):
            return "tuple", tuple(map(edge, item))
        return "atom", item

    root = edge(value)
    packed = []
    cursor = 0
    while cursor < len(nodes):
        packed.append(tuple(map(edge, nodes[cursor])))
        cursor += 1
    return root, tuple(packed)


def reference_state(reference):
    return (
        graph_key(
            tuple(
                (
                    frame.position,
                    frame.direction,
                    frame.variables,
                    pending_expression(frame.evaluation),
                )
                for frame in reference.frames
            )
        ),
        reference.done,
        reference.offset,
    )
