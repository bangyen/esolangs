"""The public API with one language bound."""

from dataclasses import dataclass
from os import PathLike
from pathlib import Path

import esolangs
from esolangs.artifacts import Artifact, ProgramArtifact
from esolangs.registry import resolve
from esolangs.registry._describe import LanguageInfo
from esolangs.results import ExecutionResult
from esolangs.runtime._input import InputSource
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource
from esolangs.settings import DialectSettings, effective_settings


@dataclass(frozen=True, slots=True)
class Language:
    """Bind a canonical language name to the package's existing functions.

    Methods follow the package split by who supplies the program:
    ``generate``/``instantiate`` are generator-made, ``run`` executes
    caller-supplied source, ``encode_inputs``/``read_answer`` and
    ``dump_program``/``load_program`` are contract adapters, and
    ``describe`` is catalog.  Boolean evaluation is private machinery.
    """

    name: str

    def __post_init__(self) -> None:
        """Resolve the supplied name before any operation."""
        object.__setattr__(self, "name", resolve(self.name))

    def from_source(
        self, source: Program, *, settings: DialectSettings | None = None
    ) -> ProgramArtifact[Program]:
        """Declare runnable source, including text that resembles a filename.

        Parsing happens on execution. Use ``from_file`` to read native source.

        Raises:
            ProgramError: Source has an unsupported type or foreign provenance.
            ArgumentError: Dialect settings are invalid for this language.
        """
        retained = effective_settings(self.name, source, settings)
        return ProgramArtifact(source, self.name, retained)

    def from_file(
        self, path: str | PathLike[str], *, settings: DialectSettings | None = None
    ) -> ProgramArtifact[Program]:
        """Read native source with file newline handling and retained metadata.

        Raises:
            ArgumentError: Settings or the path argument are invalid.
            ProgramNotFoundError: The source file does not exist.
            ProgramError: Source cannot be decoded or belongs to another language.
            MissingDependencyError: PNG loading needs the image extra.
        """
        from esolangs.exceptions import ArgumentError
        from esolangs.settings import dialect_options

        dialect_options(self.name, settings)
        if not isinstance(path, (str, PathLike)):
            raise ArgumentError("path must be a string or Path")
        source = esolangs._read_source(self.name, Path(path))  # noqa: SLF001 - API boundary
        return self.from_source(source, settings=settings)

    def generate(
        self,
        truth_table: str,
        *,
        width: int | None = None,
        balance: bool = False,
        scale: int = 1,
        settings: DialectSettings | None = None,
    ) -> Program:
        """Return a program computing ``truth_table``.

        Arguments and errors: :func:`esolangs.generate`.
        """
        return esolangs.generate(
            self.name,
            truth_table,
            width=width,
            balance=balance,
            scale=scale,
            settings=settings,
        )

    def generate_artifact(
        self,
        truth_table: str,
        *,
        width: int | None = None,
        balance: bool = False,
        scale: int = 1,
        settings: DialectSettings | None = None,
    ) -> Artifact:
        """Build an explicit record; see :func:`esolangs.generate_artifact`."""
        return esolangs.generate_artifact(
            self.name,
            truth_table,
            width=width,
            balance=balance,
            scale=scale,
            settings=settings,
        )

    def load_artifact(self, document: str) -> Artifact:
        """Restore an explicit record; errors follow :func:`esolangs.load_artifact`."""
        return esolangs.load_artifact(self.name, document)

    def instantiate(
        self,
        template: Program | Artifact,
        bits: list[int] | tuple[int, ...],
        *,
        width: int | None = None,
        truth_table: str | None = None,
        settings: DialectSettings | None = None,
    ) -> str:
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
        )

    def dump_program(
        self, program: Program | Artifact, *, settings: DialectSettings | None = None
    ) -> str:
        """Return portable JSON retaining source and dialect choices.

        Arguments and errors: :func:`esolangs.dump_program`.
        """
        return esolangs.dump_program(self.name, program, settings=settings)

    def load_program(self, document: str) -> Program:
        """Restore portable JSON as this language's tagged source.

        Arguments and errors: :func:`esolangs.load_program`.
        """
        return esolangs.load_program(self.name, document)

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
    ) -> str:
        """Execute source.

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
        )

    def run_result(
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
        """Execute source and retain its metadata; see :func:`esolangs.run_result`."""
        return esolangs.run_result(
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
        )

    def describe(self) -> LanguageInfo:
        """Return this language's registry metadata and interpreter description.

        Arguments and errors: :func:`esolangs.describe`.
        """
        return esolangs.describe(self.name)

    def encode_inputs(
        self, bits: list[int] | tuple[int, ...], *, truth_table: str | None = None
    ) -> str:
        """Return the stdin encoding for ``bits``.

        Arguments and errors: :func:`esolangs.encode_inputs`.
        """
        return esolangs.encode_inputs(self.name, bits, truth_table=truth_table)

    def read_answer(self, output: str) -> str:
        """Extract the answer bit from raw output.

        Arguments and errors: :func:`esolangs.read_answer`.
        """
        return esolangs.read_answer(self.name, output)
