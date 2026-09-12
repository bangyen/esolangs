r"""Interpreter for Packlang."""

import re
import sys
from collections.abc import Callable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# There is no recursion ceiling.
# recursing natively, so a.
# heap and never touches.
# it is what ``esolangs.run``'s.
# reasoning ``grapheme.py`` and.

# : Statement opcodes.
# : function, with the two jump.
# : is an index increment and.
_PRINT = "print"  # charPut(expr).
_READ = "read"  # charGet(lvalue).
_INIT = "init"
_INCR = "incr"
_DECR = "decr"
_JUMP_UNLESS = "jz"  # If/While guard: jump when the.
_JUMP = "jmp"  # While back-edge.
_VALUE = "val"  # a bare expression statement:.

# : An expression node: a tag.
# : Heterogeneous by nature, so.
# : :func:`_node` and.
type _Expr = tuple[object, ...]

# : One variable: its name and.
#: scalars a single int.
type _Slot = tuple[str, object]
type _Store = tuple[_Slot, ...]

# : The whole run state as a.
# : store, and the function's.
# : for a run, so it is not.
# : with names, and.
type _State = tuple[int, _Store, int]


class _Type:
    r"""A declared type's bounds and the values it wraps to."""

    __slots__ = ("high", "length", "low", "over", "under")

    def __init__(
        self,
        low: int = 0,
        high: int = 255,
        under: int | None = None,
        over: int | None = None,
        length: int | None = None,
    ) -> None:
        self.low = low
        self.high = high
        # Default wrapping is modular,.
        # output implies for a plain.
        self.under = high if under is None else under
        self.over = low if over is None else over
        self.length = length

    def clamp(self, value: int) -> int:
        r"""Return ``value`` folded into the type's range."""
        if value < self.low:
            return self.under
        if value > self.high:
            return self.over
        return value

    def zero(self) -> object:
        r"""Return the type's default: its minimum, or a row of them."""
        return (self.low,) * self.length if self.length is not None else self.low


class _Function:
    r"""One function: its parameters, its statement list, and its owner."""

    __slots__ = ("body", "locals", "name", "package", "params", "uses")

    def __init__(
        self,
        name: str,
        params: tuple[str, ...],
        body: tuple[tuple[object, ...], ...],
        package: str,
        local_types: dict[str, _Type],
        uses: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.package = package
        self.locals = local_types
        self.uses = uses


class _Frame:
    r"""One call frame: the function, its cursor, and its own variables."""

    __slots__ = ("func", "pc", "pending", "result", "returned", "store")

    def __init__(self, func: _Function, store: _Store, pc: int = 0) -> None:
        self.func = func
        self.store = store
        self.pc = pc
        self.result = 0
        self.pending: _Expr | None = None
        self.returned: int | None = None

    def key(self) -> tuple[object, ...]:
        r"""Return the frame as a hashable value for :meth:`snapshot`."""
        return (self.func.name, self.pc, self.store, self.result)


def _strip_comments(code: str) -> str:
    r"""Remove ``%$ ."""
    out = []
    i = 0
    while i < len(code):
        if code.startswith("%$", i):
            end = code.find("%", i + 2)
            i = len(code) if end < 0 else end + 1
            out.append(" ")
        elif code[i] == "%":
            end = code.find("\n", i)
            i = len(code) if end < 0 else end
            out.append(" ")
        else:
            out.append(code[i])
            i += 1
    return "".join(out)


_TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\d+|[{}();:,^!]")


def _tokenize(code: str) -> list[str]:
    r"""Return the program's tokens, comments already stripped."""
    tokens = _TOKEN.findall(code)
    if "".join(tokens) != "".join(code.split()):
        raise ValueError("program contains characters that are not Packlang tokens")
    return tokens


class _Parser:
    r"""Recursive-descent parser producing flat statement lists."""

    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next_token(self) -> str:
        word = self.peek()
        if word is None:
            raise ValueError("unexpected end of program")
        self.pos += 1
        return word

    def expect(self, word: str) -> None:
        got = self.next_token()
        if got != word:
            raise ValueError(f"expected {word!r}, got {got!r}")

    # -- types.

    def parse_type(self) -> _Type:
        r"""Parse a datatype, including its parenthesized parameters."""
        name = self.next_token()
        if name == "Integer" and self.peek() == "(":
            self.next_token()
            args = [self.number() for _ in self.commas(4)]
            self.expect(")")
            return _Type(args[0], args[1], args[2], args[3])
        if name == "Array":
            self.expect("(")
            inner = self.parse_type()
            self.expect(",")
            length = self.number()
            self.expect(")")
            if length < 0:  # pragma: no cover - `number` requires isdigit
                raise ValueError("array length must not be negative")
            return _Type(inner.low, inner.high, inner.under, inner.over, length)
        if name == "Pointer":
            self.expect("(")
            inner = self.parse_type()
            self.expect(")")
            # A pointer is stored as the.
            # takes an address, and.
            # behaves identically either.
            return inner
        if name in ("Integer", "Char", "String"):
            # String is a byte sequence;.
            # the wiki, it is an array.
            return _Type() if name != "String" else _Type(length=0)
        raise ValueError(f"unknown datatype {name!r}")

    def commas(self, count: int) -> range:
        r"""Yield ``count`` slots, consuming the commas between them."""
        return range(count)

    def number(self) -> int:
        r"""Parse a decimal integer literal; see the module docstring."""
        word = self.next_token()
        if word == ",":
            word = self.next_token()
        if not word.isdigit():
            raise ValueError(f"expected a number, got {word!r}")
        return int(word)

    # -- expressions.

    def expression(self) -> tuple[object, ...]:
        r"""Parse ``a ^ b`` (left-associative) into a postfix tuple."""
        node = self.unary()
        while self.peek() == "^":
            self.next_token()
            node = ("xor", node, self.unary())
        return node

    def unary(self) -> tuple[object, ...]:
        if self.peek() == "!":
            self.next_token()
            return ("not", self.unary())
        return self.primary()

    def primary(self) -> tuple[object, ...]:
        word = self.next_token()
        if word == "(":
            node = self.expression()
            self.expect(")")
            return node
        if word.isdigit():
            return ("lit", int(word))
        if not word[:1].isalpha() and word[:1] != "_":
            raise ValueError(f"unexpected token {word!r} in an expression")
        if self.peek() == "(":
            self.next_token()
            # ``myArray(length)`` is.
            # so ``length`` here is the.
            if self.peek() == "length":
                self.next_token()
                self.expect(")")
                return ("length", word)
            args = []
            if self.peek() != ")":
                args.append(self.expression())
                while self.peek() == ",":
                    self.next_token()
                    args.append(self.expression())
            self.expect(")")
            # An index and a call are.
            # depends on the name, so it is.
            return ("apply", word, tuple(args))
        return ("var", word)

    # -- statements.

    def lvalue(self) -> tuple[str, tuple[object, ...] | None]:
        r"""Parse a target: a name, optionally with an index."""
        name = self.next_token()
        if not (name[:1].isalpha() or name[:1] == "_"):
            raise ValueError(f"expected a variable name, got {name!r}")
        index = None
        if self.peek() == "(":
            self.next_token()
            index = self.expression()
            self.expect(")")
        return name, index

    def block(self, out: list[list[object]], local_types: dict[str, _Type]) -> None:
        r"""Parse ``{ ."""
        self.expect("{")
        while self.peek() != "}":
            if self.peek() is None:
                raise ValueError("unbalanced '{' in program")
            self.statement(out, local_types)
        self.next_token()

    def statement(self, out: list[list[object]], local_types: dict[str, _Type]) -> None:
        word = self.peek()
        if word in ("INIT", "INCR", "DECR"):
            self.next_token()
            name, index = self.lvalue()
            self.expect(";")
            op = {"INIT": _INIT, "INCR": _INCR, "DECR": _DECR}[str(word)]
            out.append([op, name, index])
            return
        if word == "If":
            self.next_token()
            guard = self.expression()
            self.expect("Then")
            patch = len(out)
            out.append([_JUMP_UNLESS, guard, -1])
            self.block(out, local_types)
            out[patch][2] = len(out)
            return
        if word == "While":
            self.next_token()
            top = len(out)
            guard = self.expression()
            self.expect("Do")
            patch = len(out)
            out.append([_JUMP_UNLESS, guard, -1])
            self.block(out, local_types)
            out.append([_JUMP, top])
            out[patch][2] = len(out)
            return
        # A declaration inside a.
        if word is not None and word in _DATATYPES and self.is_declaration():
            declared = self.parse_type()
            name = self.next_token()
            self.expect(";")
            local_types[name] = declared
            return
        # Otherwise an expression.
        # call or the function's.
        expr = self.expression()
        self.expect(";")
        if expr[0] == "apply" and expr[1] in ("charPut", "charGet"):
            args = expr[2]
            # ``_primary`` always builds an.
            # so this narrowing cannot.
            # and would be a malformed tree.
            if not isinstance(args, tuple):
                raise AssertionError("isinstance(args, tuple)")
            if expr[1] == "charPut":
                if len(args) != 1:
                    raise ValueError("charPut takes exactly one argument")
                out.append([_PRINT, args[0]])
                return
            target = args[0] if len(args) == 1 else None
            if not isinstance(target, tuple) or target[0] not in ("var", "apply"):
                raise ValueError("charGet takes exactly one variable")
            name = str(target[1])
            # ``charGet(a(i))`` reads into.
            # the sole argument of the.
            index = None
            if target[0] == "apply":
                slots = target[2]
                if not isinstance(slots, tuple):
                    raise AssertionError("isinstance(slots, tuple)")
                index = slots[0] if slots else None
            out.append([_READ, name, index])
            return
        out.append([_VALUE, expr])

    def is_declaration(self) -> bool:
        r"""Whether the tokens at the cursor open a declaration, not a call."""
        save = self.pos
        try:
            self.parse_type()
            name = self.peek()
            ok = bool(name and (name[:1].isalpha() or name[:1] == "_"))
            if ok:
                self.pos += 1
                ok = self.peek() == ";"
            return ok
        except ValueError:
            return False
        finally:
            self.pos = save


_DATATYPES = frozenset({"Integer", "Char", "String", "Array", "Pointer"})
# : The built-in package every.
_IO_PACKAGE = "IO"


class _Program:
    r"""A parsed program: its functions, globals, and dependency graph."""

    __slots__ = ("dependencies", "entry", "functions", "globals", "types")

    def __init__(self) -> None:
        self.functions: dict[str, _Function] = {}
        self.globals: dict[str, _Type] = {}
        self.dependencies: dict[str, frozenset[str]] = {}
        self.types: dict[str, _Type] = {}
        self.entry: _Function | None = None


def _parse(code: str) -> _Program:
    r"""Parse a whole program into its packages and functions."""
    tokens = _tokenize(_strip_comments(code))
    if not tokens:
        raise ValueError("empty program")
    parser = _Parser(tokens)
    program = _Program()
    order: list[str] = []
    while parser.peek() is not None:
        kind = parser.next_token()
        if kind not in ("Package", "Dependency"):
            raise ValueError(f"expected a Package or Dependency, got {kind!r}")
        deps = []
        if parser.peek() == ":":
            parser.next_token()
            deps.append(parser.next_token())
            while parser.peek() == ",":
                parser.next_token()
                deps.append(parser.next_token())
        parser.expect("{")
        members: list[tuple[str, _Function]] = []
        globals_here: dict[str, _Type] = {}
        while parser.peek() != "}":
            if parser.peek() is None:
                raise ValueError("unbalanced '{' in package body")
            _member(parser, members, globals_here)
        parser.next_token()
        package = parser.next_token()
        parser.expect(";")
        program.dependencies[package] = frozenset(deps)
        program.globals.update(globals_here)
        program.types.update(globals_here)
        for name, func in members:
            func.package = package
            program.functions[name] = func
        order.append(package)
    program.entry = _entry(program, order)
    return program


def _member(
    parser: _Parser,
    members: list[tuple[str, _Function]],
    globals_here: dict[str, _Type],
) -> None:
    r"""Parse one package member: a variable declaration or a function."""
    declared = parser.parse_type()
    name = parser.next_token()
    if parser.peek() == ";":
        parser.next_token()
        globals_here[name] = declared
        return
    params: list[str] = []
    uses: list[str] = []
    local_types: dict[str, _Type] = {}
    if parser.peek() == ":":
        parser.next_token()
        while True:
            # ``Type name`` is a value.
            # ``Integer a, Integer b``); a.
            # the function uses.
            # spelled differently on the.
            if parser.peek() in _DATATYPES:
                param_type = parser.parse_type()
                param = parser.next_token()
                local_types[param] = param_type
                params.append(param)
            else:
                uses.append(parser.next_token())
            if parser.peek() != ",":
                break
            parser.next_token()
    body: list[list[object]] = []
    parser.block(body, local_types)
    members.append(
        (
            name,
            _Function(
                name,
                tuple(params),
                tuple(tuple(stmt) for stmt in body),
                "",
                local_types,
                tuple(uses),
            ),
        )
    )


def _entry(program: _Program, order: list[str]) -> _Function:
    r"""Return the function a run starts at; see the module docstring."""
    main = program.functions.get("main")
    if main is not None and not main.params:
        return main
    for package in reversed(order):
        candidates = [
            f
            for f in program.functions.values()
            if f.package == package and not f.params
        ]
        if len(candidates) == 1:
            return candidates[0]
    # A parameterless function.
    # own function takes a.
    raise ValueError("program has no parameterless entry function")


def _get(store: _Store, name: str) -> object:
    for slot, value in store:
        if slot == name:
            return value
    raise HaltError(f"undefined variable {name!r}")


def _set(store: _Store, name: str, value: object) -> _Store:
    return tuple((slot, value if slot == name else old) for slot, old in store)


def _truth(value: int) -> bool:
    return value != 0


def _node(value: object) -> _Expr:
    r"""Narrow a child slot back to an expression node."""
    if not isinstance(value, tuple):
        raise HaltError(f"malformed expression node {value!r}")
    return value


def _int(value: object) -> int:
    r"""Narrow a literal or a stored scalar to an ``int``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise HaltError(f"expected a number, got {value!r}")
    return value


def _evaluate(node: _Expr, store: _Store, program: _Program, caller: str) -> int:
    r"""Return the value of an expression, which contains no unresolved."""
    kind = node[0]
    if kind in ("lit", "done"):
        return _int(node[1])
    if kind == "var":
        value = _get(store, str(node[1]))
        if isinstance(value, tuple):
            raise HaltError(f"{node[1]!r} is an array and has no scalar value")
        return _int(value)
    if kind == "length":
        value = _get(store, str(node[1]))
        if not isinstance(value, tuple):
            raise HaltError(f"{node[1]!r} is not an array")
        return len(value)
    if kind == "xor":
        left = _evaluate(_node(node[1]), store, program, caller)
        right = _evaluate(_node(node[2]), store, program, caller)
        return left ^ right
    if kind == "not":
        value = _evaluate(_node(node[1]), store, program, caller)
        return 0 if _truth(value) else 1
    if kind == "apply":
        return _apply(node, store, program, caller)
    raise HaltError(f"cannot evaluate {kind!r}")


def _apply(node: _Expr, store: _Store, program: _Program, caller: str) -> int:
    r"""Evaluate an array index."""
    name = str(node[1])
    args = [_node(arg) for arg in _node(node[2])]
    if not any(slot == name for slot, _ in store):
        raise HaltError(f"unresolved call to {name!r}")
    value = _get(store, name)
    if not isinstance(value, tuple):
        raise HaltError(f"{name!r} is not an array")
    if len(args) != 1:
        raise HaltError(f"indexing {name!r} takes exactly one index")
    index = _evaluate(args[0], store, program, caller)
    if not 0 <= index < len(value):
        raise HaltError(f"index {index} is outside {name!r}")
    return _int(value[index])


def _visible(func: _Function, caller: str, program: _Program) -> bool:
    r"""Whether ``caller``'s package may call ``func``."""
    if func.package == caller:
        return True
    seen: set[str] = set()
    frontier = [caller]
    while frontier:
        package = frontier.pop()
        if package in seen:
            continue
        seen.add(package)
        if package == func.package:
            return True
        frontier.extend(program.dependencies.get(package, frozenset()))
    return func.package in seen


def _pending_call(
    node: _Expr, store: _Store, program: _Program, caller: str
) -> _Expr | None:
    r"""Return the call :func:`_evaluate` would reach first, or None."""
    kind = node[0]
    if kind in ("lit", "done", "var", "length"):
        return None
    if kind == "not":
        return _pending_call(_node(node[1]), store, program, caller)
    if kind == "xor":
        return _pending_call(_node(node[1]), store, program, caller) or _pending_call(
            _node(node[2]), store, program, caller
        )
    if kind != "apply":
        return None
    for arg in _node(node[2]):
        found = _pending_call(_node(arg), store, program, caller)
        if found is not None:
            return found
    name = str(node[1])
    if any(slot == name for slot, _ in store):
        return None  # an array index, evaluated in.
    return node


def _substitute(node: _Expr, target: _Expr, value: int) -> _Expr:
    r"""Return ``node`` with ``target`` replaced by the literal ``value``."""
    if node is target:
        return ("done", value)
    kind = node[0]
    if kind in ("lit", "done", "var", "length"):
        return node
    if kind == "not":
        return ("not", _substitute(_node(node[1]), target, value))
    if kind == "xor":
        return (
            "xor",
            _substitute(_node(node[1]), target, value),
            _substitute(_node(node[2]), target, value),
        )
    if kind != "apply":
        return node
    return (
        "apply",
        node[1],
        tuple(_substitute(_node(arg), target, value) for arg in _node(node[2])),
    )


def _callee(node: _Expr, program: _Program, caller: str) -> _Function:
    r"""Resolve the function a pending call names, checking visibility."""
    name = str(node[1])
    func = program.functions.get(name)
    if func is None:
        raise HaltError(f"undefined function {name!r}")
    if not _visible(func, caller, program):
        raise HaltError(
            f"{caller!r} does not depend on {func.package!r}, "
            f"so {name!r} is not in scope"
        )
    return func


def _entered(func: _Function, values: list[int], program: _Program) -> _Frame:
    r"""Build the frame a call runs in, binding its arguments."""
    if len(values) != len(func.params):
        raise HaltError(f"{func.name!r} takes {len(func.params)} arguments")
    store = _initial_store(func, program)
    bound = dict(zip(func.params, values, strict=True))
    return _Frame(func, tuple((slot, bound.get(slot, value)) for slot, value in store))


def _initial_store(func: _Function, program: _Program) -> _Store:
    r"""Build a function's store: the globals it sees, plus its own locals."""
    types = dict(program.globals)
    types.update(func.locals)
    return tuple((name, kind.zero()) for name, kind in sorted(types.items()))


def _type_of(name: str, func: _Function, program: _Program) -> _Type:
    return func.locals.get(name) or program.types.get(name) or _Type()


def _advance(
    frame: _Frame,
    program: _Program,
    byte: int | None,
    stmt: tuple[object, ...] | None = None,
) -> tuple[_Frame, str | None, bool]:
    r"""Return the frame after one statement, any output, and whether to."""
    if stmt is None:  # pragma: no cover - both call sites pass `prepared`
        stmt = frame.func.body[frame.pc]
    op = stmt[0]
    store = frame.store
    # Name resolution is done from.
    package = frame.func.package
    pc = frame.pc + 1
    out: str | None = None
    result = frame.result

    if op == _PRINT:
        value = _evaluate(_node(stmt[1]), store, program, package)
        out = chr(value % 256)
    elif op == _READ:
        if byte is None:
            return frame, None, True
        store = _write(
            store,
            program,
            str(stmt[1]),
            stmt[2],
            lambda _old: byte,
            package,
        )
    elif op == _INIT:
        kind = _type_of(str(stmt[1]), frame.func, program)
        store = _write(
            store,
            program,
            str(stmt[1]),
            stmt[2],
            lambda _o: kind.low,
            package,
            whole=kind,
        )
    elif op in (_INCR, _DECR):
        step = 1 if op == _INCR else -1
        kind = _type_of(str(stmt[1]), frame.func, program)
        store = _write(
            store,
            program,
            str(stmt[1]),
            stmt[2],
            lambda old: kind.clamp(old + step),
            package,
        )
    elif op == _JUMP_UNLESS:
        guard = _evaluate(_node(stmt[1]), store, program, package)
        if not _truth(guard):
            pc = _int(stmt[2])
    elif op == _JUMP:
        pc = _int(stmt[1])
    # Every opcode the parser emits.
    # exhaustive and this last test.
    elif op == _VALUE:  # pragma: no branch
        result = _evaluate(_node(stmt[1]), store, program, package)

    new = _Frame(frame.func, store, pc)
    new.result = result
    return new, out, False


def _write(
    store: _Store,
    program: _Program,
    name: str,
    index: object,
    update: Callable[[int], int],
    caller: str,
    whole: _Type | None = None,
) -> _Store:
    r"""Apply ``update`` to a variable or one array element."""
    value = _get(store, name)
    if isinstance(value, tuple):
        if index is None:
            if whole is not None:
                return _set(store, name, whole.zero())
            raise HaltError(f"{name!r} is an array and needs an index")
        at = _evaluate(_node(index), store, program, caller)
        if not 0 <= at < len(value):
            raise HaltError(f"index {at} is outside {name!r}")
        row = list(value)
        row[at] = update(_int(row[at]))
        return _set(store, name, tuple(row))
    if index is not None:
        raise HaltError(f"{name!r} is not an array")
    return _set(store, name, update(_int(value)))


# : Where each statement kind.
# : The three write opcodes.
# : itself be a call; ``_JUMP``.
_EXPR_SLOT = {
    _PRINT: 1,
    _JUMP_UNLESS: 1,
    _VALUE: 1,
    _READ: 2,
    _INIT: 2,
    _INCR: 2,
    _DECR: 2,
}


def _expression_of(stmt: tuple[object, ...]) -> _Expr | None:
    r"""Return the expression ``stmt`` evaluates, or None if it has none."""
    slot = _EXPR_SLOT.get(str(stmt[0]))
    if slot is None or slot >= len(stmt) or stmt[slot] is None:
        return None
    return _node(stmt[slot])


def _resolved(frame: _Frame) -> tuple[object, ...]:
    r"""Return the statement to run: the parsed one, or the resolved copy."""
    stmt = frame.func.body[frame.pc]
    if frame.pending is None:
        return stmt
    slot = _EXPR_SLOT.get(str(stmt[0]))
    if slot is None:  # pragma: no cover - only _JUMP lacks a slot, and a
        # jump never has a pending.
        return stmt
    parts = list(stmt)
    parts[slot] = frame.pending
    return tuple(parts)


class _Machine:
    r"""The run state: a stack of call frames and the parsed program."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.program = _parse(code)
        entry = self.program.entry
        # _parse raises when a program.
        if entry is None:
            raise AssertionError("entry is not None")
        self.frames = [_Frame(entry, _initial_store(entry, self.program))]

    @property
    def frame(self) -> _Frame:
        r"""The innermost frame: the one ``step`` advances."""
        return self.frames[-1]

    @property
    def halted(self) -> bool:
        r"""Whether every frame has run out, the entry function last."""
        return not self.frames

    @property
    def ip(self) -> int:
        r"""The current statement position."""
        return self.frame.pc if self.frames else 0

    @property
    def memory(self) -> list[object]:
        r"""The addressable cells: the innermost frame's variables, in order."""
        cells: list[object] = []
        if not self.frames:
            return cells
        for _name, value in self.frame.store:
            cells.extend(value) if isinstance(value, tuple) else cells.append(value)
        return cells

    @property
    def stack(self) -> list[object]:
        r"""The suspended callers, innermost last."""
        return [frame.pc for frame in self.frames[:-1]]

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # Every frame's cursor, store.
        # through resolving the calls.
        # input position -- a repeat.
        # real cycle.
        # returns, so it is built fresh.
        return (
            tuple(
                (frame.key(), repr(frame.pending), frame.returned)
                for frame in self.frames
            ),
            self.io.position(),
        )

    def step(self) -> None:
        r"""Advance the innermost frame, owning the two ports."""
        if self.halted:
            return
        frame = self.frame
        if frame.pc >= len(frame.func.body):
            self._finish(frame)
            return
        if self._resolve(frame):
            return
        prepared = _resolved(frame)
        result, out, wants_read = _advance(frame, self.program, None, prepared)
        if wants_read:
            # ``input_char`` reads a line.
            # already gives a blank line.
            # ``tests/interpreters/test_inpu.
            # callee reaches this the same.
            # its statements are stepped,.
            byte = self.io.input_char()
            result, out, _ = _advance(frame, self.program, byte, prepared)
        result.pending = None
        result.returned = None
        self.frames[-1] = result
        if out is not None:
            self.io.print_char(out)

    def _resolve(self, frame: _Frame) -> bool:
        r"""Push a frame for the next unresolved call, if the statement has one."""
        expr = _expression_of(frame.func.body[frame.pc])
        if expr is None:
            return False
        working = frame.pending if frame.pending is not None else expr
        package = frame.func.package
        if frame.returned is not None:
            call = _pending_call(working, frame.store, self.program, package)
            # A value is waiting only.
            # so the same search finds it.
            if call is not None:  # pragma: no branch
                working = _substitute(working, call, frame.returned)
            frame.returned = None
        call = _pending_call(working, frame.store, self.program, package)
        if call is None:
            frame.pending = working
            return False
        frame.pending = working
        func = _callee(call, self.program, package)
        values = [
            _evaluate(_node(arg), frame.store, self.program, package)
            for arg in _node(call[2])
        ]
        self.frames.append(_entered(func, values, self.program))
        return True

    def _finish(self, frame: _Frame) -> None:
        r"""Pop a finished frame, delivering its value to the caller."""
        self.frames.pop()
        if self.frames:
            self.frames[-1].returned = frame.result


def run(code: str, io: IO) -> None:
    r"""Run a Packlang program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
