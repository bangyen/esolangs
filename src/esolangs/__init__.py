"""Generate programs, run supplied source, and describe languages.

Public operations split by who supplies the program:

* Generator-made: ``generate`` returns a program artifact or template;
  ``instantiate`` fills a template into a runnable artifact;
  ``evaluate`` executes one Boolean row.
* Caller-supplied: ``run`` returns output, input consumption and completion
  evidence in an immutable execution result; ``execute`` returns an outcome
  instead of raising; ``prepare`` loads source once for many invocations.
  Stepping and debugging live in :mod:`esolangs.debugger`.
* Records: ``from_source``, ``from_file`` and ``from_json`` declare or
  restore an artifact; ``to_file`` writes native source and ``to_json``
  portable JSON.
* Contract adapters: ``encode_inputs`` spells input bits as stdin and
  ``read_answer`` extracts an answer bit from output.
* Catalog: ``describe`` and ``list_languages`` provide registry facts.

Boolean evaluation over every row is private certification machinery,
not public API.  ``Language(name)`` binds every function above that takes a
language, and adds ``settings``.
Names resolve case-insensitively; deliberate errors derive from EsolangError.
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
    "PreparedProgram": "esolangs.runtime._prepared",
    "Language": "esolangs._language",
    "run": "esolangs.operations.execution",
    "execute": "esolangs.operations.execution",
    "prepare": "esolangs.operations.execution",
    "evaluate": "esolangs.operations.evaluation",
    "from_file": "esolangs.operations.source",
    "from_source": "esolangs.operations.source",
    "generate": "esolangs.operations.generation",
    "instantiate": "esolangs.operations.generation",
    "to_json": "esolangs.portable",
    "from_json": "esolangs.portable",
    "to_file": "esolangs.portable",
    "LanguageInfo": "esolangs.registry._info",
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
    from esolangs.operations.execution import execute as execute
    from esolangs.operations.execution import prepare as prepare
    from esolangs.operations.execution import run as run
    from esolangs.operations.generation import generate as generate
    from esolangs.operations.generation import instantiate as instantiate
    from esolangs.operations.source import from_file as from_file
    from esolangs.operations.source import from_source as from_source
    from esolangs.portable import from_json as from_json
    from esolangs.portable import to_file as to_file
    from esolangs.portable import to_json as to_json
    from esolangs.registry._catalog import Catalog as Catalog
    from esolangs.registry._describe import describe as describe
    from esolangs.registry._describe import list_languages as list_languages
    from esolangs.registry._info import LanguageInfo as LanguageInfo
    from esolangs.runtime._prepared import PreparedProgram as PreparedProgram
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
    "Catalog",
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
    "evaluate",
    "execute",
    "from_file",
    "from_json",
    "from_source",
    "generate",
    "instantiate",
    "list_languages",
    "prepare",
    "read_answer",
    "run",
    "to_file",
    "to_json",
]


def __dir__() -> list[str]:
    """Return the public surface, so tab-completion matches ``__all__``."""
    return sorted(__all__)
