"""Generate programs, run supplied source, and describe languages.

Public operations split by who supplies the program:

* Generator-made: ``generate`` returns a program artifact or template;
  ``instantiate`` fills a template into a runnable artifact.
  An artifact's ``evaluate`` method executes one Boolean row.
* Caller-supplied: ``run`` returns output, input consumption and completion
  evidence in an immutable execution result.
  Stepping and debugging live in :mod:`esolangs.debugger`.
* Contract adapters: ``encode_inputs`` spells input bits as stdin,
  ``read_answer`` extracts an answer bit from output,
  ``to_file`` writes native source files, and
  ``dump_program``/``load_program`` preserve source in portable JSON.
* Catalog: ``describe`` and ``list_languages`` provide registry facts.

Boolean evaluation over every row is private certification machinery,
not public API.  ``Language(name)`` binds these functions to one language
and adds its own: ``execute`` (an outcome instead of a raise), ``evaluate``,
``prepare``, ``from_source``/``from_file`` and ``settings``.
Names resolve case-insensitively; deliberate errors derive from EsolangError.
"""

import importlib
from typing import TYPE_CHECKING

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
from esolangs.settings import DialectSettings

_LAZY = {
    "Catalog": "esolangs.registry._catalog",
    "PreparedProgram": "esolangs.runtime._prepared",
    "Language": "esolangs._language",
    "run": "esolangs.operations.execution",
    "generate": "esolangs.operations.generation",
    "instantiate": "esolangs.operations.generation",
    "dump_program": "esolangs.portable",
    "load_program": "esolangs.portable",
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
    from esolangs.operations.execution import run as run
    from esolangs.operations.generation import generate as generate
    from esolangs.operations.generation import instantiate as instantiate
    from esolangs.portable import dump_program as dump_program
    from esolangs.portable import load_program as load_program
    from esolangs.portable import to_file as to_file
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
    "dump_program",
    "encode_inputs",
    "generate",
    "instantiate",
    "list_languages",
    "load_program",
    "read_answer",
    "run",
    "to_file",
]


def __dir__() -> list[str]:
    """Return the public surface, so tab-completion matches ``__all__``."""
    return sorted(__all__)
