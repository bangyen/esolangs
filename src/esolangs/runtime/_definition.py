"""Runtime declarations independent of generators, examples and certification."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from esolangs._dialect import DialectSchema
    from esolangs.runtime._capabilities import MachineCapabilities


class SourceKind(StrEnum):
    """The representation an interpreter consumes."""

    TEXT = "text"
    RASTER = "raster"


class SourceLoader(StrEnum):
    """Declared container decoding and file-newline policy."""

    TEXT = "text"
    VERBATIM = "verbatim"
    COMPRESSED = "compressed"
    RASTER = "raster"


@dataclass(frozen=True)
class RuntimeSpec:
    """Interpreter, source representation and language-defined runtime choices."""

    interpreter: str | None = None
    #: Pass the interpreter one string per source line.
    split: bool = False
    path_like_source: bool = False
    source_kind: SourceKind = SourceKind.TEXT
    compressed_source: bool = False
    source_loader: SourceLoader = field(default=SourceLoader.TEXT, kw_only=True)
    #: Text exports append a terminator unless every LF is a command.
    file_newline: bool = True
    #: One defaulted keyword per supported dialect setting.
    dialect: Callable[..., Any] | None = None
    dialect_schema: DialectSchema | None = None
    random: bool = False
    #: Seed for reproducible stepping; ordinary runs retain real randomness.
    reproducible_seed: int = 0
    #: What an exhausted read does instead of raising EOFError.
    eof: str = ""
    underfed_raises: bool = False
    #: Error raised when the specification rejects an empty program.
    empty_program: str = ""
    category: str = "other"
    #: Native entry point returning a CompletionReport.
    completion_entrypoint: str = field(kw_only=True)
    #: Typed preparation hook in the interpreter module.
    machine_preparation: str = field(kw_only=True)

    #: Explicit machine traits and optional debug surface.
    capabilities: MachineCapabilities = field(kw_only=True)

    def __post_init__(self) -> None:
        """Require lifecycle declarations and exact dialect defaults."""
        if not isinstance(self.source_loader, SourceLoader):
            raise ValueError("source loader must be a declared policy")
        if self.capabilities is None:
            raise TypeError("runtime capabilities must be declared")
        for name in ("machine_preparation", "completion_entrypoint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.isidentifier():
                raise ValueError(f"runtime {name} must name a declared entry point")
        if self.dialect is None:
            if self.dialect_schema is not None:
                raise ValueError("dialect metadata requires a validator")
        elif self.dialect_schema is None or not self.dialect_schema.choices:
            raise ValueError("dialect validator requires an explicit schema")
