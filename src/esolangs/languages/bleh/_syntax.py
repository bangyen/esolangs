"""Bleh expression and pattern records shared by parsing and execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from reprlib import recursive_repr
from typing import Any, cast

from esolangs.runtime._state import repr_snapshot_record


def _utf8_bits(text: str) -> str:
    return "".join(format(byte, "08b") for byte in text.encode())


class _RecursiveRecord:
    """Share the workspace display budget with nested syntax and values."""

    __slots__ = ()

    @recursive_repr()
    def __repr__(self) -> str:
        return repr_snapshot_record(self, fields(cast("Any", self)))


@dataclass(frozen=True, slots=True)
class _Bits:
    value: str


@dataclass(frozen=True, slots=True)
class _Ref:
    name: str


@dataclass(frozen=True, slots=True, repr=False)
class _Join(_RecursiveRecord):
    parts: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _Seq(_RecursiveRecord):
    parts: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _Call(_RecursiveRecord):
    #: A function's name, or ``io.<builtin>``.
    func: str
    args: tuple[_Expr, ...]


@dataclass(frozen=True, slots=True)
class _Slot:
    """A bound value in an expression's place: a lazy join's part."""

    val: _Val


class _LazyHashStorage(_RecursiveRecord):
    # Pickle and worker records carry only dataclass fields. A hash of strings
    # must be computed afresh in the process that reads them.
    __slots__ = ("_hash",)

    _hash: int


@dataclass(frozen=True, slots=True, repr=False, eq=False)
class _Lazy(_LazyHashStorage):
    """An unforced ``x..`` binding: the arguments it spans, joined."""

    parts: tuple[_Val, ...]

    def __hash__(self) -> int:
        try:
            return self._hash
        except AttributeError:
            self._cache_hashes()
            return self._hash

    def _cache_hashes(self) -> None:
        """Cache each shared node before its parents ask for their hash."""
        pending = [(self, False)]
        while pending:
            node, ready = pending.pop()
            if hasattr(node, "_hash"):
                continue
            if ready:
                object.__setattr__(node, "_hash", hash((node.parts,)))
            else:
                pending.append((node, True))
                pending.extend(
                    (part, False) for part in node.parts if isinstance(part, _Lazy)
                )

    def __eq__(self, other: object) -> bool:
        """Compare content independently of how either argument shares its parts."""
        if not isinstance(other, _Lazy) or type(self) is not type(other):
            return NotImplemented
        pending: list[tuple[_Val, _Val]] = [(self, other)]
        seen: set[tuple[int, int]] = set()
        while pending:
            left, right = pending.pop()
            if left is right:
                continue
            if isinstance(left, _Lazy) and isinstance(right, _Lazy):
                if type(left) is not type(right) or len(left.parts) != len(right.parts):
                    return False
                pair = id(left), id(right)
                if pair not in seen:
                    seen.add(pair)
                    pending.extend(
                        zip(reversed(left.parts), reversed(right.parts), strict=True)
                    )
            elif left == right:
                continue
            else:
                return False
        return True


type _Expr = _Bits | _Ref | _Join | _Seq | _Call | _Slot
#: A bound value: a heap address, known bits, or a lazy join.
type _Val = int | str | _Lazy


@dataclass(frozen=True, slots=True)
class _PLit:
    value: str


@dataclass(frozen=True, slots=True)
class _PAny:
    pass


@dataclass(frozen=True, slots=True)
class _PVar:
    name: str


@dataclass(frozen=True, slots=True)
class _PRest:
    name: str | None


@dataclass(frozen=True, slots=True, repr=False)
class _PSplit(_RecursiveRecord):
    name: str | None
    subs: tuple[_Pattern, ...]


type _Pattern = _PLit | _PAny | _PVar | _PRest | _PSplit
#: One branch: its patterns and its expression.
type _Branch = tuple[tuple[_Pattern, ...], _Expr]
type _Funcs = Mapping[str, tuple[_Branch, ...]]

_SYNTAX_RECORDS = (
    _Bits,
    _Ref,
    _Join,
    _Seq,
    _Call,
    _Slot,
    _Lazy,
    _PLit,
    _PAny,
    _PVar,
    _PRest,
    _PSplit,
)

# Keep the interpreter's record names in existing snapshot payloads.
for _record in _SYNTAX_RECORDS:
    _record.__module__ = "esolangs.languages.bleh.interpreter"
