"""Declared callable references without importing their implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from keyword import iskeyword
from typing import Any


@dataclass(frozen=True)
class FunctionRef:
    """A module attribute and its declared parameter names; loaded on use."""

    module: str
    name: str
    parameters: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Retain diagnostic identity without loading the target."""
        if (
            not isinstance(self.parameters, tuple)
            or any(
                not isinstance(name, str) or not name.isidentifier() or iskeyword(name)
                for name in self.parameters
            )
            or len(set(self.parameters)) != len(self.parameters)
        ):
            raise ValueError("callable parameters must be distinct identifiers")
        object.__setattr__(self, "__module__", self.module)
        object.__setattr__(self, "__name__", self.name)

    def load(self) -> Callable[..., Any]:
        """Resolve afresh so mutation probes cannot be hidden by a cached target."""
        target: Callable[..., Any] = getattr(import_module(self.module), self.name)
        return target

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the selected implementation."""
        return self.load()(*args, **kwargs)
