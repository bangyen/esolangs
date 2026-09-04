"""Interpreter for Algebraic Programming Language.

An algebra-shaped language with no input command and no output command.
A program is a series of lines: a line *containing* ``=`` is a definition
(a variable, a function ``F(x) = ...``, or a custom operator ``a ~ b =
...``), and a line without one is *executed*, its result printed to
STDOUT.  Every lowercase variable appearing on an executed line is read
from user input, so reading is a side effect of naming a variable and
printing is a side effect of having a line to evaluate.  The only data
type is a number.

Branching is short-circuit evaluation.  ``&`` and ``|`` skip their
right-hand side, and ``$`` (return) may *be* that side, so ``x & $0``
returns 0 exactly when ``x`` is truthy -- the wiki's own spelling of
"not", and the only conditional the language has.  Looping is the same
mechanism recursing: the wiki's truth machine is ``x? = x & x?``.

Decisions for gaps in the wiki spec (documented):

- **Input binding is a pre-scan.**  The spec says variables are "set
  initially to user input in the order they first appear in the line",
  so this interpreter binds every unbound lowercase variable on an
  executed line *before* evaluating it, in left-to-right order of first
  appearance.  Evaluating lazily would let a short-circuit skip a read
  and consume input in an order the spec's own worked example (``a + b +
  d`` then ``c + e + b`` asking for ``a, b, d, c, e``) contradicts.
  Bindings persist across lines, which is what makes that example ask
  for ``b`` once.
- **Truthiness and the value of a short-circuit.**  The wiki pins only
  the false case ("false -> 0 or 0.0").  Zero is false and every other
  number is true; ``&`` returns its right operand when the left is
  truthy and ``0`` otherwise, and ``|`` returns its left operand when
  that is truthy and its right otherwise.  This is the reading that
  makes the wiki's ``WHILE`` example terminate.
- **Printing.**  An executed line prints its result followed by a
  newline; an integral value prints without a trailing ``.0`` (so the
  Hello-World example prints ``72``, not ``72.0``).  A line whose
  evaluation returns via a top-level ``$`` still prints.
- **Numbers.**  Values are Python ``int`` where a computation stays
  integral and ``float`` once division or a fractional literal makes it
  otherwise, so the unbounded integers the wiki's Turing-completeness
  argument relies on are unbounded here.
- **EOF** while binding a variable raises :class:`EOFError`, as the
  Brainfuck interpreter does; a line that is not a number raises
  :class:`~esolangs.exceptions.HaltError`.
- Malformed programs raise :class:`ValueError`: an unparsable
  expression, an unknown name, an unbalanced ``()`` or ``{}``, a
  definition whose left-hand side is not a variable, call, or operator
  pattern, a call with the wrong argument count, and the wiki's own
  ``1(2)`` (bracket multiplication is invalid syntax).
- Division or modulo by zero, and ``0 ** -1``, raise
  :class:`~esolangs.exceptions.HaltError`.
- **An uppercase name defined without parentheses** (``F = 7``) is a
  nullary function, called as ``F()``.  The wiki only writes ``F() =
  123``, but its own rule that a bare-variable left-hand side is an
  assignment is restricted to *lowercase* names, so this is the reading
  that leaves the uppercase case meaning something.  Printing a function
  rather than calling it is an invalid operation
  (:class:`~esolangs.exceptions.HaltError`), since the only printable
  values are numbers.

``_Machine`` evaluates on an explicit stack of :class:`_Frame` objects
rather than by Python recursion, because in this language recursion *is*
the loop.  A ``step()`` that evaluated a whole line would never return on
``n?``, the frame stack would never be observed growing, and
:func:`~esolangs.vm.run_until_halt_or_ancestor` would have nothing to
step between.  Each frame holds one call's expression and a cursor into
its sub-evaluations, so ``step()`` advances exactly one node and a
recursion pushes one frame per lap -- the granularity the ancestor check
needs to prove ``x? = x & x?`` hangs.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# -- values ---------------------------------------------------------------

# The only datatype is a number, but a *function* reaches an expression
# slot too: the wiki's ``WHILE(x, c)`` takes its condition and body as
# arguments and calls them with ``x()``.  A bare uppercase name therefore
# evaluates to the definition it names.
_Number = int | float

# -- parse tree -----------------------------------------------------------

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

_LOWER = "abcdefghijklmnopqrstuvwxyz"
_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
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


# -- tokenizer ------------------------------------------------------------


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


def _number(token: str) -> _Number:
    """Parse a numeric literal, keeping integers exact."""
    return float(token) if "." in token else int(token)


# -- parser ---------------------------------------------------------------


class _Parser:
    """A recursive-descent parser for one expression.

    Precedence, lowest first: ``|``, ``&``, ``+``/``-``, ``*``/``/``/``%``,
    ``**`` (right-associative), unary ``-`` and ``$``, then custom
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
        token = self.tokens[self.ind]
        self.ind += 1
        return token

    def expect(self, token: str) -> None:
        """Consume ``token`` or fail as malformed."""
        if self.peek() != token:
            raise ValueError(f"expected {token!r}")
        self.ind += 1

    def parse(self) -> _Node:
        """Parse the whole token list, rejecting a trailing remainder."""
        node = self.expr()
        if self.peek() is not None:
            raise ValueError(f"trailing input at {self.peek()!r}")
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
            return self._power()
        node = self._binary(level + 1)
        while True:
            token = self.peek()
            # No ``**`` guard is needed here: ``_power`` consumes one
            # before returning, so the cursor never sits on the first
            # ``*`` of a ``**`` by the time this loop sees it.
            if token is None or token not in self._LEVELS[level]:
                return node
            self.take()
            node = ("bin", token, node, self._binary(level + 1))

    def _at_power(self) -> bool:
        """Whether the cursor sits on a ``**`` rather than a ``*``."""
        return (
            self.ind + 1 < len(self.tokens)
            and self.tokens[self.ind] == "*"
            and self.tokens[self.ind + 1] == "*"
        )

    def _power(self) -> _Node:
        """Parse ``**``, which is right-associative."""
        base = self._unary()
        if self._at_power():
            self.take()
            self.take()
            return ("bin", "**", base, self._power())
        return base

    def _unary(self) -> _Node:
        """Parse unary ``-``, the ``$`` return operator, and prefix operators."""
        token = self.peek()
        if token == "-":  # nosec B105
            self.take()
            return ("neg", self._unary())
        if token == "$":  # nosec B105
            self.take()
            return ("ret", self._unary())
        return self._operand()

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
        return sorted(
            (d for d in self.defs.values() if "\0" in d.name),
            key=lambda d: -len(d.name),
        )

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
        token = self.peek()
        if token is None:
            raise ValueError("unexpected end of expression")
        if token[0] in _DIGITS:
            self.take()
            node: _Node = ("lit", _number(token))
            # ``1(2)`` is invalid syntax by the spec, and so is ``1 a``:
            # implied multiplication is between *variables*.
            if self.peek() == "(":
                raise ValueError("bracket multiplication is invalid syntax")
            return self._implied(node)
        if token == "(":  # nosec B105
            self.take()
            inner = self.expr()
            self.expect(")")
            return self._implied(inner)
        if _is_lower(token):
            self.take()
            if self.peek() == "(":
                # ``c()`` where ``c`` is a parameter holding a function:
                # the wiki's ``IF(x, c) = x & c()`` calls its argument.
                return ("call", token, self._arguments())
            return self._implied(("var", token))
        if _is_upper(token):
            name = ""
            while self.peek() is not None and _is_upper(str(self.peek())):
                name += self.take()
            if self.peek() == "(":
                return ("call", name, self._arguments())
            # A bare uppercase name is the function itself, which is how
            # ``WHILE(x, c)`` receives something it can call.
            return ("ref", name)
        raise ValueError(f"unexpected token {token!r}")

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

    def _implied(self, node: _Node) -> _Node:
        """Fold implied multiplication (``ab`` is ``a * b``) onto ``node``."""
        while True:
            token = self.peek()
            if token is None or not _is_lower(token):
                return node
            self.take()
            node = ("bin", "*", node, ("var", token))


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
            # The loop cannot run out of tokens: getting past it needs a
            # closer, and ``)`` ends it here while ``}`` fails the
            # ``bad parameter`` check above.
            ind += 1
        if ind != len(tokens):
            raise ValueError(f"trailing input in header {lhs!r}")
        return name, params
    # A custom operator: letters are argument slots, everything else is a
    # literal symbol of the pattern.
    pattern = ""
    op_params: list[str] = []
    for token in tokens:
        if _is_lower(token):
            pattern += "\0"
            op_params.append(token)
        elif len(token) == 1 and _is_symbol(token):
            pattern += token
        else:
            raise ValueError(f"bad operator pattern {lhs!r}")
    if not op_params or "\0" not in pattern:
        raise ValueError(f"operator {lhs!r} takes no arguments")
    if len(set(op_params)) != len(op_params):
        raise ValueError(f"operator {lhs!r} repeats a parameter")
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
        raise ValueError("unbalanced { in program")
    return out


def _body(rhs: str, defs: dict[str, _Definition]) -> list[_Node]:
    """Parse a definition's right-hand side into its list of statements."""
    text = rhs.strip()
    if text.startswith("{"):
        if not text.endswith("}"):
            # ``_blocks`` has already balanced the braces, so what is left
            # is a block with something after its closer -- ``F() = {1} 2``.
            raise ValueError(f"trailing input after block in {text!r}")
        inner = text[1:-1]
        return [
            _Parser(_tokens(line), defs).parse()
            for line in (s.strip() for s in inner.splitlines())
            if line
        ]
    return [_Parser(_tokens(text), defs).parse()]


# -- evaluation -----------------------------------------------------------


class _Frame:
    """One call in progress: its body, its bindings, and its cursor.

    ``work`` is an explicit stack of (node, resolved-operands) pairs
    standing in for what Python recursion would keep on its own stack, so
    a single ``step()`` resolves one node and returns.  ``stmt`` indexes
    the definition's body, since a multiline function prints every
    statement but its last.

    ``printing`` marks the synthetic frame wrapping an *executed line*,
    whose result goes to STDOUT; ``assign`` names the variable an
    assignment line binds instead.  Both are false/None for an ordinary
    call, whose value simply returns to its caller.
    """

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
        """Identify the frame by its function and cursor."""
        return f"<frame {self.fn.name} @{self.stmt}>"


@dataclass
class _State:
    """Every changing value in an Algebraic Programming Language run."""

    defs: dict[str, _Definition]
    globals: dict[str, object]
    frames: list[_Frame]
    line: int
    pending: _Node | None
    steps: int


class _Machine:
    """The run state: the definitions, the globals, and the call stack.

    A program is a list of logical lines; ``self.line`` is the cursor into
    the executed ones.  A definition line binds a name and advances.  An
    executed line binds its free variables from input, then evaluates on
    the frame stack, printing the result when the stack empties.
    """

    #: The wiki gives no bound; this caps *one* line's evaluation so a
    #: runaway expression cannot allocate without limit while still
    #: leaving the hang detectors room to prove a loop.
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

    # -- the VM's language-shaped view --------------------------------

    @property
    def halted(self) -> bool:
        """Whether every line has been executed and no frame is live."""
        return self.line >= len(self.lines) and not self.frames

    @property
    def ip(self) -> tuple[int, ...]:
        """The line cursor followed by each live frame's statement index."""
        return (self.line, *(f.stmt for f in self.frames))

    @property
    def memory(self) -> list[int]:
        """The global bindings' integral values, in name order.

        APL has no addressable store; the nearest thing is the set of
        variables input has bound, which is what a reader wants to see.
        Non-integral and function values are reported as 0, since this
        view is typed ``list[int]``.
        """
        return [
            int(v) if isinstance(v, (int, float)) else 0
            for _, v in sorted(self.globals.items())
        ]

    @property
    def stack(self) -> list[object]:
        """The live call stack, outermost first."""
        return list(self.frames)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Bindings go through ``repr`` because a value may be a
        :class:`_Definition`, which is not meaningfully hashable; the
        input cursor is included so a loop that keeps reading is never
        mistaken for a repeat.

        The work stack is captured *by content*, not by depth.  Recording
        only its length made two genuinely different states compare equal
        -- one operand of ``1 + 1`` resolved versus both -- and the cycle
        detector called a halting program a hang.  A node is identified
        by ``id``, which is stable because the parse tree is built once
        and never rewritten.
        """
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
        """Return what ``frame`` is about to run, for the ancestor check.

        Two frames with equal keys replay each other, so the key is the
        function, its bindings, and the input cursor.  The input position
        carries the soundness: a recursion whose base case waits on an
        unread line enters with identical bindings every lap and is one
        read from returning, not looping.  See
        :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        assert isinstance(frame, _Frame)  # nosec B101
        return (
            frame.fn.name,
            tuple(sorted((k, repr(v)) for k, v in frame.locals.items())),
            self.io.position(),
        )

    # -- stepping -----------------------------------------------------

    def step(self) -> None:
        """Advance the program by one definition, read, or expression node."""
        if self.halted:
            return
        if self.frames:
            self._step_frame(self.frames[-1])
            return
        self._start_line()

    def _start_line(self) -> None:
        """Consume one logical line: define a name, or begin evaluating."""
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
            # ``n = 123``: a plain assignment.  It binds rather than
            # prints and takes no input, so its body runs in a frame
            # flagged to assign the result instead of printing it.
            self._push(_Definition("", [], _body(rhs, self.defs)), {}, assign=name)
            return
        # The name is registered *before* its body is parsed, so a
        # definition can refer to itself: the wiki's truth machine is
        # ``x? = x & x?``, whose body names the very operator being
        # defined, and the parser can only match ``?`` against a pattern
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
        """Push a frame for ``definition`` and queue its first statement."""
        frame = _Frame(definition, args, printing=printing, assign=assign)
        frame.work.append((definition.body[0], []))
        self.frames.append(frame)

    def _bind_inputs(self, node: _Node) -> None:
        """Bind every unbound variable in ``node`` from input, in order.

        The spec's example asks for ``a, b, d, c, e`` across two lines,
        which is first-appearance order with bindings persisting, so the
        walk is left-to-right and skips names already bound.
        """
        for name in _free_variables(node):
            if name not in self.globals:
                self.globals[name] = self._read_number()

    def _read_number(self) -> _Number:
        """Read one line of input as a number."""
        text = self.io.input_str().strip()
        if not text:
            return 0
        try:
            return _number(text)
        except ValueError as exc:
            raise HaltError(f"input {text!r} is not a number") from exc

    def _step_frame(self, frame: _Frame) -> None:
        """Resolve one node of ``frame``'s current expression."""
        self._steps += 1
        if self._steps > self._WORK_LIMIT:
            raise HaltError("expression exceeded the evaluation budget")
        if not frame.work:
            self._advance(frame)
            return
        node, done = frame.work[-1]
        # Narrowed on ``node`` itself rather than through a ``kind`` local,
        # so mypy can discriminate the tuple union: binding the tag to a
        # variable first loses the link between it and the node's shape.
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
            # ``$`` exits the function immediately, so the rest of the
            # expression around it is abandoned rather than resumed.
            frame.returned = True
            frame.value = done[0]
            frame.work.clear()
            return
        if node[0] == "bin":
            self._step_binary(frame, node, done)
            return
        self._step_call(frame, node, done)

    def _lookup(self, frame: _Frame, name: str) -> object:
        """Resolve a variable against the frame's locals, then the globals."""
        if name in frame.locals:
            return frame.locals[name]
        if name in self.globals:
            return self.globals[name]
        raise ValueError(f"unknown variable {name!r}")

    def _lookup_function(self, name: str) -> object:
        """Resolve a bare uppercase name to the definition it refers to.

        Only the globals are searched.  A ``ref`` node's name is
        uppercase by construction and every parameter is validated
        lowercase, so a bare name can never be a local; a *parameter*
        holding a function is called as ``c()``, which resolves through
        ``_step_call``'s own locals lookup instead.
        """
        if name in self.defs:
            return self.defs[name]
        raise ValueError(f"unknown function {name!r}")

    def _descend(self, frame: _Frame, node: _Node) -> None:
        """Queue ``node`` as the next sub-evaluation of the current one."""
        frame.work.append((node, []))

    def _step_binary(self, frame: _Frame, node: _Bin, done: list[object]) -> None:
        """Resolve one stage of a binary operator, short-circuiting & and |.

        ``&`` and ``|`` evaluate their left side first and skip the right
        entirely when it cannot change the answer, which is what makes
        ``x & $0`` a conditional: the ``$`` on the right never runs unless
        ``x`` is truthy.
        """
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
            # The left operand did not decide the answer, so the value is
            # the right one as evaluated.
            self._resolve(frame, right)
            return
        self._resolve(frame, _arith(op, _as_number(left), _as_number(right)))

    def _step_call(self, frame: _Frame, node: _Call, done: list[object]) -> None:
        """Evaluate a call's arguments, then push the callee's frame."""
        name, args = node[1], node[2]
        if len(done) < len(args):
            self._descend(frame, args[len(done)])
            return
        # A name bound to a *value* is a parameter holding a function,
        # which is how the wiki's ``WHILE(x, c)`` calls ``x()``.
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
        """Finish the innermost node, handing ``value`` to its parent."""
        frame.work.pop()
        frame.value = value
        if frame.work:
            frame.work[-1][1].append(value)

    def _advance(self, frame: _Frame) -> None:
        """Move to the frame's next statement, or return from it."""
        if not frame.returned and frame.stmt + 1 < len(frame.fn.body):
            # Every statement but the last prints, per the wiki's
            # MULTILINE example -- unless it carries a ``$``, which makes
            # it a conditional return rather than a printed value.
            if not frame.fn.control[frame.stmt]:
                self._print(frame.value)
            frame.stmt += 1
            frame.work.append((frame.fn.body[frame.stmt], []))
            return
        self._pop(frame)

    def _pop(self, frame: _Frame) -> None:
        """Return the frame's value to its caller, printing or assigning it."""
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
        """Write one result, formatted the way the wiki's examples read."""
        number = _as_number(value)
        text = str(number) if isinstance(number, int) else _format_float(number)
        self.io.print_str(text + "\n")


def _format_float(value: float) -> str:
    """Render a float, dropping a trailing ``.0`` from an integral one."""
    return str(int(value)) if value.is_integer() else str(value)


def _truthy(value: object) -> bool:
    """Whether ``value`` is true: every number but zero, and any function."""
    if isinstance(value, _Definition):
        return True
    return _as_number(value) != 0


def _as_number(value: object) -> _Number:
    """Coerce a value to a number, refusing a function."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HaltError(f"expected a number, got {value!r}")
    return value


def _arith(op: str, left: _Number, right: _Number) -> _Number:
    """Apply one arithmetic operator, keeping integers exact.

    ``op`` is one of the six the parser emits for a ``bin`` node other
    than ``&``/``|``, which short-circuit and never reach here.  The
    parser is the only producer, so ``**`` is the fallthrough rather
    than a tested case followed by an unreachable "unknown operator".
    """
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
        # Keep an exact integer where the division is exact, so the
        # unbounded-integer model survives a round trip through ``/``.
        return int(quotient) if quotient.is_integer() else quotient
    if op == "%":
        if right == 0:
            raise HaltError("modulo by zero")
        return left % right
    if left == 0 and right < 0:
        raise HaltError("zero to a negative power")
    return left**right


def _contains_return(node: _Node) -> bool:
    """Whether ``$`` appears anywhere in ``node``; see :class:`_Definition`."""
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
    """List the variables in ``node``, in order of first appearance."""
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
    """Run an APL program, printing the result of every executed line."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
