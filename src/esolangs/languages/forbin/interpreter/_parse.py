"""Forbin parsing: source text into nested function definitions."""

from __future__ import annotations

from typing import Literal, NoReturn

from esolangs.interpreters.source_hints import syntax_error

# The parse tree, as tuples discriminated by their first element.  Four
# families, because the grammar has four: a value, a for-loop pattern, the
# spec that heads a for-loop, and a statement.  They nest -- a statement
# holds a spec, a spec holds patterns, a pattern holds values -- so the
# aliases quote their forward references.
_Lit = tuple[Literal["lit"], int]
_Not = tuple[Literal["not"], "_ValueNode"]
_Var = tuple[Literal["var"], str]
_FnLit = tuple[Literal["fnlit"], "_Function"]
_CallNode = tuple[Literal["call"], "_ValueNode", list["_ValueNode"]]
_ValueNode = _Lit | _Not | _Var | _FnLit | _CallNode

# ``*`` is a wildcard standing for both bit values, so it is a bare
# one-tuple: reading [1] off one is a type error rather than an IndexError.
_Star = tuple[Literal["*"]]
_ValuePat = tuple[Literal["value"], _ValueNode]
_Group = tuple[Literal["group"], list["_Star | _ValuePat"]]
_Pattern = _Star | _ValuePat | _Group

_Range = tuple[Literal["range"], str, _ValueNode, _ValueNode]
_Iter = tuple[Literal["iter"], list[str], list[_Pattern]]
_ForSpec = _Range | _Iter

_Return = tuple[Literal["return"], _ValueNode]
_Assign = tuple[Literal["assign"], list[str], list[_ValueNode]]
_For = tuple[Literal["for"], _ForSpec, list["_Statement"]]
_Statement = _Return | _Assign | _CallNode | _For


class _Function:
    """A parsed function: name, parameter names, body, nested definitions."""

    __slots__ = ("args", "body", "name", "nested")

    def __init__(self, name: str, args: list[str]) -> None:
        self.name = name
        self.args = args
        self.body: list[_Statement] = []
        self.nested: dict[str, _Function] = {}


class _Parser:
    """Recursive-descent parser for Forbin source text."""

    def __init__(self, text: str) -> None:
        self.t = text
        self.i = 0
        self.n = len(text)
        self.initializers: list[_Statement] = []
        self._definition_scopes: list[dict[str, _Function]] = []

    def _skip_ws(self) -> None:
        while self.i < self.n:
            c = self.t[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == "/" and self.i + 1 < self.n and self.t[self.i + 1] == "/":
                while self.i < self.n and self.t[self.i] not in "\r\n":
                    self.i += 1
            else:
                return

    def _peek(self) -> str:
        self._skip_ws()
        return self.t[self.i] if self.i < self.n else ""

    def _fail(self, msg: str) -> NoReturn:
        raise syntax_error(
            f"{msg} at position {self.i}",
            (
                "use bit literals 0/1, identifiers, and balanced call "
                "parentheses or block braces at this position"
            ),
        )

    def _expect(self, ch: str) -> None:
        self._skip_ws()
        if self.i >= self.n or self.t[self.i] != ch:
            self._fail(f"expected {ch!r}")
        self.i += 1

    def _ident(self) -> str:
        self._skip_ws()
        if self.i >= self.n or not (self.t[self.i].isalpha() or self.t[self.i] == "_"):
            self._fail("expected an identifier")
        start = self.i
        self.i += 1
        while self.i < self.n and (self.t[self.i].isalnum() or self.t[self.i] == "_"):
            self.i += 1
        return self.t[start : self.i]

    def _value(self) -> _ValueNode:
        self._skip_ws()
        if self.i >= self.n:
            self._fail("expected a value")
        c = self.t[self.i]
        if c == "!":
            self.i += 1
            return ("not", self._value())
        if c in "01":
            self.i += 1
            return ("lit", int(c))
        if c == "{":  # a bare {code} block is a function literal (no args)
            body, nested = self._block()
            fn = _Function("", [])
            fn.body, fn.nested = body, nested
            return ("fnlit", fn)
        if c == "(":
            self.i += 1
            save = self.i
            first = self._ident()
            params = [first]
            while self._peek() == ",":
                self._expect(",")
                params.append(self._ident())
            self._skip_ws()
            if self._peek() == "@":  # anonymous function literal
                self._expect("@")
                body, nested = self._block()
                self._expect(")")
                fn = _Function("", params)
                fn.body, fn.nested = body, nested
                return ("fnlit", fn)
            self.i = save
            callee: _Var = ("var", self._ident())
            args: list[_ValueNode] = []
            self._skip_ws()
            while self._peek() != ")":
                if args:
                    self._expect(",")
                args.append(self._value())
            self._expect(")")
            return ("call", callee, args)
        if not (c.isalpha() or c == "_"):
            self._fail(f"unexpected character {c!r}")
        return ("var", self._ident())

    def _values(self) -> list[_ValueNode]:
        values = [self._value()]
        while self._peek() == ",":
            self.i += 1
            values.append(self._value())
        return values

    def _semi(self) -> None:
        self._skip_ws()
        if self._peek() == ";":
            self.i += 1

    def _pattern(self) -> _Star | _ValuePat:
        self._skip_ws()
        if self._peek() == "*":
            self.i += 1
            return ("*",)
        return ("value", self._value())

    def _pattern_group(self) -> _Pattern:
        self._expect("(")
        pats: list[_Star | _ValuePat] = []
        while self._peek() != ")":
            if pats:
                self._expect(",")
            pats.append(self._pattern())
        self._expect(")")
        return ("group", pats)

    def _for_spec(self) -> _ForSpec:
        self._skip_ws()
        if self._peek() == "(":
            self.i += 1
            vars_ = [self._ident()]
            while self._peek() == ",":
                self.i += 1
                vars_.append(self._ident())
            self._expect(")")
        else:
            vars_ = [self._ident()]
        self._expect(":")
        self._skip_ws()
        if self._peek() == "(":
            self.i += 1
            items: list[_Pattern] = []
            if len(vars_) > 1 and self._peek() != "(":
                shorthand: list[_Star | _ValuePat] = []
                while self._peek() != ")":
                    if shorthand:
                        self._expect(",")
                    shorthand.append(self._pattern())
                self._expect(")")
                group: _Group = ("group", shorthand)
                iteration: _Iter = ("iter", vars_, [group])
                return iteration
            while self._peek() != ")":
                if items:
                    self._expect(",")
                if len(vars_) == 1:
                    items.append(self._pattern())
                else:
                    items.append(self._pattern_group())
            self._expect(")")
            return ("iter", vars_, items)
        start = self._value()
        self._skip_ws()
        if not self.t.startswith("..", self.i):
            self._fail("expected '..' or an iteration list")
        self.i += 2
        end = self._value()
        return ("range", vars_[0], start, end)

    def _header(self) -> tuple[str, list[str]]:
        """Parse ``name [param (, param)*]``, stopping before any ``{``."""
        name = self._ident()
        params: list[str] = []
        while True:
            self._skip_ws()
            if self._peek() == ",":
                self.i += 1
                self._skip_ws()
                if self.i < self.n and (
                    self.t[self.i].isalpha() or self.t[self.i] == "_"
                ):
                    params.append(self._ident())
                    continue
                break
            if self.i < self.n and (self.t[self.i].isalpha() or self.t[self.i] == "_"):
                params.append(self._ident())
                continue
            break
        return name, params

    def _block(self) -> tuple[list[_Statement], dict[str, _Function]]:
        self._expect("{")
        stmts: list[_Statement] = []
        nested: dict[str, _Function] = {}
        self._definition_scopes.append(nested)
        while True:
            self._skip_ws()
            if self.i >= self.n:
                self._fail("unterminated block, expected '}'")
            if self.t[self.i] == "}":
                self.i += 1
                self._definition_scopes.pop()
                return stmts, nested
            c = self.t[self.i]
            if c.isalpha() or c == "_":
                save = self.i
                name, params = self._header()
                self._skip_ws()
                if self._peek() == "{":
                    fn = _Function(name, params)
                    fn.body, fn.nested = self._block()
                    nested[name] = fn
                    continue
                self.i = save
            stmts.append(self._statement())

    def _statement(self) -> _Statement:
        self._skip_ws()
        if self.t.startswith("return", self.i):
            j = self.i + 6
            if j >= self.n or not (self.t[j].isalnum() or self.t[j] == "_"):
                self.i = j
                value = self._value()
                self._semi()
                return ("return", value)
        if self.t.startswith("for", self.i):
            j = self.i + 3
            if j >= self.n or not (self.t[j].isalnum() or self.t[j] == "_"):
                self.i = j
                spec = self._for_spec()
                body, nested = self._block()
                # Top-level parsing only admits definitions and assignments.
                self._definition_scopes[-1].update(nested)
                return ("for", spec, body)
        first = self._value()
        self._skip_ws()
        if self._peek() == "=":
            if first[0] != "var":
                self._fail("assignment target must be a variable")
            self.i += 1
            rhs = self._values()
            self._semi()
            return ("assign", [first[1]], rhs)
        if self._peek() == ",":
            values = [first]
            while self._peek() == ",":
                self.i += 1
                values.append(self._value())
            self._skip_ws()
            if self._peek() != "=":
                self._fail("expected '=' after assignment targets")
            self.i += 1
            # Collecting the names as they are checked keeps the target
            # list typed, which an ``all(...)`` over the values would not.
            names: list[str] = []
            for v in values:
                if v[0] != "var":
                    self._fail("assignment target must be a variable")
                names.append(v[1])
            rhs = self._values()
            self._semi()
            return ("assign", names, rhs)
        if first[0] not in ("var", "call", "fnlit"):
            self._fail("statement must be a call, assignment, or return")
        args = (
            self._values() if self._peek() in "01!(_" or self._peek().isalpha() else []
        )
        self._semi()
        return ("call", first, args)

    def parse(self) -> dict[str, _Function]:
        funcs: dict[str, _Function] = {}
        while True:
            self._skip_ws()
            if self.i >= self.n:
                return funcs
            start = self.i
            name, params = self._header()
            self._skip_ws()
            if self._peek() != "{":
                if self._peek() != "=":
                    self._fail("expected '{' after function name")
                self.i = start
                initializer = self._statement()
                self.initializers.append(initializer)
                continue
            fn = _Function(name, params)
            fn.body, fn.nested = self._block()
            funcs[fn.name] = fn
