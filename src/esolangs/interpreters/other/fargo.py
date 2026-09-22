"""Interpreter for Fargo.

Memory is an *input number* (read once before the run; empty or
non-integer is 0, so there is no EOF) and a write-only *output number*.
A line is a definition, a call, blank, or a ``#`` comment.  Builtins:
``<``/``>`` shift by 1; ``&`` ``|`` ``^`` bitwise; ``[] x``, ``+[] x y``,
``[?] x y`` make/concatenate/index arrays; ``@ x`` reads input bit
``x``; ``% x y`` sets output bit ``x``; ``$`` prints the output number;
``: x y`` does ``y`` iff ``x`` is nonzero.  A definition's parameters
are the tokens before the first already-defined name (the function's own
name counts, so it can recurse); a ``:``-prefixed token is passed raw.

Gaps decided: ``:`` is lazy, forced by the wiki truth machine's
``: @ 0 one`` (strict evaluation would loop on input 0); ``%``, ``$``
and a failed ``:`` return 0; a definition's code must be exactly one
outer call (:class:`ValueError`), though a top-level line may hold
several (``$ $``); redefinition is unreachable, since a defined first
token parses as a call.  :class:`~esolangs.exceptions.HaltError` for an
undefined name, a ``:`` body taking arguments, bad array indexing, and
shifting or combining an array.  No expression can build a negative bit
index (see :meth:`_Machine._bit`).

Evaluation uses an explicit ``_Frame`` stack: recursion is Fargo's only
loop, native recursion would hit Python's limit, and the growing stack is
what :func:`esolangs.vm.run_until_halt_or_ancestor` proves a hang on.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, replace

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

# The wiki renders the truth machine with zero-width spaces inside two of
# its lines; they are invisible presentation, not syntax, so the tokenizer
# drops them rather than letting them ride along inside a token.
_ZERO_WIDTH = "​"


class _Func:
    """A callable: a builtin or a user definition, with its arity.

    Not a ``@dataclass``: ``scripts/mutate_one.py`` rewrites the decorator
    to ``C = dataclass(C)`` after the body, below ``_BUILTINS``' use of it.
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

    ``tokens``/``pos`` is the cursor; ``pending`` stacks partially-applied
    calls with their gathered arguments; ``binds`` maps parameters to values.
    Frozen with tuple collections, so a step returns new frames.
    """

    tokens: tuple[str, ...]
    pos: int = 0
    pending: tuple[tuple[_Func, tuple[_Value, ...]], ...] = ()
    binds: tuple[tuple[str, _Value], ...] = ()
    fn_name: str = ""
    result: _Value = 0

    def bound(self, name: str) -> _Value | None:
        """Return ``name``'s bound value, or ``None`` when it is unbound."""
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

    The bare ``:`` is the conditional itself and is returned untouched.
    """
    return token.removeprefix(":") or token


def _parse_program(code: str) -> tuple[dict[str, _Def], list[tuple[str, ...]]]:
    """Split a program into its definitions and its top-level calls.

    A line whose first token is already defined (or a literal) is a call.
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

    Tokens before the first defined name are parameters; ``name`` and each
    gathered parameter count as defined.
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

    #: Whether a read past the end of the input yields a *value* here
    #: rather than raising.  Six languages do; the other 59 raise
    #: :class:`~esolangs.exceptions.InputExhaustedError`, which is the
    #: package norm and what :func:`esolangs.run` documents; this one does
    #: not, so an underfed program answers a different row of its table
    #: instead of refusing, and a caller has no way to tell from the output
    #: that it happened.
    #:
    #: Declared rather than changed.  The zero-beyond-input convention was
    #: audited against every wiki page and settled deliberately
    #: (``docs/limitations.md``, Interpreter conventions); rewriting it
    #: would be a decision about what these languages *mean*, not a fix.
    #: What was wrong was that nothing said so, so the promise ``run`` made
    #: was false for seven languages and a generic caller could not find
    #: out which.
    eof_is_a_value = True

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
        """Read the input number, treating empty or invalid input as 0."""
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

        Arguments are captured via ``repr()``.  A non-returning recursion
        grows the frame tuple, so it is never mistaken for a repeat.
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

        The function and its bindings; the output number is absent because
        nothing reads it.  See :func:`esolangs.vm.run_until_halt_or_ancestor`.
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

        The owed-argument count must return to zero exactly once, at the last
        token.
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

        The stack stays a list: depth is unbounded, so rebuilding it per step
        would be quadratic.
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

        Replaces the top frame, so callers re-read the top afterwards.
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

        Only a top-level line can end owing arguments;
        :meth:`_check_outer_call` rejected every definition that could.
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

        No negative guard: literals match ``/[0-1]+/``, ``@`` yields 0 or 1,
        and every operator preserves non-negativity.
        """
        return (self.number >> self._number(which)) & 1

    def _set_bit(self, which: _Value, value: _Value) -> None:
        """Set the ``which``th bit of the output number (LSB = 0th)."""
        pos = self._number(which)
        if self._number(value) & 1:
            self.output |= 1 << pos
        else:
            self.output &= ~(1 << pos)

    def _conditional(self, frame: _Frame, args: list[_Value]) -> _Value | _Pending:
        """``: x y`` -- do ``y`` iff ``x`` is nonzero.

        ``y`` arrives raw; a zero guard yields 0 without touching it.
        Invoking a user body pushes a frame that supplies the waiting slot
        later, so this returns :data:`_PENDING` rather than a second value.
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
    script_main(run)
