"""The metadata a language declares about itself.

Each language owns ``descriptor.py`` with ``LANGUAGE = Language(...)``.
The registry collects descriptors without importing generator implementations.  This
module keeps declarations independent of example generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._slug import canonical_id
from esolangs.runtime._capabilities import MachineCapabilities
from esolangs.runtime._definition import RuntimeSpec, SourceKind


@dataclass(frozen=True)
class Example:
    """Invocation and expected output of a committed example."""

    table: str = "0001"
    bits: tuple[int, ...] = (0, 1)
    expected: str = "0"
    expected_compared: bool = True
    kwargs: tuple[tuple[str, int], ...] = ()
    scale: int = 1
    #: Building it balanced is a medium-length run.
    slow_build: bool = False


@dataclass(frozen=True)
class Language:
    """Everything the package and its tests know about one language."""

    # Identity.  ``id`` defaults to :func:`canonical_id` of the name.
    name: str
    runtime: RuntimeSpec
    id: str = ""
    #: Other names :func:`~esolangs.registry.resolve` accepts.
    aliases: tuple[str, ...] = ()
    backend: BooleanBackend | None = None
    # Also decodes caller-supplied output without a generator backend.
    contract: BooleanContract = field(default_factory=BooleanContract)
    #: The committed example, where the default AND reader does not fit.
    example: Example = field(default_factory=Example)

    def __post_init__(self) -> None:
        """Validate assembled capabilities and fill an absent canonical id."""
        if not isinstance(self.runtime.capabilities, MachineCapabilities):
            raise TypeError("runtime capabilities must be declared")
        if not self.id:
            object.__setattr__(self, "id", canonical_id(self.name))

    @property
    def source_suffix(self) -> str:
        """Return the file suffix this language's source is saved under."""
        if self.runtime.source_kind is SourceKind.RASTER:
            return ".png"
        return ".txt.gz" if self.runtime.compressed_source else ".txt"

    @property
    def parameterized(self) -> bool:
        """Whether the backend embeds inputs instead of reading stdin."""
        return self.backend is not None and self.backend.template is not None
