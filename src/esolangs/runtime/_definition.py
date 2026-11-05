"""Runtime declarations independent of generators, examples and certification."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SourceKind(StrEnum):
    """The representation an interpreter consumes."""

    TEXT = "text"
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
    #: One defaulted keyword per supported dialect setting.
    dialect: Callable[..., Any] | None = None
    dialect_values: Mapping[str, tuple[int | str, ...]] | None = None
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
    completion_entrypoint: str = "_execute"
