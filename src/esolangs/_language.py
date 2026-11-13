"""The public API with one language bound."""

from __future__ import annotations

from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path

import esolangs
import esolangs.operations.source as _source_operations
from esolangs.artifacts import (
    Artifact,
    BooleanEvaluation,
    ProgramArtifact,
    TemplateArtifact,
)
from esolangs.limits import ExecutionLimits
from esolangs.outcomes import ExecutionOutcome
from esolangs.registry import Catalog, get_catalog
from esolangs.registry._info import LanguageInfo
from esolangs.results import ExecutionResult
from esolangs.runtime._input import InputSource
from esolangs.runtime._prepared import PreparedProgram, prepare_program
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource
from esolangs.settings import DialectSettings, effective_settings


@dataclass(frozen=True, slots=True)
class Language:
    """Bind a canonical language name to one immutable catalog.

    Methods follow the package split by who supplies the program:
    ``generate``/``instantiate`` are generator-made, ``run`` executes
    caller-supplied source, ``encode_inputs``/``read_answer`` and
    ``dump_program``/``load_program``/``save_program`` are contract adapters, and
    ``describe`` is catalog. ``evaluate`` runs one Boolean row.
    """

    name: str
    catalog: Catalog = field(default_factory=get_catalog, kw_only=True, repr=False)

    def __post_init__(self) -> None:
        """Resolve the supplied name before any operation.

        Raises:
            UnknownLanguageError: ``name`` is not registered.
            ArgumentError: ``name`` is not a string.
        """
        object.__setattr__(self, "catalog", get_catalog(self.catalog))
        object.__setattr__(self, "name", self.catalog.resolve(self.name))

    def settings(self, **choices: int | str) -> DialectSettings:
        """Return overrides validated within this language's dialect schema.

        Raises:
            ArgumentError: A choice is unknown or outside its declared values.
        """
        from esolangs.settings import _settings_for

        return _settings_for(self.name, choices, catalog=self.catalog)

    def from_source(
        self, source: Program, *, settings: DialectSettings | None = None
    ) -> ProgramArtifact[Program]:
        """Declare runnable source, including text that resembles a filename.

        Parsing happens on execution. Use ``from_file`` to read native source.

        Raises:
            TemplateError: Source is an unfilled template.
            ProgramError: Source has an unsupported type, such as a program
                artifact (pass its ``.source``).
            ArgumentError: Dialect settings are invalid for this language.
        """
        from esolangs.exceptions import ProgramError

        if isinstance(source, ProgramArtifact):
            raise ProgramError(
                f"from_source takes source, not a {source.language} artifact; "
                "pass its .source"
            )
        retained = effective_settings(self.name, source, settings, catalog=self.catalog)
        return ProgramArtifact(source, self.name, retained)

    def from_file(
        self,
        path: str | PathLike[str],
        *,
        settings: DialectSettings | None = None,
        normalize: bool = False,
    ) -> ProgramArtifact[Program]:
        """Read lossless source with retained metadata.

        ``normalize=True`` applies the language's native file newline policy.

        Raises:
            ArgumentError: Settings or the path argument are invalid.
            ProgramNotFoundError: The source file does not exist.
            ProgramError: Source cannot be decoded or belongs to another language.
            MissingDependencyError: PNG loading needs the image extra.
        """
        from esolangs.exceptions import ArgumentError
        from esolangs.runtime._validate import check_flag
        from esolangs.settings import dialect_options

        check_flag(normalize, "normalize")
        dialect_options(self.name, settings, catalog=self.catalog)
        if not isinstance(path, (str, PathLike)):
            raise ArgumentError(
                f"path must be a str or PathLike, got {type(path).__name__}"
            )
        artifact = _source_operations.read_artifact(
            self.name, Path(path), catalog=self.catalog, normalize=normalize
        )
        retained = effective_settings(
            self.name, artifact, settings, catalog=self.catalog
        )
        assert isinstance(artifact, ProgramArtifact)
        return ProgramArtifact(artifact.source, self.name, retained, artifact.scale)

    def prepare(
        self,
        program: ProgramSource,
        *,
        settings: DialectSettings | None = None,
        scale: int | None = None,
    ) -> PreparedProgram:
        """Load reusable source; each run or VM owns fresh IO, state and randomness.

        Arguments and errors: :func:`esolangs.run`.
        """
        return prepare_program(
            self.name,
            program,
            settings=settings,
            scale=scale,
            catalog=self.catalog,
            bind_machine=True,
        )

    def generate(
        self,
        truth_table: str,
        *,
        width: int | None = None,
        balance: bool = False,
        scale: int = 1,
        settings: DialectSettings | None = None,
    ) -> Artifact:
        """Return a program artifact or template computing ``truth_table``.

        Arguments and errors: :func:`esolangs.generate`.
        """
        return esolangs.generate(
            self.name,
            truth_table,
            width=width,
            balance=balance,
            scale=scale,
            settings=settings,
            catalog=self.catalog,
        )

    def evaluate(
        self,
        artifact: Artifact,
        bits: list[int] | tuple[int, ...],
        *,
        limits: ExecutionLimits | None = None,
    ) -> BooleanEvaluation:
        """Run one Boolean row and return its answer and execution evidence.

        Raises:
            ProgramError: ``artifact`` is not an artifact, or belongs to
                another language.
            ArgumentError: ``bits`` is not one 0 or 1 per input.
            EsolangError: Any error :func:`esolangs.run` raises for the row.
        """
        from esolangs.exceptions import ProgramError
        from esolangs.operations.evaluation import evaluate

        if not isinstance(artifact, (ProgramArtifact, TemplateArtifact)):
            raise ProgramError("evaluation requires a program or template artifact")
        if self.catalog.resolve(artifact.language) != self.name:
            raise ProgramError(
                f"artifact belongs to {artifact.language}, not {self.name}"
            )
        return evaluate(artifact, bits, limits=limits, catalog=self.catalog)

    def instantiate(
        self,
        template: Artifact,
        bits: list[int] | tuple[int, ...],
        *,
        width: int | None = None,
        truth_table: str | None = None,
        settings: DialectSettings | None = None,
    ) -> ProgramArtifact[str]:
        """Fill a parameterized template with ``bits``.

        Arguments and errors: :func:`esolangs.instantiate`.
        """
        return esolangs.instantiate(
            self.name,
            template,
            bits,
            width=width,
            truth_table=truth_table,
            settings=settings,
            catalog=self.catalog,
        )

    def dump_program(
        self, program: ProgramSource, *, settings: DialectSettings | None = None
    ) -> str:
        """Return portable JSON retaining source and dialect choices.

        Arguments and errors: :func:`esolangs.dump_program`.
        """
        return esolangs.dump_program(
            self.name, program, settings=settings, catalog=self.catalog
        )

    def load_program(self, document: str) -> Artifact:
        """Restore portable JSON as this language's program or template artifact.

        Arguments and errors: :func:`esolangs.load_program`.
        """
        return esolangs.load_program(self.name, document, catalog=self.catalog)

    def save_program(
        self,
        program: ProgramSource,
        path: str | PathLike[str],
        *,
        gzip: bool = False,
        normalize: bool = False,
    ) -> None:
        """Write a program as a native source file.

        Arguments and errors: :func:`esolangs.save_program`.
        """
        esolangs.save_program(
            self.name,
            program,
            path,
            gzip=gzip,
            normalize=normalize,
            catalog=self.catalog,
        )

    def execute(
        self,
        program: ProgramSource,
        *,
        stdin: InputSource = "",
        limits: ExecutionLimits | None = None,
        seed: int | None = None,
        isolated: bool = False,
        settings: DialectSettings | None = None,
        scale: int | None = None,
    ) -> ExecutionOutcome:
        """Return completion, rejection, input exhaustion, fault or limit evidence.

        Total deadlines and output/memory caps select isolation. Execution
        deadlines bound reading the program and stdin, and execution, each
        separately; total deadlines also include worker startup.
        Use outcome.unwrap() for the exception-raising result convention.

        Raises nothing deliberate: each package error is the outcome's
        ``error``, with status ``rejected``, ``input_exhausted``, ``limit``
        or ``fault``.
        """
        from esolangs.operations.execution import _execute_outcome

        return _execute_outcome(
            self.name,
            program,
            stdin=stdin,
            limits=limits,
            seed=seed,
            isolated=isolated,
            settings=settings,
            scale=scale,
            catalog=self.catalog,
        )

    def run(
        self,
        program: ProgramSource,
        *,
        stdin: InputSource = "",
        timeout: float | None = None,
        seed: int | None = None,
        isolated: bool = False,
        max_steps: int | None = None,
        max_output: int | None = None,
        max_memory: int | None = None,
        settings: DialectSettings | None = None,
        scale: int | None = None,
    ) -> ExecutionResult:
        """Execute source and return output, input usage and completion evidence.

        Arguments and errors: :func:`esolangs.run`.
        """
        return esolangs.run(
            self.name,
            program,
            stdin=stdin,
            timeout=timeout,
            seed=seed,
            isolated=isolated,
            max_steps=max_steps,
            max_output=max_output,
            max_memory=max_memory,
            settings=settings,
            scale=scale,
            catalog=self.catalog,
        )

    def describe(self) -> LanguageInfo:
        """Return this language's registry metadata and interpreter description.

        Arguments and errors: :func:`esolangs.describe`.
        """
        return esolangs.describe(self.name, catalog=self.catalog)

    def encode_inputs(
        self, bits: list[int] | tuple[int, ...], *, truth_table: str | None = None
    ) -> str:
        """Return the stdin encoding for ``bits``.

        Arguments and errors: :func:`esolangs.encode_inputs`.
        """
        return esolangs.encode_inputs(
            self.name, bits, truth_table=truth_table, catalog=self.catalog
        )

    def read_answer(self, output: str) -> str:
        """Extract the answer bit from raw output.

        Arguments and errors: :func:`esolangs.read_answer`.
        """
        return esolangs.read_answer(self.name, output, catalog=self.catalog)
