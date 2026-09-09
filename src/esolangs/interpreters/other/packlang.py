"""Interpreter for Packlang.

Packlang organizes code into *packages*: a package declares variables and
one or more functions, and names the dependencies whose functions it may
call (``Package : IO, myDep { ... } myName;``).  Variables are typed
(``Integer``, ``Char``, ``String``, ``Array(type, length)``) and manipulated
by ``INIT``/``INCR``/``DECR`` rather than assignment; ``Integer(min, max,
under, over)`` bounds a counter and names the values it wraps to.  Control
flow is ``If cond Then { ... }`` and ``While cond Do { ... }``.  ``^`` is
XOR and ``!`` is logical negation, so ``a ^ b`` is a not-equal test and
``!(a ^ b)`` an equality test -- the spelling every wiki example uses.  The
built-in ``IO`` package provides ``charPut(value)`` and ``charGet(var)``.

Programs are parsed into a flat statement list per function, so
:class:`_Machine` steps one statement at a time and :func:`_advance` is a
pure transition over an immutable state.  The variable store is a tuple of
``(name, value)`` pairs and the call stack a tuple of frames, so
:meth:`_Machine.snapshot` is hashable as it stands and a repeated state
proves a loop.  The scope stack grows without bound, so a call returns an
*effect* for the shell to apply rather than a whole new store.

**Numeric literals are decimal.**  The wiki's examples disagree, and this
is the gap the roadmap flags.  ``charPut(72)`` (Hello, World!),
``charPut(48)``/``charPut(49)`` (truth-machine) and ``c ^ 10`` with
``Array(Char, 100)`` (cat) only work read as decimal; PlusOrMinus's
``101011``/``101101`` and the dependency example's ``110000``/``101``/
``011``/``001`` only work read as *binary* character codes.  A pure binary
reading is refuted outright -- four of the five examples contain literals
that are not binary at all, including PlusOrMinus's own ``Integer(0, 255,
255, 0)``.  That leaves decimal against a hybrid ("all-0/1 digits mean
binary"), 3 examples each; decimal wins because a literal's base must not
depend on its digit inventory, and because the two examples it declares
wrong carry the author's own error markers: the comment ``48 (1100000)``
mis-writes 48, whose binary is ``110000``, and ``equals(101, 011)`` uses
leading zeros, a binary-writing habit.  So PlusOrMinus and the dependency
example are declared wrong here and print mojibake rather than ``+-`` and
``0110``; the tests pin both readings so the decision is visible.

Further decisions for gaps the wiki leaves open:

* **Entry point.**  The wiki never says what runs.  This interpreter calls
  the parameterless function named ``main``, else the sole parameterless
  function of the last-declared package -- which is what makes
  PlusOrMinus runnable, its ``Integer plusOrMinus : code`` naming a
  package variable rather than taking an argument.  A program with no
  such function raises :class:`ValueError`, as does an unbalanced or
  empty program, a malformed declaration, or a call with the wrong
  argument count.
* **EOF.**  ``charGet`` reads a line and takes its first byte.  The wiki
  says empty input returns a newline, but this package reads a blank line
  as 0 everywhere (``tests/interpreters/test_input_convention.py`` pins
  that across all interpreters), so the shared convention wins over the
  wiki here and an empty line is 0.  Reading past the end of the input is
  the separate case and raises :class:`EOFError`.

  One consequence is worth naming: input arrives through ``splitlines``,
  so a line never *begins* with byte 10 and ``charGet`` cannot return it.
  The wiki cat's ``While c ^ 10 Do`` terminator is therefore unreachable
  here -- the program parses and accumulates but never leaves the loop.
  That is a property of the package's line-oriented IO rather than of
  this interpreter; the test file pins both the cat's real behavior and
  the same construction with a reachable guard.
* **Invalid runtime operations** raise
  :class:`~esolangs.exceptions.HaltError`: an undefined variable or
  function, a call to a function the caller's package does not depend on,
  an array index outside its length, and recursion past
  :data:`_MAX_DEPTH` frames.
* **Bounds.**  A plain ``Integer`` and a ``Char`` are unbounded below at 0
  and wrap modulo 256 above, matching ``charPut``'s byte output;
  ``Integer(min, max, under, over)`` wraps to the named values instead.
  ``INIT`` sets a variable to its type's minimum, and an ``Array`` to a
  row of them, which is what the cat example's ``INIT input`` relies on.
* **A function's value** is its last evaluated expression statement (the
  trailing ``0;`` in every wiki example); a function that evaluates none
  returns 0.
"""

import re
import sys
from collections.abc import Callable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# Recursion ceiling.  The wiki gives no limit, but an interpreter must
# terminate by construction: the fuzz suite feeds random programs, and a
# self-calling function would otherwise exhaust the Python stack rather
# than raise.  1000 frames is far past what any wiki example needs (the
# deepest calls one level, into a dependency).
_MAX_DEPTH = 1000

#: Statement opcodes.  A program is parsed into a flat tuple of these per
#: function, with the two jump targets resolved at parse time, so stepping
#: is an index increment and no tree walk survives into the run.
_PRINT = "print"  # charPut(expr)
_READ = "read"  # charGet(lvalue)
_INIT = "init"
_INCR = "incr"
_DECR = "decr"
_JUMP_UNLESS = "jz"  # If/While guard: jump when the expression is false
_JUMP = "jmp"  # While back-edge
_VALUE = "val"  # a bare expression statement: the function's return value

#: An expression node: a tag followed by names, literals, or sub-nodes.
#: Heterogeneous by nature, so the slots are narrowed at use by
#: :func:`_node` and :func:`_int` rather than modelled per tag.
type _Expr = tuple[object, ...]

#: One variable: its name and its value.  Arrays hold a tuple of values;
#: scalars a single int.
type _Slot = tuple[str, object]
type _Store = tuple[_Slot, ...]

#: The whole run state as a value: the statement cursor, the variable
#: store, and the function's value so far.  The parsed program is constant
#: for a run, so it is not part of the state; :class:`_Frame` is this tuple
#: with names, and :meth:`_Frame.key` is the tuple itself.
type _State = tuple[int, _Store, int]


class _Type:
    """A declared type's bounds and the values it wraps to.

    ``length`` is None for a scalar and the row count for an array, so one
    object describes both and ``INIT`` can build either from it.
    """

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
        # Default wrapping is modular, which is what ``charPut``'s byte
        # output implies for a plain Integer and a Char.
        self.under = high if under is None else under
        self.over = low if over is None else over
        self.length = length

    def clamp(self, value: int) -> int:
        """Return ``value`` folded into the type's range."""
        if value < self.low:
            return self.under
        if value > self.high:
            return self.over
        return value

    def zero(self) -> object:
        """Return the type's default: its minimum, or a row of them."""
        return (self.low,) * self.length if self.length is not None else self.low


class _Function:
    """One function: its parameters, its statement list, and its owner.

    ``params`` holds only the *typed* parameters (``: Integer a``), which
    take a value from the caller.  A bare name after the colon
    (PlusOrMinus's ``Integer plusOrMinus : code``) names a package
    variable the function uses rather than an argument it receives, so it
    is not a parameter and does not make the function uncallable as an
    entry point.
    """

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
    """One call frame: the function, its cursor, and its own variables."""

    __slots__ = ("func", "pc", "result", "store")

    def __init__(self, func: _Function, store: _Store, pc: int = 0) -> None:
        self.func = func
        self.store = store
        self.pc = pc
        self.result = 0

    def key(self) -> tuple[object, ...]:
        """Return the frame as a hashable value for :meth:`snapshot`."""
        return (self.func.name, self.pc, self.store, self.result)


def _strip_comments(code: str) -> str:
    """Remove ``%$ ... %`` blocks and ``% ...`` line comments.

    Block comments are taken first: ``%$`` opens one and the next bare
    ``%`` closes it, so a line comment inside a block is part of the block.
    Both are replaced by a space rather than deleted, so ``a%c%b`` cannot
    fuse into one token.
    """
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
    """Return the program's tokens, comments already stripped.

    Any character the pattern does not match is not a Packlang token, so a
    program containing one is malformed -- the fuzz suite's random input is
    exactly that case, and it must raise rather than be silently skipped.
    """
    tokens = _TOKEN.findall(code)
    if "".join(tokens) != "".join(code.split()):
        raise ValueError("program contains characters that are not Packlang tokens")
    return tokens


class _Parser:
    """Recursive-descent parser producing flat statement lists.

    Expressions become a small postfix tuple and statements a flat list
    with jumps resolved, so nothing in the run has to walk a tree.
    """

    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next_token(self) -> str:
        token = self.peek()
        if token is None:
            raise ValueError("unexpected end of program")
        self.pos += 1
        return token

    def expect(self, token: str) -> None:
        got = self.next_token()
        if got != token:
            raise ValueError(f"expected {token!r}, got {got!r}")

    # -- types ---------------------------------------------------------

    def parse_type(self) -> _Type:
        """Parse a datatype, including its parenthesized parameters."""
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
            if length < 0:
                raise ValueError("array length must not be negative")
            return _Type(inner.low, inner.high, inner.under, inner.over, length)
        if name == "Pointer":
            self.expect("(")
            inner = self.parse_type()
            self.expect(")")
            # A pointer is stored as the value it refers to: no example
            # takes an address, and charGet's "variable or pointer" case
            # behaves identically either way.
            return inner
        if name in ("Integer", "Char", "String"):
            # String is a byte sequence; with no literal syntax for one on
            # the wiki, it is an array whose length a declaration fixes.
            return _Type() if name != "String" else _Type(length=0)
        raise ValueError(f"unknown datatype {name!r}")

    def commas(self, count: int) -> range:
        """Yield ``count`` slots, consuming the commas between them."""
        return range(count)

    def number(self) -> int:
        """Parse a decimal integer literal; see the module docstring."""
        token = self.next_token()
        if token == ",":  # nosec B105
            token = self.next_token()
        if not token.isdigit():
            raise ValueError(f"expected a number, got {token!r}")
        return int(token)

    # -- expressions ---------------------------------------------------

    def expression(self) -> tuple[object, ...]:
        """Parse ``a ^ b`` (left-associative) into a postfix tuple."""
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
        token = self.next_token()
        if token == "(":  # nosec B105
            node = self.expression()
            self.expect(")")
            return node
        if token.isdigit():
            return ("lit", int(token))
        if not token[:1].isalpha() and token[:1] != "_":
            raise ValueError(f"unexpected token {token!r} in an expression")
        if self.peek() == "(":
            self.next_token()
            # ``myArray(length)`` is spelled exactly like that on the wiki,
            # so ``length`` here is the keyword, not a variable named so.
            if self.peek() == "length":
                self.next_token()
                self.expect(")")
                return ("length", token)
            args = []
            if self.peek() != ")":
                args.append(self.expression())
                while self.peek() == ",":
                    self.next_token()
                    args.append(self.expression())
            self.expect(")")
            # An index and a call are spelled identically; which one it is
            # depends on the name, so it is resolved at run time.
            return ("apply", token, tuple(args))
        return ("var", token)

    # -- statements ----------------------------------------------------

    def lvalue(self) -> tuple[str, tuple[object, ...] | None]:
        """Parse a target: a name, optionally with an index."""
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
        """Parse ``{ ... }``, appending statements to ``out``."""
        self.expect("{")
        while self.peek() != "}":
            if self.peek() is None:
                raise ValueError("unbalanced '{' in program")
            self.statement(out, local_types)
        self.next_token()

    def statement(self, out: list[list[object]], local_types: dict[str, _Type]) -> None:
        token = self.peek()
        if token in ("INIT", "INCR", "DECR"):
            self.next_token()
            name, index = self.lvalue()
            self.expect(";")
            op = {"INIT": _INIT, "INCR": _INCR, "DECR": _DECR}[str(token)]
            out.append([op, name, index])
            return
        if token == "If":  # nosec B105
            self.next_token()
            guard = self.expression()
            self.expect("Then")
            patch = len(out)
            out.append([_JUMP_UNLESS, guard, -1])
            self.block(out, local_types)
            out[patch][2] = len(out)
            return
        if token == "While":  # nosec B105
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
        # A declaration inside a function body: a type followed by a name.
        if token is not None and token in _DATATYPES and self.is_declaration():
            declared = self.parse_type()
            name = self.next_token()
            self.expect(";")
            local_types[name] = declared
            return
        # Otherwise an expression statement, which may be a charPut/charGet
        # call or the function's trailing return value.
        expr = self.expression()
        self.expect(";")
        if expr[0] == "apply" and expr[1] in ("charPut", "charGet"):
            args = expr[2]
            # ``_primary`` always builds an "apply" with a tuple of nodes,
            # so this narrowing cannot fail; it is spelled for the checker
            # and would be a malformed tree rather than a bad program.
            assert isinstance(args, tuple)  # nosec B101
            if expr[1] == "charPut":
                if len(args) != 1:
                    raise ValueError("charPut takes exactly one argument")
                out.append([_PRINT, args[0]])
                return
            target = args[0] if len(args) == 1 else None
            if not isinstance(target, tuple) or target[0] not in ("var", "apply"):
                raise ValueError("charGet takes exactly one variable")
            name = str(target[1])
            # ``charGet(a(i))`` reads into an array element; the index is
            # the sole argument of the "apply" the parser built for it.
            index = None
            if target[0] == "apply":
                slots = target[2]
                assert isinstance(slots, tuple)  # nosec B101
                index = slots[0] if slots else None
            out.append([_READ, name, index])
            return
        out.append([_VALUE, expr])

    def is_declaration(self) -> bool:
        """Whether the tokens at the cursor open a declaration, not a call.

        A declaration is a type then a name then ``;``; an expression
        statement starting with the same word is a call or a variable.
        Scanning ahead is what separates them without a symbol table.
        """
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
#: The built-in package every example depends on for its two IO functions.
_IO_PACKAGE = "IO"


class _Program:
    """A parsed program: its functions, globals, and dependency graph."""

    __slots__ = ("dependencies", "entry", "functions", "globals", "types")

    def __init__(self) -> None:
        self.functions: dict[str, _Function] = {}
        self.globals: dict[str, _Type] = {}
        self.dependencies: dict[str, frozenset[str]] = {}
        self.types: dict[str, _Type] = {}
        self.entry: _Function | None = None


def _parse(code: str) -> _Program:
    """Parse a whole program into its packages and functions."""
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
    """Parse one package member: a variable declaration or a function."""
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
            # ``Type name`` is a value parameter (the dependency example's
            # ``Integer a, Integer b``); a bare name is a package variable
            # the function uses (PlusOrMinus's ``: code``).  The two are
            # spelled differently on the wiki and mean different things.
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
    """Return the function a run starts at; see the module docstring.

    ``main`` wins when it exists, else the last package's sole
    parameterless function.  The wiki names no entry point at all, and
    every example but PlusOrMinus calls its function ``main``.
    """
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
    # A parameterless function anywhere, as the last resort: PlusOrMinus's
    # own function takes a parameter, so such a program has no entry.
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
    """Narrow a child slot back to an expression node.

    The parser builds heterogeneous tuples -- a tag, then names, ints, and
    sub-nodes -- so a slot's static type is ``object`` and every recursive
    call would otherwise need a cast.  This is the one place the shape is
    re-checked, and a violation is a malformed tree rather than bad input.
    """
    if not isinstance(value, tuple):
        raise HaltError(f"malformed expression node {value!r}")
    return value


def _int(value: object) -> int:
    """Narrow a literal or a stored scalar to an ``int``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise HaltError(f"expected a number, got {value!r}")
    return value


def _evaluate(node: _Expr, store: _Store, program: _Program, depth: int) -> int:
    """Return the value of an expression, calling functions as needed.

    Pure with respect to the store: a call runs on its own frame's store
    and returns only its value, so nothing here writes to ``store``.
    Recursion is bounded by ``depth`` so a self-calling program raises
    rather than exhausting the Python stack.
    """
    if depth > _MAX_DEPTH:
        raise HaltError("call depth exceeded")
    kind = node[0]
    if kind == "lit":
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
        left = _evaluate(_node(node[1]), store, program, depth)
        right = _evaluate(_node(node[2]), store, program, depth)
        return left ^ right
    if kind == "not":
        return 0 if _truth(_evaluate(_node(node[1]), store, program, depth)) else 1
    if kind == "apply":
        return _apply(node, store, program, depth)
    raise HaltError(f"cannot evaluate {kind!r}")


def _apply(node: _Expr, store: _Store, program: _Program, depth: int) -> int:
    """Evaluate an array index or a function call, which look alike."""
    name = str(node[1])
    args = [_node(arg) for arg in _node(node[2])]
    known = any(slot == name for slot, _ in store)
    if known:
        value = _get(store, name)
        if not isinstance(value, tuple):
            raise HaltError(f"{name!r} is not an array")
        if len(args) != 1:
            raise HaltError(f"indexing {name!r} takes exactly one index")
        index = _evaluate(args[0], store, program, depth)
        if not 0 <= index < len(value):
            raise HaltError(f"index {index} is outside {name!r}")
        return _int(value[index])
    func = program.functions.get(name)
    if func is None:
        raise HaltError(f"undefined function {name!r}")
    values = [_evaluate(arg, store, program, depth) for arg in args]
    return _call(func, values, program, depth + 1)


def _call(func: _Function, values: list[int], program: _Program, depth: int) -> int:
    """Run a function to completion and return its value.

    A called function runs its own statement list on its own store, so it
    is a plain recursive evaluation rather than a frame pushed onto the
    machine: only the *entry* function is stepped, which is what keeps
    ``step()`` one statement of the visible program.
    """
    if depth > _MAX_DEPTH:
        raise HaltError("call depth exceeded")
    if len(values) != len(func.params):
        raise HaltError(f"{func.name!r} takes {len(func.params)} arguments")
    store = _initial_store(func, program)
    store = tuple(
        (slot, dict(zip(func.params, values, strict=True)).get(slot, value))
        for slot, value in store
    )
    frame = _Frame(func, store)
    while frame.pc < len(func.body):
        frame, out, read = _advance(frame, program, None)
        if out is not None or read:
            # charPut/charGet inside a called function would need the
            # shell's ports, and no wiki example does it -- every IO call
            # sits in the entry function.  Refusing is honest; guessing an
            # order in which a pure evaluation performs IO is not.
            raise HaltError("IO inside a called function is not supported")
    return frame.result


def _initial_store(func: _Function, program: _Program) -> _Store:
    """Build a function's store: the globals it sees, plus its own locals."""
    types = dict(program.globals)
    types.update(func.locals)
    return tuple((name, kind.zero()) for name, kind in sorted(types.items()))


def _type_of(name: str, func: _Function, program: _Program) -> _Type:
    return func.locals.get(name) or program.types.get(name) or _Type()


def _advance(
    frame: _Frame, program: _Program, byte: int | None
) -> tuple[_Frame, str | None, bool]:
    """Return the frame after one statement, any output, and whether to read.

    Pure: it reads the frame and returns a new one, reaching no ``IO``.  A
    read is requested by returning True for the third element, and the
    shell calls back with the byte in ``byte`` -- so the transition stays a
    function of its arguments and the two ports remain the shell's.
    """
    stmt = frame.func.body[frame.pc]
    op = stmt[0]
    store = frame.store
    pc = frame.pc + 1
    out: str | None = None
    result = frame.result

    if op == _PRINT:
        value = _evaluate(_node(stmt[1]), store, program, 0)
        out = chr(value % 256)
    elif op == _READ:
        if byte is None:
            return frame, None, True
        store = _write(store, program, str(stmt[1]), stmt[2], lambda _old: byte)
    elif op == _INIT:
        kind = _type_of(str(stmt[1]), frame.func, program)
        store = _write(
            store,
            program,
            str(stmt[1]),
            stmt[2],
            lambda _o: kind.low,
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
        )
    elif op == _JUMP_UNLESS:
        if not _truth(_evaluate(_node(stmt[1]), store, program, 0)):
            pc = _int(stmt[2])
    elif op == _JUMP:
        pc = _int(stmt[1])
    elif op == _VALUE:
        result = _evaluate(_node(stmt[1]), store, program, 0)

    new = _Frame(frame.func, store, pc)
    new.result = result
    return new, out, False


def _write(
    store: _Store,
    program: _Program,
    name: str,
    index: object,
    update: Callable[[int], int],
    whole: _Type | None = None,
) -> _Store:
    """Apply ``update`` to a variable or one array element.

    ``whole`` is set by ``INIT``, which resets an entire array rather than
    one element -- the cat example's ``INIT input`` depends on that.
    """
    value = _get(store, name)
    if isinstance(value, tuple):
        if index is None:
            if whole is not None:
                return _set(store, name, whole.zero())
            raise HaltError(f"{name!r} is an array and needs an index")
        at = _evaluate(_node(index), store, program, 0)
        if not 0 <= at < len(value):
            raise HaltError(f"index {at} is outside {name!r}")
        row = list(value)
        row[at] = update(_int(row[at]))
        return _set(store, name, tuple(row))
    if index is not None:
        raise HaltError(f"{name!r} is not an array")
    return _set(store, name, update(_int(value)))


class _Machine:
    """The run state: the entry function's frame and the parsed program."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.program = _parse(code)
        entry = self.program.entry
        # _parse raises when a program has no entry, so this cannot be None.
        assert entry is not None  # nosec B101
        self.frame = _Frame(entry, _initial_store(entry, self.program))

    @property
    def halted(self) -> bool:
        return self.frame.pc >= len(self.frame.func.body)

    @property
    def ip(self) -> int:
        """The current statement position."""
        return self.frame.pc

    @property
    def memory(self) -> list[object]:
        """The addressable cells: the entry function's variables, in order.

        An array variable contributes its row, so the list is flat and a
        caller reading it sees the same cells the program writes.
        """
        cells: list[object] = []
        for _name, value in self.frame.store:
            cells.extend(value) if isinstance(value, tuple) else cells.append(value)
        return cells

    @property
    def stack(self) -> list[object]:
        """The stack.

        Packlang has no user-visible stack: a call is evaluated to its
        value within one statement rather than pushed as a frame, so
        nothing is ever suspended for a caller to observe.
        """
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # The frame carries the store and the cursor; the input position
        # joins them, since a repeat that ignores consumed input is not a
        # real cycle.
        return (self.frame.key(), self.io.position())

    def step(self) -> None:
        """Execute one statement, owning the two ports.

        The transition asks for a read by returning True rather than
        reaching ``io`` itself, so the read happens here and the byte goes
        back in as an argument.

        Stepping a halted machine is a no-op rather than an
        ``IndexError``: ``run_until_halt_or_cycle`` steps once more after
        the halt to prove it stayed there.
        """
        if self.halted:
            return
        frame, out, wants_read = _advance(self.frame, self.program, None)
        if wants_read:
            # ``input_char`` reads a line and takes its first byte, and
            # already gives a blank line the package-wide 0 that
            # ``tests/interpreters/test_input_convention.py`` pins.
            byte = self.io.input_char()
            frame, out, _ = _advance(self.frame, self.program, byte)
        self.frame = frame
        if out is not None:
            self.io.print_char(out)


def run(code: str, io: IO) -> None:
    """Run a Packlang program to completion."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
