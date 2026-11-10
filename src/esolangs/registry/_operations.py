"""Lazy references whose entry points take one typed operation request."""

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from keyword import iskeyword
from typing import cast


@dataclass(frozen=True)
class OperationRef[Request, Result]:
    """A lazy request/result function; parameter names never choose capabilities."""

    module: str
    name: str

    def __post_init__(self) -> None:
        """Validate declared identity without loading an implementation."""
        if (
            not isinstance(self.name, str)
            or not self.name.isidentifier()
            or iskeyword(self.name)
        ):
            raise ValueError("operation name must be an identifier")
        if (
            not isinstance(self.module, str)
            or not self.module
            or any(
                not part.isidentifier() or iskeyword(part)
                for part in self.module.split(".")
            )
        ):
            raise ValueError("operation module must be an import path")
        object.__setattr__(self, "__module__", self.module)
        object.__setattr__(self, "__name__", self.name)

    def load(self) -> Callable[[Request], Result]:
        """Resolve afresh so an injected implementation fault stays observable."""
        target = getattr(import_module(self.module), self.name)
        if not callable(target):
            raise TypeError("backend operation must be callable")
        return cast("Callable[[Request], Result]", target)

    def __call__(self, request: Request) -> Result:
        """Invoke the declared request/result operation."""
        return self.load()(request)
