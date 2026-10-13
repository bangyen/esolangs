r"""Interpreter for INTERCAL-72 with the C-INTERCAL extensions.

Implements the C-INTERCAL manual's single-threaded language: onespot ``.`` and
twospot ``:`` scalars, tail ``,`` and hybrid ``;`` arrays (``BY`` dimensions,
``SUB`` subscripts), mingle ``$`` (also the currency signs), select ``~``, the
unary ``&``/``V``/``?`` (infix, and prefix as in C-INTERCAL 0.26+), sparks and
rabbit-ears with the wow ``!``; ``NEXT``/``RESUME``/``FORGET``, ``STASH``/
``RETRIEVE``, ``IGNORE``/``REMEMBER``, ``ABSTAIN``/``REINSTATE`` by label, by
gerund and computed, ``DO NOT`` and ``%n`` chances, ``ONCE``/``AGAIN``,
``COME FROM`` and ``NEXT FROM`` by label, expression and gerund, ``TRY AGAIN``,
``GIVE UP``, numeric I/O and Turing Tape array I/O. Not implemented: the system
library, threads, backtracking, ``CREATE``, operand overloading, ``PIN``,
CLC-INTERCAL I/O and wimpmode.

Unparsable statements are E000 syntax errors raised only when executed. Errors
raise ``HaltError`` naming their E-number; program-wide checks (labels,
politeness, NEXT/ABSTAIN/COME FROM targets) raise at load. Numeric ``WRITE IN``
at EOF raises ``EOFError``; Turing Tape input stores 256 at EOF. A ``%n`` draws
from the ``rng`` hook (:mod:`esolangs.runtime.randomness`).

The semantics are a pure transition.  :func:`_advance` maps an immutable
``_State`` -- the statement cursor, the scalar and array stores, the ignore,
stash and abstain bookkeeping, the NEXT stack, the two I/O deltas, plus the
explicit draw values and input values a step may consume -- to a new state and
the texts it asks to print.  ``step`` is the shell: it draws from the ``rng``
hook and reads from ``io`` only when the transition asks, and writes what the
transition returns.  A step can draw any number of times (a ``%`` qualifier and
each candidate ``COME FROM``), so the draws cannot be hoisted; each
:data:`_NeedDraw` draws one more value and retries, and each :data:`_NeedInput`
reads one more input and retries.  :meth:`_Machine.branching_successors`
replays the same transition over explicit draw prefixes, so the branch search
never touches a port.

Judgment calls where the manual or C-INTERCAL leave a gap:

* A statement starts at ``DO``/``PLEASE`` even inside a word (``DOUBLE``), as
  C-INTERCAL lexes; a label starts one only before an identifier. A line with
  no identifier that is a complete core command stays its own statement.
* Politeness keeps the stricter one-fifth to one-third rule for any length;
  running off the end halts quietly instead of E633.
* Zero prints a lone overbar over an empty line, as the manual says; a value
  below 4000 prints one line, where C-INTERCAL prints an empty overbar line first.
* Whitespace may split a number from its sigil and its own digits, as
  C-INTERCAL's lexer allows, though the manual says it cannot.
* Digit words read in any case, split at any whitespace; C-INTERCAL wants
  upper case split at spaces.  Of two errors in one statement, the
  right-hand side's is raised before the target subscript's.
* ``READ OUT`` takes any expression; a subscript list holds bare operands, and
  a subscripted element may be the left operand of a binary operator.
* Array elements start at 0, where C-INTERCAL leaves them uninitialised;
  ``RETRIEVE`` restores an array even if it is undimensioned.
* Turing Tape characters are code points; the tape differences are taken
  modulo 256 and output bytes are written as code points 0-255.
* ``ONCE``/``AGAIN`` take effect when the statement is reached (for ``COME
  FROM`` when it fires); a computed ``COME FROM`` is checked at every labelled
  statement, a gerund one after every statement of that kind.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import partial
from types import MappingProxyType
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.intercal.interpreter._parse import (
    _fail,
    _Key,
    _load,
    _Node,
    _parse_expression,
    _SelfAbstain,
    _Statement,
    _statements,
    _unary,
)
from esolangs.runtime._drive import drive
from esolangs.runtime._fault import _Fault
from esolangs.runtime.io import IO
from esolangs.runtime.randomness import Randomness, draw

type _Value = tuple[int, int]
#: An array's dimensions and its data.  The data mapping is copied before a
#: write, so a step returns new arrays rather than editing the ones it was
#: handed.
type _Array = tuple[tuple[int, ...], Mapping[int, int]]

# Digit words 0-9: English and, as the manual says C-INTERCAL accepts
# (src/numerals.c), Sanskrit, Basque, Tagalog, Classical Nahuatl, Georgian,
# Kwakiutl, Volapuk and Latin.
_DIGIT_WORDS = (
    "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE",
    "SUTYA EKA DVI TRI CHATUR PANCHAN SHASH SAPTAM ASHTAN NAVAN",
    "ZEROA BAT BI HIRO LAU BORTZ SEI ZAZPI ZORTZI BEDERATZI",
    "WALA ISA DALAWA TATLO APAT LIMA ANIM PITO WALO SIYAM",
    "AHTLE CE OME IEI NAUI NACUILI CHIQUACE CHICOME CHICUE CHICUNAUI",
    "NULI ERTI ORI SAMI OTXI XUTI EKSVI SHVIDI RVA CXRA",
    "KE'YOS 'NEM MAL'H YUDEXW MU SEK'A Q'ETL'A ETLEBU MALHGWENALH 'NA'NE'MA",
    "NOS BAL TEL KIL FOL LUL MÄL VEL JÖL ZÜL",
    "NIL UNUS DUO TRES QUATTUOR QUINQUE SEX SEPTEM OCTO NOVEM",
)
_DIGITS = {
    word: digit for line in _DIGIT_WORDS for digit, word in enumerate(line.split())
} | {
    "OH": 0, "NINER": 9, "SHUTYA": 0, 'M\\"AL': 6, 'J\\"OL': 8, 'Z\\"UL': 9,
    "NIHIL": 0, "UNA": 1, "UNUM": 1, "DUAE": 2, "QUATUOR": 4,
}  # fmt: skip

_WIDTH = {".": 16, ":": 32, ",": 16, ";": 32}
_ONESPOT_MAX = 0xFFFF
_TWOSPOT_MAX = 0xFFFFFFFF
_NEXT_LIMIT = 80

# Bit reversal of a byte, for Turing Tape output (C-INTERCAL's binout).
_REVERSED = tuple(int(f"{byte:08b}"[::-1], 2) for byte in range(256))


def _spread(value: int) -> int:
    """Move bit ``k`` of a 16-bit value to bit ``2k``."""
    value = (value | (value << 8)) & 0x00FF00FF
    value = (value | (value << 4)) & 0x0F0F0F0F
    value = (value | (value << 2)) & 0x33333333
    return (value | (value << 1)) & 0x55555555


def _select(value: int, mask: int) -> int:
    result = place = 0
    while mask:
        low = mask & -mask
        if value & low:
            result |= 1 << place
        place += 1
        mask ^= low
    return result


def _evaluate(
    node: _Node, scalars: Mapping[_Key, int], arrays: Mapping[_Key, _Array]
) -> _Value:
    """Return ``(value, width)``; C-INTERCAL types every result statically."""
    tag = node.tag
    if tag == "#":
        return node.arg1, 16
    if tag == "." or tag == ":":
        return scalars.get((tag, node.arg1), 0), _WIDTH[tag]
    if tag == "u":
        value, width = _evaluate(node.arg2, scalars, arrays)
        return _unary(value, width, node.arg1), width
    if tag == "$":
        left, _ = _evaluate(node.arg1, scalars, arrays)
        right, _ = _evaluate(node.arg2, scalars, arrays)
        if left > _ONESPOT_MAX or right > _ONESPOT_MAX:
            raise _fail(
                "E533",
                "INTERCAL mingle needs two onespot values",
                hint="use two 16-bit onespot values as mingle operands",
            )
        return (_spread(left) << 1) | _spread(right), 32
    if tag == "~":
        left, _ = _evaluate(node.arg1, scalars, arrays)
        right, width = _evaluate(node.arg2, scalars, arrays)
        return _select(left, right), width
    data, index = _element(node, scalars, arrays)
    return data.get(index, 0), _WIDTH[node.arg1]


def _element(
    node: _Node, scalars: Mapping[_Key, int], arrays: Mapping[_Key, _Array]
) -> tuple[Mapping[int, int], int]:
    """Locate a subscripted element: its array's store and flat index."""
    sigil, number, subscripts = node.arg1, node.arg2, node.arg3
    dimensions, data = arrays.get((sigil, number), ((), {}))
    if len(subscripts) != len(dimensions):
        raise _fail(
            "E241",
            "INTERCAL subscripts do not match the array's dimensions",
            hint="dimension the array first and give one subscript per dimension",
        )
    index = 0
    for subscript, size in zip(subscripts, dimensions, strict=True):
        value, _ = _evaluate(subscript, scalars, arrays)
        if not 1 <= value <= size:
            raise _fail("E241", "INTERCAL subscript out of range")
        index = index * size + value - 1
    return data, index


def _expression(
    text: str, variables: dict[int, int], at: int = 0
) -> tuple[_Value, int]:
    """Parse and evaluate one expression over onespot ``variables``."""
    node, end = _parse_expression(text, at)
    scalars = {(".", number): value for number, value in variables.items()}
    return _evaluate(node, scalars, {}), end


def _roman(value: int) -> str:
    """Return Roman output; emit a separate overbar line when needed."""
    if not 0 <= value <= _TWOSPOT_MAX:
        raise HaltError("INTERCAL output out of range")
    chunks: list[tuple[str, str]] = []
    place = 0
    while value:
        value, digit = divmod(value, 10)
        group, column = divmod(place, 3)
        one, five, ten = ("IVX", "XLC", "CDM")[column]
        if column == 0 and group and digit <= 3:
            text = "M" * digit
            group -= 1
        elif digit <= 3:
            text = one * digit
        elif digit == 4:
            text = one + five
        elif digit <= 8:
            text = five + one * (digit - 5)
        else:
            text = one + ten
        if group >= 2:
            text = text.lower()
        chunks.append((text, ("_" if group % 2 else " ") * len(text)))
        place += 1
    body = "".join(text for text, _bars in reversed(chunks))
    bars = "".join(bars for _text, bars in reversed(chunks)) or "_"
    # "Zero is indicated by an overline with no character underneath."
    return bars + "\n" + body if "_" in bars else body


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


def _frozen_scalars(scalars: Mapping[_Key, int]) -> Mapping[_Key, int]:
    """Return ``scalars`` as an immutable mapping, sharing an existing freeze."""
    return (
        scalars if isinstance(scalars, MappingProxyType) else MappingProxyType(scalars)
    )


def _frozen_data(data: Mapping[int, int]) -> Mapping[int, int]:
    """Return an array's data as an immutable mapping."""
    return data if isinstance(data, MappingProxyType) else MappingProxyType(data)


def _frozen_arrays(arrays: Mapping[_Key, _Array]) -> Mapping[_Key, _Array]:
    """Return ``arrays`` as an immutable mapping, sharing an existing freeze."""
    return arrays if isinstance(arrays, MappingProxyType) else MappingProxyType(arrays)


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

    A value, not a record: the stores are copied before a write and
    :func:`_advance` returns a new state rather than editing this one.
    """

    ind: int
    scalars: Mapping[_Key, int]
    arrays: Mapping[_Key, _Array]
    ignored: frozenset[_Key]
    stashes: Mapping[_Key, tuple[int | _Array, ...]]
    abstained: tuple[int, ...]
    nexts: tuple[tuple[int, int], ...]
    last_in: int
    last_out: int


def _link(
    statements: Sequence[_Statement], labels: Mapping[int, int]
) -> tuple[
    Mapping[str, tuple[int, ...]],
    Mapping[int, tuple[int, ...]],
    Mapping[str, tuple[int, ...]],
    tuple[int, ...],
    tuple[bool, ...],
]:
    """Check every constant label target and index the COME FROMs."""
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
    return (
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
    """Return ``state`` with ``value`` stored at ``target``."""
    if target.tag == "sub":
        sigil = str(target.arg1)
        dimensions, data = state.arrays.get(
            (sigil, target.arg2), ((), MappingProxyType({}))
        )
        _unused, index = _element(target, state.scalars, state.arrays)
    else:
        sigil = str(target.tag)
    if sigil in ".," and value > _ONESPOT_MAX:
        raise _fail("E275", "INTERCAL onespot assignment overflow")
    key = (sigil, target.arg2) if target.tag == "sub" else (sigil, target.arg1)
    if key in state.ignored:
        return state
    if target.tag == "sub":
        arrays = _frozen_arrays(
            {
                **state.arrays,
                key: (dimensions, _frozen_data({**data, index: value})),
            }
        )
        return replace(state, arrays=arrays)
    return replace(state, scalars=_frozen_scalars({**state.scalars, key: value}))


def _array(state: _State, key: _Key) -> _Array:
    array = state.arrays.get(key, ((), MappingProxyType({})))
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
                data = _frozen_data({**data, index: value})
        state = replace(
            state,
            arrays=_frozen_arrays({**state.arrays, key: ((size,), data)}),
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
            dimensions, data = state.arrays.get(key, ((), MappingProxyType({})))
            value = (dimensions, _frozen_data(data))
        else:
            value = state.scalars.get(key, 0)
        stashes = MappingProxyType(
            {**state.stashes, key: (*state.stashes.get(key, ()), value)}
        )
        return replace(state, stashes=stashes)
    stash = state.stashes.get(key)
    if not stash:
        raise _fail("E436", f"INTERCAL RETRIEVE of an unstashed {key[0]}")
    value = stash[-1]
    state = replace(state, stashes=MappingProxyType({**state.stashes, key: stash[:-1]}))
    if key in state.ignored:
        return state
    if isinstance(value, int):
        return replace(state, scalars=_frozen_scalars({**state.scalars, key: value}))
    return replace(state, arrays=_frozen_arrays({**state.arrays, key: value}))


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


@dataclass
class _Step:
    """The working state of one ``_execute`` call, shared by its handlers."""

    state: _State
    i: int
    statement: _Statement
    program: _Program
    draws: Sequence[int]
    pos: int
    inputs: Sequence[int | str | None]
    input_pos: int
    out: list[str]


def _handle_calculate(step: _Step) -> bool:
    """``.1 <- expr``: evaluate and store."""
    command = step.statement.command
    step.state = _store(step.state, command.arg1, _value(step.state, command.arg2))
    return False


def _handle_dimension(step: _Step) -> bool:
    """``,1 SUB #1 <- #n BY #m``: dimension an array."""
    command = step.statement.command
    sizes = tuple(_value(step.state, size) for size in command.arg2)
    if 0 in sizes:
        raise _fail("E240", "an INTERCAL array dimension must be positive")
    if command.arg1 not in step.state.ignored:
        step.state = replace(
            step.state,
            arrays=_frozen_arrays(
                {**step.state.arrays, command.arg1: (sizes, MappingProxyType({}))}
            ),
        )
    return False


def _handle_next(step: _Step) -> bool:
    """``NEXT``: push the return and jump to the label."""
    step.state = _push(step.state, step.i + 1, step.i)
    step.state = replace(
        step.state, ind=step.program.labels[step.statement.command.arg1]
    )
    return True


def _handle_forget(step: _Step) -> bool:
    """``FORGET``: drop that many entries off the NEXT stack."""
    nexts = step.state.nexts
    count = _value(step.state, step.statement.command.arg1)
    step.state = replace(step.state, nexts=nexts[: max(0, len(nexts) - count)])
    return False


def _handle_resume(step: _Step) -> bool:
    """``RESUME``: pop the stack down to the ``count``th-from-top entry."""
    count = _value(step.state, step.statement.command.arg1)
    step.state, step.pos = _resume(
        step.state, count, step.program, step.draws, step.pos
    )
    return True


def _handle_variable_item(step: _Step, action: str) -> bool:
    """One ``STASH``/``RETRIEVE``/``IGNORE``/``REMEMBER`` item."""
    for key in step.statement.command.arg1:
        step.state = _variable(step.state, action, key)
    return False


def _handle_abstain(step: _Step) -> bool:
    """``ABSTAIN``: raise the targets' abstain counters."""
    command = step.statement.command
    amount = None if command.arg2 is None else _value(step.state, command.arg2)
    for target in _targets(command.arg1, step.program):
        if amount is not None:
            step.state = _set_abstained(
                step.state, target, step.state.abstained[target] + amount
            )
        elif not step.state.abstained[target]:
            step.state = _set_abstained(step.state, target, 1)
    return False


def _handle_reinstate(step: _Step) -> bool:
    """``REINSTATE``: lower the targets' abstain counters."""
    command = step.statement.command
    for target in _targets(command.arg1, step.program):
        if (
            step.program.statements[target].kind is not None
            and step.state.abstained[target]
        ):
            step.state = _set_abstained(
                step.state, target, step.state.abstained[target] - 1
            )
    return False


def _handle_read(step: _Step) -> bool:
    """``READ OUT``: append each item's text to the output."""
    for item in step.statement.command.arg1:
        step.state, text = _read_out(step.state, item)
        step.out.append(text)
    return False


def _handle_write(step: _Step) -> bool:
    """``WRITE IN``: consume one input per item."""
    for item in step.statement.command.arg1:
        step.state, step.input_pos = _write_in(
            step.state, item, step.inputs, step.input_pos
        )
    return False


def _handle_give_up(step: _Step) -> bool:
    """``GIVE UP``: run past the last statement."""
    step.state = replace(step.state, ind=len(step.program.statements))
    return True


def _handle_try_again(step: _Step) -> bool:
    """``TRY AGAIN``: restart at the first statement."""
    step.state = replace(step.state, ind=0)
    return True


#: The command handlers, by action tag.  A handler returns ``True`` when the
#: command already continued the run itself (``NEXT``/``RESUME`` finish the
#: statement early); ``False`` means ``_execute`` still runs ``_leave``.
_EXECUTE_HANDLERS: dict[str, Callable[[_Step], bool]] = {
    "calculate": _handle_calculate,
    "dimension": _handle_dimension,
    "next": _handle_next,
    "forget": _handle_forget,
    "resume": _handle_resume,
    **{
        action: partial(_handle_variable_item, action=action)
        for action in ("stash", "retrieve", "ignore", "remember")
    },
    "abstain": _handle_abstain,
    "reinstate": _handle_reinstate,
    "read": _handle_read,
    "write": _handle_write,
    "give up": _handle_give_up,
    "try again": _handle_try_again,
}


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
    """Run one statement's command, appending its output to ``out``."""
    command = statement.command
    handler = _EXECUTE_HANDLERS.get(command.tag)
    if handler is None:
        raise HaltError(
            f"INTERCAL syntax error (E000) in {statement.text!r}: {command.arg1}",
            hint="use statements supported by esolangs describe --spec INTERCAL",
        )
    step = _Step(state, i, statement, program, draws, pos, inputs, 0, out)
    if handler(step):
        return step.state, step.pos
    return _leave(step.state, step.i, step.program, step.draws, step.pos)


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
    return dimensions, _frozen_data(dict(data))


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


class _Machine:
    """Parsed INTERCAL statements and the immutable run state.

    ``step`` is the shell: it draws and reads only when the pure transition
    asks and writes what it returns.
    """

    reproducible_seed = 0

    def __init__(self, code: str, io: IO, rng: Randomness | None = None) -> None:
        self.io = io
        self._rng = rng
        self.lines = _statements(code)
        statements = tuple(_load(line) for line in self.lines)
        polite = sum(statement.polite for statement in statements)
        if (
            not self.lines
            or polite * 5 < len(self.lines)
            or polite * 3 > len(self.lines)
        ):
            raise _fail(
                "E079" if polite * 5 < len(self.lines) else "E099",
                "INTERCAL program is insufficiently or excessively polite",
                hint="use PLEASE on one fifth to one third of the statements",
            )
        labels: dict[int, int] = {}
        for i, statement in enumerate(statements):
            if statement.label is not None:
                if statement.label in labels:
                    raise _fail("E182", f"duplicate INTERCAL label: {statement.label}")
                labels[statement.label] = i
        by_kind, come_label, come_kind, come_computed, sucks = _link(statements, labels)
        self._program = _Program(
            statements,
            labels,
            by_kind,
            come_label,
            come_kind,
            come_computed,
            sucks,
        )
        self.state = _State(
            0,
            MappingProxyType({}),
            MappingProxyType({}),
            frozenset(),
            MappingProxyType({}),
            tuple(int(statement.abstained) for statement in statements),
            (),
            0,
            0,
        )

    @property
    def halted(self) -> bool:
        return self.state.ind >= len(self._program.statements)

    @property
    def ip(self) -> int:
        return self.state.ind

    @property
    def memory(self) -> list[int]:
        return [value for _key, value in sorted(self.state.scalars.items())]

    @property
    def stack(self) -> list[object]:
        return [resume for resume, _origin in self.state.nexts]

    def snapshot(self) -> tuple[Any, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (*_snapshot(self.state), self.io.progress())

    def branching_snapshot(self) -> tuple[Any, ...]:
        """Return immutable state for exhaustive ``%`` branch search."""
        return self.snapshot()

    def branching_halted(self, state: Any) -> bool:
        """Report whether an immutable state has run past its last statement."""
        return bool(state[0] >= len(self._program.statements))

    def _restore(self, state: tuple[Any, ...]) -> _State:
        """Rebuild a run state from a snapshot tuple."""
        (
            ind,
            scalars,
            arrays,
            ignored,
            stashes,
            abstained,
            nexts,
            last_in,
            last_out,
        ) = state[:9]
        return _State(
            ind=ind,
            scalars=_frozen_scalars(dict(scalars)),
            arrays=_frozen_arrays(
                {
                    key: (dimensions, _frozen_data(dict(data)))
                    for key, dimensions, data in arrays
                }
            ),
            ignored=frozenset(ignored),
            stashes=MappingProxyType(
                {
                    key: tuple(_thaw(value) for value in values)
                    for key, values in stashes
                }
            ),
            abstained=tuple(abstained),
            nexts=tuple(nexts),
            last_in=last_in,
            last_out=last_out,
        )

    def branching_successors(
        self, state: Any, _limit: int
    ) -> tuple[tuple[Any, ...], ...] | None:
        """Return every outcome of the step's draws, or ``None`` at input.

        Replays the pure transition over explicit draw prefixes: a missing
        draw is filled with ``0`` (the scripted default) and every position
        the run drew at is also tried with ``99``, which forces the other
        outcome of a ``%chance`` qualifier.
        """
        current: tuple[Any, ...] = state
        if self.branching_halted(current):
            return (current,)
        ind: int = current[0]
        if self._program.statements[ind].command.tag == "write" and not current[5][ind]:
            return None
        successors = []
        pending: list[tuple[int, ...]] = [()]
        while pending:
            prefix = pending.pop()
            base = len(prefix)
            draws = list(prefix)
            branch = self._restore(current)
            while True:
                try:
                    new_state, _effects, _used = _advance(
                        branch, self._program, tuple(draws), ()
                    )
                except _NeedDraw:
                    draws.append(0)
                    continue
                except _NeedInput:
                    return None
                except _Fault as fault:
                    raise fault.error from None
                break
            filled = tuple(draws)
            for at in range(base, len(filled)):
                pending.append((*filled[:at], 99))
            successors.append((*_snapshot(new_state), current[-1]))
        return tuple(successors)

    def step(self) -> None:
        """Execute one statement, drawing and reading only as asked.

        The shell performs the draws and reads the pure transition asks for
        and writes what it returns.  Each request flushes the output computed
        before it, and a fault flushes the same prefix before it is re-raised,
        so output written before a later draw, read, or halt is not lost.
        """
        if self.halted:
            return
        draws: list[int] = []
        inputs: list[int | str | None] = []
        flushed = 0
        while True:
            try:
                self.state, effects, _used = _advance(
                    self.state, self._program, tuple(draws), tuple(inputs)
                )
            except _NeedDraw as need:
                flushed = self._flush(need.effects, flushed)
                draws.append(draw(self._rng, 100))
                continue
            except _NeedInput as need:
                flushed = self._flush(need.effects, flushed)
                if need.kind == "char":
                    try:
                        inputs.append(self.io.input_char())
                    except EOFError:
                        inputs.append(None)
                else:
                    inputs.append(self.io.input_str())
                continue
            except _Fault as fault:
                self._flush(fault.effects, flushed)
                raise fault.error from None
            break
        self._flush(effects, flushed)

    def _flush(self, effects: Sequence[str], flushed: int) -> int:
        """Print ``effects`` past ``flushed``; return the new flush count."""
        for text in effects[flushed:]:
            self.io.print_str(text)
        return len(effects)


def run(code: str, io: IO, rng: Randomness | None = None) -> None:
    """Execute an INTERCAL program."""
    machine = _Machine(code, io, rng)
    drive(machine)
