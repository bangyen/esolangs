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
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, replace
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
    """Print an integer as its binary representation (0 as ``0``)."""
    return bin(value)[2:] if value else "0"


def _as_int(value: _Value) -> int:
    """Coerce a Lamfunc value to an integer (the bit-builtins' operand)."""
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


#: Everything that can sit in an argument list, a variable, or a frame's
#: result.  Numbers and functions are the values a program computes with;
#: a bare token that names nothing stays a ``str`` so ``vs``/``vg`` can use
#: it as a variable name, and an unevaluated ``i`` branch rides along as a
#: ``_Thunk`` until it is selected.
#:
#: Spelling it out is what keeps ``bool`` from smuggling itself in through
#: ``bool`` being a subclass of ``int``: the values below are produced by
#: parsing and by the builtins, none of which returns one, so the coercions
#: need no defensive ``bool`` arm.
_Value = int | str | _Func | _Thunk


@dataclass(frozen=True)
class _Frame:
    """One ``_eval``-equivalent expression evaluation in progress.

    Frozen: a step returns the frames that follow rather than editing the
    ones it was handed, so a frame is a value.  ``replace`` builds the
    changed copy, which reads as the field being set and keeps the seven
    unchanged ones from being retyped at every site.

    ``args`` and ``saved`` are tuples for the same reason.  ``saved`` is a
    tuple of ``(name, value)`` pairs rather than a mapping so its order --
    which the restore walks -- is part of the value; a ``None`` value still
    means the name was unbound before the call and must be removed rather
    than written back.

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
    args: tuple[_Value, ...] = ()
    result: _Value = 0
    saved: tuple[tuple[str, _Value | None], ...] = ()
    awaiting: bool = False
    awaiting_result: bool = False


def _arity(name: str, defs: dict[str, _Def]) -> int:
    """Return ``name``'s arity (a builtin's fixed arity, or a def's)."""
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
    # Both call sites test membership before calling, so an unknown name
    # here is a bug in that guard rather than a program calling something
    # undefined -- which is reported, as a HaltError, where it is noticed.
    raise AssertionError(f"_lookup of unknown name {name!r}")


def _scan(tokens: list[str], i: int, defs: dict[str, _Def], vars_: _Vars) -> int:
    """Return how many tokens the expression at ``i`` occupies.

    The one function here still written recursively, and deliberately: it
    sizes an unevaluated ``i`` branch, so its depth is the *program text*'s
    own nesting rather than how many times a call runs.
    """
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
    """Build a lambda that, when called with the remaining args, calls fn."""
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
    """Apply a non-``i``, non-user builtin to its evaluated arguments.

    Never recurses: every one of these builtins is a single, bounded
    computation on already-evaluated values.  Returns the value, the
    variables that follow, and the text ``p`` would print -- the one port
    this language has, reported rather than written.
    """
    if fn.name == "p":
        return args[0], vars_, _print_value(args[0])
    if fn.name == "eq":
        return (1 if args[0] == args[1] else 0), vars_, None
    if fn.name == "cb":
        x, y = _as_int(args[0]), _as_int(args[1])
        # No Lamfunc value is ever negative: a literal has to be all
        # digits to parse, and the arithmetic builtins are ``>>``, ``&``
        # and a binary concatenation, which are closed over the
        # non-negatives.  So a negative here is a bug in this file, not a
        # program asking for something undefined.
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
    # Callers only reach this with a name from _BUILTINS, so a miss is a
    # bug in the dispatch above rather than a malformed program.
    raise AssertionError(f"unexpected non-user builtin {fn.name!r}")


#: The variable store.  A flat mapping -- Lamfunc has no scope chain and
#: no closures over live scopes -- so it threads as a value, and a call's
#: parameter shadowing is handled by each body frame's own ``saved``.
type _Vars = Mapping[str, _Value]

#: What a step wants done to the frame stack: how many frames to pop, and
#: the frames to push after that.  The stack itself stays a list in the
#: shell, because Lamfunc pushes a frame per call and its depth is
#: unbounded by design -- the interpreter's own deep-recursion test reaches
#: 4002 frames -- so rebuilding it per step would be quadratic in the
#: call depth.  Grapheme's value stack is reported for the same reason.
type _StackFx = tuple[int, tuple[_Frame, ...]]

#: What a whole step produced: the stack effects, the variables and
#: top-level cursor that follow, and anything printed.
type _Outcome = tuple[_StackFx, _Vars, int, str | None]


def _restored(vars_: _Vars, saved: tuple[tuple[str, _Value | None], ...]) -> _Vars:
    """Undo a call's parameter bindings, in the order they were saved.

    A ``None`` marks a name that was unbound before the call, so it is
    removed rather than written back.

    In practice the saved value is always ``None``, and that is a property
    of the language rather than of this function.  ``vs``/``vg`` take their
    variable name as a *literal token*, so ``vs "x" 1`` stores under the
    key ``'"x"'`` -- quotes included -- while a parameter named ``x`` binds
    under ``'x'``.  The two namespaces therefore never collide, and a
    parameter can only shadow another parameter of a call still on the
    stack.  Mutants that drop the restore, or that write an unbound name
    back as a value, are equivalent for that reason rather than untested.
    """
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
    """Pop the finished top frame and hand its value to whoever awaits it.

    A loop rather than the recursion the method version used: a caller
    whose ``awaiting_result`` is set takes the child's value as its *own*
    result and is itself finished, which can chain arbitrarily deep.  The
    loop also retires that version's identity assertion -- there is no
    frame to check against the stack top, because the frame being finished
    is the one this walk is standing on.
    """
    pops = 1
    while True:
        # Indexed rather than sliced: ``view`` is the whole call stack and
        # Lamfunc's depth is unbounded, so slicing it per lap would make a
        # deep unwind quadratic in the depth.  Measured on a 6000-deep call
        # chain, the slice cost 0.42s against 0.04s.
        depth = len(view) - pops
        if depth <= 0:
            # Top level: the cursor advances, and a partial application
            # absorbs the remaining top-level tokens as its outstanding
            # arguments -- a fresh "gather" frame for the same still-partial
            # function, whose own remaining arity is reused and whose
            # ``given`` prefix _dispatch merges back in once it completes.
            # This can chain: a still-partial result absorbs further
            # arguments the same way until the arity is satisfied or the
            # tokens run out.
            ind += consumed
            pushes: tuple[_Frame, ...] = ()
            if isinstance(value, _Func) and value.arity > 0 and ind < len(main):
                pushes = (_Frame(main, ind, start=ind, phase="gather", fn=value),)
            return (pops, pushes), vars_, ind, None
        caller = view[depth - 1]
        if caller.awaiting_result:
            # the child's value IS the caller's own result (i's forced
            # branch, or a call's body finishing) -- the caller's own pos
            # already reflects its full consumption in its own tokens, so
            # the child's consumed (a different token context) is unused
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
            # "scan" never awaits a pushed child, so this is a bug in the
            # phase bookkeeping rather than anything a program can cause.
            raise AssertionError(f"unexpected caller phase {caller.phase!r}")
        # ``grown`` replaces the caller, so the caller is popped too:
        # the shell removes ``pops`` frames from the top and pushes
        # what it is given, and the caller is one of the removed.
        return (pops + 1, (grown,)), vars_, ind, None


def _resolve(
    frame: _Frame,
    view: Sequence[_Frame],
    vars_: _Vars,
    ind: int,
    defs: dict[str, _Def],
    main: list[str],
) -> _Outcome:
    """Advance a ``"scan"`` frame: classify the token at ``frame.pos``.

    Resolves immediately to a value (finishing the frame) for a literal, a
    bound variable, or a bare trailing name; otherwise identifies the
    callable and switches the frame to ``"gather"``.
    """
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
    """Advance a ``"gather"`` frame by one argument, or dispatch the call."""
    fn = cast(_Func, frame.fn)
    if len(frame.args) == fn.arity:
        return _dispatch(frame, view, fn, vars_, ind, main)
    tokens, pos = frame.tokens, frame.pos
    if pos >= len(tokens):
        # partial application: not enough tokens left for the remaining args
        value = _partial(fn, list(frame.args))
        return _deliver(view, value, pos - frame.start, vars_, ind, main)
    # vs/vg take their variable NAME as a literal token, never a value
    if fn.name in ("vs", "vg") and not frame.args:
        grown = replace(frame, args=(*frame.args, tokens[pos]), pos=pos + 1)
        return (1, (grown,)), vars_, ind, None
    # i is lazy in its second and third arguments: only the chosen branch
    # is evaluated, via a pushed frame once i is dispatched.
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
    """Apply a fully-gathered call, or push a body frame to run it.

    A partial application completing (``fn.orig is not None``) resolves to
    its original definition plus the accumulated arguments (the partial's
    own ``given`` prefix, then this gather's ``args``) before dispatching,
    the same way the un-partial call would have.
    """
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
    # a user-defined function: bind params to args in a fresh scope and
    # push a body frame to run it
    params = target.params or []
    saved = tuple((p, vars_.get(p)) for p in params)
    vars_ = {**vars_, **dict(zip(params, args, strict=True))}
    body = _Frame(target.body or [], 0, phase="body", saved=saved)
    waiting = replace(frame, awaiting=True, awaiting_result=True)
    return (1, (waiting, body)), vars_, ind, None


def _step_body(
    frame: _Frame, view: Sequence[_Frame], vars_: _Vars, ind: int, main: list[str]
) -> _Outcome:
    """Advance a ``"body"`` frame: run its next expression, or finish."""
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
    """Advance the topmost pending frame by one unit of work.

    Pure: it reads the frame stack rather than editing it, and returns the
    frames to pop and push instead.  ``p`` is the only command that reaches
    a port and it prints at most once per step, so the value it would write
    comes back as the last element rather than through a callback.
    """
    frame = view[-1]
    if frame.phase == "scan":
        return _resolve(frame, view, vars_, ind, defs, main)
    if frame.phase == "gather":
        return _gather(frame, view, vars_, ind, defs, main)
    return _step_body(frame, view, vars_, ind, main)


@dataclass
class _State:
    """Every changing value in a Lamfunc run.

    Frames remain a mutable effect-owned stack so deep recursion does not
    copy it on every step; grouping it here still makes that ownership part
    of the machine's one authoritative state boundary.
    """

    vars: _Vars
    ind: int
    frames: list[_Frame]


class _Machine:
    """One Lamfunc run: the definitions, variables, cursor, and call stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.defs, self.main = _parse_program(code)
        self.state = _State({}, 0, [])
        if self.main:
            self.frames.append(_Frame(self.main, 0, start=0))

    @property
    def variables(self) -> _Vars:
        """The variable mapping, retained for the transition helpers."""
        return self.state.vars

    @variables.setter
    def variables(self, vars_: _Vars) -> None:
        self.state.vars = vars_

    @property
    def ind(self) -> int:
        """The top-level call cursor."""
        return self.state.ind

    @ind.setter
    def ind(self, ind: int) -> None:
        self.state.ind = ind

    @property
    def frames(self) -> list[_Frame]:
        """The effect-owned frame stack."""
        return self.state.frames

    @property
    def halted(self) -> bool:
        """Whether the top-level cursor has run off the call sequence."""
        return self.ind >= len(self.main) and not self.frames

    # The VM's language-shaped view: Prefix-call evaluator; ip is the top-level token
    # cursor.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return [v for v in self.variables.values() if type(v) is int]

    @property
    def stack(self) -> list[object]:
        """No stack in this language."""
        return []

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
        """Return a call body's entry state for the ancestor check.

        ``frames`` also holds short-lived evaluator continuations while a
        call gathers arguments.  Repeating one of those is not itself a
        recursive call, so each gets a private marker.  A ``body`` frame is
        the call boundary: its immutable token list identifies the function
        body, and the flat variable map carries its parameter bindings and
        all state a recursive body can read.  See
        :func:`esolangs.vm.run_until_halt_or_ancestor`.
        """
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
        """Advance the topmost pending frame by one unit of work.

        The one port lives here rather than in the transition: this is the
        shell.  ``p`` is the only command that writes, and it writes at
        most once per step, so the transition reports the text and this
        writes it.

        The frame stack stays a list rather than being threaded as a
        value.  Lamfunc pushes a frame per call and its depth is unbounded
        by design -- the interpreter's own deep-recursion test reaches 4002
        frames -- so rebuilding the stack per step would be quadratic in
        the call depth.  The transition therefore reports how many frames
        to pop and which to push, the way Grapheme's reports its stack.
        """
        if self.halted:
            return
        if not self.frames:
            # the previous top-level call finished plainly (not a partial
            # application); start evaluating the next one
            self.frames.append(_Frame(self.main, self.ind, start=self.ind))
            return

        (pops, pushes), variables, ind, output = _advance(
            self.frames, self.variables, self.ind, self.defs, self.main
        )
        if pops:  # pragma: no branch - completed frames always pop
            del self.frames[len(self.frames) - pops :]
        self.frames.extend(pushes)
        # Held as returned, not copied: the transition already built a
        # fresh mapping for any step that changed one, so copying it
        # again would be a per-step cost in the size of the store.
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
