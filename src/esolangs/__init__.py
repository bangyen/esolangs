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

from esolangs._language import Language
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
from esolangs.operations.execution import run
from esolangs.operations.generation import generate, instantiate
from esolangs.portable import dump_program, load_program, save_program
from esolangs.raster import Raster
from esolangs.registry._describe import LanguageInfo, describe, list_languages
from esolangs.results import ExecutionResult
from esolangs.runtime._answers import encode_inputs, read_answer
from esolangs.runtime._input import InputSource
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource
from esolangs.settings import DialectSettings

#: From the installed distribution (a hand-kept copy said 0.1.0 at 0.2.0);
#: the fallback covers an uninstalled tree.  Read on first access, not
#: import: ``importlib.metadata`` was 23ms of the 56ms import (PEP 562).
#: Hidden from type checkers, which otherwise typed ``esolangs.generat`` as
#: ``str`` and ``from esolangs import generat`` as ``Any``.
if TYPE_CHECKING:
    __version__: str
else:

    def __getattr__(name: str) -> str:
        """Resolve ``__version__`` lazily; everything else is a normal miss."""
        if name != "__version__":
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        import importlib.metadata

        try:
            version = importlib.metadata.version("esolangs")
        except importlib.metadata.PackageNotFoundError:  # pragma: no cover
            # A source tree that was never installed.
            version = "0.0.0+unknown"
        globals()["__version__"] = version
        return version


#: The public surface.  Without it ``dir(esolangs)`` advertised ``Any``,
#: ``Callable``, ``importlib``, ``pathlib``, ``signal`` and ``threading``
#: alongside the six functions anyone wants, and there was no way to tell
#: from the outside which was which.
__all__ = [
    "ArgumentError",
    "Artifact",
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
