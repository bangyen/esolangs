r"""Interpreter for function x(y)."""

from __future__ import annotations

import re
import sys
from typing import Final

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# A value is an integer or a.
type _Value = int | str

# An expression node.
# frame stack embeds nodes and.
type _Expr = tuple[object, ...]

# Binary operators, longest.
# ``/``.
# since the spec's own spelling.
_BINARY: Final = ("//", "<=", "=>", "==", "!=", "+", "-", "*", "/", "<", ">")

# Precedence: BDMAS, so.
# addition and subtraction, and.
_PRECEDENCE: Final = {
    "<": 0,
    ">": 0,
    "<=": 0,
    "=>": 0,
    "==": 0,
    "!=": 0,
    "+": 1,
    "-": 1,
    "*": 2,
    "/": 2,
    "//": 2,
}

_COMPOUND: Final = {"+&": "+", "-&": "-", "*&": "*", "/&": "/"}

_NAME: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Deepest expression nesting.
# the source, so unbounded.
# parentheses did.
# rather than a.
# nests past 3, and.
# the recursion the language is.
_MAX_NESTING: Final = 50


class _Function:
    r"""One parsed ``function`` block: its parameters and its statements."""

    def __init__(
        self, name: str, params: list[tuple[str, _Expr | None]], body: list[_Expr]
    ) -> None:
        self.name = name
        self.params = params
        self.body = body


def _strip_comments(line: str) -> str:
    r"""Drop a ``#`` comment, ignoring a ``#`` inside a string literal."""
    out = []
    quoted = False
    for char in line:
        if char == '"':
            quoted = not quoted
        elif char == "#" and not quoted:
            break
        out.append(char)
    return "".join(out)


def _split_top(text: str, sep: str) -> list[str]:
    r"""Split on ``sep`` at bracket depth 0, outside string literals."""
    parts = []
    depth = 0
    quoted = False
    start = 0
    for i, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif quoted:
            continue
        elif char in "([<":
            depth += 1
        elif char in ")]>":
            depth -= 1
        elif char == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


class _Parser:
    r"""Recursive-descent parser for one expression string."""

    def __init__(self, text: str, depth: int = 0) -> None:
        self.text = text
        self.pos = 0
        if depth > _MAX_NESTING:
            raise ValueError(f"expression nests deeper than {_MAX_NESTING}")
        self.depth = depth

    def _error(self, why: str) -> ValueError:
        return ValueError(f"{why}: {self.text.strip()!r}")

    def _skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] == " ":
            self.pos += 1

    def parse(self) -> _Expr:
        r"""Parse the whole string, rejecting anything left over."""
        node = self.expr()
        self._skip()
        if self.pos != len(self.text):
            raise self._error("trailing input in expression")
        return node

    def expr(self, level: int = 0) -> _Expr:
        r"""Parse a binary-operator expression at ``level`` precedence."""
        if level > 2:
            return self.ternary()
        node = self.expr(level + 1)
        while True:
            save = self.pos
            self._skip()
            op = self._binary_op()
            if op is None or _PRECEDENCE[op] != level:
                self.pos = save
                return node
            right = self.expr(level + 1)
            node = ("bin", op, node, right)

    def _binary_op(self) -> str | None:
        r"""Read a spaced binary operator, or rewind and return None."""
        if self.pos == 0 or self.text[self.pos - 1] != " ":
            return None
        for op in _BINARY:
            end = self.pos + len(op)
            if self.text.startswith(op, self.pos) and self.text[end : end + 1] == " ":
                self.pos = end + 1
                return op
        return None

    def ternary(self) -> _Expr:
        r"""Parse ``cond<a, b>``: an atom optionally followed by arms."""
        node = self.atom()
        while self.pos < len(self.text) and self.text[self.pos] == "<":
            depth = 0
            for i in range(self.pos, len(self.text)):
                if self.text[i] == "<":
                    depth += 1
                elif self.text[i] == ">":
                    depth -= 1
                    if depth == 0:
                        break
            else:
                raise self._error("unbalanced ternary")
            arms = _split_top(self.text[self.pos + 1 : i], ",")
            if len(arms) != 2:
                raise self._error("ternary needs exactly two arms")
            node = (
                "if",
                node,
                _Parser(arms[0].strip(), self.depth + 1).parse(),
                _Parser(arms[1].strip(), self.depth + 1).parse(),
            )
            self.pos = i + 1
        return node

    def atom(self) -> _Expr:
        r"""Parse a literal, a print/input form, a call, or a variable."""
        self._skip()
        if self.pos >= len(self.text):
            raise self._error("expression expected")
        char = self.text[self.pos]
        if char == '"':
            end = self.text.find('"', self.pos + 1)
            if end < 0:
                raise self._error("unterminated string")
            node: _Expr = ("lit", self.text[self.pos + 1 : end])
            self.pos = end + 1
            return node
        if char == "(":
            inner = self._balanced("(", ")")
            return _Parser(inner, self.depth + 1).parse()
        if char == "[":
            inner = self._balanced("[", "]")
            if inner.strip() == "~":
                return ("read_line",)
            return ("print", _Parser(inner.strip(), self.depth + 1).parse(), True)
        if char == "`":
            self.pos += 1
            self._skip()
            if self.text[self.pos : self.pos + 1] == "~":
                self.pos += 1
                return ("read_char",)
            return ("print", self.ternary(), False)
        if char == "{":
            inner = self._balanced("{", "}")
            args = [] if not inner.strip() else _split_top(inner, ",")
            return (
                "recurse",
                tuple(_Parser(a.strip(), self.depth + 1).parse() for a in args),
            )
        if char == "-" or char.isdigit():
            return self._number()
        match = _NAME.match(self.text, self.pos)
        if match is None:
            raise self._error("unexpected character in expression")
        self.pos = match.end()
        name = match.group()
        if self.text[self.pos : self.pos + 1] == "(":
            inner = self._balanced("(", ")")
            args = [] if not inner.strip() else _split_top(inner, ",")
            return (
                "call",
                name,
                tuple(_Parser(a.strip(), self.depth + 1).parse() for a in args),
            )
        return ("var", name)

    def _number(self) -> _Expr:
        r"""Parse an integer literal, which may be glued to a ``-`` sign."""
        start = self.pos
        if self.text[self.pos] == "-":
            self.pos += 1
        digits = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isdigit():
            self.pos += 1
        if self.pos == digits:
            raise self._error("expected a number")
        return ("lit", int(self.text[start : self.pos]))

    def _balanced(self, open_c: str, close_c: str) -> str:
        r"""Consume a balanced ``open_c``/``close_c`` group, returning inside."""
        depth = 0
        for i in range(self.pos, len(self.text)):
            if self.text[i] == open_c:
                depth += 1
            elif self.text[i] == close_c:
                depth -= 1
                if depth == 0:
                    inner = self.text[self.pos + 1 : i]
                    self.pos = i + 1
                    return inner
        raise self._error(f"unbalanced {open_c}{close_c}")


def _parse_statement(line: str) -> _Expr:
    r"""Parse one statement line into an expression node."""
    if line.startswith("->"):
        return ("return", _Parser(line[2:].strip()).parse())
    if line.startswith("var "):
        name, _, rest = line[4:].partition(":")
        if not rest or not _NAME.fullmatch(name.strip()):
            raise ValueError(f"malformed variable declaration: {line!r}")
        return ("declare", name.strip(), _Parser(rest.strip()).parse())
    for token, op in _COMPOUND.items():
        head, sep, rest = line.partition(f" {token} ")
        if sep and _NAME.fullmatch(head.strip()):
            target = head.strip()
            value = _Parser(rest.strip()).parse()
            return ("assign", target, ("bin", op, ("var", target), value))
    head, sep, rest = line.partition(";")
    if sep and _NAME.fullmatch(head.strip()):
        return ("assign", head.strip(), _Parser(rest.strip()).parse())
    return ("bare", _Parser(line).parse())


def _parse(code: str) -> list[_Function]:
    r"""Parse a program into its functions, rejecting a malformed one."""
    functions: list[_Function] = []
    for raw in code.splitlines():
        line = _strip_comments(raw).strip()
        if not line:
            continue
        if line.startswith("function "):
            header = line[len("function ") :].strip()
            name, _, rest = header.partition("(")
            if not rest.endswith(")") or not _NAME.fullmatch(name.strip()):
                raise ValueError(f"malformed function header: {line!r}")
            params = []
            inside = rest[:-1].strip()
            for part in _split_top(inside, ",") if inside else []:
                pname, sep, default = part.partition("|")
                if not _NAME.fullmatch(pname.strip()):
                    raise ValueError(f"malformed parameter: {part!r}")
                node = _Parser(default.strip()).parse() if sep else None
                params.append((pname.strip(), node))
            functions.append(_Function(name.strip(), params, []))
        elif not functions:
            raise ValueError(f"statement outside any function: {line!r}")
        else:
            functions[-1].body.append(_parse_statement(line))
    if not functions:
        raise ValueError("program declares no function")
    return functions


def _sub(node: _Expr, i: int) -> _Expr:
    r"""Return child ``i`` of a node."""
    child = node[i]
    if not isinstance(child, tuple):
        raise AssertionError("isinstance(child, tuple)")
    return child


def _text(node: _Expr, i: int) -> str:
    r"""Return child ``i`` of a node as the name or operator it is."""
    value = node[i]
    if not isinstance(value, str):
        raise AssertionError("isinstance(value, str)")
    return value


def _truthy(value: _Value) -> bool:
    r"""Report truth: a nonzero integer, or a nonempty string."""
    return value != 0 if isinstance(value, int) else value != ""


def _binary(op: str, left: _Value, right: _Value) -> _Value:
    r"""Apply a binary operator, raising ``HaltError`` for an invalid one."""
    if op == "==":
        return int(left == right)
    if op == "!=":
        return int(left != right)
    if isinstance(left, str) or isinstance(right, str):
        # ``+`` concatenates when.
        # other arithmetic have no.
        if op == "+":
            return f"{left}{right}"
        raise HaltError(f"cannot apply {op!r} to a string")
    if op == "<":
        return int(left < right)
    if op == ">":
        return int(left > right)
    if op == "<=":
        return int(left <= right)
    if op == "=>":
        return int(left >= right)
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if right == 0:
        raise HaltError("division by zero")
    # ``/`` is integer division per.
    # same operation ``//``; both.
    return int(left / right) if (left < 0) != (right < 0) else left // right


# A frame is ``(function index,.
# ``todo`` is the tuple of.
# hashable and ``snapshot`` can.
type _Frame = tuple[int, int, tuple[tuple[str, _Value], ...], tuple[_Expr, ...]]

# : The whole run state as a.
# : stack the finished operands.
# : recursion, held here rather.
#: the depth unbounded.
type _State = tuple[tuple[_Frame, ...], tuple[_Value, ...]]


class _Machine:
    r"""The run state: the functions, the frame stack, and the value stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.functions = _parse(code)
        self.by_name = {fn.name: i for i, fn in enumerate(self.functions)}
        entry = self.functions[0]
        variables = []
        for name, default in entry.params:
            if default is None:
                raise ValueError(
                    f"entry function {entry.name!r} is called with no arguments, "
                    f"so its parameter {name!r} needs a default"
                )
            variables.append((name, _const(default)))
        # The entry frame: the first.
        self.frames: tuple[_Frame, ...] = ((0, 0, tuple(variables), ()),)
        self.stack: list[_Value] = []

    @property
    def halted(self) -> bool:
        return not self.frames

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # The frame stack is tuples.
        # cursor rides along because a.
        # is not a real cycle.
        return (self.frames, tuple(self.stack), self.io.position())

    # : ``ip`` is a position, but.
    #: statement), root-to-leaf.
    # : Declared rather than left.
    # : classified is a missing.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""Each active frame's ``(function, statement)``, root-to-leaf."""
        return tuple(
            value for func_i, stmt_i, _, _ in self.frames for value in (func_i, stmt_i)
        )

    @property
    def memory(self) -> list[int]:
        r"""No addressable cells; the store is the frames' variables."""
        return []

    def step(self) -> None:
        r"""Perform one evaluation step, applying whatever it asks for."""
        want = _wants_read(self.frames)
        byte: _Value | None = None
        if want == "line":
            byte = self.io.input_str()
        elif want == "char":
            # ``input_char`` returns 0 for.
            # no ``if val:`` guard; running.
            byte = chr(self.io.input_char())

        self.frames, self.stack, out = _advance(
            self.frames, self.stack, self.functions, self.by_name, byte
        )

        if out is not None:
            self.io.print_str(out)


def _const(node: _Expr) -> _Value:
    r"""Evaluate a parameter default, which the wiki only ever writes."""
    if node[0] == "lit":
        value = node[1]
        if not isinstance(value, int | str):
            raise AssertionError("isinstance(value, int | str)")
        return value
    raise ValueError("a parameter default must be a literal")


def _wants_read(stack: tuple[_Frame, ...]) -> str | None:
    r"""Report whether the next step reads input, and which way."""
    if not stack:
        return None
    todo = stack[-1][3]
    if not todo:
        return None
    node = todo[-1]
    if node[0] == "read_line":
        return "line"
    if node[0] == "read_char":
        return "char"
    return None


def _advance(
    stack: tuple[_Frame, ...],
    values: list[_Value],
    functions: list[_Function],
    by_name: dict[str, int],
    byte: _Value | None = None,
) -> tuple[tuple[_Frame, ...], list[_Value], str | None]:
    r"""Return the state after one evaluation step, and anything to print."""
    if not stack:
        # Stepping a halted machine is.
        # contract steps past the halt.
        return stack, values, None
    func_i, stmt_i, variables, todo = stack[-1]
    func = functions[func_i]

    if not todo:
        # No expression in flight:.
        # by falling off the end (the.
        if stmt_i >= len(func.body):
            return _return(stack, values, 0)
        return (
            (*stack[:-1], (func_i, stmt_i + 1, variables, (func.body[stmt_i],))),
            values,
            None,
        )

    node, rest = todo[-1], todo[:-1]
    kind = node[0]
    frame = (func_i, stmt_i, variables, rest)

    if kind == "lit":
        value = node[1]
        if not isinstance(value, int | str):
            raise AssertionError("isinstance(value, int | str)")
        return (*stack[:-1], frame), [*values, value], None
    if kind in ("read_line", "read_char"):
        if byte is None:
            raise AssertionError("byte is not None")
        return (*stack[:-1], frame), [*values, byte], None
    if kind == "var":
        name = node[1]
        for var, value in variables:
            if var == name:
                return (*stack[:-1], frame), [*values, value], None
        raise HaltError(f"undefined variable {name!r}")
    if kind == "bare":
        # A statement evaluated for.
        after = (*rest, ("drop",), _sub(node, 1))
        return (*stack[:-1], (func_i, stmt_i, variables, after)), values, None
    if kind == "drop":
        return (*stack[:-1], frame), values[:-1], None
    if kind == "bin":
        return _push_operands(stack, values, frame, node, ("bin_do", node[1]))
    if kind == "bin_do":
        right, left = values[-1], values[-2]
        combined = _binary(_text(node, 1), left, right)
        return (*stack[:-1], frame), [*values[:-2], combined], None

    def scheduling(*steps: _Expr) -> tuple[_Frame, ...]:
        r"""Replace the current frame with one whose ``todo`` is ``steps``."""
        return (*stack[:-1], (func_i, stmt_i, variables, (*rest, *steps)))

    if kind == "print":
        return scheduling(("print_do", node[2]), _sub(node, 1)), values, None
    if kind == "print_do":
        value = values[-1]
        # ``[a]`` prints with a.
        # used as a value yields 0, the.
        out = f"{value}\n" if node[1] else str(value)
        return (*stack[:-1], frame), [*values[:-1], 0], out
    if kind == "if":
        return scheduling(("if_do", node[2], node[3]), _sub(node, 1)), values, None
    if kind == "if_do":
        # Lazily: exactly one arm is.
        # do not both fire.
        arm = _sub(node, 1 if _truthy(values[-1]) else 2)
        return scheduling(arm), values[:-1], None
    if kind == "declare" or kind == "assign":
        return scheduling(("bind", node[1]), _sub(node, 2)), values, None
    if kind == "bind":
        name = _text(node, 1)
        bound = tuple((v, values[-1] if v == name else x) for v, x in variables)
        if all(v != name for v, _ in variables):
            bound = (*variables, (name, values[-1]))
        return (*stack[:-1], (func_i, stmt_i, bound, rest)), values[:-1], None
    if kind == "return":
        return scheduling(("return_do",), _sub(node, 1)), values, None
    if kind == "return_do":
        return _return((*stack[:-1], frame), values[:-1], values[-1])
    if kind in ("call", "recurse"):
        target = by_name.get(_text(node, 1)) if kind == "call" else func_i
        if target is None:
            raise HaltError(f"unknown function {node[1]!r}")
        args = node[2] if kind == "call" else node[1]
        if not isinstance(args, tuple):
            raise AssertionError("isinstance(args, tuple)")
        # The two leading slots are.
        # node's operands from index 2,.
        enter = ("enter", target, len(args))
        return _push_operands(stack, values, frame, ("x", "x", *args), enter)
    if kind == "enter":
        index, count = node[1], node[2]
        if not isinstance(index, int):
            raise AssertionError("isinstance(index, int)")
        if not isinstance(count, int):
            raise AssertionError("isinstance(count, int)")
        callee = functions[index]
        if count > len(callee.params):
            raise HaltError(
                f"{callee.name!r} takes {len(callee.params)} arguments, got {count}"
            )
        supplied = values[len(values) - count :] if count else []
        entered: list[tuple[str, _Value]] = []
        for i, (name, default) in enumerate(callee.params):
            if i < count:
                entered.append((name, supplied[i]))
            elif default is not None:
                entered.append((name, _const(default)))
            else:
                raise HaltError(f"{callee.name!r} is missing argument {name!r}")
        rest_values = values[: len(values) - count] if count else values
        return (
            (*stack[:-1], frame, (index, 0, tuple(entered), ())),
            rest_values,
            None,
        )
    raise HaltError(f"unknown expression {kind!r}")


def _push_operands(
    stack: tuple[_Frame, ...],
    values: list[_Value],
    frame: _Frame,
    node: _Expr,
    after: _Expr,
) -> tuple[tuple[_Frame, ...], list[_Value], str | None]:
    r"""Schedule ``node``'s operands, then the step that combines them."""
    func_i, stmt_i, variables, rest = frame
    operands = tuple(_sub(node, i) for i in range(2, len(node)))
    return (
        (*stack[:-1], (func_i, stmt_i, variables, (*rest, after, *reversed(operands)))),
        values,
        None,
    )


def _return(
    stack: tuple[_Frame, ...], values: list[_Value], value: _Value
) -> tuple[tuple[_Frame, ...], list[_Value], str | None]:
    r"""Pop the current frame, leaving its value for the caller."""
    outer = stack[:-1]
    # The entry frame's value is.
    return outer, ([*values, value] if outer else values), None


def run(code: str, io: IO) -> None:
    r"""Run a function x(y) program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
