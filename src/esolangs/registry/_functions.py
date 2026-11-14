"""Declared callable references without importing their implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from keyword import iskeyword
from typing import Any

from esolangs.exceptions import MissingDependencyError, ProgramError


def _validate_reference(module: str, name: str, kind: str) -> None:
    """Validate target identity without importing its module."""
    if not isinstance(name, str) or not name.isidentifier() or iskeyword(name):
        raise ValueError(f"{kind} name must be an identifier")
    if (
        not isinstance(module, str)
        or not module
        or any(not part.isidentifier() or iskeyword(part) for part in module.split("."))
    ):
        raise ValueError(f"{kind} module must be an import path")


def _load_callable(module: str, name: str, kind: str) -> Callable[..., Any]:
    """Load a declared callable, distinguishing an absent target from a dependency."""
    try:
        implementation = import_module(module)
    except ModuleNotFoundError as error:
        missing = error.name
        if missing is not None and (
            module == missing or module.startswith(f"{missing}.")
        ):
            raise ProgramError(f"{kind} module {module!r} is missing") from error
        raise MissingDependencyError(
            f"{kind} {module}.{name} could not load {missing!r}"
        ) from error
    target: object = getattr(implementation, name, None)
    if not callable(target):
        raise ProgramError(f"{kind} {module}.{name} is missing or is not callable")
    return target


@dataclass(frozen=True)
class FunctionRef:
    """A module attribute and its declared parameter names; loaded on use."""

    module: str
    name: str
    parameters: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Retain diagnostic identity without loading the target."""
        _validate_reference(self.module, self.name, "callable")
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
        return _load_callable(self.module, self.name, "declared callable")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the selected implementation."""
        return self.load()(*args, **kwargs)
