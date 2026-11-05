"""Language-owned interpreters, descriptors and generators."""

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from esolangs.languages import generators as generators


def __getattr__(name: str) -> ModuleType:
    """Retain the generator namespace without loading it during catalog access."""
    if name != "generators":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.generators")
    globals()[name] = module
    return module


def __dir__() -> list[str]:
    """Include the deferred compatibility namespace."""
    return sorted(set(globals()) | {"generators"})
