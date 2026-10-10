"""Packlang parsing: packages and functions into flat statement lists."""

import re

from esolangs.interpreters.other.packlang._lex import _strip_comments, _tokenize
from esolangs.interpreters.other.packlang._literals import PacklangLiterals
from esolangs.interpreters.source_hints import keyword_hint, syntax_error

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


class _Parser:
    """Recursive-descent parser producing flat statement lists.

    Expressions become a small postfix tuple and statements a flat list
    with jumps resolved, so nothing in the run has to walk a tree.
    """

    def __init__(self, tokens: list[str], literal_policy: str = "decimal") -> None:
        self.literals = PacklangLiterals(literal_policy)
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next_token(self) -> str:
        word = self.peek()
        if word is None:
            raise syntax_error(
                "unexpected end of program",
                "complete the declaration or statement and close its delimiters",
            )
        self.pos += 1
        return word

    def expect(self, word: str) -> None:
        got = self.next_token()
        if got != word:
            raise syntax_error(
                f"expected {word!r}, got {got!r}",
                (
                    "put the expected token at this position; Packlang keywords "
                    "are case-sensitive"
                ),
            )

    def package_kind(self) -> str:
        """Read the required package declaration keyword."""
        kind = self.next_token()
        if kind not in ("Package", "Dependency"):
            raise syntax_error(
                f"expected a Package or Dependency, got {kind!r}",
                "start the declaration with Package or Dependency",
            )
        return kind

    def identifier(self) -> str:
        word = self.next_token()
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", word) is None:
            raise ValueError(f"expected an identifier, got {word!r}")
        return word

    def parse_type(self) -> _Type:
        """Parse a datatype, including its parenthesized parameters."""
        name = self.next_token()
        if name == "Integer" and self.peek() == "(":
            self.next_token()
            args = [self.number()]
            for _ in range(3):
                self.expect(",")
                args.append(self.number())
            self.expect(")")
            if args[0] > args[1]:
                raise ValueError("integer minimum exceeds maximum")
            return _Type(args[0], args[1], args[2], args[3])
        if name == "Array":
            self.expect("(")
            inner = self.parse_type()
            self.expect(",")
            length = self.number()
            self.expect(")")
            if length < 0:  # pragma: no cover - `number` requires isdigit
                raise syntax_error(
                    "array length must not be negative",
                    "use an array length of zero or greater",
                )
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
        raise syntax_error(
            f"unknown datatype {name!r}",
            keyword_hint(
                name,
                ("Integer", "Char", "String", "Array", "Pointer"),
                "use Integer, Char, String, Array(type, length) or Pointer(type)",
            ),
        )

    def number(self) -> int:
        """Parse a decimal integer literal; see :mod:`.packlang`."""
        word = self.next_token()
        if not word.isdigit():
            raise syntax_error(
                f"expected a number, got {word!r}",
                "write a nonnegative decimal integer",
            )
        return self.literals.parse(word)

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
        word = self.next_token()
        if word == "(":
            node = self.expression()
            self.expect(")")
            return node
        if word.isdigit():
            return ("lit", self.literals.parse(word))
        if not word[:1].isalpha() and word[:1] != "_":
            raise syntax_error(
                f"unexpected token {word!r} in an expression",
                "use a decimal number, variable, call or ! expression",
            )
        if self.peek() == "(":
            self.next_token()
            # ``myArray(length)`` is spelled exactly like that on the wiki,
            # so ``length`` here is the keyword, not a variable named so.
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
            # An index and a call are spelled identically; which one it is
            # depends on the name, so it is resolved at run time.
            return ("apply", word, tuple(args))
        return ("var", word)

    def lvalue(self) -> tuple[str, tuple[object, ...] | None]:
        """Parse a target: a name, optionally with an index."""
        name = self.next_token()
        if not (name[:1].isalpha() or name[:1] == "_"):
            raise syntax_error(
                f"expected a variable name, got {name!r}",
                "use an identifier starting with a letter or underscore",
            )
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
                raise syntax_error(
                    "unbalanced '{' in program", "close the statement block with }"
                )
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
        # A declaration inside a function body: a type followed by a name.
        if word is not None and word in _DATATYPES and self.is_declaration():
            declared = self.parse_type()
            name = self.identifier()
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
            if not isinstance(args, tuple):
                raise AssertionError("isinstance(args, tuple)")
            if expr[1] == "charPut":
                if len(args) != 1:
                    raise syntax_error(
                        "charPut takes exactly one argument",
                        "pass one value to charPut, for example charPut(65)",
                    )
                out.append([_PRINT, args[0]])
                return
            target = args[0] if len(args) == 1 else None
            if not isinstance(target, tuple) or target[0] not in ("var", "apply"):
                raise syntax_error(
                    "charGet takes exactly one variable",
                    "pass one variable to charGet, for example charGet(c)",
                )
            name = str(target[1])
            # ``charGet(a(i))`` reads into an array element; the index is
            # the sole argument of the "apply" the parser built for it.
            index = None
            if target[0] == "apply":
                slots = target[2]
                if not isinstance(slots, tuple):
                    raise AssertionError("isinstance(slots, tuple)")
                if len(slots) != 1:
                    raise ValueError("charGet array target takes exactly one index")
                index = slots[0]
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


class _Program:
    """A parsed program: its functions, globals, and dependency graph."""

    __slots__ = ("dependencies", "entry", "functions", "globals", "types")

    def __init__(self) -> None:
        self.functions: dict[tuple[str, str], _Function] = {}
        self.globals: dict[tuple[str, str], _Type] = {}
        self.dependencies: dict[str, frozenset[str]] = {}
        self.types: dict[tuple[str, str], _Type] = {}
        self.entry: _Function | None = None


def _parse(code: str, literal_policy: str = "decimal") -> _Program:
    """Parse a whole program into its packages and functions."""
    tokens = _tokenize(_strip_comments(code))
    return _parse_packages(_Parser(tokens, literal_policy))


def _parse_packages(parser: _Parser) -> _Program:
    """Parse packages with the supplied token parser."""
    if parser.peek() is None:
        raise syntax_error(
            "empty program",
            "provide a Package containing a parameterless entry function",
        )
    program = _Program()
    order: list[str] = []
    while parser.peek() is not None:
        parser.package_kind()
        deps = []
        if parser.peek() == ":":
            parser.next_token()
            deps.append(parser.identifier())
            while parser.peek() == ",":
                parser.next_token()
                deps.append(parser.identifier())
        parser.expect("{")
        members: list[tuple[str, _Function]] = []
        globals_here: dict[str, _Type] = {}
        while parser.peek() != "}":
            if parser.peek() is None:
                raise syntax_error(
                    "unbalanced '{' in package body",
                    "close the package body with } before its package name and ;",
                )
            _member(parser, members, globals_here)
        parser.next_token()
        package = parser.identifier()
        parser.expect(";")
        program.dependencies[package] = frozenset(deps)
        program.globals.update(
            ((package, name), kind) for name, kind in globals_here.items()
        )
        program.types.update(
            ((package, name), kind) for name, kind in globals_here.items()
        )
        for name, func in members:
            func.package = package
            key = (package, name)
            if key in program.functions:
                raise ValueError(f"duplicate function {name!r} in {package!r}")
            program.functions[key] = func
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
    name = parser.identifier()
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
                param = parser.identifier()
                local_types[param] = param_type
                params.append(param)
            else:
                uses.append(parser.identifier())
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
    """Return the function a run starts at; see :mod:`.packlang`.

    ``main`` wins when it exists, else the last package's sole
    parameterless function.  The wiki names no entry point at all, and
    every example but PlusOrMinus calls its function ``main``.
    """
    mains = [
        func
        for func in program.functions.values()
        if func.name == "main" and not func.params
    ]
    if len(mains) > 1:
        raise ValueError("program has multiple parameterless main functions")
    if mains:
        return mains[0]
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
    raise syntax_error(
        "program has no parameterless entry function",
        (
            "define a parameterless main function or a sole "
            "parameterless function in the last package"
        ),
    )
