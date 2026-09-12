r"""Interpreter for Fargo."""

from __future__ import annotations

import sys
from collections.abc import Hashable
from dataclasses import dataclass, replace

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# The wiki renders the truth.
# its lines; they are invisible.
# drops them rather than.
_ZERO_WIDTH = "​"


class _Func:
    r"""A callable: a builtin or a user definition, with its arity."""

    __slots__ = ("arity", "name", "raw")

    def __init__(self, name: str, arity: int, raw: tuple[int, ...] = ()) -> None:
        self.name = name
        self.arity = arity
        # : Parameter positions taking.
        self.raw = raw


# Arrays nest (``+[] x y``.
# recursive; the ``type``.
# it name itself.
type _Value = int | tuple[_Value, ...] | _Func


class _Pending:
    r"""The "no value to deliver" marker returned by ``:`` (see below)."""


# ``:`` alone can finish.
# body hands the delivery to.
# ``None`` so it cannot be.
_PENDING = _Pending()


# The builtins, by name.
# bare ``$`` is a complete call.
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
    r"""One user-defined function: its parameters and its code tokens."""

    name: str
    params: tuple[str, ...]
    code: tuple[str, ...]


@dataclass(frozen=True)
class _Frame:
    r"""One expression evaluation in progress."""

    tokens: tuple[str, ...]
    pos: int = 0
    pending: tuple[tuple[_Func, tuple[_Value, ...]], ...] = ()
    binds: tuple[tuple[str, _Value], ...] = ()
    fn_name: str = ""
    result: _Value = 0

    def bound(self, name: str) -> _Value | None:
        r"""Return ``name``'s bound value, or ``None`` when it is unbound."""
        for key, value in self.binds:
            if key == name:
                return value
        return None


def _strip_comment(line: str) -> str:
    r"""Drop a ``#`` comment and the zero-width spaces the wiki renders."""
    return line.split("#", 1)[0].replace(_ZERO_WIDTH, "")


def _is_literal(token: str) -> bool:
    r"""Whether ``token`` is a binary literal (the regex ``/[0-1]+/``)."""
    return bool(token) and all(c in "01" for c in token)


def _bare_name(token: str) -> str:
    r"""Return the name ``token`` refers to, without a raw-function mark."""
    return token.removeprefix(":") or token


def _parse_program(code: str) -> tuple[dict[str, _Def], list[tuple[str, ...]]]:
    r"""Split a program into its definitions and its top-level calls."""
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
    r"""Split a definition's tokens into its parameters and its code."""
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
    r"""Every changing value in a Fargo run."""

    number: int
    output: int
    ind: int
    frames: list[_Frame]


class _Machine:
    r"""One Fargo run: the definitions, the two numbers, and the call stack."""

    # : Whether a read past the end.
    # : rather than raising.
    # :.
    # : package norm and what.
    # : not, so an underfed program.
    # : instead of refusing, and a.
    #: that it happened.
    # :.
    # : Declared rather than.
    # : audited against every wiki.
    # : (``docs/limitations.md``,.
    # : would be a decision about.
    # : What was wrong was that.
    # : was false for seven.
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
        r"""Read the input number, treating empty or invalid input as 0."""
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
        r"""Whether every top-level call has run to completion."""
        return self.ind >= len(self.calls) and not self.frames

    # The VM's language-shaped.
    # cursor.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [self.number, self.output]

    @property
    def stack(self) -> list[object]:
        r"""The stack."""
        return list(self.frames)

    def snapshot(self) -> Hashable:
        r"""Return the complete internal state, hashable for cycle detection."""
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
        r"""Return what ``frame`` is about to run, for the ancestor check."""
        return (
            frame.fn_name,
            tuple(sorted((k, repr(v)) for k, v in frame.binds)),
            self.io.position(),
        )

    def _lookup(self, name: str, frame: _Frame | None) -> _Func:
        r"""Resolve ``name`` to a callable in ``frame``'s scope."""
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
        r"""Raise unless ``definition``'s code is exactly one outer call."""
        if not definition.code:
            raise ValueError(f"function {definition.name!r} has no outer call")
        owed = 1
        for index, token in enumerate(definition.code):
            bare = _bare_name(token)
            # A raw reference (``:f``) is a.
            # nothing -- but the bare ``:``.
            if bare != token or _is_literal(bare) or bare in definition.params:
                arity = 0
            elif bare in _BUILTINS:
                arity = _BUILTINS[bare].arity
            elif bare in self.defs:
                # Including the definition.
                # into ``defs`` before this.
                # here and needs no separate.
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
        r"""Execute one command, advancing the machine."""
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
        r"""Replace the top of the frame stack with ``frame``."""
        self.frames[-1] = frame

    def _consume(self, frame: _Frame, token: str) -> None:
        r"""Handle one token: a literal, a raw function, or a call."""
        if _is_literal(token):
            self._supply(frame, int(token, 2))
            return
        if token.startswith(":") and len(token) > 1:
            name = token.removeprefix(":")
            self._supply(frame, self._lookup(name, frame))
            return
        if self._wants_raw(frame):
            # The waiting call takes this.
            # name is passed along as a.
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
        r"""Whether the innermost waiting call takes its next argument raw."""
        if not frame.pending:
            return False
        fn, args = frame.pending[-1]
        return len(args) in fn.raw

    def _supply(self, frame: _Frame, value: _Value) -> None:
        r"""Deliver ``value`` to whichever call is waiting for it."""
        frame = self.frames[-1]
        if not frame.pending:
            self._retop(replace(frame, result=value))
            return
        fn, args = frame.pending[-1]
        # A raw slot takes whatever.
        # later, or a plain value ``:``.
        args = (*args, value)
        # ``==`` rather than ``>=``,.
        # argument arrives one at a.
        # it is full, so the count.
        # on it.
        # deliveries and no overshoot.
        if len(args) == fn.arity:
            self._retop(replace(frame, pending=frame.pending[:-1]))
            self._invoke(self.frames[-1], fn, list(args))
            return
        self._retop(replace(frame, pending=(*frame.pending[:-1], (fn, args))))

    def _invoke(self, frame: _Frame, fn: _Func, args: list[_Value]) -> None:
        r"""Apply ``fn`` to ``args``, pushing a frame for a user function."""
        if fn.name in _BUILTINS and fn.name not in self.defs:
            result = self._builtin(frame, fn, args)
            if not isinstance(result, _Pending):
                self._supply(frame, result)
            return
        definition = self.defs[fn.name]
        binds = tuple(zip(definition.params, args, strict=False))
        self.frames.append(_Frame(definition.code, fn_name=fn.name, binds=binds))

    def _finish(self, frame: _Frame) -> None:
        r"""Pop a finished frame, delivering its value to its caller."""
        if frame.pending:
            raise ValueError("call wants more args")
        self.frames.pop()
        if self.frames:
            self._supply(self.frames[-1], frame.result)

    def _number(self, value: _Value) -> int:
        r"""Coerce ``value`` to an integer, refusing an array or function."""
        if isinstance(value, int):
            return value
        raise HaltError("expected a number, got an array or function")

    def _builtin(
        self, frame: _Frame, fn: _Func, args: list[_Value]
    ) -> _Value | _Pending:
        r"""Apply one builtin to its finished arguments."""
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
        r"""Coerce ``value`` to an array, refusing anything else."""
        if isinstance(value, tuple):
            return value
        raise HaltError("expected an array")

    def _index(self, array: _Value, which: _Value) -> _Value:
        r"""Return the ``which``th element of ``array``."""
        items = self._array(array)
        pos = self._number(which)
        if not 0 <= pos < len(items):
            raise HaltError(f"array index {pos} out of range")
        return items[pos]

    def _bit(self, which: _Value) -> int:
        r"""Return the ``which``th bit of the input number (LSB = 0th)."""
        return (self.number >> self._number(which)) & 1

    def _set_bit(self, which: _Value, value: _Value) -> None:
        r"""Set the ``which``th bit of the output number (LSB = 0th)."""
        pos = self._number(which)
        if self._number(value) & 1:
            self.output |= 1 << pos
        else:
            self.output &= ~(1 << pos)

    def _conditional(self, frame: _Frame, args: list[_Value]) -> _Value | _Pending:
        r"""``: x y`` -- do ``y`` iff ``x`` is nonzero."""
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
        # Either way the value is.
        # arrives when its pushed frame.
        # body (``: 1 $``) was supplied.
        return _PENDING


def run(code: str, io: IO) -> None:
    r"""Run a Fargo program, reading its input number before it begins."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
