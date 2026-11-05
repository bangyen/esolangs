"""Named semantic components for workspace accounting, independent of storage."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass


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
