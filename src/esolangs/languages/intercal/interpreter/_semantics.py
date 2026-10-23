"""INTERCAL statement semantics over the immutable run state."""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.intercal.interpreter._expr import (
    _DIGITS,
    _NEXT_LIMIT,
    _NO_DATA,
    _ONESPOT_MAX,
    _REVERSED,
    _TWOSPOT_MAX,
    _Array,
    _element,
    _evaluate,
    _roman,
)
from esolangs.languages.intercal.interpreter._parse import (
    _fail,
    _Key,
    _Node,
    _SelfAbstain,
    _Statement,
)
from esolangs.languages.intercal.interpreter._pmap import _PMap
from esolangs.runtime._fault import _Fault


class _NeedDraw(Exception):  # noqa: N818 - an internal resumption signal
    """Signals that a step needs one more random draw than supplied.

    ``effects`` is the output already computed before the draw, so the shell
    can flush it before drawing.  The shell draws one value and retries; the
    transition is deterministic, so the retry reaches the same point with the
    new value.
    """

    def __init__(self, effects: tuple[str, ...] = ()) -> None:
        super().__init__()
        self.effects = effects


class _NeedInput(Exception):  # noqa: N818 - an internal resumption signal
    """Signals that a step needs one more input value than supplied.

    ``kind`` is ``"char"`` for a Turing Tape character (whose EOF value the
    shell supplies as ``None``) or ``"line"`` for a numeric line.  ``effects``
    is the output already computed before the read.
    """

    def __init__(self, kind: str, effects: tuple[str, ...] = ()) -> None:
        super().__init__(kind)
        self.kind = kind
        self.effects = effects


class _Program(NamedTuple):
    """The load-time facts about a program, fixed for the whole run."""

    statements: tuple[_Statement, ...]
    labels: Mapping[int, int]
    by_kind: Mapping[str, tuple[int, ...]]
    come_label: Mapping[int, tuple[int, ...]]
    come_kind: Mapping[str, tuple[int, ...]]
    come_computed: tuple[int, ...]
    sucks: tuple[bool, ...]


@dataclass(frozen=True)
class _State:
    """Every changing value in an INTERCAL run.

    A value, not a record: a write returns a store sharing its untouched
    buckets and :func:`_advance` returns a new state rather than editing this one.
    """

    ind: int
    scalars: _PMap[_Key, int]
    arrays: _PMap[_Key, _Array]
    ignored: frozenset[_Key]
    stashes: _PMap[_Key, tuple[int | _Array, ...]]
    abstained: tuple[int, ...]
    nexts: tuple[tuple[int, int], ...]
    last_in: int
    last_out: int


def _link(statements: tuple[_Statement, ...]) -> _Program:
    """Check every label and constant target, and index the COME FROMs."""
    labels: dict[int, int] = {}
    for i, statement in enumerate(statements):
        if statement.label is not None:
            if statement.label in labels:
                raise _fail("E182", f"duplicate INTERCAL label: {statement.label}")
            labels[statement.label] = i
    by_kind: dict[str, list[int]] = {}
    come_label: dict[int, list[int]] = {}
    come_kind: dict[str, list[int]] = {}
    come_computed: list[int] = []
    codes = {"next": "E129", "abstain": "E139", "reinstate": "E139"}
    for i, statement in enumerate(statements):
        command, kind = statement.command, statement.kind
        if kind is not None:
            by_kind.setdefault(kind, []).append(i)
        target = command.arg1
        if kind in codes and isinstance(target, int) and target not in labels:
            raise _fail(codes[kind], f"unknown INTERCAL label: {target}")
        if kind not in ("come from", "next from"):
            continue
        if isinstance(target, int):
            if target not in labels:
                raise _fail("E444", f"unknown INTERCAL label: {target}")
            come_label.setdefault(target, []).append(i)
            if len(come_label[target]) > 1:
                raise _fail("E555", f"two COME FROMs aim at label {target}")
        elif isinstance(target, frozenset):
            for name in target:
                come_kind.setdefault(str(name), []).append(i)
        else:
            come_computed.append(i)
    sucks = tuple(
        (statement.label is not None and bool(come_computed))
        or statement.label in come_label
        or statement.kind in come_kind
        for statement in statements
    )
    last = len(statements) - 1
    for i in by_kind.get("try again", ()):
        if i != last:
            raise _fail("E993", "TRY AGAIN must be the last statement")
    return _Program(
        statements,
        labels,
        {kind: tuple(indexes) for kind, indexes in by_kind.items()},
        {label: tuple(indexes) for label, indexes in come_label.items()},
        {kind: tuple(indexes) for kind, indexes in come_kind.items()},
        tuple(come_computed),
        sucks,
    )


def _set_abstained(state: _State, i: int, value: int) -> _State:
    """Return ``state`` with statement ``i``'s abstain counter replaced."""
    abstained = state.abstained
    return replace(state, abstained=(*abstained[:i], value, *abstained[i + 1 :]))


def _value(state: _State, node: _Node) -> int:
    return _evaluate(node, state.scalars, state.arrays)[0]


def _targets(target: int | frozenset[str], program: _Program) -> tuple[int, ...]:
    if isinstance(target, int):
        return (program.labels[target],)
    return tuple(i for kind in target for i in program.by_kind.get(kind, ()))


def _push(state: _State, resume: int, origin: int) -> _State:
    if len(state.nexts) >= _NEXT_LIMIT:
        raise _fail("E123", "INTERCAL NEXT stack overflow")
    return replace(state, nexts=(*state.nexts, (resume, origin)))


def _runs(chance: int, draws: Sequence[int], pos: int) -> tuple[bool, int]:
    """Roll a ``%chance`` qualifier from the explicit draws.

    ``0`` never runs and ``100`` always does; anything between consumes the
    next draw and runs when it is below ``chance``.
    """
    if chance >= 100:
        return True, pos
    if chance <= 0:
        return False, pos
    if pos >= len(draws):
        raise _NeedDraw
    return draws[pos] < chance, pos + 1


def _reach(state: _State, i: int, program: _Program) -> tuple[_State, bool]:
    """Apply ONCE/AGAIN at statement ``i``; report if it was reinstated."""
    before = state.abstained[i]
    after = program.statements[i].after
    if after == _SelfAbstain.ABSTAIN:
        state = _set_abstained(state, i, before or 1)
    elif after == _SelfAbstain.REINSTATE:
        state = _set_abstained(state, i, 0)
    return state, not before


def _store(state: _State, target: _Node, value: int) -> _State:
    """Return ``state`` with ``value`` stored at ``target``.

    A bad subscript (E241) is raised before an overflow (E275), and both
    even when the target is ignored.
    """
    if target.tag != "sub":
        key = (str(target.tag), target.arg1)
        if key[0] == "." and value > _ONESPOT_MAX:
            raise _fail("E275", "INTERCAL onespot assignment overflow")
        if key in state.ignored:
            return state
        return replace(state, scalars=state.scalars.set(key, value))
    key = (str(target.arg1), target.arg2)
    data, index = _element(target, state.scalars, state.arrays)
    if key[0] == "," and value > _ONESPOT_MAX:
        raise _fail("E275", "INTERCAL onespot assignment overflow")
    if key in state.ignored:
        return state
    dimensions = state.arrays.get(key, ((), data))[0]
    element = (dimensions, data.set(index, value))
    return replace(state, arrays=state.arrays.set(key, element))


def _array(state: _State, key: _Key) -> _Array:
    array: _Array = state.arrays.get(key, ((), _NO_DATA))
    if len(array[0]) != 1:
        raise _fail(
            "E241",
            "INTERCAL array I/O needs a one-dimensional array",
            hint="dimension the array with a single size first",
        )
    return array


def _read_out(state: _State, item: _Node) -> tuple[_State, str]:
    """Return the state and the text one READ OUT item writes."""
    if item.tag != "array":
        return state, _roman(_value(state, item)) + "\n"
    (size,), data = _array(state, (str(item.arg1), int(item.arg2)))
    characters = []
    last_out = state.last_out
    for index in range(size):
        last_out = (last_out - data.get(index, 0)) % 256
        characters.append(chr(_REVERSED[last_out]))
    return replace(state, last_out=last_out), "".join(characters)


def _write_in(
    state: _State, item: _Node, inputs: Sequence[int | str | None], pos: int
) -> tuple[_State, int]:
    """Return the state and the input cursor after one WRITE IN item.

    A Turing Tape array consumes one explicit character per element (``None``
    for the EOF value 256); a numeric target consumes one explicit line.
    """
    if item.tag == "array":
        key = (str(item.arg1), int(item.arg2))
        (size,), data = _array(state, key)
        last_in = state.last_in
        written: dict[int, int] = {}
        for index in range(size):
            if pos >= len(inputs):
                raise _NeedInput("char")
            character = inputs[pos]
            pos += 1
            if character is None:
                value, last_in = 256, -1
            else:
                value = (int(character) - last_in) % 256
                last_in = int(character)
            if key not in state.ignored:
                written[index] = value
        state = replace(
            state,
            arrays=state.arrays.set(key, ((size,), data.update(written))),
            last_in=last_in,
        )
        return state, pos
    if pos >= len(inputs):
        raise _NeedInput("line")
    text = inputs[pos]
    pos += 1
    words = str(text).upper().split()
    if not words or any(word not in _DIGITS for word in words):
        raise _fail(
            "E579" if words else "E562",
            "invalid INTERCAL numeric input",
            hint="spell each decimal digit as a word, for example ONE TWO",
        )
    value = 0
    for word in words:
        value = value * 10 + _DIGITS[word]
        if value > _TWOSPOT_MAX:
            raise _fail("E533", "INTERCAL twospot input overflow")
    sigil = item.arg1 if item.tag == "sub" else item.tag
    if sigil in ".," and value > _ONESPOT_MAX:
        raise _fail("E275", "INTERCAL onespot input overflow")
    return _store(state, item, value), pos


def _variable(state: _State, action: str, key: _Key) -> _State:
    """Apply one STASH/RETRIEVE/IGNORE/REMEMBER item."""
    if action == "ignore":
        return replace(state, ignored=state.ignored | {key})
    if action == "remember":
        return replace(state, ignored=state.ignored - {key})
    if action == "stash":
        value: int | _Array
        if key[0] in ",;":
            value = state.arrays.get(key, ((), _NO_DATA))
        else:
            value = state.scalars.get(key, 0)
        stashes = state.stashes.set(key, (*state.stashes.get(key, ()), value))
        return replace(state, stashes=stashes)
    stash = state.stashes.get(key)
    if not stash:
        raise _fail("E436", f"INTERCAL RETRIEVE of an unstashed {key[0]}")
    value = stash[-1]
    state = replace(state, stashes=state.stashes.set(key, stash[:-1]))
    if key in state.ignored:
        return state
    if isinstance(value, int):
        return replace(state, scalars=state.scalars.set(key, value))
    return replace(state, arrays=state.arrays.set(key, value))


def _resume(
    state: _State, count: int, program: _Program, draws: Sequence[int], pos: int
) -> tuple[_State, int]:
    """Resume the ``count``th-from-top NEXT entry."""
    if count == 0:
        raise _fail(
            "E621",
            "invalid INTERCAL stack count: RESUME #0",
            hint="use a positive stack count",
        )
    if count > len(state.nexts):
        raise _fail(
            "E632",
            "INTERCAL NEXT stack underflow",
            hint="leave enough stack entries for the operation to consume",
        )
    resume, origin = state.nexts[-count]
    nexts = state.nexts[:-count]
    if origin < 0:
        return replace(state, nexts=nexts, ind=resume), pos
    # The NEXT finishes only now, so a COME FROM aimed at it fires.
    state = replace(state, nexts=nexts)
    return _leave(state, origin, program, draws, pos)


def _leave(
    state: _State, i: int, program: _Program, draws: Sequence[int], pos: int
) -> tuple[_State, int]:
    """Continue past statement ``i``, unless a COME FROM takes control."""
    state = replace(state, ind=i + 1)
    if not program.sucks[i]:
        return state, pos
    statement = program.statements[i]
    candidates = [
        *program.come_label.get(statement.label or 0, ()),
        *program.come_kind.get(statement.kind or "", ()),
    ]
    if statement.label is not None:
        candidates.extend(
            c
            for c in program.come_computed
            if not state.abstained[c]
            and _value(state, program.statements[c].command.arg1) == statement.label
        )
    taken = []
    for c in candidates:
        state, reinstated = _reach(state, c, program)
        if not reinstated:
            continue
        runs, pos = _runs(program.statements[c].chance, draws, pos)
        if runs:
            taken.append(c)
    if len(taken) > 1:
        raise _fail(
            "E555", "two COME FROMs take control at once in a one-thread program"
        )
    if taken:
        if program.statements[taken[0]].kind == "next from":
            state = _push(state, i + 1, -1)
        # Control passes to the COME FROM, which then finishes in turn:
        # the manual's DO COME FROM COMING FROM is an infinite loop.
        state = replace(state, ind=taken[0])
    return state, pos


def _dimension(state: _State, key: _Key, sizes: tuple[int, ...]) -> _State:
    """Return ``state`` with array ``key`` freshly dimensioned, all zeros."""
    if 0 in sizes:
        raise _fail("E240", "an INTERCAL array dimension must be positive")
    if key in state.ignored:
        return state
    return replace(state, arrays=state.arrays.set(key, (sizes, _NO_DATA)))


def _abstain(state: _State, targets: Sequence[int], amount: int | None) -> _State:
    """Raise each target's abstain counter by ``amount``, or to at least 1."""
    for target in targets:
        count = state.abstained[target]
        if amount is not None:
            state = _set_abstained(state, target, count + amount)
        elif not count:
            state = _set_abstained(state, target, 1)
    return state


def _reinstate(state: _State, targets: Sequence[int], program: _Program) -> _State:
    """Lower each abstained target's counter; ``GIVE UP`` stays abstained."""
    for target in targets:
        count = state.abstained[target]
        if program.statements[target].kind is not None and count:
            state = _set_abstained(state, target, count - 1)
    return state


def _execute(
    state: _State,
    i: int,
    statement: _Statement,
    program: _Program,
    draws: Sequence[int],
    pos: int,
    inputs: Sequence[int | str | None],
    out: list[str],
) -> tuple[_State, int]:
    """Run one statement's command, appending its output to ``out``.

    ``NEXT``, ``RESUME``, ``GIVE UP`` and ``TRY AGAIN`` move the cursor
    themselves; every other command continues through :func:`_leave`, where
    a ``COME FROM`` may take control.
    """
    command = statement.command
    match command.tag:
        case "calculate":
            state = _store(state, command.arg1, _value(state, command.arg2))
        case "dimension":
            sizes = tuple(_value(state, size) for size in command.arg2)
            state = _dimension(state, command.arg1, sizes)
        case "next":
            state = _push(state, i + 1, i)
            return replace(state, ind=program.labels[command.arg1]), pos
        case "forget":
            keep = max(0, len(state.nexts) - _value(state, command.arg1))
            state = replace(state, nexts=state.nexts[:keep])
        case "resume":
            count = _value(state, command.arg1)
            return _resume(state, count, program, draws, pos)
        case "stash" | "retrieve" | "ignore" | "remember":
            for key in command.arg1:
                state = _variable(state, command.tag, key)
        case "abstain":
            amount = None if command.arg2 is None else _value(state, command.arg2)
            state = _abstain(state, _targets(command.arg1, program), amount)
        case "reinstate":
            state = _reinstate(state, _targets(command.arg1, program), program)
        case "read":
            for item in command.arg1:
                state, text = _read_out(state, item)
                out.append(text)
        case "write":
            read = 0
            for item in command.arg1:
                state, read = _write_in(state, item, inputs, read)
        case "give up":
            return replace(state, ind=len(program.statements)), pos
        case "try again":
            return replace(state, ind=0), pos
        case _:
            raise HaltError(
                f"INTERCAL syntax error (E000) in {statement.text!r}: {command.arg1}",
                hint="use statements supported by esolangs describe --spec INTERCAL",
            )
    return _leave(state, i, program, draws, pos)


# :func:`_advance` is the pure transition from one immutable ``_State`` to the next,
# returning the texts to print.  A step can draw any number of times (a ``%`` qualifier
# and each candidate ``COME FROM``) and read any number of inputs, so neither can be
# hoisted: it raises :data:`_NeedDraw` or :data:`_NeedInput`, and ``step``, the shell,
# supplies one more and retries.  :meth:`_Machine.branching_successors` replays it over
# explicit draw prefixes.
def _advance(
    state: _State,
    program: _Program,
    draws: Sequence[int] = (),
    inputs: Sequence[int | str | None] = (),
) -> tuple[_State, tuple[str, ...], int]:
    """Return the state after one statement, the texts to print, and draws used.

    Pure: ``program``, ``draws`` and ``inputs`` are parameters, and output
    leaves in the returned effects.  A missing draw raises :data:`_NeedDraw`
    and a missing input :data:`_NeedInput`, each carrying the output prefix
    computed before it; any other fault raises :data:`_Fault` with the same
    prefix, so the shell can flush output before drawing, reading, or
    re-raising.
    """
    out: list[str] = []
    try:
        new_state, pos = _statement_step(state, program, draws, inputs, out)
    except _NeedDraw:
        raise _NeedDraw(tuple(out)) from None
    except _NeedInput as need:
        raise _NeedInput(need.kind, tuple(out)) from None
    except _Fault:
        raise
    except BaseException as exc:
        raise _Fault(tuple(out), exc) from None
    return new_state, tuple(out), pos


def _statement_step(
    state: _State,
    program: _Program,
    draws: Sequence[int],
    inputs: Sequence[int | str | None],
    out: list[str],
) -> tuple[_State, int]:
    """Run one statement, appending output to ``out``; return state and draws."""
    if state.ind >= len(program.statements):
        return state, 0
    i = state.ind
    statement = program.statements[i]
    pos = 0
    if statement.kind in ("come from", "next from"):
        state, pos = _leave(state, i, program, draws, pos)
        return state, pos
    state, reinstated = _reach(state, i, program)
    if reinstated:
        runs, pos = _runs(statement.chance, draws, pos)
        if runs:
            return _execute(state, i, statement, program, draws, pos, inputs, out)
    state, pos = _leave(state, i, program, draws, pos)
    return state, pos


def _freeze(value: int | _Array) -> Hashable:
    if isinstance(value, int):
        return value
    return value[0], tuple(sorted(value[1].items()))


def _thaw(value: Any) -> int | _Array:
    if isinstance(value, int):
        return value
    dimensions, data = value
    return dimensions, _PMap(dict(data))


def _snapshot(state: _State) -> tuple[Any, ...]:
    """Return the nine hashable state fields a snapshot and a branch share."""
    arrays = tuple(
        (key, dimensions, tuple(sorted(data.items())))
        for key, (dimensions, data) in sorted(state.arrays.items())
    )
    stashes = tuple(
        (key, tuple(map(_freeze, values)))
        for key, values in sorted(state.stashes.items())
    )
    return (
        state.ind,
        tuple(sorted(state.scalars.items())),
        arrays,
        tuple(sorted(state.ignored)),
        stashes,
        state.abstained,
        state.nexts,
        state.last_in,
        state.last_out,
    )
