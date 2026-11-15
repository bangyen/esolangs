"""Runtime declarations independent of generators, examples and certification."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, fields
from enum import StrEnum
from reprlib import recursive_repr
from types import FunctionType
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from esolangs._dialect import DialectSchema, Scalar
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


def _check_validator_defaults(
    validator: FunctionType, defaults: dict[str, Scalar]
) -> None:
    """Read declared keyword defaults without evaluating annotations."""
    code = validator.__code__
    names = code.co_varnames
    end = code.co_argcount
    available: dict[str, object] = {}
    positional = validator.__defaults__
    if positional is not None:
        count = min(end - code.co_posonlyargcount, tuple.__len__(positional))
        if count:
            values = tuple.__getitem__(positional, slice(-count, None))
            available.update(zip(names[end - count : end], values, strict=True))
    keyword = validator.__kwdefaults__
    if keyword is not None:
        keyword_names = names[end : end + code.co_kwonlyargcount]
        available.update(
            (name, value)
            for name, value in dict.items(keyword)
            if type(name) is str and name in keyword_names
        )
    for name, expected in defaults.items():
        if name in available and (
            type(actual := available[name]) is not type(expected) or actual != expected
        ):
            raise ValueError(
                f"dialect validator default for {name} disagrees with its schema"
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
    #: Whether any program can read stdin. The CLI acquires stdin only if true.
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

    @recursive_repr()
    def __repr__(self) -> str:
        from esolangs.runtime.memory import repr_record

        return repr_record(self, fields(RuntimeSpec))

    def __post_init__(self) -> None:
        """Require lifecycle declarations and valid runtime defaults."""
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
            if (
                not issubclass(type(value), str)
                or not (identifier := str.__str__(value)).isidentifier()
            ):
                raise ValueError(f"runtime {name} must name a declared entry point")
            if type(value) is not str:
                object.__setattr__(self, name, identifier)
        interpreter = self.interpreter
        if interpreter is not None:
            if not issubclass(type(interpreter), str):
                raise ValueError("runtime interpreter must be a string or None")
            if type(interpreter) is not str:
                object.__setattr__(self, "interpreter", str.__str__(interpreter))
        seed = self.reproducible_seed
        if type(seed) is bool or not issubclass(type(seed), int):
            from esolangs.exceptions import ArgumentError
            from esolangs.runtime._validate import _argument_repr

            raise ArgumentError(
                f"reproducible_seed must be an integer, got {_argument_repr(seed)}"
            )
        if type(seed) is not int:
            object.__setattr__(self, "reproducible_seed", int.__int__(seed))
        if self.dialect is None:
            if self.dialect_schema is not None:
                raise ValueError("dialect metadata requires a validator")
            return
        if self.dialect_schema is None or not (
            defaults := self.dialect_schema.defaults
        ):
            raise ValueError("dialect validator requires an explicit schema")
        if "scale" in defaults and self.capabilities.supports_scale:
            raise ValueError("dialect setting scale conflicts with raster scale")
        if "rng" in defaults and self.random:
            raise ValueError("dialect setting rng conflicts with runtime randomness")
        if isinstance(self.dialect, FunctionType):
            _check_validator_defaults(self.dialect, defaults)

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
