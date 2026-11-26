"""Generate Boolean programs and run source.

Use generate for a Boolean artifact, run for an execution outcome, and
prepare for repeated invocations. Use from_source to declare an artifact.
Generated artifacts bind or evaluate one row. The low-level Boolean
adapters encode_inputs and read_answer expose the language's I/O convention.
Use list_languages and describe to inspect the catalog. Language binds a
catalog and dialect. Serialization lives in esolangs.serialization,
construction decisions in esolangs.planning and declarations in esolangs.registry.
"""

import importlib
from typing import TYPE_CHECKING

from esolangs._dialect import DialectSchema, DialectSettings
from esolangs.artifacts import (
    Artifact,
    BooleanEvaluation,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.compressed import CompressedText, TextLimits
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionBudgetError,
    ExecutionCapError,
    ExecutionTimeoutError,
    GeneratorCapError,
    HaltError,
    InputExhaustedError,
    InterpreterLimitError,
    MissingDependencyError,
    ProgramError,
    ProgramNotFoundError,
    TemplateError,
    TruthTableError,
    UnknownLanguageError,
)
from esolangs.limits import ExecutionLimits
from esolangs.outcomes import ExecutionOutcome
from esolangs.raster import Raster
from esolangs.results import ExecutionResult
from esolangs.runtime._input import InputSource
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource

_LAZY = {
    "Catalog": "esolangs.registry._catalog",
    "PreparedProgram": "esolangs.operations.prepared",
    "Language": "esolangs._language",
    "run": "esolangs.operations.execution",
    "prepare": "esolangs.operations.execution",
    "evaluate": "esolangs.operations.evaluation",
    "from_file": "esolangs.operations.source",
    "from_source": "esolangs.operations.source",
    "generate": "esolangs.operations.generation",
    "plan_generation": "esolangs.planning",
    "instantiate": "esolangs.operations.instantiation",
    "to_json": "esolangs.portable",
    "from_json": "esolangs.portable",
    "to_file": "esolangs.operations.export",
    "LanguageInfo": "esolangs.registry._info",
    "LanguageDeclaration": "esolangs.registry._language",
    "describe": "esolangs.registry._describe",
    "list_languages": "esolangs.registry._describe",
    "encode_inputs": "esolangs.operations.boolean_io",
    "read_answer": "esolangs.operations.boolean_io",
}

if TYPE_CHECKING:
    __version__: str
    from esolangs._language import Language as Language
    from esolangs.operations.boolean_io import encode_inputs as encode_inputs
    from esolangs.operations.boolean_io import read_answer as read_answer
    from esolangs.operations.evaluation import evaluate as evaluate
    from esolangs.operations.execution import prepare as prepare
    from esolangs.operations.execution import run as run
    from esolangs.operations.export import to_file as to_file
    from esolangs.operations.generation import generate as generate
    from esolangs.operations.instantiation import instantiate as instantiate
    from esolangs.operations.prepared import PreparedProgram as PreparedProgram
    from esolangs.operations.source import from_file as from_file
    from esolangs.operations.source import from_source as from_source
    from esolangs.planning import plan_generation as plan_generation
    from esolangs.portable import from_json as from_json
    from esolangs.portable import to_json as to_json
    from esolangs.registry._catalog import Catalog as Catalog
    from esolangs.registry._describe import describe as describe
    from esolangs.registry._describe import list_languages as list_languages
    from esolangs.registry._info import LanguageInfo as LanguageInfo
    from esolangs.registry._language import (
        LanguageDeclaration as LanguageDeclaration,
    )
else:

    def __getattr__(name: str) -> object:
        """Resolve service exports on use; importing value types needs no catalog."""
        if name == "__version__":
            from importlib import metadata

            try:
                value = metadata.version("esolangs")
            except metadata.PackageNotFoundError:  # pragma: no cover
                value = "0.0.0+unknown"
        else:
            module = _LAZY.get(name)
            if module is None:
                raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
            value = getattr(importlib.import_module(module), name)
        globals()[name] = value
        return value


#: The public surface.  Without it ``dir(esolangs)`` advertised ``Any``,
#: ``Callable``, ``importlib``, ``pathlib``, ``signal`` and ``threading``
#: alongside the functions anyone wants, and there was no way to tell
#: from the outside which was which.
__all__ = [
    "ArgumentError",
    "Artifact",
    "BooleanEvaluation",
    "CompressedText",
    "DialectSchema",
    "DialectSettings",
    "EsolangError",
    "ExecutionBudgetError",
    "ExecutionCapError",
    "ExecutionLimits",
    "ExecutionOutcome",
    "ExecutionResult",
    "ExecutionTimeoutError",
    "GeneratorCapError",
    "HaltError",
    "InputExhaustedError",
    "InputSource",
    "InterpreterLimitError",
    "Language",
    "LanguageInfo",
    "MissingDependencyError",
    "PreparedProgram",
    "Program",
    "ProgramArtifact",
    "ProgramError",
    "ProgramNotFoundError",
    "ProgramSource",
    "Raster",
    "TemplateArtifact",
    "TemplateBindings",
    "TemplateError",
    "TextLimits",
    "TruthTableError",
    "UnknownLanguageError",
    "describe",
    "encode_inputs",
    "from_source",
    "generate",
    "list_languages",
    "prepare",
    "read_answer",
    "run",
]


def __dir__() -> list[str]:
    """Return the public surface, so tab-completion matches ``__all__``."""
    return sorted(__all__)
