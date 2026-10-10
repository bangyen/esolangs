"""Algebraic Programming Language parsing: definitions and expression trees."""

from __future__ import annotations

from math import isfinite
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.memory import parse_integer
from esolangs.interpreters.source_hints import syntax_error

# The only datatype is a number, but a *function* reaches an expression
# slot too: the wiki's ``WHILE(x, c)`` takes its condition and body as
# arguments and calls them with ``x()``.  A bare uppercase name therefore
# evaluates to the definition it names.
_Number = int | float


# Tuples discriminated by their first element, the way Forbin spells the
# same idea.  ``call`` covers functions and custom operators alike: an
# operator is a call whose name is its symbol pattern, so one node type
# and one lookup serve both.
_Lit = tuple[Literal["lit"], _Number]
_Var = tuple[Literal["var"], str]
_Ref = tuple[Literal["ref"], str]
_Neg = tuple[Literal["neg"], "_Node"]
_Ret = tuple[Literal["ret"], "_Node"]
_Bin = tuple[Literal["bin"], str, "_Node", "_Node"]
_Call = tuple[Literal["call"], str, list["_Node"]]
_Node = _Lit | _Var | _Ref | _Neg | _Ret | _Bin | _Call

# The spec allows accented Latin, Cyrillic, and Greek letters as well, so
# case is tested with ``str`` methods rather than against these ASCII
# spellings; the constants are kept for the digits and the symbol class.
_DIGITS = "0123456789"
# Operator symbols are "any non-alphanumeric ... and non-+-*/%&|()={}$
# symbol", so the reserved set is exactly what a custom operator may not
# use.
_RESERVED = set("+-*/%&|()={}$ \t,")


def _is_lower(char: str) -> bool:
    """Whether ``char`` is a variable/argument letter (any script)."""
    return char.isalpha() and char.islower()


def _is_upper(char: str) -> bool:
    """Whether ``char`` is a function-name letter (any script)."""
    return char.isalpha() and char.isupper()


def _is_symbol(char: str) -> bool:
    """Whether ``char`` may appear in a custom operator's name."""
    return not char.isalnum() and not char.isspace() and char not in _RESERVED


class _Definition:
    """A named function or custom operator, with its parameters and body.

    ``body`` is the list of expressions a call evaluates in order; all but
    the last print, and the last is the return value, unless a ``$``
    returns earlier.  ``name`` is the function's letters or the operator's
    symbol pattern, which is what makes both callable through one node.

    ``control`` marks, per statement, whether a ``$`` appears anywhere in
    it.  Such a statement never prints: the wiki says ``x & $0`` "will
    never output x", and with ``x`` false the ``&`` yields x itself, so
    only suppressing the whole statement makes that true.  The test is
    syntactic because the false case never *evaluates* the ``$``.
    """

    def __init__(self, name: str, params: list[str], body: list[_Node]) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.control = [_contains_return(node) for node in body]

    def __repr__(self) -> str:
        """Show the name and arity; frame keys are built from this."""
        return f"<{self.name}/{len(self.params)}>"


def _tokens(line: str) -> list[str]:
    """Split ``line`` into number, letter, and symbol tokens.

    Operator symbols are *not* merged into runs: ``~a`b``c~`` is a pattern
    of single symbols around its arguments, and the parser matches them
    one at a time, so keeping them separate is what lets a multi-symbol
    pattern be recognised at all.
    """
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
            # A fractional part only counts when a digit follows the dot;
            # otherwise the dot is an operator symbol in its own right.
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
    """Parse a numeric literal, keeping integers exact."""
    return _as_number(float(word)) if "." in word else parse_integer(word)


class _Parser:
    """A recursive-descent parser for one expression.

    Precedence, lowest first: ``|``, ``&``, ``+``/``-``, ``*``/``/``/``%``,
    unary ``-`` and ``$``, ``**`` (right-associative), then custom
    operators, calls, and brackets.  The wiki says custom operators bind
    tighter than everything except brackets and functions, which is where
    :meth:`_postfix` sits.

    Parsing is by Python recursion over the *program text*, which is
    bounded by the line's length; only *evaluation* uses the explicit
    stack, because only evaluation can recurse without bound.
    """

    def __init__(self, tokens: list[str], defs: dict[str, _Definition]) -> None:
        self.tokens = tokens
        self.defs = defs
        self.ind = 0
        # Definitions are fixed during one parse. Rescanning them per operand
        # timed out the 219,826-character generated n=16 dense control at 2s.
        self.operator_patterns = sorted(
            (d for d in defs.values() if "\0" in d.name),
            key=lambda d: -len(d.name),
        )

    def peek(self) -> str | None:
        """Return the next token, or None at the end of the expression."""
        return self.tokens[self.ind] if self.ind < len(self.tokens) else None

    def take(self) -> str:
        """Consume and return the next token.

        Every call site has already established that a token is there:
        the precedence levels and ``_unary`` peek before consuming,
        ``_try_pattern`` returns None on a mismatch before taking, and
        the loops in ``_atom`` and ``_arguments`` carry the end check in
        their own conditions.  So there is no unreachable "ran out"
        branch here -- ``_atom`` raises that message where it *can*
        happen.
        """
        word = self.tokens[self.ind]
        self.ind += 1
        return word

    def expect(self, word: str) -> None:
        """Consume ``token`` or fail as malformed."""
        if self.peek() != word:
            raise syntax_error(
                f"expected {word!r}", "put the expected token at this position"
            )
        self.ind += 1

    def parse(self) -> _Node:
        """Parse the whole token list, rejecting a trailing remainder."""
        node = self.expr()
        if self.peek() is not None:
            raise syntax_error(
                f"trailing input at {self.peek()!r}",
                "keep exactly one expression on this line",
            )
        return node

    def expr(self) -> _Node:
        """Parse at the lowest precedence (``|``)."""
        return self._binary(0)

    # ``|`` then ``&`` then additive then multiplicative; ``**`` is handled
    # by :meth:`_power` because it associates the other way.
    _LEVELS: tuple[tuple[str, ...], ...] = (("|",), ("&",), ("+", "-"), ("*", "/", "%"))

    def _binary(self, level: int) -> _Node:
        """Parse a left-associative level of the precedence ladder."""
        if level == len(self._LEVELS):
            return self._unary()
        node = self._binary(level + 1)
        while True:
            word = self.peek()
            # No ``**`` guard is needed here: ``_power`` consumes one
            # before returning, so the cursor never sits on the first
            # ``*`` of a ``**`` by the time this loop sees it.
            implied = (
                level == 3
                and word is not None
                and _is_lower(word)
                and self.ind > 0
                and _is_lower(self.tokens[self.ind - 1])
            )
            if implied:
                node = ("bin", "*", node, self._binary(level + 1))
                continue
            if word is None or word not in self._LEVELS[level]:
                return node
            self.take()
            node = ("bin", word, node, self._binary(level + 1))

    def _at_power(self) -> bool:
        """Whether the cursor sits on a ``**`` rather than a ``*``."""
        return (
            self.ind + 1 < len(self.tokens)
            and self.tokens[self.ind] == "*"
            and self.tokens[self.ind + 1] == "*"
        )

    def _power(self) -> _Node:
        """Parse ``**``, which is right-associative."""
        base = self._operand()
        if self._at_power():
            self.take()
            self.take()
            return ("bin", "**", base, self._unary())
        return base

    def _unary(self) -> _Node:
        """Parse unary ``-``, the ``$`` return operator, and prefix operators."""
        word = self.peek()
        if word == "-":
            self.take()
            return ("neg", self._unary())
        if word == "$":
            self.take()
            return ("ret", self._unary())
        return self._power()

    def _operand(self) -> _Node:
        """Parse a prefix operator, or an atom with its trailing operators."""
        prefix = self._match_operator(None)
        if prefix is not None:
            return prefix
        return self._postfix()

    def _postfix(self) -> _Node:
        """Parse an atom followed by any custom operators applying to it.

        A custom operator is matched by walking its stored pattern against
        the token stream: the pattern alternates symbols and argument
        slots, and a *leading* slot is the atom already parsed.  Longer
        patterns are tried first so ``^a^b^c^`` wins over a shorter one
        that would otherwise match its opening ``^``.
        """
        node = self._atom()
        while True:
            match = self._match_operator(node)
            if match is None:
                return node
            node = match

    def _operators(self) -> list[_Definition]:
        """Return the custom operators, longest pattern first."""
        return self.operator_patterns

    def _match_operator(self, left: _Node | None) -> _Node | None:
        """Try each custom operator pattern at the cursor; None if none fit.

        ``left`` is the operand already parsed for an infix or postfix
        operator, and None when looking for a *prefix* one, whose pattern
        opens with a symbol and so takes nothing from its left.
        """
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
        r"""Match ``definition``'s pattern, with ``left`` filling a leading slot.

        The pattern is the operator's stored name with ``\0`` marking each
        argument slot; a leading slot is the operand already parsed, so it
        consumes no tokens.
        """
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
                # An argument slot inside the pattern parses a tightly
                # bound operand, not a whole expression: the surrounding
                # symbols delimit it.  A *prefix* operator is allowed
                # there, so ``!!a`` is a complement of a complement.
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
        """Parse a literal, name, call, or bracketed expression."""
        word = self.peek()
        if word is None:
            raise syntax_error(
                "unexpected end of expression",
                "provide a literal, variable or function call after the operator",
            )
        if word[0] in _DIGITS:
            self.take()
            node: _Node = ("lit", _number(word))
            # ``1(2)`` is invalid syntax by the spec, and so is ``1 a``:
            # implied multiplication is between *variables*.
            if self.peek() == "(":
                raise syntax_error(
                    "bracket multiplication is invalid syntax",
                    "write multiplication explicitly with *, for example 1*(2)",
                )
            return node
        if word == "(":
            self.take()
            inner = self.expr()
            self.expect(")")
            return inner
        if _is_lower(word):
            self.take()
            if self.peek() == "(":
                # ``c()`` where ``c`` is a parameter holding a function:
                # the wiki's ``IF(x, c) = x & c()`` calls its argument.
                return ("call", word, self._arguments())
            return ("var", word)
        if _is_upper(word):
            name = ""
            while self.peek() is not None and _is_upper(str(self.peek())):
                name += self.take()
            if self.peek() == "(":
                return ("call", name, self._arguments())
            # A bare uppercase name is the function itself, which is how
            # ``WHILE(x, c)`` receives something it can call.
            return ("ref", name)
        raise syntax_error(
            f"unexpected token {word!r}",
            "use a number, lowercase variable or uppercase function call here",
        )

    def _arguments(self) -> list[_Node]:
        """Parse a parenthesised, comma-separated argument list."""
        self.expect("(")
        args: list[_Node] = []
        if self.peek() != ")":
            args.append(self.expr())
            while self.peek() == ",":
                self.take()
                args.append(self.expr())
        self.expect(")")
        return args


def _split_definition(line: str) -> tuple[str, str] | None:
    """Split a definition line into its left and right sides.

    A line is a definition when it has an ``=`` outside brackets.  The
    body may open a ``{`` block, which the caller joins before parsing.
    """
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
    r"""Parse a definition's left-hand side into a name and parameters.

    Three shapes: a bare variable (``n = 123``), a function with
    parentheses (``F(x) = ...``), and a custom operator pattern
    (``a ~ b = ...``, ``a@ = ...``), whose name records its symbols with
    ``\0`` standing in for each argument slot so the parser can match it
    against the token stream.
    """
    # The surrounding whitespace is not part of the header, and quoting it
    # back in an error message only misleads the reader.
    lhs = lhs.strip()
    tokens = _tokens(lhs)
    if not tokens:
        raise syntax_error(
            "definition has no left-hand side",
            "put a variable, function header or operator pattern before =",
        )
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
                raise syntax_error(
                    f"malformed function header {lhs!r}",
                    (
                        "write an uppercase function name with lowercase "
                        "parameters, for example F(x)"
                    ),
                )
            ind += 1
            if ind < len(tokens) and tokens[ind] != ")":
                # _split_definition only supplies bracket-balanced headers;
                # a comma cannot be the final token before the equals sign.
                while True:
                    if not _is_lower(tokens[ind]):
                        raise ValueError(f"bad parameter {tokens[ind]!r}")
                    if tokens[ind] in params:
                        raise ValueError(f"function {lhs!r} repeats a parameter")
                    params.append(tokens[ind])
                    ind += 1
                    if ind >= len(tokens) or tokens[ind] != ",":
                        break
                    ind += 1
            if ind >= len(tokens) or tokens[ind] != ")":
                raise ValueError(f"malformed function header {lhs!r}")
            ind += 1
        if ind != len(tokens):
            raise syntax_error(
                f"trailing input in header {lhs!r}",
                "end the function header after its closing parenthesis",
            )
        return name, params
    # A custom operator: letters are argument slots, everything else is a
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
            raise syntax_error(
                f"bad operator pattern {lhs!r}",
                (
                    "use lowercase parameter letters and operator symbols, for "
                    "example a#b"
                ),
            )
    if not op_params or "\0" not in pattern:
        raise syntax_error(
            f"operator {lhs!r} takes no arguments",
            "include at least one lowercase parameter in the operator pattern",
        )
    if len(set(op_params)) != len(op_params):
        raise syntax_error(
            f"operator {lhs!r} repeats a parameter",
            "give each operator parameter a distinct lowercase letter",
        )
    return pattern, op_params


def _blocks(code: str) -> list[str]:
    """Join a program's physical lines into logical ones.

    A ``{`` opens a multiline body that runs to its matching ``}``, so the
    lines between them belong to the definition rather than being executed
    on their own.  Blank lines are dropped.
    """
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
        raise syntax_error("unbalanced { in program", "close each { block with }")
    return out


def _body(rhs: str, defs: dict[str, _Definition]) -> list[_Node]:
    """Parse a definition's right-hand side into its list of statements."""
    text = rhs.strip()
    if text.startswith("{"):
        if not text.endswith("}"):
            # ``_blocks`` has already balanced the braces, so what is left
            # is a block with something after its closer -- ``F() = {1} 2``.
            raise syntax_error(
                f"trailing input after block in {text!r}",
                "end the definition after its closing }",
            )
        inner = text[1:-1]
        if not inner.strip():
            raise ValueError("empty function body")
        return [
            _Parser(_tokens(line), defs).parse()
            for line in (s.strip() for s in inner.splitlines())
            if line
        ]
    return [_Parser(_tokens(text), defs).parse()]


def _as_number(value: object) -> _Number:
    """Coerce a value to a number, refusing a function."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HaltError(
            f"expected a number, got {value!r}",
            hint="use a numeric value in this expression",
        )
    if isinstance(value, float) and not isfinite(value):
        raise HaltError("number must be finite")
    return value


def _contains_return(node: _Node) -> bool:
    """Return whether a statement syntactically contains a return."""
    pending = [node]
    while pending:
        current = pending.pop()
        if current[0] == "ret":
            return True
        if current[0] == "neg":
            pending.append(current[1])
        elif current[0] == "bin":
            pending.extend((current[2], current[3]))
        elif current[0] == "call":
            pending.extend(current[2])
    return False


def _free_variables(node: _Node) -> list[str]:
    """Return variables in first-appearance order without recursive traversal."""
    out: list[str] = []
    seen: set[str] = set()
    pending = [node]
    while pending:
        current = pending.pop()
        if current[0] == "var":
            if current[1] not in seen:
                seen.add(current[1])
                out.append(current[1])
        elif current[0] in ("neg", "ret"):
            pending.append(current[1])
        elif current[0] == "bin":
            pending.extend((current[3], current[2]))
        elif current[0] == "call":
            pending.extend(reversed(current[2]))
    return out
