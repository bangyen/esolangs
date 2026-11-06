"""Named semantic components for workspace accounting, independent of storage."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkspaceModel:
    """A versioned grouping of semantic state; scalar widths use state_bits."""

    name: str
    components: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require a name and distinct, named components."""
        if (
            not isinstance(self.name, str)
            or not self.name
            or not isinstance(self.components, tuple)
            or not self.components
            or any(
                not isinstance(name, str) or not name.isidentifier()
                for name in self.components
            )
            or len(set(self.components)) != len(self.components)
        ):
            raise ValueError("workspace models need a name and distinct components")

    def capture(self, **values: Hashable) -> WorkspaceSnapshot:
        """Order named values by the model, refusing missing or extra state."""
        if values.keys() != set(self.components):
            raise ValueError("workspace values do not match the declared components")
        return WorkspaceSnapshot(self, tuple(values[name] for name in self.components))


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    """Immutable semantic components; model metadata is not counted as workspace."""

    model: WorkspaceModel
    parts: tuple[Hashable, ...]

    def __post_init__(self) -> None:
        """Require the declared shape and hashable component values."""
        if not isinstance(self.parts, tuple) or len(self.parts) != len(
            self.model.components
        ):
            raise ValueError("workspace snapshot does not match its model")
        hash(self.parts)


@dataclass(frozen=True, slots=True, eq=False)
class WorkspaceVariant:
    """Typed logical fields; the kind and cached hash are schema, not payload."""

    kind: str
    values: tuple[Hashable, ...]
    _hash: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate the variant and hash children once, including shared subterms."""
        if not isinstance(self.kind, str) or not self.kind.isidentifier():
            raise ValueError("workspace variants need an identifier kind")
        if not isinstance(self.values, tuple):
            raise TypeError("workspace variant fields must be a tuple")
        object.__setattr__(self, "_hash", hash((self.kind, self.values)))

    def __hash__(self) -> int:
        """Return the construction-time hash without recursing down a term."""
        return self._hash

    def __reduce__(
        self,
    ) -> tuple[type[WorkspaceVariant], tuple[str, tuple[Hashable, ...]]]:
        """Recompute salted hashes when the value crosses a process boundary."""
        return type(self), (self.kind, self.values)

    def __eq__(self, other: object) -> bool:
        """Compare typed content iteratively, visiting shared pairs once."""
        if not isinstance(other, WorkspaceVariant):
            return NotImplemented
        if self._hash != other._hash:
            return False
        pending: list[tuple[object, object]] = [(self, other)]
        seen = set()
        while pending:
            left, right = pending.pop()
            if left is right:
                continue
            pair = (id(left), id(right))
            if pair in seen:
                continue
            seen.add(pair)
            if isinstance(left, WorkspaceVariant):
                if not isinstance(right, WorkspaceVariant) or left.kind != right.kind:
                    return False
                pending.append((left.values, right.values))
            elif isinstance(left, tuple):
                if not isinstance(right, tuple) or len(left) != len(right):
                    return False
                pending.extend(zip(left, right, strict=True))
            elif left != right:
                return False
        return True
