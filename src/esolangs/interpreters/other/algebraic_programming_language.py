r"""Interpreter for Algebraic Programming Language."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# -- values.

# The only datatype is a.
# slot too: the wiki's.
# arguments and calls them with.
# evaluates to the definition.
_Number = int | float

# -- parse tree.

# Tuples discriminated by their.
# same idea.
# operator is a call whose name.
# and one lookup serve both.
_Lit = tuple[Literal["lit"], _Number]
_Var = tuple[Literal["var"], str]
_Ref = tuple[Literal["ref"], str]
_Neg = tuple[Literal["neg"], "_Node"]
_Ret = tuple[Literal["ret"], "_Node"]
_Bin = tuple[Literal["bin"], str, "_Node", "_Node"]
_Call = tuple[Literal["call"], str, list["_Node"]]
_Node = _Lit | _Var | _Ref | _Neg | _Ret | _Bin | _Call

_LOWER = "abcdefghijklmnopqrstuvwxyz"
_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# The spec allows accented.
# case is tested with ``str``.
# spellings; the constants are.
_DIGITS = "0123456789"
# Operator symbols are "any.
# symbol", so the reserved set.
# use.
_RESERVED = set("+-*/%&|()={}$ \t,")


def _is_lower(char: str) -> bool:
    r"""Whether ``char`` is a variable/argument letter (any script)."""
    return char.isalpha() and char.islower()


def _is_upper(char: str) -> bool:
    r"""Whether ``char`` is a function-name letter (any script)."""
    return char.isalpha() and char.isupper()


def _is_symbol(char: str) -> bool:
    r"""Whether ``char`` may appear in a custom operator's name."""
    return not char.isalnum() and not char.isspace() and char not in _RESERVED


class _Definition:
    r"""A named function or custom operator, with its parameters and body."""

    def __init__(self, name: str, params: list[str], body: list[_Node]) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.control = [_contains_return(node) for node in body]

    def __repr__(self) -> str:
        r"""Show the name and arity; frame keys are built from this."""
        return f"<{self.name}/{len(self.params)}>"


# -- tokenizer.


def _tokens(line: str) -> list[str]:
    r"""Split ``line`` into number, letter, and symbol tokens."""
    out: list[str] = []
    ind = 0
    while ind < len(line):
        char = line[ind]
        if char.isspace():
            ind += 1
            continue
        if char in _DIGITS:
            start = ind
            while ind < len(line) and line[ind] in _DIGITS:
                ind += 1
            # A fractional part only counts.
            # otherwise the dot is an.
            if ind + 1 < len(line) and line[ind] == "." and line[ind + 1] in _DIGITS:
                ind += 1
                while ind < len(line) and line[ind] in _DIGITS:
                    ind += 1
            out.append(line[start:ind])
            continue
        out.append(char)
        ind += 1
    return out


def _number(word: str) -> _Number:
    r"""Parse a numeric literal, keeping integers exact."""
    return float(word) if "." in word else int(word)


# -- parser.


class _Parser:
    r"""A recursive-descent parser for one expression."""

    def __init__(self, tokens: list[str], defs: dict[str, _Definition]) -> None:
        self.tokens = tokens
        self.defs = defs
        self.ind = 0

    def peek(self) -> str | None:
        r"""Return the next token, or None at the end of the expression."""
        return self.tokens[self.ind] if self.ind < len(self.tokens) else None

    def take(self) -> str:
        r"""Consume and return the next token."""
        word = self.tokens[self.ind]
        self.ind += 1
        return word

    def expect(self, word: str) -> None:
        r"""Consume ``token`` or fail as malformed."""
        if self.peek() != word:
            raise ValueError(f"expected {word!r}")
        self.ind += 1

    def parse(self) -> _Node:
        r"""Parse the whole token list, rejecting a trailing remainder."""
        node = self.expr()
        if self.peek() is not None:
            raise ValueError(f"trailing input at {self.peek()!r}")
        return node

    def expr(self) -> _Node:
        r"""Parse at the lowest precedence (``|``)."""
        return self._binary(0)

    # ``|`` then ``&`` then.
    # by :meth:`_power` because it.
    _LEVELS: tuple[tuple[str, ...], ...] = (("|",), ("&",), ("+", "-"), ("*", "/", "%"))

    def _binary(self, level: int) -> _Node:
        r"""Parse a left-associative level of the precedence ladder."""
        if level == len(self._LEVELS):
            return self._power()
        node = self._binary(level + 1)
        while True:
            word = self.peek()
            # No ``**`` guard is needed.
            # before returning, so the.
            # ``*`` of a ``**`` by the time.
            if word is None or word not in self._LEVELS[level]:
                return node
            self.take()
            node = ("bin", word, node, self._binary(level + 1))

    def _at_power(self) -> bool:
        r"""Whether the cursor sits on a ``**`` rather than a ``*``."""
        return (
            self.ind + 1 < len(self.tokens)
            and self.tokens[self.ind] == "*"
            and self.tokens[self.ind + 1] == "*"
        )

    def _power(self) -> _Node:
        r"""Parse ``**``, which is right-associative."""
        base = self._unary()
        if self._at_power():
            self.take()
            self.take()
            return ("bin", "**", base, self._power())
        return base

    def _unary(self) -> _Node:
        r"""Parse unary ``-``, the ``$`` return operator, and prefix operators."""
        word = self.peek()
        if word == "-":
            self.take()
            return ("neg", self._unary())
        if word == "$":
            self.take()
            return ("ret", self._unary())
        return self._operand()

    def _operand(self) -> _Node:
        r"""Parse a prefix operator, or an atom with its trailing operators."""
        prefix = self._match_operator(None)
        if prefix is not None:
            return prefix
        return self._postfix()

    def _postfix(self) -> _Node:
        r"""Parse an atom followed by any custom operators applying to it."""
        node = self._atom()
        while True:
            match = self._match_operator(node)
            if match is None:
                return node
            node = match

    def _operators(self) -> list[_Definition]:
        r"""Return the custom operators, longest pattern first."""
        return sorted(
            (d for d in self.defs.values() if "\0" in d.name),
            key=lambda d: -len(d.name),
        )

    def _match_operator(self, left: _Node | None) -> _Node | None:
        r"""Try each custom operator pattern at the cursor; None if none fit."""
        for definition in self._operators():
            leading = definition.name.startswith("\0")
            if leading != (left is not None):
                continue
            saved = self.ind
            args = self._try_pattern(definition, left)
            if args is not None:
                return ("call", definition.name, args)
            self.ind = saved
        return None

    def _try_pattern(
        self, definition: _Definition, left: _Node | None
    ) -> list[_Node] | None:
        r"""Match ``definition``'s pattern, with ``left`` filling a leading."""
        pattern = definition.name
        args: list[_Node] = []
        ind = 0
        if pattern.startswith("\0"):
            if left is None:  # pragma: no cover - filtered by the caller
                return None
            args.append(left)
            ind = 1
        while ind < len(pattern):
            char = pattern[ind]
            if char == "\0":
                # An argument slot inside the.
                # bound operand, not a whole.
                # symbols delimit it.
                # there, so ``!!a`` is a.
                try:
                    args.append(self._operand())
                except ValueError:
                    return None
                ind += 1
                continue
            if self.peek() != char:
                return None
            self.take()
            ind += 1
        return args

    def _atom(self) -> _Node:
        r"""Parse a literal, name, call, or bracketed expression."""
        word = self.peek()
        if word is None:
            raise ValueError("unexpected end of expression")
        if word[0] in _DIGITS:
            self.take()
            node: _Node = ("lit", _number(word))
            # ``1(2)`` is invalid syntax by.
            # implied multiplication is.
            if self.peek() == "(":
                raise ValueError("bracket multiplication is invalid syntax")
            return self._implied(node)
        if word == "(":
            self.take()
            inner = self.expr()
            self.expect(")")
            return self._implied(inner)
        if _is_lower(word):
            self.take()
            if self.peek() == "(":
                # ``c()`` where ``c`` is a.
                # the wiki's ``IF(x, c) = x &.
                return ("call", word, self._arguments())
            return self._implied(("var", word))
        if _is_upper(word):
            name = ""
            while self.peek() is not None and _is_upper(str(self.peek())):
                name += self.take()
            if self.peek() == "(":
                return ("call", name, self._arguments())
            # A bare uppercase name is the.
            # ``WHILE(x, c)`` receives.
            return ("ref", name)
        raise ValueError(f"unexpected token {word!r}")

    def _arguments(self) -> list[_Node]:
        r"""Parse a parenthesised, comma-separated argument list."""
        self.expect("(")
        args: list[_Node] = []
        if self.peek() != ")":
            args.append(self.expr())
            while self.peek() == ",":
                self.take()
                args.append(self.expr())
        self.expect(")")
        return args

    def _implied(self, node: _Node) -> _Node:
        r"""Fold implied multiplication (``ab`` is ``a * b``) onto ``node``."""
        while True:
            word = self.peek()
            if word is None or not _is_lower(word):
                return node
            self.take()
            node = ("bin", "*", node, ("var", word))


def _split_definition(line: str) -> tuple[str, str] | None:
    r"""Split a definition line into its left and right sides."""
    depth = 0
    for ind, char in enumerate(line):
        if char in "({":
            depth += 1
        elif char in ")}":
            depth -= 1
        elif char == "=" and depth == 0:
            return line[:ind], line[ind + 1 :]
    return None


def _parse_lhs(lhs: str) -> tuple[str, list[str]]:
    r"""Parse a definition's left-hand side into a name and parameters."""
    # The surrounding whitespace is.
    # back in an error message only.
    lhs = lhs.strip()
    tokens = _tokens(lhs)
    if not tokens:
        raise ValueError("definition has no left-hand side")
    if len(tokens) == 1 and _is_lower(tokens[0]):
        return tokens[0], []
    if _is_upper(tokens[0]):
        name = ""
        ind = 0
        while ind < len(tokens) and _is_upper(tokens[ind]):
            name += tokens[ind]
            ind += 1
        params: list[str] = []
        if ind < len(tokens):
            if tokens[ind] != "(":
                raise ValueError(f"malformed function header {lhs!r}")
            ind += 1
            while ind < len(tokens) and tokens[ind] != ")":
                if tokens[ind] == ",":
                    ind += 1
                    continue
                if not _is_lower(tokens[ind]):
                    raise ValueError(f"bad parameter {tokens[ind]!r}")
                params.append(tokens[ind])
                ind += 1
            # The loop cannot run out of.
            # closer, and ``)`` ends it.
            # ``bad parameter`` check above.
            ind += 1
        if ind != len(tokens):
            raise ValueError(f"trailing input in header {lhs!r}")
        return name, params
    # A custom operator: letters.
    # literal symbol of the pattern.
    pattern = ""
    op_params: list[str] = []
    for word in tokens:
        if _is_lower(word):
            pattern += "\0"
            op_params.append(word)
        elif len(word) == 1 and _is_symbol(word):
            pattern += word
        else:
            raise ValueError(f"bad operator pattern {lhs!r}")
    if not op_params or "\0" not in pattern:
        raise ValueError(f"operator {lhs!r} takes no arguments")
    if len(set(op_params)) != len(op_params):
        raise ValueError(f"operator {lhs!r} repeats a parameter")
    return pattern, op_params


def _blocks(code: str) -> list[str]:
    r"""Join a program's physical lines into logical ones."""
    out: list[str] = []
    pending = ""
    depth = 0
    for raw in code.splitlines():
        line = raw.strip()
        if not line and depth == 0:
            continue
        pending = f"{pending}\n{line}" if pending else line
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            out.append(pending)
            pending = ""
            depth = 0
    if pending:
        raise ValueError("unbalanced { in program")
    return out


def _body(rhs: str, defs: dict[str, _Definition]) -> list[_Node]:
    r"""Parse a definition's right-hand side into its list of statements."""
    text = rhs.strip()
    if text.startswith("{"):
        if not text.endswith("}"):
            # ``_blocks`` has already.
            # is a block with something.
            raise ValueError(f"trailing input after block in {text!r}")
        inner = text[1:-1]
        return [
            _Parser(_tokens(line), defs).parse()
            for line in (s.strip() for s in inner.splitlines())
            if line
        ]
    return [_Parser(_tokens(text), defs).parse()]


# -- evaluation.


class _Frame:
    r"""One call in progress: its body, its bindings, and its cursor."""

    def __init__(
        self,
        definition: _Definition,
        args: dict[str, object],
        *,
        printing: bool,
        assign: str | None,
    ) -> None:
        self.fn = definition
        self.locals = args
        self.stmt = 0
        self.work: list[tuple[_Node, list[object]]] = []
        self.value: object = 0
        self.returned = False
        self.printing = printing
        self.assign = assign

    def __repr__(self) -> str:
        r"""Identify the frame by its function and cursor."""
        return f"<frame {self.fn.name} @{self.stmt}>"


@dataclass
class _State:
    r"""Every changing value in an Algebraic Programming Language run."""

    defs: dict[str, _Definition]
    globals: dict[str, object]
    frames: list[_Frame]
    line: int
    pending: _Node | None
    steps: int


class _Machine:
    r"""The run state: the definitions, the globals, and the call stack."""

    # : The wiki gives no bound;.
    # : runaway expression cannot.
    # : leaving the hang detectors.
    _WORK_LIMIT = 1 << 20

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.lines = _blocks(code)
        self.state = _State({}, {}, [], 0, None, 0)

    @property
    def defs(self) -> dict[str, _Definition]:
        return self.state.defs

    @property
    def globals(self) -> dict[str, object]:
        return self.state.globals

    @property
    def frames(self) -> list[_Frame]:
        return self.state.frames

    @property
    def line(self) -> int:
        return self.state.line

    @line.setter
    def line(self, value: int) -> None:
        self.state.line = value

    @property
    def _steps(self) -> int:
        return self.state.steps

    @_steps.setter
    def _steps(self, value: int) -> None:
        self.state.steps = value

    # -- the VM's language-shaped.

    @property
    def halted(self) -> bool:
        r"""Whether every line has been executed and no frame is live."""
        return self.line >= len(self.lines) and not self.frames

    # : ``ip`` starts with a line.
    # : with each open frame's.
    ip_shape = "line"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""The line cursor followed by each live frame's statement index."""
        return (self.line, *(f.stmt for f in self.frames))

    @property
    def memory(self) -> list[int]:
        r"""The global bindings' integral values, in name order."""
        return [
            int(v) if isinstance(v, (int, float)) else 0
            for _, v in sorted(self.globals.items())
        ]

    @property
    def stack(self) -> list[object]:
        r"""The live call stack, outermost first."""
        return list(self.frames)

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.line,
            tuple(sorted((k, repr(v)) for k, v in self.globals.items())),
            tuple(
                (
                    f.fn.name,
                    f.stmt,
                    tuple(
                        (id(node), tuple(repr(v) for v in done))
                        for node, done in f.work
                    ),
                    repr(f.value),
                    f.returned,
                    tuple(sorted((k, repr(v)) for k, v in f.locals.items())),
                )
                for f in self.frames
            ),
            self.io.position(),
        )

    def frame_entry_key(self, frame: object) -> tuple[object, ...]:
        r"""Return what ``frame`` is about to run, for the ancestor check."""
        if not isinstance(frame, _Frame):
            raise AssertionError("isinstance(frame, _Frame)")
        return (
            frame.fn.name,
            tuple(sorted((k, repr(v)) for k, v in frame.locals.items())),
            self.io.position(),
        )

    # -- stepping.

    def step(self) -> None:
        r"""Advance the program by one definition, read, or expression node."""
        if self.halted:
            return
        if self.frames:
            self._step_frame(self.frames[-1])
            return
        self._start_line()

    def _start_line(self) -> None:
        r"""Consume one logical line: define a name, or begin evaluating."""
        text = self.lines[self.line]
        self.line += 1
        split = _split_definition(text)
        if split is None:
            node = _Parser(_tokens(text), self.defs).parse()
            self._bind_inputs(node)
            self._push(_Definition("", [], [node]), {}, printing=True)
            return
        lhs, rhs = split
        name, params = _parse_lhs(lhs)
        if not params and _is_lower(name):
            # ``n = 123``: a plain.
            # prints and takes no input, so.
            # flagged to assign the result.
            self._push(_Definition("", [], _body(rhs, self.defs)), {}, assign=name)
            return
        # The name is registered.
        # definition can refer to.
        # ``x.
        # defined, and the parser can.
        # it already knows.
        definition = _Definition(name, params, [("lit", 0)])
        self.defs[name] = definition
        definition.body = _body(rhs, self.defs)
        definition.control = [_contains_return(node) for node in definition.body]

    def _push(
        self,
        definition: _Definition,
        args: dict[str, object],
        *,
        printing: bool = False,
        assign: str | None = None,
    ) -> None:
        r"""Push a frame for ``definition`` and queue its first statement."""
        frame = _Frame(definition, args, printing=printing, assign=assign)
        frame.work.append((definition.body[0], []))
        self.frames.append(frame)

    def _bind_inputs(self, node: _Node) -> None:
        r"""Bind every unbound variable in ``node`` from input, in order."""
        for name in _free_variables(node):
            if name not in self.globals:
                self.globals[name] = self._read_number()

    def _read_number(self) -> _Number:
        r"""Read one line of input as a number."""
        text = self.io.input_str().strip()
        if not text:
            return 0
        try:
            return _number(text)
        except ValueError as exc:
            raise HaltError(f"input {text!r} is not a number") from exc

    def _step_frame(self, frame: _Frame) -> None:
        r"""Resolve one node of ``frame``'s current expression."""
        self._steps += 1
        if self._steps > self._WORK_LIMIT:
            raise HaltError("expression exceeded the evaluation budget")
        if not frame.work:
            self._advance(frame)
            return
        node, done = frame.work[-1]
        # Narrowed on ``node`` itself.
        # so mypy can discriminate the.
        # variable first loses the link.
        if node[0] == "lit":
            self._resolve(frame, node[1])
            return
        if node[0] == "var":
            self._resolve(frame, self._lookup(frame, node[1]))
            return
        if node[0] == "ref":
            self._resolve(frame, self._lookup_function(node[1]))
            return
        if node[0] == "neg":
            if not done:
                self._descend(frame, node[1])
            else:
                self._resolve(frame, -_as_number(done[0]))
            return
        if node[0] == "ret":
            if not done:
                self._descend(frame, node[1])
                return
            # ``$`` exits the function.
            # expression around it is.
            frame.returned = True
            frame.value = done[0]
            frame.work.clear()
            return
        if node[0] == "bin":
            self._step_binary(frame, node, done)
            return
        self._step_call(frame, node, done)

    def _lookup(self, frame: _Frame, name: str) -> object:
        r"""Resolve a variable against the frame's locals, then the globals."""
        if name in frame.locals:
            return frame.locals[name]
        if name in self.globals:
            return self.globals[name]
        raise ValueError(f"unknown variable {name!r}")

    def _lookup_function(self, name: str) -> object:
        r"""Resolve a bare uppercase name to the definition it refers to."""
        if name in self.defs:
            return self.defs[name]
        raise ValueError(f"unknown function {name!r}")

    def _descend(self, frame: _Frame, node: _Node) -> None:
        r"""Queue ``node`` as the next sub-evaluation of the current one."""
        frame.work.append((node, []))

    def _step_binary(self, frame: _Frame, node: _Bin, done: list[object]) -> None:
        r"""Resolve one stage of a binary operator, short-circuiting & and |."""
        op = node[1]
        if not done:
            self._descend(frame, node[2])
            return
        if len(done) == 1:
            left = done[0]
            if op == "&" and not _truthy(left):
                self._resolve(frame, 0)
                return
            if op == "|" and _truthy(left):
                self._resolve(frame, left)
                return
            self._descend(frame, node[3])
            return
        left, right = done[0], done[1]
        if op in ("&", "|"):
            # The left operand did not.
            # the right one as evaluated.
            self._resolve(frame, right)
            return
        self._resolve(frame, _arith(op, _as_number(left), _as_number(right)))

    def _step_call(self, frame: _Frame, node: _Call, done: list[object]) -> None:
        r"""Evaluate a call's arguments, then push the callee's frame."""
        name, args = node[1], node[2]
        if len(done) < len(args):
            self._descend(frame, args[len(done)])
            return
        # A name bound to a *value* is.
        # which is how the wiki's.
        target = frame.locals.get(name)
        definition = target if isinstance(target, _Definition) else self.defs.get(name)
        if definition is None:
            raise ValueError(f"unknown function {name!r}")
        if len(done) != len(definition.params):
            raise ValueError(
                f"{definition.name!r} takes {len(definition.params)} "
                f"argument(s), got {len(done)}"
            )
        frame.work.pop()
        self._push(definition, dict(zip(definition.params, done, strict=True)))

    def _resolve(self, frame: _Frame, value: object) -> None:
        r"""Finish the innermost node, handing ``value`` to its parent."""
        frame.work.pop()
        frame.value = value
        if frame.work:
            frame.work[-1][1].append(value)

    def _advance(self, frame: _Frame) -> None:
        r"""Move to the frame's next statement, or return from it."""
        if not frame.returned and frame.stmt + 1 < len(frame.fn.body):
            # Every statement but the last.
            # MULTILINE example -- unless.
            # it a conditional return.
            if not frame.fn.control[frame.stmt]:
                self._print(frame.value)
            frame.stmt += 1
            frame.work.append((frame.fn.body[frame.stmt], []))
            return
        self._pop(frame)

    def _pop(self, frame: _Frame) -> None:
        r"""Return the frame's value to its caller, printing or assigning it."""
        value = frame.value
        self.frames.pop()
        if frame.assign is not None:
            self.globals[frame.assign] = value
        if not self.frames:
            if frame.printing:
                self._print(value)
            return
        parent = self.frames[-1]
        parent.value = value
        if parent.work:
            parent.work[-1][1].append(value)

    def _print(self, value: object) -> None:
        r"""Write one result, formatted the way the wiki's examples read."""
        number = _as_number(value)
        text = str(number) if isinstance(number, int) else _format_float(number)
        self.io.print_str(text + "\n")


def _format_float(value: float) -> str:
    r"""Render a float, dropping a trailing ``.0`` from an integral one."""
    return str(int(value)) if value.is_integer() else str(value)


def _truthy(value: object) -> bool:
    r"""Whether ``value`` is true: every number but zero, and any function."""
    if isinstance(value, _Definition):
        return True
    return _as_number(value) != 0


def _as_number(value: object) -> _Number:
    r"""Coerce a value to a number, refusing a function."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HaltError(f"expected a number, got {value!r}")
    return value


def _arith(op: str, left: _Number, right: _Number) -> _Number:
    r"""Apply one arithmetic operator, keeping integers exact."""
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            raise HaltError("division by zero")
        quotient = left / right
        # Keep an exact integer where.
        # unbounded-integer model.
        return int(quotient) if quotient.is_integer() else quotient
    if op == "%":
        if right == 0:
            raise HaltError("modulo by zero")
        return left % right
    if left == 0 and right < 0:
        raise HaltError("zero to a negative power")
    return left**right


def _contains_return(node: _Node) -> bool:
    r"""Whether ``$`` appears anywhere in ``node``; see."""
    if node[0] == "ret":
        return True
    if node[0] == "neg":
        return _contains_return(node[1])
    if node[0] == "bin":
        return _contains_return(node[2]) or _contains_return(node[3])
    if node[0] == "call":
        return any(_contains_return(arg) for arg in node[2])
    return False


def _free_variables(node: _Node) -> list[str]:
    r"""List the variables in ``node``, in order of first appearance."""
    out: list[str] = []

    def walk(current: _Node) -> None:
        if current[0] == "var":
            if current[1] not in out:
                out.append(current[1])
            return
        if current[0] in ("neg", "ret"):
            walk(current[1])
            return
        if current[0] == "bin":
            walk(current[2])
            walk(current[3])
            return
        if current[0] == "call":
            for arg in current[2]:
                walk(arg)

    walk(node)
    return out


def run(code: str, io: IO) -> None:
    r"""Run an APL program, printing the result of every executed line."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
