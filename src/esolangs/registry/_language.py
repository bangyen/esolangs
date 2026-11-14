"""The metadata a language declares about itself.

Each language owns ``descriptor.py`` with ``LANGUAGE = LanguageDeclaration(...)``.
The registry collects descriptors without importing generator implementations.  This
module keeps declarations independent of example generation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import KW_ONLY, dataclass, field
from functools import cache
from typing import TYPE_CHECKING, cast

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._slug import canonical_id
from esolangs.runtime._capabilities import MachineCapabilities
from esolangs.runtime._definition import RuntimeSpec, SourceKind

if TYPE_CHECKING:
    from esolangs.registry._backend import BooleanBackend


# Descriptors annotate their factories without importing synthesis at runtime.
type BackendDefinition = BooleanBackend


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
class DeferredBackend:
    """A language-owned factory for its synthesis declaration."""

    factory: Callable[[], BooleanBackend]


@cache
def _load_backend(factory: Callable[[], BooleanBackend]) -> BooleanBackend:
    return factory()


class _BackendSlot:
    """Expose concrete backend values through the declaration's dataclass field."""

    def __get__(
        self, language: LanguageDeclaration | None, owner: type[LanguageDeclaration]
    ) -> BooleanBackend | None:
        if language is None:
            return None
        value = self.raw(language)
        return (
            _load_backend(value.factory)
            if isinstance(value, DeferredBackend)
            else value
        )

    def __set__(
        self,
        language: LanguageDeclaration,
        value: BooleanBackend | DeferredBackend | None,
    ) -> None:
        object.__setattr__(language, "_backend", value)

    @staticmethod
    def raw(language: LanguageDeclaration) -> BooleanBackend | DeferredBackend | None:
        return cast(
            "BooleanBackend | DeferredBackend | None",
            object.__getattribute__(language, "_backend"),
        )


_BACKEND_SLOT = _BackendSlot()


@dataclass(frozen=True)
class LanguageDeclaration:
    """Everything the package and its tests know about one language."""

    # Identity.  ``id`` defaults to :func:`canonical_id` of the name.
    name: str
    runtime: RuntimeSpec
    _: KW_ONLY
    id: str = ""
    #: Other names :func:`~esolangs.registry.resolve` accepts.
    aliases: tuple[str, ...] = ()
    backend: _BackendSlot = _BACKEND_SLOT
    # Also decodes caller-supplied output without a generator backend.
    contract: BooleanContract = field(default_factory=BooleanContract)
    #: The committed example, where the default AND reader does not fit.
    example: Example = field(default_factory=Example)

    def __post_init__(self) -> None:
        """Validate assembled capabilities and fill an absent canonical id."""
        if not isinstance(self.runtime.capabilities, MachineCapabilities):
            raise TypeError("runtime capabilities must be declared")
        schema = self.runtime.dialect_schema
        if schema is not None and schema.language != self.name:
            raise ValueError("dialect schema must belong to the declaring language")
        if not self.id:
            object.__setattr__(self, "id", canonical_id(self.name))

    @property
    def source_suffix(self) -> str:
        """Return the file suffix this language's source is saved under."""
        if self.runtime.source_kind is SourceKind.RASTER:
            return ".png"
        return ".txt.gz" if self.runtime.compressed_source else ".txt"

    @property
    def has_backend(self) -> bool:
        """Whether synthesis is declared, without loading it."""
        return _BackendSlot.raw(self) is not None

    @property
    def parameterized(self) -> bool:
        """Whether the backend embeds inputs instead of reading stdin."""
        return self.backend is not None and self.backend.template is not None
