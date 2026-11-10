"""Generate programs, run supplied source, and describe languages.

Public operations split by who supplies the program:

* Generator-made: ``generate`` returns a program artifact or template;
  ``instantiate`` fills a template into a runnable artifact.
* Caller-supplied: ``run`` returns output, input consumption and completion
  evidence in an immutable execution result.
  Stepping and debugging live in :mod:`esolangs.debugger`.
* Contract adapters: ``encode_inputs`` spells input bits as stdin,
  ``read_answer`` extracts an answer bit from output,
  ``save_program`` writes native source files, and
  ``dump_program``/``load_program`` preserve source in portable JSON.
* Catalog: ``describe`` and ``list_languages`` provide registry facts.

Boolean evaluation over every row is private certification machinery,
not public API.  ``Language(name)`` binds these functions to one language.
Names resolve case-insensitively; deliberate errors derive from EsolangError.
"""

import importlib
from typing import TYPE_CHECKING

from esolangs.artifacts import (
    Artifact,
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.compressed import CompressedText, TextLimits
from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
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
from esolangs.raster import Raster
from esolangs.results import ExecutionResult
from esolangs.runtime._input import InputSource
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource
from esolangs.settings import DialectSettings

_LAZY = {
    "Catalog": "esolangs.registry._catalog",
    "Language": "esolangs._language",
    "run": "esolangs.operations.execution",
    "generate": "esolangs.operations.generation",
    "instantiate": "esolangs.operations.generation",
    "dump_program": "esolangs.portable",
    "load_program": "esolangs.portable",
    "save_program": "esolangs.portable",
    "LanguageInfo": "esolangs.registry._describe",
    "describe": "esolangs.registry._describe",
    "list_languages": "esolangs.registry._describe",
    "encode_inputs": "esolangs.runtime._answers",
    "read_answer": "esolangs.runtime._answers",
}

if TYPE_CHECKING:
    __version__: str
    from esolangs._language import Language as Language
    from esolangs.operations.execution import run as run
    from esolangs.operations.generation import generate as generate
    from esolangs.operations.generation import instantiate as instantiate
    from esolangs.portable import dump_program as dump_program
    from esolangs.portable import load_program as load_program
    from esolangs.portable import save_program as save_program
    from esolangs.registry._catalog import Catalog as Catalog
    from esolangs.registry._describe import LanguageInfo as LanguageInfo
    from esolangs.registry._describe import describe as describe
    from esolangs.registry._describe import list_languages as list_languages
    from esolangs.runtime._answers import encode_inputs as encode_inputs
    from esolangs.runtime._answers import read_answer as read_answer
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
#: alongside the six functions anyone wants, and there was no way to tell
#: from the outside which was which.
__all__ = [
    "ArgumentError",
    "Artifact",
    "Catalog",
    "CompressedText",
    "DialectSettings",
    "EsolangError",
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
    "save_program",
]


def __dir__() -> list[str]:
    """Return the public surface, so tab-completion matches ``__all__``."""
    return sorted(__all__)
