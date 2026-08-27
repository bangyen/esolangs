"""Interpreter for Lamfunc.

A functional prefix-call language: a program is a list of function
definitions (``F name - code`` on one line each) followed by a top-level
call sequence.  Values are integers (decimal or ``0b`` binary literals),
functions, and strings used as variable names.  ``.f`` returns the function
``f`` without calling it, and a call with fewer arguments than the
function's arity returns a lambda that takes the rest, so partial
application is expressible.

A call ``f g x y h i`` means ``f(g(x(), y()), h()); i()``: each argument is
itself a full prefix expression consumed by that expression's own arity.
The eight builtins:

- ``p x`` prints ``x`` (as binary for a number) and returns it.
- ``eq x y`` returns 1 if ``x == y`` else 0.
- ``i x y z`` returns ``y`` if ``x`` is nonzero else ``z``.
- ``cb x y`` combines the bits of ``x`` and ``y`` (``0b10`` and ``0b110``
  give ``0b10110``).
- ``lb x`` returns the last bit of ``x``.
- ``fb x`` returns all but the last bit of ``x``.
- ``vs x y`` sets the variable named ``x`` to ``y`` and returns ``y``.
- ``vg x`` returns the value of the variable named ``x`` (0 if undefined).

Decisions for gaps in the wiki spec (documented):
- a user function's ``return`` value is the value of the last evaluated
  expression in its body (the wiki shows ``Return`` only in Procedure; here
  the last expression's value is the function's result, matching the prefix
  model);
- redefining a function, calling an undefined function, applying a
  non-function, or a top-level call with more arguments than a function's
  arity (an un-consumed dangling argument) is a malformed program
  (:class:`ValueError`); an invalid runtime operation (e.g. printing a
  function, or an overflowed bit combine) raises
  :class:`~esolangs.exceptions.HaltError`.

``_Machine`` runs on an explicit stack of ``_Frame``s (``self.frames``),
each representing one ``_eval``-equivalent expression evaluation in
progress: scanning for a leading token, gathering a callable's arguments,
or running a user function's body / a forced ``i``-branch as a token
span.  A call in any position -- not just at the top level or a function
body's own sequence, but nested inside another call's argument list --
pushes a new frame instead of recursing natively, since Lamfunc has no
"statement" position whose value is always discarded (unlike languages
with real statements): a recursive call reached through the lazy ``i``
builtin's chosen branch is exactly as likely to need this as one at
plain argument position.  This removes recursion depth as a correctness
limit entirely; only ``_scan`` (sizing an unevaluated ``i`` branch, bounded
by the *program text*'s own nesting rather than by how many times it
runs) is left as native recursion, a narrower and much less likely limit.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Literal, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# A frame is always in one of three phases; naming them lets the type
# checker prove the dispatch below is exhaustive.
_Phase = Literal["scan", "gather", "body"]


@dataclass
class _Def:
    """One ``F name - code`` function definition."""

    params: list[str]
    body: list[str]


class _Func:
    """A callable: a builtin, a user function, or a partial application."""

    __slots__ = ("arity", "body", "given", "name", "orig", "params")

    def __init__(
        self,
        name: str,
        arity: int,
        body: list[str] | None = None,
        params: list[str] | None = None,
        given: list[object] | None = None,
        orig: _Func | None = None,
    ) -> None:
        self.name = name
        self.arity = arity
        self.body = body
        self.params = params
        self.given = given or []
        self.orig = orig


_BUILTINS: dict[str, _Func] = {
    "p": _Func("p", 1),
    "eq": _Func("eq", 2),
    "i": _Func("i", 3),
    "cb": _Func("cb", 2),
    "lb": _Func("lb", 1),
    "fb": _Func("fb", 1),
    "vs": _Func("vs", 2),
    "vg": _Func("vg", 1),
}


def _is_int(tok: str) -> bool:
    if tok.startswith("0b"):
        return bool(tok[2:]) and all(c in "01" for c in tok[2:])
    return tok.isdigit()


def _parse_int(tok: str) -> int:
    return int(tok, 2) if tok.startswith("0b") else int(tok)


def _to_binary(value: int) -> str:
    """Print an integer as its binary representation (0 as ``0``)."""
    return bin(value)[2:] if value else "0"


def _as_int(value: object) -> int:
    """Coerce a Lamfunc value to an integer (the bit-builtins' operand)."""
    if isinstance(value, bool):
        return int(value)  # pragma: no cover - Lamfunc never produces a bool
    if isinstance(value, int):
        return value
    raise HaltError(f"expected a number, got {value!r}")


class _Thunk:
    """An unevaluated ``i`` branch: a token span, forced only when selected."""

    __slots__ = ("end", "start", "tokens")

    def __init__(self, tokens: list[str], start: int, end: int) -> None:
        self.tokens = tokens
        self.start = start
        self.end = end


@dataclass
class _Frame:
    """One ``_eval``-equivalent expression evaluation in progress.

    ``phase`` is ``"scan"`` (looking for the leading token at ``pos``),
    ``"gather"`` (a callable ``fn`` is resolved; collecting ``args`` up to
    its arity), or ``"body"`` (running a user function's body as a
    sequence, threading ``result`` forward).  ``awaiting`` is set while a
    pushed child frame's value is pending; ``awaiting_result`` further
    distinguishes "the child's value directly becomes mine" (forcing an
    ``i`` branch, or a call's body finishing) from "append the child's
    value to my own ``args``" (gathering an ordinary argument).
    """

    tokens: list[str]
    pos: int
    start: int = 0
    phase: _Phase = "scan"
    fn: _Func | None = None
    args: list[object] = field(default_factory=list)
    result: object = 0
    saved: dict[str, object] = field(default_factory=dict)
    awaiting: bool = False
    awaiting_result: bool = False


class _Machine:
    """One Lamfunc run: the definitions, variables, cursor, and call stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.defs, self.main = _parse_program(code)
        self.vars: dict[str, object] = {}
        self.ind = 0
        self.frames: list[_Frame] = []
        if self.main:
            self.frames.append(_Frame(self.main, 0, start=0))

    @property
    def halted(self) -> bool:
        """Whether the top-level cursor has run off the call sequence."""
        return self.ind >= len(self.main) and not self.frames

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        Function values are not meaningfully hashable (a closure captures
        live definitions), so argument/result values are captured via
        ``repr()`` -- sufficient for the state-cycle detector's purpose,
        since a genuine hang re-evaluates the same position with the same
        bindings on every lap.  A call that never returns pushes one new
        frame per step and none is ever popped, so this cannot mistake
        unbounded recursion for a repeat: the frame tuple's length
        strictly grows.
        """
        return (
            self.ind,
            tuple(sorted((k, repr(v)) for k, v in self.vars.items())),
            tuple(
                (
                    id(f.tokens),
                    f.pos,
                    f.phase,
                    f.fn.name if f.fn else "",
                    tuple(repr(a) for a in f.args),
                    repr(f.result),
                    f.awaiting,
                    f.awaiting_result,
                )
                for f in self.frames
            ),
            self.io.position(),
        )

    def _arity(self, name: str) -> int:
        """Return ``name``'s arity (a builtin's fixed arity, or a def's)."""
        if name in _BUILTINS:
            return _BUILTINS[name].arity
        if name in self.defs:
            return len(self.defs[name].params)
        raise HaltError(f"calling undefined function {name!r}")

    def _lookup(self, name: str) -> _Func:
        if name in _BUILTINS:
            return _BUILTINS[name]
        if name in self.defs:
            d = self.defs[name]
            return _Func(name, len(d.params), d.body, d.params)
        raise HaltError(  # pragma: no cover - callers only look up known names
            f"calling undefined function {name!r}"
        )

    def _scan(self, tokens: list[str], i: int) -> int:
        """Return how many tokens the expression at ``i`` occupies."""
        tok = tokens[i]
        if (
            tok.startswith(".")
            or _is_int(tok)
            or tok in self.vars
            or (tok not in _BUILTINS and tok not in self.defs)
        ):
            return i + 1
        fn = self._lookup(tok)
        end = i + 1
        for _ in range(fn.arity):
            if end >= len(tokens):
                return end
            end = self._scan(tokens, end)
        return end

    def _def_fields(self, name: str) -> tuple[list[str] | None, list[str] | None]:
        d = self.defs.get(name)
        return (d.body if d else None, d.params if d else None)

    def _partial(self, fn: _Func, given: list[object]) -> _Func:
        """Build a lambda that, when called with the remaining args, calls fn."""
        return _Func(
            fn.name + "..",
            fn.arity - len(given),
            fn.body,
            fn.params,
            given=given,
            orig=fn,
        )

    def _apply_builtin(self, fn: _Func, args: list[object]) -> object:
        """Apply a non-``i``, non-user builtin to its evaluated arguments.

        Never recurses: every one of these builtins is a single, bounded
        computation on already-evaluated values.
        """
        if fn.name == "p":
            self.io.print_str(_print_value(args[0]))
            return args[0]
        if fn.name == "eq":
            return 1 if args[0] == args[1] else 0
        if fn.name == "cb":
            x, y = _as_int(args[0]), _as_int(args[1])
            if x < 0 or y < 0:  # pragma: no cover - Lamfunc values are never negative
                raise HaltError("cb of a negative number is undefined")
            return int(bin(x)[2:] + bin(y)[2:], 2) if (x or y) else 0
        if fn.name == "lb":
            return _as_int(args[0]) & 1
        if fn.name == "fb":
            return _as_int(args[0]) >> 1
        if fn.name == "vs":
            self.vars[str(args[0])] = args[1]
            return args[1]
        if fn.name == "vg":
            return self.vars.get(str(args[0]), 0)
        # pragma: no cover - callers only pass a name from _BUILTINS
        raise AssertionError(f"unexpected non-user builtin {fn.name!r}")

    def _push_scan(self, tokens: list[str], pos: int) -> None:
        """Push a fresh ``"scan"`` frame to evaluate one expression at ``pos``."""
        self.frames.append(_Frame(tokens, pos, start=pos))

    def _resolve(self, frame: _Frame) -> None:
        """Advance a ``"scan"`` frame: classify the token at ``frame.pos``.

        Resolves immediately to a value (popping the frame) for a literal,
        a bound variable, or a bare trailing name; otherwise identifies the
        callable and switches the frame to ``"gather"``.
        """
        tokens, i = frame.tokens, frame.pos
        tok = tokens[i]
        if tok.startswith("."):
            name = tok[1:]
            if name in self.vars:
                self._finish(frame, self.vars[name], 1)
                return
            value = _Func(name, self._arity(name), *self._def_fields(name))
            self._finish(frame, value, 1)
            return
        if _is_int(tok):
            self._finish(frame, _parse_int(tok), 1)
            return
        if tok in self.vars and isinstance(bound := self.vars[tok], _Func):
            fn = bound
        elif tok in _BUILTINS or tok in self.defs:
            fn = self._lookup(tok)
        elif tok in self.vars:
            self._finish(frame, self.vars[tok], 1)
            return
        elif i + 1 < len(tokens):
            raise HaltError(f"calling undefined function {tok!r}")
        else:
            self._finish(frame, tok, 1)
            return
        frame.fn = fn
        frame.pos = i + 1
        frame.phase = "gather"

    def _gather(self, frame: _Frame) -> None:
        """Advance a ``"gather"`` frame by one argument, or dispatch the call."""
        fn = cast(_Func, frame.fn)
        if len(frame.args) == fn.arity:
            self._dispatch(frame, fn)
            return
        tokens, pos = frame.tokens, frame.pos
        if pos >= len(tokens):
            # partial application: not enough tokens left for the remaining args
            value = self._partial(fn, frame.args)
            self._finish(frame, value, pos - frame.start)
            return
        # vs/vg take their variable NAME as a literal token, never a value
        if fn.name in ("vs", "vg") and not frame.args:
            frame.args.append(tokens[pos])
            frame.pos = pos + 1
            return
        # i is lazy in its second and third arguments: only the chosen
        # branch is evaluated, via a pushed frame once i is dispatched.
        if fn.name == "i" and len(frame.args) >= 1:
            end = self._scan(tokens, pos)
            frame.args.append(_Thunk(tokens, pos, end))
            frame.pos = end
            return
        frame.awaiting = True
        self._push_scan(tokens, pos)

    def _dispatch(self, frame: _Frame, fn: _Func) -> None:
        """Apply a fully-gathered call, or push a body frame to run it.

        A partial application completing (``fn.orig is not None``) resolves
        to its original definition plus the accumulated arguments (the
        partial's own ``given`` prefix, then this gather's ``args``) before
        dispatching, the same way the un-partial call would have.
        """
        if fn.orig is not None:
            target = fn.orig
            args = fn.given + frame.args
        else:
            target = fn
            args = frame.args
        if target.name == "i":
            cond, branch_t, branch_f = args[0], args[1], args[2]
            chosen = branch_t if cond != 0 else branch_f
            if isinstance(chosen, _Thunk):
                frame.awaiting = True
                frame.awaiting_result = True
                thunk_frame = _Frame(chosen.tokens, chosen.start, start=chosen.start)
                self.frames.append(thunk_frame)
                return
            self._finish(frame, chosen, frame.pos - frame.start)
            return
        if target.name in _BUILTINS:
            value = self._apply_builtin(target, args)
            self._finish(frame, value, frame.pos - frame.start)
            return
        # a user-defined function: bind params to args in a fresh scope and
        # push a body frame to run it
        saved = {p: self.vars.get(p) for p in (target.params or [])}
        self.vars.update(dict(zip(target.params or [], args, strict=True)))
        body_frame = _Frame(target.body or [], 0, phase="body", saved=saved)
        frame.awaiting = True
        frame.awaiting_result = True
        self.frames.append(body_frame)

    def _step_body(self, frame: _Frame) -> None:
        """Advance a ``"body"`` frame: run its next expression, or finish."""
        if frame.pos >= len(frame.tokens):
            for p in frame.saved:
                self.vars.pop(p, None)
            self.vars.update({p: v for p, v in frame.saved.items() if v is not None})
            self._finish(frame, frame.result, frame.pos - frame.start)
            return
        frame.awaiting = True
        self._push_scan(frame.tokens, frame.pos)

    def _finish(self, frame: _Frame, value: object, consumed: int) -> None:
        """Pop ``frame`` (already the top of the stack) and deliver its value."""
        if self.frames[-1] is not frame:  # pragma: no cover - internal invariant
            raise AssertionError("_finish called on a frame that is not on top")
        self.frames.pop()
        if not self.frames:
            self._toplevel_result(value, consumed)
            return
        caller = self.frames[-1]
        if caller.awaiting_result:
            # the child's value IS the caller's own result (i's forced
            # branch, or a call's body finishing) -- the caller's own pos
            # already reflects its full consumption in its own tokens, so
            # the child's consumed (a different token context) is unused
            caller.awaiting = False
            caller.awaiting_result = False
            self._finish(caller, value, caller.pos - caller.start)
        elif caller.phase == "gather":
            caller.awaiting = False
            caller.args.append(value)
            caller.pos += consumed
        elif caller.phase == "body":
            caller.awaiting = False
            caller.result = value
            caller.pos += consumed
        else:  # pragma: no cover - "scan" never awaits a pushed child
            raise AssertionError(f"unexpected caller phase {caller.phase!r}")

    def _toplevel_result(self, value: object, consumed: int) -> None:
        """Resolve one top-level call's value, advancing the cursor.

        A partial application absorbs the remaining top-level tokens as
        its outstanding arguments: push a fresh ``"gather"`` frame for the
        same (still-partial) function, reusing its own remaining arity and
        an empty ``args`` list -- ``_dispatch`` merges ``fn.given`` back in
        once that gather completes.  This can chain (a still-partial
        result absorbs further arguments the same way) until either the
        arity is fully satisfied or the top-level tokens run out.
        """
        self.ind += consumed
        if isinstance(value, _Func) and value.arity > 0 and self.ind < len(self.main):
            gather_frame = _Frame(
                self.main, self.ind, start=self.ind, phase="gather", fn=value
            )
            self.frames.append(gather_frame)

    def step(self) -> None:
        """Advance the topmost pending frame by one unit of work."""
        if self.halted:
            return
        if not self.frames:
            # the previous top-level call finished plainly (not a partial
            # application); start evaluating the next one
            self._push_scan(self.main, self.ind)
            return
        frame = self.frames[-1]
        if frame.phase == "scan":
            self._resolve(frame)
        elif frame.phase == "gather":
            self._gather(frame)
        else:
            self._step_body(frame)


def _print_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"  # pragma: no cover - Lamfunc never produces a bool
    if isinstance(value, int):
        return _to_binary(value)
    if isinstance(value, _Func):
        return value.name
    return str(value)


def _parse_program(code: str) -> tuple[dict[str, _Def], list[str]]:
    """Split the program into definitions and the top-level call sequence.

    A definition is ``F name - code`` on one line; anything else is part of
    the top-level sequence.  Redefinition is malformed (:class:`ValueError`).
    """
    defs: dict[str, _Def] = {}
    main: list[str] = []
    for line in code.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("F "):
            rest = line[2:]
            if "-" not in rest:
                raise ValueError("function definition must contain '-'")
            head, _, body = rest.partition("-")
            name = head.split()[0]
            params = head.split()[1:]
            if name in defs:
                raise ValueError(f"function {name!r} redefined")
            defs[name] = _Def(params, body.split())
        else:
            main.extend(line.split())
    return defs, main


def run(code: str, io: IO) -> None:
    """Run a Lamfunc program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
