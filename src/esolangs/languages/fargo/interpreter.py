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
outer call (:class:`ValueError`; a bare literal or value argument is
none), though a top-level line may hold several (``$ $``); ``% x y``
writes ``y``'s low bit ("sets the xth bit ... to y" leaves y=10 open;
the clean-room reading writes 1 for any nonzero y); redefinition is
unreachable, since a defined first token parses as a call.
:class:`~esolangs.exceptions.HaltError` for an undefined name, a ``:``
body taking arguments, bad array indexing, and shifting or combining an
array.  No expression can build a negative bit index (see
:meth:`_Machine._bit`).

Evaluation uses an explicit ``_Frame`` stack: recursion is Fargo's only
loop, native recursion would hit Python's limit, and the growing stack is
what :func:`esolangs.vm.run_until_halt_or_ancestor` proves a hang on.

The semantics are a pure transition: :func:`_advance` maps an immutable
``_State`` (the two numbers, the top-level cursor, the frame tuple) plus
the parsed definitions to a new state and the number ``$`` asks to print.
``step`` is the shell that performs that one write.  The input number is
read once before the run, so no read reaches the transition.

Its initial number is a whitespace-delimited integer token; the spec does not
define text framing.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, replace

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

# The wiki renders the truth machine with zero-width spaces inside two of
# its lines; they are invisible presentation, not syntax, so the tokenizer
# drops them rather than letting them ride along inside a token.
_ZERO_WIDTH = "​"


class _Func:
    """A callable: a builtin or a user definition, with its arity.

    Not a ``@dataclass``: the removed mutation harness rewrote the decorator
    to ``C = dataclass(C)`` after the body, below ``_BUILTINS``' use of it.
    """

    __slots__ = ("arity", "name", "raw")

    def __init__(self, name: str, arity: int, raw: tuple[int, ...] = ()) -> None:
        self.name = name
        self.arity = arity
        #: Parameter positions taking a function unevaluated (``:``'s second).
        self.raw = raw

    def __repr__(self) -> str:
        """Identify a callable's semantics, independent of allocation."""
        return f"_Func({self.name!r}, {self.arity}, {self.raw!r})"


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
        known.add(bare)
    else:
        index = len(rest)
    return _Def(name, tuple(params), tuple(rest[index:]))


@dataclass(frozen=True)
class _State:
    """Every changing value in a Fargo run.

    A value, not a record: the frame stack is an immutable tuple and
    :func:`_advance` returns a new state rather than editing this one.
    """

    number: int
    output: int
    ind: int
    frames: tuple[_Frame, ...]


class _Machine:
    """One Fargo run: the definitions, the two numbers, and the call stack.

    The run state is an immutable :class:`_State`; :func:`_advance` is the
    semantics, and :meth:`step` is the shell that performs the effect it
    returns.
    """

    #: Whether a read past the end of the input yields a *value* here
    #: rather than raising.  A few languages do; the rest raise
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
            _check_outer_call(definition, self.defs)
        self.state = _State(self._read_input(), 0, 0, ())

    @property
    def number(self) -> int:
        return self.state.number

    @property
    def output(self) -> int:
        return self.state.output

    @output.setter
    def output(self, value: int) -> None:
        self.state = replace(self.state, output=value)

    @property
    def ind(self) -> int:
        return self.state.ind

    @ind.setter
    def ind(self, value: int) -> None:
        self.state = replace(self.state, ind=value)

    @property
    def frames(self) -> list[_Frame]:
        return list(self.state.frames)

    def _read_input(self) -> int:
        """Read the input number, treating empty or invalid input as 0."""
        try:
            text = self.io.input_token()
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
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [self.number, self.output]

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return list(self.state.frames)

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
                for frame in self.state.frames
            ),
            self.io.progress(),
        )

    def frame_entry_key(self, frame: _Frame) -> Hashable:
        """Return what ``frame`` is about to run, for the ancestor check.

        The function and its bindings; the output number is absent because
        nothing reads it.  See :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
        return (
            frame.fn_name,
            tuple(sorted((k, repr(v)) for k, v in frame.binds)),
            self.io.progress(),
        )

    def step(self) -> None:
        """Execute one command, advancing the machine.

        The shell: the input number was read once before the run, so the
        only port left is ``$``'s write, performed from the effect the pure
        transition returns.
        """
        if self.halted:
            return
        self.state, effect = _advance(self.state, self.defs, self.calls)
        if effect is not None:
            self.io.print_num(effect)


def _retop(frames: tuple[_Frame, ...], frame: _Frame) -> tuple[_Frame, ...]:
    """Return ``frames`` with its top replaced by ``frame``."""
    return (*frames[:-1], frame)


def _lookup(name: str, frame: _Frame | None, defs: dict[str, _Def]) -> _Func:
    """Resolve ``name`` to a callable in ``frame``'s scope."""
    if frame is not None and (bound := frame.bound(name)) is not None:
        value = bound
        if isinstance(value, _Func):
            return value
        raise HaltError(
            f"calling non-function argument {name!r}",
            hint="pass a callable function argument before invoking it",
        )
    if name in _BUILTINS:
        return _BUILTINS[name]
    if name in defs:
        return _defined(name, defs)
    raise HaltError(
        f"calling undefined function {name!r}",
        hint="define the function before calling it; check its spelling",
    )


def _defined(name: str, defs: dict[str, _Def]) -> _Func:
    """Return a definition's arity and unevaluated argument positions."""
    definition = defs[name]
    raw = tuple(
        index
        for index, parameter in enumerate(definition.params)
        if _bare_name(parameter) != parameter
    )
    return _Func(name, len(definition.params), raw)


def _check_outer_call(
    definition: _Def, defs: dict[str, _Def], binds: dict[str, _Value] | None = None
) -> None:
    """Require one expression; bound functions supply their arity at invocation."""
    parameters = {_bare_name(parameter) for parameter in definition.params}
    raw_parameters = {
        _bare_name(parameter)
        for parameter in definition.params
        if _bare_name(parameter) != parameter
    }
    head = definition.code[0] if definition.code else ":"
    if (
        _bare_name(head) != head
        or _is_literal(head)
        or (head in parameters and head not in raw_parameters)
    ):
        # A literal, raw name or value argument is no call (``f0 101``).
        raise syntax_error(
            f"function {definition.name!r} has no outer call",
            "start the code with a function call",
        )
    # Whether each still-expected argument is passed raw (unevaluated);
    # the body must fill every slot with exactly one outer prefix call.
    expected_raw = [False]
    finished = True
    for index, token in enumerate(definition.code):
        if not expected_raw:
            raise syntax_error(
                f"function {definition.name!r} has more than one outer call",
                "nest calls as arguments of one outer prefix call",
            )
        raw = expected_raw.pop()
        bare = _bare_name(token)
        if bare != token or _is_literal(bare) or raw:
            continue
        if bare in parameters:
            if binds is None and bare not in raw_parameters:
                # Wiki: an unmarked argument is a value, so
                # ``myFn x y z otherFn x y z anotherFn x`` is malformed.
                continue
            if binds is None:
                # Each remaining token supplies at most one owed argument.
                # Extra tokens may belong to this parameter's unknown arity.
                if len(definition.code) - index < len(expected_raw) + 1:
                    finished = False
                    break
                return
            value = binds[bare]
            if not isinstance(value, _Func):
                continue
            fn = value
        elif bare in _BUILTINS:
            fn = _BUILTINS[bare]
        elif bare in defs:
            fn = _defined(bare, defs)
        else:
            continue
        expected_raw.extend(i in fn.raw for i in reversed(range(fn.arity)))
    if finished and not expected_raw:
        return
    raise syntax_error(
        f"function {definition.name!r} has no outer call",
        "supply every argument required by the outer prefix call",
    )


def _wants_raw(frame: _Frame) -> bool:
    """Whether the innermost waiting call takes its next argument raw."""
    if not frame.pending:
        return False
    fn, args = frame.pending[-1]
    return len(args) in fn.raw


def _advance(
    state: _State, defs: dict[str, _Def], calls: list[tuple[str, ...]]
) -> tuple[_State, int | None]:
    """Return the state after one command, and the number to print, if any.

    Pure: ``defs`` and ``calls`` are parameters, the frame stack is a value,
    and ``$``'s write leaves as the returned effect instead of reaching a
    port.
    """
    number, output, ind, frames = state.number, state.output, state.ind, state.frames
    if not frames:
        return _State(number, output, ind + 1, (_Frame(calls[ind]),)), None
    frame = frames[-1]
    if frame.pos >= len(frame.tokens):
        frames, output, effect = _finish(frames, number, output, defs)
        return _State(number, output, ind, frames), effect
    token = frame.tokens[frame.pos]
    frames = _retop(frames, replace(frame, pos=frame.pos + 1))
    frames, output, effect = _consume(frames, frames[-1], token, number, output, defs)
    return _State(number, output, ind, frames), effect


def _consume(
    frames: tuple[_Frame, ...],
    frame: _Frame,
    token: str,
    number: int,
    output: int,
    defs: dict[str, _Def],
) -> tuple[tuple[_Frame, ...], int, int | None]:
    """Handle one token: a literal, a raw function, or a call."""
    if _is_literal(token):
        return _supply(frames, int(token, 2), number, output, defs)
    if token.startswith(":") and len(token) > 1:
        name = token.removeprefix(":")
        return _supply(frames, _lookup(name, frame, defs), number, output, defs)
    if _wants_raw(frame):
        # The waiting call takes this parameter unevaluated, so the
        # name is passed along as a function instead of being run.
        return _supply(frames, _lookup(token, frame, defs), number, output, defs)
    if frame.binds and (bound := frame.bound(token)) is not None:
        value = bound
        if not isinstance(value, _Func):
            return _supply(frames, value, number, output, defs)
    fn = _lookup(token, frame, defs)
    if fn.arity == 0:
        return _invoke(frames, frame, fn, (), number, output, defs)
    return (
        _retop(frames, replace(frame, pending=(*frame.pending, (fn, ())))),
        output,
        None,
    )


def _supply(
    frames: tuple[_Frame, ...],
    value: _Value,
    number: int,
    output: int,
    defs: dict[str, _Def],
) -> tuple[tuple[_Frame, ...], int, int | None]:
    """Deliver ``value`` to whichever call is waiting for it.

    Replaces the top frame, so callers re-read the top afterwards.
    """
    frame = frames[-1]
    if not frame.pending:
        return _retop(frames, replace(frame, result=value)), output, None
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
        frames = _retop(frames, replace(frame, pending=frame.pending[:-1]))
        return _invoke(frames, frames[-1], fn, args, number, output, defs)
    return (
        _retop(frames, replace(frame, pending=(*frame.pending[:-1], (fn, args)))),
        output,
        None,
    )


def _invoke(
    frames: tuple[_Frame, ...],
    frame: _Frame,
    fn: _Func,
    args: list[_Value] | tuple[_Value, ...],
    number: int,
    output: int,
    defs: dict[str, _Def],
) -> tuple[tuple[_Frame, ...], int, int | None]:
    """Apply ``fn`` to ``args``, pushing a frame for a user function."""
    if fn.name in _BUILTINS and fn.name not in defs:
        result, frames, output, effect = _builtin(
            frames, frame, fn, args, number, output, defs
        )
        if isinstance(result, _Pending):
            return frames, output, effect
        frames, output, supplied = _supply(frames, result, number, output, defs)
        return frames, output, effect if effect is not None else supplied
    definition = defs[fn.name]
    binds = tuple(
        zip(
            (_bare_name(parameter) for parameter in definition.params),
            args,
            strict=True,
        )
    )
    _check_outer_call(definition, defs, dict(binds))
    return (
        (*frames, _Frame(definition.code, fn_name=fn.name, binds=binds)),
        output,
        None,
    )


def _finish(
    frames: tuple[_Frame, ...], number: int, output: int, defs: dict[str, _Def]
) -> tuple[tuple[_Frame, ...], int, int | None]:
    """Pop a finished frame, delivering its value to its caller.

    Definitions are checked again once parameter arities are bound.
    """
    frame = frames[-1]
    if frame.pending:
        raise syntax_error(
            "call wants more args",
            "supply every argument required by the pending prefix call",
        )
    frames = frames[:-1]
    if frames:
        return _supply(frames, frame.result, number, output, defs)
    return frames, output, None


def _number(value: _Value) -> int:
    """Coerce ``value`` to an integer, refusing an array or function."""
    if isinstance(value, int):
        return value
    raise HaltError(
        "expected a number, got an array or function",
        hint="use a numeric value in this expression",
    )


def _builtin(
    frames: tuple[_Frame, ...],
    frame: _Frame,
    fn: _Func,
    args: list[_Value] | tuple[_Value, ...],
    number: int,
    output: int,
    defs: dict[str, _Def],
) -> tuple[_Value | _Pending, tuple[_Frame, ...], int, int | None]:
    """Apply one builtin to its finished arguments."""
    name = fn.name
    if name == "<":
        return _number(args[0]) >> 1, frames, output, None
    if name == ">":
        return _number(args[0]) << 1, frames, output, None
    if name == "&":
        return _number(args[0]) & _number(args[1]), frames, output, None
    if name == "|":
        return _number(args[0]) | _number(args[1]), frames, output, None
    if name == "^":
        return _number(args[0]) ^ _number(args[1]), frames, output, None
    if name == "[]":
        return (args[0],), frames, output, None
    if name == "+[]":
        return _array(args[0]) + _array(args[1]), frames, output, None
    if name == "[?]":
        return _index(args[0], args[1]), frames, output, None
    if name == "@":
        return _bit(number, args[0]), frames, output, None
    if name == "%":
        return 0, frames, _set_bit(output, args[0], args[1]), None
    if name == "$":
        return 0, frames, output, output
    return _conditional(frames, frame, args, number, output, defs)


def _array(value: _Value) -> tuple[_Value, ...]:
    """Coerce ``value`` to an array, refusing anything else."""
    if isinstance(value, tuple):
        return value
    raise HaltError("expected an array", hint="pass an array value to this operation")


def _index(array: _Value, which: _Value) -> _Value:
    """Return the ``which``th element of ``array``."""
    items = _array(array)
    pos = _number(which)
    if not 0 <= pos < len(items):
        raise HaltError(
            f"array index {pos} out of range",
            hint="keep the index within the array bounds",
        )
    return items[pos]


def _bit(number: int, which: _Value) -> int:
    """Return the ``which``th bit of the input number (LSB = 0th).

    No negative guard: literals match ``/[0-1]+/``, ``@`` yields 0 or 1,
    and every operator preserves non-negativity.
    """
    return (number >> _number(which)) & 1


def _set_bit(output: int, which: _Value, value: _Value) -> int:
    """Return ``output`` with the ``which``th bit set (LSB = 0th)."""
    pos = _number(which)
    if _number(value) & 1:
        return output | (1 << pos)
    return output & ~(1 << pos)


def _conditional(
    frames: tuple[_Frame, ...],
    frame: _Frame,
    args: list[_Value] | tuple[_Value, ...],
    number: int,
    output: int,
    defs: dict[str, _Def],
) -> tuple[_Value | _Pending, tuple[_Frame, ...], int, int | None]:
    """``: x y`` -- do ``y`` iff ``x`` is nonzero.

    ``y`` arrives raw; a zero guard yields 0 without touching it.
    Invoking a user body pushes a frame that supplies the waiting slot
    later, so this returns :data:`_PENDING` rather than a second value.
    """
    if not _number(args[0]):
        return 0, frames, output, None
    body = args[1]
    if not isinstance(body, _Func):
        return body, frames, output, None
    if body.arity:
        raise HaltError(
            f"conditional body {body.name!r} takes {body.arity} argument(s)",
            hint="pass the conditional body its declared number of arguments",
        )
    frames, output, effect = _invoke(frames, frame, body, (), number, output, defs)
    # Either way the value is already accounted for: a user function's
    # arrives when its pushed frame finishes, and a zero-arity builtin
    # body (``: 1 $``) was supplied by ``_invoke`` itself.
    return _PENDING, frames, output, effect


def run(code: str, io: IO) -> None:
    """Run a Fargo program, reading its input number before it begins."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
