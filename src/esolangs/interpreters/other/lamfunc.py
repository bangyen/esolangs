r"""Interpreter for Lamfunc."""

from __future__ import annotations

import sys
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal, cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# A frame is always in one of.
# checker prove the dispatch.
_Phase = Literal["scan", "gather", "body"]


@dataclass
class _Def:
    r"""One ``F name - code`` function definition."""

    params: list[str]
    body: list[str]


class _Func:
    r"""A callable: a builtin, a user function, or a partial application."""

    __slots__ = ("arity", "body", "given", "name", "orig", "params")

    def __init__(
        self,
        name: str,
        arity: int,
        body: list[str] | None = None,
        params: list[str] | None = None,
        given: list[_Value] | None = None,
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
    r"""Print an integer as its binary representation (0 as ``0``)."""
    return bin(value)[2:] if value else "0"


def _as_int(value: _Value) -> int:
    r"""Coerce a Lamfunc value to an integer (the bit-builtins' operand)."""
    if isinstance(value, int):
        return value
    raise HaltError(f"expected a number, got {value!r}")


class _Thunk:
    r"""An unevaluated ``i`` branch: a token span, forced only when."""

    __slots__ = ("end", "start", "tokens")

    def __init__(self, tokens: list[str], start: int, end: int) -> None:
        self.tokens = tokens
        self.start = start
        self.end = end


# : Everything that can sit in.
# : result.
# : a bare token that names.
# : it as a variable name, and.
# : ``_Thunk`` until it is.
# :.
# : Spelling it out is what.
# : ``bool`` being a subclass.
# : parsing and by the.
# : need no defensive ``bool``.
_Value = int | str | _Func | _Thunk


@dataclass(frozen=True)
class _Frame:
    r"""One ``_eval``-equivalent expression evaluation in progress."""

    tokens: list[str]
    pos: int
    start: int = 0
    phase: _Phase = "scan"
    fn: _Func | None = None
    args: tuple[_Value, ...] = ()
    result: _Value = 0
    saved: tuple[tuple[str, _Value | None], ...] = ()
    awaiting: bool = False
    awaiting_result: bool = False


def _arity(name: str, defs: dict[str, _Def]) -> int:
    r"""Return ``name``'s arity (a builtin's fixed arity, or a def's)."""
    if name in _BUILTINS:
        return _BUILTINS[name].arity
    if name in defs:
        return len(defs[name].params)
    raise HaltError(f"calling undefined function {name!r}")


def _lookup(name: str, defs: dict[str, _Def]) -> _Func:
    if name in _BUILTINS:
        return _BUILTINS[name]
    if name in defs:
        d = defs[name]
        return _Func(name, len(d.params), d.body, d.params)
    # Both call sites test.
    # here is a bug in that guard.
    # undefined -- which is.
    raise AssertionError(f"_lookup of unknown name {name!r}")


def _scan(tokens: list[str], i: int, defs: dict[str, _Def], vars_: _Vars) -> int:
    r"""Return how many tokens the expression at ``i`` occupies."""
    tok = tokens[i]
    if (
        tok.startswith(".")
        or _is_int(tok)
        or tok in vars_
        or (tok not in _BUILTINS and tok not in defs)
    ):
        return i + 1
    fn = _lookup(tok, defs)
    end = i + 1
    for _ in range(fn.arity):
        if end >= len(tokens):
            return end
        end = _scan(tokens, end, defs, vars_)
    return end


def _def_fields(
    name: str, defs: dict[str, _Def]
) -> tuple[list[str] | None, list[str] | None]:
    d = defs.get(name)
    return (d.body if d else None, d.params if d else None)


def _partial(fn: _Func, given: list[_Value]) -> _Func:
    r"""Build a lambda that, when called with the remaining args, calls fn."""
    return _Func(
        fn.name + "..",
        fn.arity - len(given),
        fn.body,
        fn.params,
        given=given,
        orig=fn,
    )


def _apply_builtin(
    fn: _Func, args: list[_Value], vars_: _Vars
) -> tuple[_Value, _Vars, str | None]:
    r"""Apply a non-``i``, non-user builtin to its evaluated arguments."""
    if fn.name == "p":
        return args[0], vars_, _print_value(args[0])
    if fn.name == "eq":
        return (1 if args[0] == args[1] else 0), vars_, None
    if fn.name == "cb":
        x, y = _as_int(args[0]), _as_int(args[1])
        # No Lamfunc value is ever.
        # digits to parse, and the.
        # and a binary concatenation,.
        # non-negatives.
        # program asking for something.
        if x < 0 or y < 0:
            raise AssertionError("cb of a negative number is undefined")
        return (int(bin(x)[2:] + bin(y)[2:], 2) if (x or y) else 0), vars_, None
    if fn.name == "lb":
        return (_as_int(args[0]) & 1), vars_, None
    if fn.name == "fb":
        return (_as_int(args[0]) >> 1), vars_, None
    if fn.name == "vs":
        return args[1], {**vars_, str(args[0]): args[1]}, None
    if fn.name == "vg":
        return vars_.get(str(args[0]), 0), vars_, None
    # Callers only reach this with.
    # bug in the dispatch above.
    raise AssertionError(f"unexpected non-user builtin {fn.name!r}")


# : The variable store.
# : no closures over live.
# : parameter shadowing is.
type _Vars = Mapping[str, _Value]

# : What a step wants done to.
# : the frames to push after.
# : shell, because Lamfunc.
# : unbounded by design -- the.
# : 4002 frames -- so.
# : call depth.
type _StackFx = tuple[int, tuple[_Frame, ...]]

# : What a whole step produced:.
# : top-level cursor that.
type _Outcome = tuple[_StackFx, _Vars, int, str | None]


def _restored(vars_: _Vars, saved: tuple[tuple[str, _Value | None], ...]) -> _Vars:
    r"""Undo a call's parameter bindings, in the order they were saved."""
    out = dict(vars_)
    for name, _ in saved:
        out.pop(name, None)
    for name, value in saved:
        if value is not None:
            out[name] = value
    return out


def _deliver(
    view: Sequence[_Frame],
    value: _Value,
    consumed: int,
    vars_: _Vars,
    ind: int,
    main: list[str],
) -> _Outcome:
    r"""Pop the finished top frame and hand its value to whoever awaits it."""
    pops = 1
    while True:
        # Indexed rather than sliced:.
        # Lamfunc's depth is unbounded,.
        # deep unwind quadratic in the.
        # chain, the slice cost 0.42s.
        depth = len(view) - pops
        if depth <= 0:
            # Top level: the cursor.
            # absorbs the remaining.
            # arguments -- a fresh "gather".
            # function, whose own remaining.
            # ``given`` prefix _dispatch.
            # This can chain: a.
            # arguments the same way until.
            # tokens run out.
            ind += consumed
            pushes: tuple[_Frame, ...] = ()
            if isinstance(value, _Func) and value.arity > 0 and ind < len(main):
                pushes = (_Frame(main, ind, start=ind, phase="gather", fn=value),)
            return (pops, pushes), vars_, ind, None
        caller = view[depth - 1]
        if caller.awaiting_result:
            # the child's value IS the.
            # branch, or a call's body.
            # already reflects its full.
            # the child's consumed (a.
            consumed = caller.pos - caller.start
            pops += 1
            continue
        if caller.phase == "gather":
            grown = replace(
                caller,
                awaiting=False,
                args=(*caller.args, value),
                pos=caller.pos + consumed,
            )
        elif caller.phase == "body":
            grown = replace(
                caller, awaiting=False, result=value, pos=caller.pos + consumed
            )
        else:
            # "scan" never awaits a pushed.
            # phase bookkeeping rather than.
            raise AssertionError(f"unexpected caller phase {caller.phase!r}")
        # ``grown`` replaces the.
        # the shell removes ``pops``.
        # what it is given, and the.
        return (pops + 1, (grown,)), vars_, ind, None


def _resolve(
    frame: _Frame,
    view: Sequence[_Frame],
    vars_: _Vars,
    ind: int,
    defs: dict[str, _Def],
    main: list[str],
) -> _Outcome:
    r"""Advance a ``"scan"`` frame: classify the token at ``frame.pos``."""
    tokens, i = frame.tokens, frame.pos
    tok = tokens[i]
    if tok.startswith("."):
        name = tok[1:]
        if name in vars_:
            return _deliver(view, vars_[name], 1, vars_, ind, main)
        value = _Func(name, _arity(name, defs), *_def_fields(name, defs))
        return _deliver(view, value, 1, vars_, ind, main)
    if _is_int(tok):
        return _deliver(view, _parse_int(tok), 1, vars_, ind, main)
    if tok in vars_ and isinstance(bound := vars_[tok], _Func):
        fn = bound
    elif tok in _BUILTINS or tok in defs:
        fn = _lookup(tok, defs)
    elif tok in vars_:
        return _deliver(view, vars_[tok], 1, vars_, ind, main)
    elif i + 1 < len(tokens):
        raise HaltError(f"calling undefined function {tok!r}")
    else:
        return _deliver(view, tok, 1, vars_, ind, main)
    grown = replace(frame, fn=fn, pos=i + 1, phase="gather")
    return (1, (grown,)), vars_, ind, None


def _gather(
    frame: _Frame,
    view: Sequence[_Frame],
    vars_: _Vars,
    ind: int,
    defs: dict[str, _Def],
    main: list[str],
) -> _Outcome:
    r"""Advance a ``"gather"`` frame by one argument, or dispatch the call."""
    fn = cast(_Func, frame.fn)
    if len(frame.args) == fn.arity:
        return _dispatch(frame, view, fn, vars_, ind, main)
    tokens, pos = frame.tokens, frame.pos
    if pos >= len(tokens):
        # partial application: not.
        value = _partial(fn, list(frame.args))
        return _deliver(view, value, pos - frame.start, vars_, ind, main)
    # vs/vg take their variable.
    if fn.name in ("vs", "vg") and not frame.args:
        grown = replace(frame, args=(*frame.args, tokens[pos]), pos=pos + 1)
        return (1, (grown,)), vars_, ind, None
    # i is lazy in its second and.
    # is evaluated, via a pushed.
    if fn.name == "i" and len(frame.args) >= 1:
        end = _scan(tokens, pos, defs, vars_)
        grown = replace(frame, args=(*frame.args, _Thunk(tokens, pos, end)), pos=end)
        return (1, (grown,)), vars_, ind, None
    waiting = replace(frame, awaiting=True)
    child = _Frame(tokens, pos, start=pos)
    return (1, (waiting, child)), vars_, ind, None


def _dispatch(
    frame: _Frame,
    view: Sequence[_Frame],
    fn: _Func,
    vars_: _Vars,
    ind: int,
    main: list[str],
) -> _Outcome:
    r"""Apply a fully-gathered call, or push a body frame to run it."""
    if fn.orig is not None:
        target = fn.orig
        args = [*fn.given, *frame.args]
    else:
        target = fn
        args = list(frame.args)
    if target.name == "i":
        cond, branch_t, branch_f = args[0], args[1], args[2]
        chosen = branch_t if cond != 0 else branch_f
        if isinstance(chosen, _Thunk):
            waiting = replace(frame, awaiting=True, awaiting_result=True)
            child = _Frame(chosen.tokens, chosen.start, start=chosen.start)
            return (1, (waiting, child)), vars_, ind, None
        return _deliver(view, chosen, frame.pos - frame.start, vars_, ind, main)
    if target.name in _BUILTINS:
        value, vars_, output = _apply_builtin(target, args, vars_)
        (pops, pushes), vars_, ind, _ = _deliver(
            view, value, frame.pos - frame.start, vars_, ind, main
        )
        return (pops, pushes), vars_, ind, output
    # a user-defined function: bind.
    # push a body frame to run it.
    params = target.params or []
    saved = tuple((p, vars_.get(p)) for p in params)
    vars_ = {**vars_, **dict(zip(params, args, strict=True))}
    body = _Frame(target.body or [], 0, phase="body", saved=saved)
    waiting = replace(frame, awaiting=True, awaiting_result=True)
    return (1, (waiting, body)), vars_, ind, None


def _step_body(
    frame: _Frame, view: Sequence[_Frame], vars_: _Vars, ind: int, main: list[str]
) -> _Outcome:
    r"""Advance a ``"body"`` frame: run its next expression, or finish."""
    if frame.pos >= len(frame.tokens):
        vars_ = _restored(vars_, frame.saved)
        return _deliver(view, frame.result, frame.pos - frame.start, vars_, ind, main)
    waiting = replace(frame, awaiting=True)
    child = _Frame(frame.tokens, frame.pos, start=frame.pos)
    return (1, (waiting, child)), vars_, ind, None


def _advance(
    view: Sequence[_Frame],
    vars_: _Vars,
    ind: int,
    defs: dict[str, _Def],
    main: list[str],
) -> _Outcome:
    r"""Advance the topmost pending frame by one unit of work."""
    frame = view[-1]
    if frame.phase == "scan":
        return _resolve(frame, view, vars_, ind, defs, main)
    if frame.phase == "gather":
        return _gather(frame, view, vars_, ind, defs, main)
    return _step_body(frame, view, vars_, ind, main)


@dataclass
class _State:
    r"""Every changing value in a Lamfunc run."""

    vars: _Vars
    ind: int
    frames: list[_Frame]


class _Machine:
    r"""One Lamfunc run: the definitions, variables, cursor, and call stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.defs, self.main = _parse_program(code)
        self.state = _State({}, 0, [])
        if self.main:
            self.frames.append(_Frame(self.main, 0, start=0))

    @property
    def variables(self) -> _Vars:
        r"""The variable mapping, retained for the transition helpers."""
        return self.state.vars

    @variables.setter
    def variables(self, vars_: _Vars) -> None:
        self.state.vars = vars_

    @property
    def ind(self) -> int:
        r"""The top-level call cursor."""
        return self.state.ind

    @ind.setter
    def ind(self, ind: int) -> None:
        self.state.ind = ind

    @property
    def frames(self) -> list[_Frame]:
        r"""The effect-owned frame stack."""
        return self.state.frames

    @property
    def halted(self) -> bool:
        r"""Whether the top-level cursor has run off the call sequence."""
        return self.ind >= len(self.main) and not self.frames

    # The VM's language-shaped.
    # cursor.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return [v for v in self.variables.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        r"""No stack in this language."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            tuple(sorted((k, repr(v)) for k, v in self.variables.items())),
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

    def frame_entry_key(self, frame: _Frame) -> Hashable:
        r"""Return a call body's entry state for the ancestor check."""
        if frame.phase != "body":
            return ("continuation", object())
        return (
            "body",
            id(frame.tokens),
            tuple(
                sorted((name, repr(value)) for name, value in self.variables.items())
            ),
            self.io.position(),
        )

    def step(self) -> None:
        r"""Advance the topmost pending frame by one unit of work."""
        if self.halted:
            return
        if not self.frames:
            # the previous top-level call.
            # application); start.
            self.frames.append(_Frame(self.main, self.ind, start=self.ind))
            return

        (pops, pushes), variables, ind, output = _advance(
            self.frames, self.variables, self.ind, self.defs, self.main
        )
        # Every transition finishes at.
        del self.frames[len(self.frames) - pops :]
        self.frames.extend(pushes)
        # Held as returned, not copied:.
        # fresh mapping for any step.
        # again would be a per-step.
        self.variables = variables
        self.ind = ind
        if output is not None:
            self.io.print_str(output)


def _print_value(value: _Value) -> str:
    if isinstance(value, int):
        return _to_binary(value)
    if isinstance(value, _Func):
        return value.name
    return str(value)


def _parse_program(code: str) -> tuple[dict[str, _Def], list[str]]:
    r"""Split the program into definitions and the top-level call sequence."""
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
    r"""Run a Lamfunc program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
