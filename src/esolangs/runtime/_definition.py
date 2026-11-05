"""Runtime declarations independent of generators, examples and certification."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from esolangs.runtime._capabilities import MachineCapabilities


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
    #: Text exports append a terminator unless every LF is a command.
    file_newline: bool = True
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
    #: Typed preparation hook in the interpreter module; legacy discovery if absent.
    machine_preparation: str | None = None
    #: Defaults for every dialect choice; absent only without a dialect.
    dialect_defaults: Mapping[str, int | str] | None = None

    #: Explicit machine traits and optional debug surface; legacy discovery if absent.
    capabilities: MachineCapabilities | None = None

    def __post_init__(self) -> None:
        """Require declared defaults to cover exactly the dialect's choices."""
        choices = self.dialect_values or {}
        if self.dialect is None:
            if self.dialect_defaults is not None or choices:
                raise ValueError("dialect metadata requires a validator")
            return
        if (
            not choices
            or self.dialect_defaults is None
            or self.dialect_defaults.keys() != choices.keys()
        ):
            raise ValueError("dialect defaults must match declared dialect choices")
        for key, value in self.dialect_defaults.items():
            if not any(
                type(value) is type(choice) and value == choice
                for choice in choices[key]
            ):
                raise ValueError(f"default for {key} must be a declared dialect choice")
