"""Runtime declarations independent of generators, examples and certification."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

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


@dataclass(frozen=True, slots=True)
class TextSourcePolicy:
    """Lossless UTF-8 text; explicit native adapters trim or append one terminator."""

    kind: ClassVar[SourceKind] = SourceKind.TEXT
    loader: ClassVar[SourceLoader] = SourceLoader.TEXT
    split: ClassVar[bool] = False
    compressed: ClassVar[bool] = False
    file_newline: ClassVar[bool] = True


@dataclass(frozen=True, slots=True)
class LineSourcePolicy(TextSourcePolicy):
    """Decoded text is passed to the interpreter as source lines."""

    split: ClassVar[bool] = True


@dataclass(frozen=True, slots=True)
class VerbatimSourcePolicy(TextSourcePolicy):
    """Preserve every source newline when importing and exporting files."""

    loader: ClassVar[SourceLoader] = SourceLoader.VERBATIM
    file_newline: ClassVar[bool] = False


@dataclass(frozen=True, slots=True)
class CompressedSourcePolicy(TextSourcePolicy):
    """Preserve compressed text storage and use gzip for native exports."""

    loader: ClassVar[SourceLoader] = SourceLoader.COMPRESSED
    compressed: ClassVar[bool] = True


@dataclass(frozen=True, slots=True)
class RasterSourcePolicy:
    """Decode native PNG files into pixels for a raster interpreter."""

    kind: ClassVar[SourceKind] = SourceKind.RASTER
    loader: ClassVar[SourceLoader] = SourceLoader.RASTER
    split: ClassVar[bool] = False
    compressed: ClassVar[bool] = False
    file_newline: ClassVar[bool] = True


type SourcePolicy = (
    TextSourcePolicy
    | LineSourcePolicy
    | VerbatimSourcePolicy
    | CompressedSourcePolicy
    | RasterSourcePolicy
)


@dataclass(frozen=True)
class RuntimeSpec:
    """Interpreter, source representation and language-defined runtime choices."""

    interpreter: str | None = None
    source_policy: SourcePolicy = field(default_factory=TextSourcePolicy, kw_only=True)
    #: One defaulted keyword per supported dialect setting.
    dialect: Callable[..., Any] | None = None
    dialect_schema: DialectSchema | None = None
    random: bool = False
    #: Seed for reproducible stepping; ordinary runs retain real randomness.
    reproducible_seed: int = 0
    #: What an exhausted read does instead of raising EOFError.
    eof: str = ""
    underfed_raises: bool = False
    #: Whether programs can read stdin. Used for CLI input diagnostics.
    reads_stdin: bool = field(default=True, kw_only=True)
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
        if type(self.source_policy) not in (
            TextSourcePolicy,
            LineSourcePolicy,
            VerbatimSourcePolicy,
            CompressedSourcePolicy,
            RasterSourcePolicy,
        ):
            raise ValueError("source must use a declared policy")
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

    @property
    def split(self) -> bool:
        """Return the source policy's split."""
        return self.source_policy.split

    @property
    def source_kind(self) -> SourceKind:
        """Return the source policy's source kind."""
        return self.source_policy.kind

    @property
    def compressed_source(self) -> bool:
        """Return the source policy's compressed source."""
        return self.source_policy.compressed

    @property
    def source_loader(self) -> SourceLoader:
        """Return the source policy's source loader."""
        return self.source_policy.loader

    @property
    def file_newline(self) -> bool:
        """Return the source policy's file newline."""
        return self.source_policy.file_newline
