"""Interpreter for Fargo.

A functional prefix-call language whose whole memory is two integers: an
*input number*, fixed before the program begins, and an *output number*,
built up a bit at a time and printed on demand.  Each line is a function
definition, a function call, a blank line, or a ``#`` comment.

A call is a name followed by space-separated arguments, evaluated left to
right; arguments are themselves full prefix expressions, so a line's arity
requirements nest.  The twelve builtins:

- ``< x`` returns ``x`` right-shifted by 1, ``> x`` left-shifted by 1.
- ``& x y``, ``| x y``, ``^ x y`` are bitwise AND, OR and XOR.
- ``[] x`` makes a one-element array; ``+[] x y`` concatenates two arrays;
  ``[?] x y`` returns the ``y``th element of the array ``x``.
- ``@ x`` returns the ``x``th bit of the input number (LSB = 0th bit).
- ``% x y`` sets the ``x``th bit of the output number to ``y``.
- ``$`` outputs the output number in base 10.
- ``: x y`` does ``y`` iff ``x`` is unequal to zero.

Function definitions split their tokens between arguments and code by a
positional rule rather than a delimiter: the first token that is already a
*defined name* -- a builtin, a user function (including the one being
defined, so a function can recurse), or an argument gathered so far -- is
the first code token, and everything before it is an argument.  A token
beginning with ``:`` is a *raw* function: passed unevaluated rather than
called.  ``:`` is the only builtin with a raw parameter, which is what
makes it a conditional rather than an eagerly-evaluated call.

Decisions for gaps in the wiki spec (documented):

- **The conditional is lazy, derived from the wiki's own truth machine.**
  That example's third line is ``: @ 0 one`` with ``one`` bare, where
  ``one`` prints and recurses forever.  Were arguments strictly evaluated,
  ``one`` would run before ``:`` could test its guard and the machine would
  loop on input 0, contradicting the example -- so ``:``'s second parameter
  takes a function *raw* and invokes it (with no arguments) only when the
  guard is nonzero.  A non-function there is returned as-is.
- **Return values the wiki does not give.**  ``%`` and ``$`` return 0, and
  ``:`` returns 0 when its guard is zero.  The output number is therefore
  write-only: no builtin reads it back, which is what lets the recursion
  check key a frame on its arguments alone.
- **The input number is read once, before the program begins**, exactly as
  the spec describes it, rather than lazily at the first ``@``.  A program
  with no ``@`` still consumes its line, so the read is a property of the
  run and not of the program text.  Input that is empty or not an integer
  is taken as 0 (there is no EOF condition to signal: the number is
  established before execution, and every later ``@`` indexes that same
  number).
- **Malformed programs** (:class:`ValueError`): a *definition* whose code
  is not exactly one outer call -- either ending while a call still owes
  arguments, or finishing one call with tokens to spare -- and a call left
  wanting arguments when its frame ends.  The wiki also calls redefining
  an existing name an error, but that is unreachable rather than checked:
  a line whose first token is already defined parses as a *call*, so a
  second definition of one name cannot be written.  The one-outer-call
  rule is likewise a property of definitions only; a top-level line may
  hold several complete calls (``$ $`` prints twice), since nothing in the
  spec makes a call line a single expression.
- **Invalid runtime operations**
  (:class:`~esolangs.exceptions.HaltError`): calling an undefined name,
  giving ``:`` a body that takes arguments (there is nothing to pass it),
  indexing an array out of range or with a non-array, and shifting or
  combining an array where a number is required.  A *negative* bit index
  is not among them because no expression can build one (see
  :meth:`_Machine._bit`); a negative input number is fine, and indexes as
  Python's arbitrary-precision two's complement does.

``_Machine`` evaluates on an explicit stack of ``_Frame``s rather than by
native recursion, because recursion is Fargo's *only* loop: the language
has no jumps and each line runs once, so the truth machine hangs by calling
itself.  Native recursion would hit Python's limit instead of running, and
the frame stack is also what lets
:func:`esolangs.vm.run_until_halt_or_ancestor` prove such a hang -- a
recursion that never returns grows the stack forever and so never revisits
a whole-machine state for the cycle detector to catch.
"""

from __future__ import annotations

import sys
from collections.abc import Hashable
from dataclasses import dataclass, replace

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The wiki renders the truth machine with zero-width spaces inside two of
# its lines; they are invisible presentation, not syntax, so the tokenizer
# drops them rather than letting them ride along inside a token.
_ZERO_WIDTH = "​"


class _Func:
    """A callable: a builtin or a user definition, with its arity.

    Written out rather than declared a ``@dataclass`` because
    :data:`_BUILTINS` instantiates it at module level, and
    ``scripts/mutate_one.py`` rewrites a decorated class into
    ``C = dataclass(C)`` *after* the class body -- which lands below that
    dict and would leave the bundle constructing an undecorated class.
    Three attributes do not need the generated ``__init__`` anyway.
    """

    __slots__ = ("arity", "name", "raw")

    def __init__(self, name: str, arity: int, raw: tuple[int, ...] = ()) -> None:
        self.name = name
        self.arity = arity
        #: Parameter positions taking a function unevaluated (``:``'s second).
        self.raw = raw


# Arrays nest (``+[] x y`` concatenates two of them), so the alias is
# recursive; the ``type`` statement is lazily evaluated, which is what lets
# it name itself.
type _Value = int | tuple[_Value, ...] | _Func


class _Pending:
    """The "no value to deliver" marker returned by ``:`` (see below)."""


# ``:`` alone can finish without a value of its own, because invoking its
# body hands the delivery to that call instead.  A sentinel rather than
# ``None`` so it cannot be confused with a legitimate result.
_PENDING = _Pending()


# The builtins, by name.  ``$`` alone takes no arguments, which is why a
# bare ``$`` is a complete call and can sit in an argument position.
_BUILTINS: dict[str, _Func] = {
    "<": _Func("<", 1),
    ">": _Func(">", 1),
    "&": _Func("&", 2),
    "|": _Func("|", 2),
    "^": _Func("^", 2),
    "[]": _Func("[]", 1),
    "+[]": _Func("+[]", 2),
    "[?]": _Func("[?]", 2),
    "@": _Func("@", 1),
    "%": _Func("%", 2),
    "$": _Func("$", 0),
    ":": _Func(":", 2, raw=(1,)),
}


@dataclass
class _Def:
    """One user-defined function: its parameters and its code tokens."""

    name: str
    params: tuple[str, ...]
    code: tuple[str, ...]


@dataclass(frozen=True)
class _Frame:
    """One expression evaluation in progress.

    ``tokens`` is the token run being consumed and ``pos`` the cursor into
    it.  ``pending`` is the stack of partially-applied calls: each entry is
    a function together with the arguments gathered for it so far, so a
    nested call's result is appended to whichever call is waiting for it.
    ``binds`` maps a user function's parameter names to their values.

    Frozen, and its two collections are tuples: a step returns the frames
    that follow rather than editing the ones it was handed, so a frame is a
    value.  ``replace`` builds the changed copy.
    """

    tokens: tuple[str, ...]
    pos: int = 0
    pending: tuple[tuple[_Func, tuple[_Value, ...]], ...] = ()
    binds: tuple[tuple[str, _Value], ...] = ()
    fn_name: str = ""
    result: _Value = 0

    def bound(self, name: str) -> _Value | None:
        """Return ``name``'s bound value, or ``None`` when it is unbound.

        The binds are a tuple of pairs rather than a mapping so the frame
        stays hashable; a function's parameter list is short, so the scan
        costs less than rebuilding a dict per call would.
        """
        for key, value in self.binds:
            if key == name:
                return value
        return None


def _strip_comment(line: str) -> str:
    """Drop a ``#`` comment and the zero-width spaces the wiki renders."""
    return line.split("#", 1)[0].replace(_ZERO_WIDTH, "")


def _is_literal(token: str) -> bool:
    """Whether ``token`` is a binary literal (the regex ``/[0-1]+/``)."""
    return bool(token) and all(c in "01" for c in token)


def _bare_name(token: str) -> str:
    """Return the name ``token`` refers to, without a raw-function mark.

    A leading ``:`` marks a raw function -- except on the bare ``:``, which
    is the conditional builtin itself.  Stripping that one would leave the
    empty string and make the language's only conditional look like an
    ordinary name, so it is returned untouched -- which is what the ``or``
    falls back to, since stripping leaves ``""`` only for ``""`` and ``":"``.
    """
    return token.removeprefix(":") or token


def _parse_program(code: str) -> tuple[dict[str, _Def], list[tuple[str, ...]]]:
    """Split a program into its definitions and its top-level calls.

    A line's first token decides which it is: a name already defined (or a
    builtin, or a literal) begins a *call*, and anything else begins a
    *definition*.  Definitions are therefore visible to every later line,
    and to themselves -- which is how a function recurses.
    """
    defs: dict[str, _Def] = {}
    calls: list[tuple[str, ...]] = []
    for raw_line in code.splitlines():
        tokens = tuple(_strip_comment(raw_line).split())
        if not tokens:
            continue
        head = tokens[0]
        if (
            head in _BUILTINS
            or head in defs
            or _is_literal(head)
            or head.startswith(":")
        ):
            calls.append(tokens)
            continue
        defs[head] = _parse_definition(head, tokens[1:], defs)
    return defs, calls


def _parse_definition(
    name: str,
    rest: tuple[str, ...],
    defs: dict[str, _Def],
) -> _Def:
    """Split a definition's tokens into its parameters and its code.

    The divide is positional: scanning left to right, a token that is *not*
    yet a defined name becomes a parameter, and the first token that is one
    starts the code.  ``name`` counts as defined from the outset, so a
    function may call itself, and each parameter joins the defined set as
    it is gathered -- so a repeated parameter name would start the code
    rather than declare a second parameter.
    """
    params: list[str] = []
    known = set(defs) | {name}
    index = 0
    for index, token in enumerate(rest):  # noqa: B007 - the cursor is the result
        bare = _bare_name(token)
        if bare in _BUILTINS or bare in known or _is_literal(bare):
            break
        params.append(token)
        known.add(token)
    else:
        index = len(rest)
    return _Def(name, tuple(params), tuple(rest[index:]))


@dataclass
class _State:
    """Every changing value in a Fargo run."""

    number: int
    output: int
    ind: int
    frames: list[_Frame]


class _Machine:
    """One Fargo run: the definitions, the two numbers, and the call stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.defs, self.calls = _parse_program(code)
        for definition in self.defs.values():
            self._check_outer_call(definition)
        self.state = _State(self._read_input(), 0, 0, [])

    @property
    def number(self) -> int:
        return self.state.number

    @property
    def output(self) -> int:
        return self.state.output

    @output.setter
    def output(self, value: int) -> None:
        self.state.output = value

    @property
    def ind(self) -> int:
        return self.state.ind

    @ind.setter
    def ind(self, value: int) -> None:
        self.state.ind = value

    @property
    def frames(self) -> list[_Frame]:
        return self.state.frames

    def _read_input(self) -> int:
        """Read the input number, treating empty or invalid input as 0.

        The spec has the interpreter establish this number *before* the
        program begins, so the read is unconditional: a program with no
        ``@`` consumes its input line just the same.
        """
        try:
            text = self.io.input_str()
        except EOFError:
            return 0
        try:
            return int(text.strip())
        except ValueError:
            return 0

    @property
    def halted(self) -> bool:
        """Whether every top-level call has run to completion."""
        return self.ind >= len(self.calls) and not self.frames

    # The VM's language-shaped view: Prefix-call evaluator; ip is the top-level line
    # cursor.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.number, self.output]

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.frames)

    def snapshot(self) -> Hashable:
        """Return the complete internal state, hashable for cycle detection.

        Carries the top-level cursor, the whole frame stack, the output
        number, and the input cursor.  Argument values are captured via
        ``repr()`` because a function value is not meaningfully hashable.
        A recursion that never returns pushes frames without popping them,
        so the frame tuple's length strictly grows and this cannot mistake
        that hang for a repeat -- which is what
        :func:`esolangs.vm.run_until_halt_or_ancestor` is for.
        """
        return (
            self.ind,
            self.number,
            self.output,
            tuple(
                (
                    frame.tokens,
                    frame.pos,
                    frame.fn_name,
                    repr(frame.result),
                    tuple(
                        (fn.name, tuple(repr(a) for a in args))
                        for fn, args in frame.pending
                    ),
                    tuple(sorted((k, repr(v)) for k, v in frame.binds)),
                )
                for frame in self.frames
            ),
            self.io.position(),
        )

    def frame_entry_key(self, frame: _Frame) -> Hashable:
        """Return what ``frame`` is about to run, for the ancestor check.

        Two frames with equal keys replay each other, so the key is the
        function and its bindings.  The output number is deliberately
        absent: nothing reads it back (``%`` and ``$`` both return 0), so
        it cannot affect what a frame goes on to do.  The input cursor is
        included for the same reason Forbin includes it, though Fargo reads
        exactly once before the run, so it never varies between frames.
        See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        return (
            frame.fn_name,
            tuple(sorted((k, repr(v)) for k, v in frame.binds)),
            self.io.position(),
        )

    def _lookup(self, name: str, frame: _Frame | None) -> _Func:
        """Resolve ``name`` to a callable in ``frame``'s scope."""
        if frame is not None and (bound := frame.bound(name)) is not None:
            value = bound
            if isinstance(value, _Func):
                return value
            raise HaltError(f"calling non-function argument {name!r}")
        if name in _BUILTINS:
            return _BUILTINS[name]
        if name in self.defs:
            return _Func(name, len(self.defs[name].params))
        raise HaltError(f"calling undefined function {name!r}")

    def _check_outer_call(self, definition: _Def) -> None:
        """Raise unless ``definition``'s code is exactly one outer call.

        Walks the code the way the evaluator does, tracking how many
        arguments the open calls still owe.  The body is one outer call
        when that debt returns to zero exactly once, at the final token:
        reaching zero early means a second top-level call follows, and
        ending above zero means the outer call never got its arguments.
        """
        if not definition.code:
            raise ValueError(f"function {definition.name!r} has no outer call")
        owed = 1
        for index, token in enumerate(definition.code):
            bare = _bare_name(token)
            # A raw reference (``:f``) is a value, not a call, so it owes
            # nothing -- but the bare ``:`` is the conditional itself.
            if bare != token or _is_literal(bare) or bare in definition.params:
                arity = 0
            elif bare in _BUILTINS:
                arity = _BUILTINS[bare].arity
            elif bare in self.defs:
                # Including the definition being checked: parsing files it
                # into ``defs`` before this runs, so a self-call resolves
                # here and needs no separate arm.
                arity = len(self.defs[bare].params)
            else:
                arity = 0
            owed += arity - 1
            if owed == 0 and index != len(definition.code) - 1:
                raise ValueError(
                    f"function {definition.name!r} has more than one outer call"
                )
        if owed != 0:
            raise ValueError(f"function {definition.name!r} has no outer call")

    def step(self) -> None:
        """Execute one command, advancing the machine."""
        if self.halted:
            return
        if not self.frames:
            self.frames.append(_Frame(self.calls[self.ind]))
            self.ind += 1
            return
        frame = self.frames[-1]
        if frame.pos >= len(frame.tokens):
            self._finish(frame)
            return
        token = frame.tokens[frame.pos]
        frame = replace(frame, pos=frame.pos + 1)
        self._retop(frame)
        self._consume(frame, token)

    def _retop(self, frame: _Frame) -> None:
        """Replace the top of the frame stack with ``frame``.

        A frame is frozen, so every change to the one being executed is a
        replacement.  The stack itself stays a list: Fargo pushes a frame
        per user-function call and its depth is unbounded, so rebuilding
        the stack per step would be quadratic in the call depth.
        """
        self.frames[-1] = frame

    def _consume(self, frame: _Frame, token: str) -> None:
        """Handle one token: a literal, a raw function, or a call."""
        if _is_literal(token):
            self._supply(frame, int(token, 2))
            return
        if token.startswith(":") and len(token) > 1:
            name = token.removeprefix(":")
            self._supply(frame, self._lookup(name, frame))
            return
        if self._wants_raw(frame):
            # The waiting call takes this parameter unevaluated, so the
            # name is passed along as a function instead of being run.
            self._supply(frame, self._lookup(token, frame))
            return
        if frame.binds and (bound := frame.bound(token)) is not None:
            value = bound
            if isinstance(value, _Func) and value.arity == 0:
                self._invoke(frame, value, [])
                return
            self._supply(frame, value)
            return
        fn = self._lookup(token, frame)
        if fn.arity == 0:
            self._invoke(frame, fn, [])
            return
        self._retop(replace(frame, pending=(*frame.pending, (fn, ()))))

    def _wants_raw(self, frame: _Frame) -> bool:
        """Whether the innermost waiting call takes its next argument raw."""
        if not frame.pending:
            return False
        fn, args = frame.pending[-1]
        return len(args) in fn.raw

    def _supply(self, frame: _Frame, value: _Value) -> None:
        """Deliver ``value`` to whichever call is waiting for it.

        The frame is frozen, so the delivery *replaces* the top of the
        stack rather than editing it in place, and the caller's own
        ``frame`` reference goes stale at that point -- every path below
        therefore re-reads the top rather than reusing it.
        """
        frame = self.frames[-1]
        if not frame.pending:
            self._retop(replace(frame, result=value))
            return
        fn, args = frame.pending[-1]
        # A raw slot takes whatever arrives unchanged: a function to invoke
        # later, or a plain value ``:`` will simply yield.
        args = (*args, value)
        # ``==`` rather than ``>=``, and the two cannot be told apart: an
        # argument arrives one at a time and the call is popped the moment
        # it is full, so the count never passes the arity without landing
        # on it.  Instrumenting this comparison over the corpus sees 16
        # deliveries and no overshoot.
        if len(args) == fn.arity:
            self._retop(replace(frame, pending=frame.pending[:-1]))
            self._invoke(self.frames[-1], fn, list(args))
            return
        self._retop(replace(frame, pending=(*frame.pending[:-1], (fn, args))))

    def _invoke(self, frame: _Frame, fn: _Func, args: list[_Value]) -> None:
        """Apply ``fn`` to ``args``, pushing a frame for a user function."""
        if fn.name in _BUILTINS and fn.name not in self.defs:
            result = self._builtin(frame, fn, args)
            if not isinstance(result, _Pending):
                self._supply(frame, result)
            return
        definition = self.defs[fn.name]
        binds = tuple(zip(definition.params, args, strict=False))
        self.frames.append(_Frame(definition.code, fn_name=fn.name, binds=binds))

    def _finish(self, frame: _Frame) -> None:
        """Pop a finished frame, delivering its value to its caller.

        A frame ending with an unfinished call is always a *top-level*
        line: :meth:`_check_outer_call` has already rejected any
        definition whose body could end that way, so a pushed frame
        cannot reach here owing arguments and the message needs no name.
        """
        if frame.pending:
            raise ValueError("call wants more args")
        self.frames.pop()
        if self.frames:
            self._supply(self.frames[-1], frame.result)

    def _number(self, value: _Value) -> int:
        """Coerce ``value`` to an integer, refusing an array or function."""
        if isinstance(value, int):
            return value
        raise HaltError("expected a number, got an array or function")

    def _builtin(
        self, frame: _Frame, fn: _Func, args: list[_Value]
    ) -> _Value | _Pending:
        """Apply one builtin to its finished arguments."""
        name = fn.name
        if name == "<":
            return self._number(args[0]) >> 1
        if name == ">":
            return self._number(args[0]) << 1
        if name == "&":
            return self._number(args[0]) & self._number(args[1])
        if name == "|":
            return self._number(args[0]) | self._number(args[1])
        if name == "^":
            return self._number(args[0]) ^ self._number(args[1])
        if name == "[]":
            return (args[0],)
        if name == "+[]":
            return self._array(args[0]) + self._array(args[1])
        if name == "[?]":
            return self._index(args[0], args[1])
        if name == "@":
            return self._bit(args[0])
        if name == "%":
            self._set_bit(args[0], args[1])
            return 0
        if name == "$":
            self.io.print_num(self.output)
            return 0
        return self._conditional(frame, args)

    def _array(self, value: _Value) -> tuple[_Value, ...]:
        """Coerce ``value`` to an array, refusing anything else."""
        if isinstance(value, tuple):
            return value
        raise HaltError("expected an array")

    def _index(self, array: _Value, which: _Value) -> _Value:
        """Return the ``which``th element of ``array``."""
        items = self._array(array)
        pos = self._number(which)
        if not 0 <= pos < len(items):
            raise HaltError(f"array index {pos} out of range")
        return items[pos]

    def _bit(self, which: _Value) -> int:
        """Return the ``which``th bit of the input number (LSB = 0th).

        A bit index is never negative, so there is no guard: literals match
        ``/[0-1]+/``, ``@`` itself yields 0 or 1, and the shifts and bitwise
        operators all preserve non-negativity, so no expression can build
        one.  The *input number* may well be negative -- it is parsed from
        the input line -- but it is the value being indexed, not the index.
        """
        return (self.number >> self._number(which)) & 1

    def _set_bit(self, which: _Value, value: _Value) -> None:
        """Set the ``which``th bit of the output number (LSB = 0th).

        As in :meth:`_bit`, the index cannot be negative.
        """
        pos = self._number(which)
        if self._number(value) & 1:
            self.output |= 1 << pos
        else:
            self.output &= ~(1 << pos)

    def _conditional(self, frame: _Frame, args: list[_Value]) -> _Value | _Pending:
        """``: x y`` -- do ``y`` iff ``x`` is nonzero.

        ``y`` arrives unevaluated (see the module docstring): a function is
        invoked only when the guard is nonzero, and a plain value is simply
        returned.  A zero guard yields 0 without touching ``y`` at all,
        which is what stops the truth machine looping on input 0.

        Invoking the body makes ``:`` *become* that call: its value is the
        body's own, which for a user function arrives later, when the
        pushed frame finishes and supplies whoever was waiting.  Returning
        anything here as well would deliver two values into one argument
        slot, so this returns :data:`_PENDING` to say "the frame will do
        it" -- invisible unless the ``:`` sits nested inside another call,
        which is exactly where the double-supply would fire.
        """
        if not self._number(args[0]):
            return 0
        body = args[1]
        if not isinstance(body, _Func):
            return body
        if body.arity:
            raise HaltError(
                f"conditional body {body.name!r} takes {body.arity} argument(s)"
            )
        self._invoke(frame, body, [])
        # Either way the value is already accounted for: a user function's
        # arrives when its pushed frame finishes, and a zero-arity builtin
        # body (``: 1 $``) was supplied by ``_invoke`` itself.
        return _PENDING


def run(code: str, io: IO) -> None:
    """Run a Fargo program, reading its input number before it begins."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
