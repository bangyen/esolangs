"""Lazy references whose entry points take one typed operation request."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from esolangs.registry._functions import _load_callable, _validate_reference


@dataclass(frozen=True)
class OperationRef[Request, Result]:
    """A lazy request/result function; parameter names never choose capabilities."""

    module: str
    name: str

    def __post_init__(self) -> None:
        """Validate declared identity without loading an implementation."""
        _validate_reference(self.module, self.name, "operation")
        object.__setattr__(self, "__module__", self.module)
        object.__setattr__(self, "__name__", self.name)

    def load(self) -> Callable[[Request], Result]:
        """Resolve afresh so an injected implementation fault stays observable."""
        return cast(
            "Callable[[Request], Result]",
            _load_callable(self.module, self.name, "backend operation"),
        )

    def __call__(self, request: Request) -> Result:
        """Invoke the declared request/result operation."""
        return self.load()(request)
