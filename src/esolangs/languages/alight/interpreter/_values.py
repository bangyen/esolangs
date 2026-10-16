"""Alight runtime values: truth, arithmetic, comparison and the builtins."""

from fractions import Fraction
from typing import TypeGuard

from esolangs.exceptions import HaltError
from esolangs.languages.alight.interpreter._hints import Hint
from esolangs.languages.alight.interpreter._parse import (
    _Special,
    _Value,
)
from esolangs.languages.alight.interpreter._state import _equal

#: The four functions the language supplies.  Everything else a call
#: names is a ``func`` on the grid, which ``step`` runs by pushing a
#: walker rather than by evaluating it in place.
_BUILTINS = ("at", "len", "trunc", "sign")


def _truth(value: _Value) -> bool:
    """Return a guard's boolean, which only ``left``/``right`` may be.

    The wiki gives booleans exactly two values and no truthiness rule for
    anything else, so a number or a list in a guard is an invalid operation
    rather than a silent coercion.
    """
    if value == "left":
        return True
    if value == "right":
        return False
    raise Hint.BOOLEAN_GUARD.halt("guard is not a boolean")


def _boolean(flag: bool) -> _Special:  # noqa: FBT001 - a conversion, not a mode
    """Return the special value for a Python boolean: ``left`` or ``right``.

    The boolean trap the lint guards against is a *mode selector* -- an
    argument the caller has to look up to read.  Here the argument is the
    datum being converted, so naming it at each call site would only repeat
    the function's own name.
    """
    return "left" if flag else "right"


def _is_num(value: _Value) -> TypeGuard[Fraction | int]:
    """Whether a value is a number.

    A ``TypeGuard`` rather than a plain ``bool`` so that a caller's branch
    narrows: every arithmetic path below tests this first, and without the
    narrowing each one needed an ``assert isinstance`` afterwards purely to
    restate what the test had already established.
    """
    return isinstance(value, Fraction | int) and not isinstance(value, bool)


def _compare(op: str, left: _Value, right: _Value) -> _Special:
    """Compare two values, returning ``left``/``right``.

    ``=`` compares any two values -- objects of different types are unequal
    rather than an error, which is what lets ``c = eof`` be asked of a
    character.  ``<`` and ``>`` are false on anything but two numbers, per
    the wiki.
    """
    if op == "=":
        if _is_num(left) != _is_num(right):
            return "right"
        return _boolean(_equal(left, right))
    if not (_is_num(left) and _is_num(right)):
        return "right"
    return _boolean(left < right if op == "<" else left > right)


def _list_value(values: list[_Value]) -> list[_Value]:
    """Validate homogeneous list elements; specials belong to either kind."""
    kinds = {isinstance(value, list) for value in values if not isinstance(value, str)}
    if len(kinds) > 1:
        raise HaltError("list contains the wrong type of value")
    return values


def _arith(op: str, left: _Value, right: _Value) -> _Value:
    """Apply an arithmetic operator, including the list forms.

    ``+`` concatenates two lists and ``*`` repeats one by a count, which is
    how the wiki defines them; every other combination of a list with a
    number is a type error.
    """
    if isinstance(left, list) and isinstance(right, list):
        if op != "+":
            raise Hint.OPERAND_TYPES.halt(f"cannot apply {op!r} to two lists")
        return _list_value([*left, *right])
    if isinstance(left, list):
        return _repeat(op, left, right)
    if isinstance(right, list):
        # Repetition is commutative in the spelling: ``3 * "ab"`` and
        # ``"ab" * 3`` are the same list.
        return _repeat(op, right, left)
    if not (_is_num(left) and _is_num(right)):
        specials = ", ".join(value for value in (left, right) if isinstance(value, str))
        raise Hint.OPERAND_TYPES.halt(
            f"cannot apply {op!r} to these values: {specials}"
        )
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if right == 0:
        raise Hint.DIVISOR.halt("division by zero")
    return Fraction(left) / right


def _repeat(op: str, seq: list[_Value], count: _Value) -> _Value:
    """Repeat a list by a count, the only list-and-number operation there is."""
    if op != "*" or not _is_num(count):
        raise Hint.OPERAND_TYPES.halt(f"cannot apply {op!r} to a list and a scalar")
    if count != int(count) or count < 0:
        raise Hint.REPEAT_COUNT.halt("list repeat count is not a whole number")
    return seq * int(count)


def _logic(op: str, left: _Value, right: _Value) -> _Special:
    """Apply a logic operator to two booleans."""
    a, b = _truth(left), _truth(right)
    if op == "&":
        return _boolean(a and b)
    if op == "|":
        return _boolean(a or b)
    return _boolean(a != b)


def _index(value: _Value) -> int:
    """Turn an Alight list index into a Python one.

    Indices are ``0.5 + k``; anything else is an error, which is the
    language's one genuinely strange rule and the reason this is a function
    rather than an inline ``int(i)``.
    """
    if not _is_num(value):
        raise Hint.NUMERIC_INDEX.halt(f"list index is not a number: {value!r}")
    slot = value - Fraction(1, 2)
    if slot != int(slot) or slot < 0:
        raise Hint.INDEX_FORM.halt(f"list index is not 0.5 + k: {value!r}")
    return int(slot)


#: Sentinels the pure layer and the shell pass each other.  ``_MISSING`` is
#: the value a step passes for input before the shell has read a character.
_MISSING: object = object()


def _has_input(value: _Value | object) -> TypeGuard[_Value]:
    """Whether the step was handed its input character already.

    A ``TypeGuard`` rather than a plain ``bool`` so the reader below
    narrows: ``value is _MISSING`` alone does not narrow the sentinel out
    for the type checker.
    """
    return value is not _MISSING


class _NeedInputError(Exception):
    """Ask the shell for the one input character an ``inp`` command needs."""


class _InPlace:
    """Marker for an in-place ``at``: replace ``old`` by ``updated`` everywhere."""

    __slots__ = ("old", "updated")

    def __init__(self, old: list[_Value], updated: list[_Value]) -> None:
        self.old = old
        self.updated = updated


def _builtin(name: str, args: list[_Value], list_update: str) -> _Value | _InPlace:
    """Apply one of the four builtin functions."""
    if name in ("trunc", "sign"):
        if len(args) != 1 or not _is_num(args[0]):
            raise Hint.BUILTIN_NUMBER.halt(f"{name} takes one number")
        value = args[0]
        if name == "trunc":
            return Fraction(int(value))
        return Fraction((value > 0) - (value < 0))
    if len(args) < 1 or not isinstance(args[0], list):
        raise Hint.BUILTIN_LIST.halt(f"{name} takes a list")
    seq = args[0]
    if name == "len":
        if len(args) == 1:
            return Fraction(len(seq))
        if len(args) != 2 or not _is_num(args[1]):
            raise Hint.BUILTIN_LIST.halt("len takes a list and optionally a count")
        count = args[1]
        if count != int(count) or count < 0:
            raise Hint.PADDING_COUNT.halt("len pad count is not a whole number")
        padding: list[_Value] = ["nil"] * int(count)
        return [*seq, *padding]
    if len(args) == 2:
        # Out of bounds reads as nil, per the wiki -- only the three-argument
        # *set* form raises.
        slot = _index(args[1])
        return seq[slot] if slot < len(seq) else "nil"
    if len(args) != 3:
        raise Hint.BUILTIN_LIST.halt(
            "at takes a list, an index, and optionally a value"
        )
    slot = _index(args[1])
    if slot >= len(seq):
        raise Hint.INDEXED_WRITE.halt(f"at index past the end of a {len(seq)}-list")
    _list_value([*seq, args[2]])
    if list_update == "in_place":
        # The value is a fresh list; the caller replaces the old one
        # everywhere it is aliased rather than editing it, so a state a
        # caller banked cannot change under it.
        updated = list(seq)
        updated[slot] = args[2]
        return _InPlace(seq, updated)
    result = seq.copy()
    result[slot] = args[2]
    return result
