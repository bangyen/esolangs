"""Persistent scope versions, prepared frames, and snapshot transport."""

from __future__ import annotations

import re
from collections.abc import Hashable, Iterator, Mapping
from types import MappingProxyType
from typing import NamedTuple, final

from esolangs.runtime._snapshot import SnapshotCodec


class _Frame(NamedTuple):
    """One active scope: its code, cursor, and whether it is a ``[`` loop body."""

    code: str
    pc: int = 0
    loop: bool = False
    offset: int = 0
    ends: Mapping[int, int] = MappingProxyType({})


# Preserve the frame name for pickled interpreter state.
_Frame.__module__ = "esolangs.languages.for_thorn.interpreter"

_EMPTY_FRAME = _Frame("")
_OPEN = {")": "(", "]": "[", "}": "{"}
_DELIMITER = re.compile(r"[()\[\]{}]")


def _prepare_source(code: str) -> _Frame:
    """Pair each delimiter kind independently for all slices of the source."""
    stacks: dict[str, list[int]] = {opener: [] for opener in _OPEN.values()}
    ends: dict[int, int] = {}
    for match in _DELIMITER.finditer(code):
        char = match[0]
        at = match.start()
        if char in stacks:
            stacks[char].append(at)
        elif pending := stacks[_OPEN[char]]:
            ends[pending.pop()] = at + 1
    return _Frame(code, ends=MappingProxyType(ends))


type _Frames = tuple[_Frame, ...]

_ABSENT = object()
_HASH_MASK = (1 << 64) - 1


def _entry_hash(key: int, scope: object) -> int:
    return hash((key, scope)) & _HASH_MASK


@final
class _Scopes(Mapping[int, str]):
    """The scope table as a persistent map: a store costs O(1), not O(scopes).

    Copying the table on every ``{`` made a run with S scopes O(S^2), and
    ``frozenset(table.items())`` made every snapshot O(S).  Versions share one
    dict (the root); an older version holds the single undo entry that turns
    its successor back into it, and reading it first moves the dict back
    along those entries.  The runtime only reads the newest version.

    Equal versions have equal ``hash`` (the sum of entry hashes, kept
    incrementally) and ``len``; ``==`` then compares contents, so a hash
    collision never merges two states.  Unchanged stores return the same object.
    """

    # Keep the registered snapshot codec key stable.
    __module__ = "esolangs.languages.for_thorn.interpreter"

    __slots__ = ("data", "key", "link", "old", "size", "total")

    def __init__(self) -> None:
        """Make the empty table."""
        self.data: dict[int, _Frame] | None = {}
        self.total = 0
        self.size = 0
        self.link: _Scopes | None = None
        self.key = 0
        self.old: object = _ABSENT

    def _root(self) -> dict[int, _Frame]:
        """Return the dict holding this version, moving it here if elsewhere."""
        if self.data is not None:
            return self.data
        path = []
        node: _Scopes = self
        while node.data is None:
            path.append(node)
            assert node.link is not None
            node = node.link
        for older in reversed(path):
            data = node.data
            assert data is not None
            key, old = older.key, older.old
            node.key, node.old = key, data.get(key, _ABSENT)
            node.link, node.data = older, None
            if old is _ABSENT:
                del data[key]
            else:
                data[key] = old  # type: ignore[assignment]
            older.data, older.link, older.old = data, None, _ABSENT
            node = older
        return node.data  # type: ignore[return-value]

    def store(self, key: int, scope: _Frame) -> _Scopes:
        """Return the table with ``key`` bound to ``scope``."""
        data = self._root()
        old = data.get(key, _ABSENT)
        if isinstance(old, _Frame) and old.code == scope.code:
            return self
        new = _Scopes.__new__(_Scopes)
        new.data, new.link, new.old = data, None, _ABSENT
        new.total = (self.total + _entry_hash(key, scope.code)) & _HASH_MASK
        new.size = self.size
        if isinstance(old, _Frame):
            new.total = (new.total - _entry_hash(key, old.code)) & _HASH_MASK
        else:
            new.size += 1
        data[key] = scope
        self.data, self.link, self.key, self.old = None, new, key, old
        return new

    def delta(
        self, last: _Scopes
    ) -> tuple[list[tuple[int, str]], list[tuple[int, str]]] | None:
        """Return (items gained, items lost) going from ``last`` to this version.

        None when ``last`` is not an older version of this one.  Costs the
        stores between them, for the workspace meter.
        """
        touched: dict[int, object] = {}
        node = last
        while node is not self:
            if node.data is not None or node.link is None:
                return None
            touched.setdefault(node.key, node.old)
            node = node.link
        data = self._root()
        gained, lost = [], []
        for key, before in touched.items():
            now = data.get(key, _ABSENT)
            old_code = before.code if isinstance(before, _Frame) else None
            new_code = now.code if isinstance(now, _Frame) else None
            if old_code != new_code:
                if old_code is not None:
                    lost.append((key, old_code))
                if new_code is not None:
                    gained.append((key, new_code))
        return gained, lost

    def __getitem__(self, key: int) -> str:
        """Return the scope stored under ``key``."""
        return self._root()[key].code

    def frame(self, key: int) -> _Frame:
        """Return the initial frame under ``key``, or an empty frame."""
        return self._root().get(key, _EMPTY_FRAME)

    def __iter__(self) -> Iterator[int]:
        """Iterate the stored keys."""
        return iter(list(self._root()))

    def __len__(self) -> int:
        """Count the stored scopes."""
        return self.size

    def __hash__(self) -> int:
        """Return the incrementally kept entry-hash sum."""
        return self.total

    def __eq__(self, other: object) -> bool:
        """Compare contents, after the O(1) rejections."""
        if self is other:
            return True
        if not isinstance(other, _Scopes):
            if isinstance(other, Mapping):
                return dict(self.items()) == dict(other)
            return NotImplemented
        if self.total != other.total or self.size != other.size:
            return False
        mine = {key: frame.code for key, frame in self._root().items()}
        return mine == {key: frame.code for key, frame in other._root().items()}


def _scope_payload(scopes: _Scopes) -> Hashable:
    return frozenset(scopes.items())


def _scope_restore(payload: Hashable) -> _Scopes:
    if not isinstance(payload, frozenset) or any(
        not isinstance(item, tuple)
        or len(item) != 2
        or type(item[0]) is not int
        or not isinstance(item[1], str)
        for item in payload
    ):
        raise TypeError("invalid scope snapshot")
    scopes = _Scopes()
    for key, code in payload:
        scopes = scopes.store(key, _prepare_source(code))
    return scopes


SNAPSHOT_CODECS = (SnapshotCodec(_Scopes, _scope_payload, _scope_restore),)
