"""The public API with one language bound."""

from __future__ import annotations

from dataclasses import dataclass, field
from os import PathLike

import esolangs
from esolangs._dialect import Scalar
from esolangs.artifacts import Artifact, BooleanEvaluation, ProgramArtifact
from esolangs.debugger import Debugger, make_debugger, make_vm
from esolangs.limits import ExecutionLimits
from esolangs.operations.prepared import PreparedProgram
from esolangs.outcomes import ExecutionOutcome
from esolangs.planning import Ready, Unsupported
from esolangs.registry import Catalog, get_catalog
from esolangs.registry._info import LanguageInfo
from esolangs.runtime._input import InputSource
from esolangs.runtime._program import Program
from esolangs.runtime._source import ProgramSource
from esolangs.runtime._vm_protocol import VM
from esolangs.settings import DialectSettings


@dataclass(frozen=True, slots=True)
class Language:
    """Bind a canonical language name to one immutable catalog.

    Operations inherit the bound dialect unless given explicit settings.
    """

    name: str
    catalog: Catalog = field(default_factory=get_catalog, kw_only=True, repr=False)
    dialect: DialectSettings | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        """Resolve the supplied name before any operation.

        Raises:
            UnknownLanguageError: ``name`` is not registered.
            ArgumentError: ``name`` is not a string.
        """
        object.__setattr__(self, "catalog", get_catalog(self.catalog))
        object.__setattr__(self, "name", self.catalog.resolve(self.name))
        if self.dialect is not None:
            from esolangs.settings import dialect_options

            dialect_options(self.name, self.dialect, catalog=self.catalog)

    def settings(self, /, **choices: Scalar) -> DialectSettings:
        """Return overrides validated within this language's dialect schema.

        Its keywords are the dialect's own names, ``catalog`` included, so it
        has no module-level twin: that would need a ``catalog`` argument.

        Raises:
            ArgumentError: A choice is unknown or outside its declared values.
        """
        from esolangs.settings import _settings_for

        return _settings_for(self.name, choices, catalog=self.catalog)

    def from_source(
        self, source: Program, *, settings: DialectSettings | None = None
    ) -> ProgramArtifact[Program]:
        """Declare runnable source, including text that resembles a filename.

        Arguments and errors: :func:`esolangs.from_source`.
        """
        return esolangs.from_source(
            self.name,
            source,
            settings=self.dialect if settings is None else settings,
            catalog=self.catalog,
        )

    def from_file(
        self,
        path: str | PathLike[str],
        *,
        settings: DialectSettings | None = None,
        normalize: bool = False,
    ) -> ProgramArtifact[Program]:
        """Read lossless source with retained metadata.

        Arguments and errors: :func:`esolangs.from_file`.
        """
        return esolangs.from_file(
            self.name,
            path,
            settings=self.dialect if settings is None else settings,
            normalize=normalize,
            catalog=self.catalog,
        )

    def from_json(self, document: str) -> Artifact:
        """Restore portable JSON as this language's program or template artifact.

        Arguments and errors: :func:`esolangs.from_json`.
        """
        return esolangs.from_json(self.name, document, catalog=self.catalog)

    def to_file(
        self,
        program: ProgramSource,
        path: str | PathLike[str],
        *,
        settings: DialectSettings | None = None,
        gzip: bool = False,
        normalize: bool = False,
    ) -> None:
        """Write a program as a native source file.

        Arguments and errors: :func:`esolangs.to_file`.
        """
        esolangs.to_file(
            self.name,
            program,
            path,
            settings=self.dialect if settings is None else settings,
            gzip=gzip,
            normalize=normalize,
            catalog=self.catalog,
        )

    def to_json(
        self, program: ProgramSource, *, settings: DialectSettings | None = None
    ) -> str:
        """Return portable JSON retaining source and dialect choices.

        Arguments and errors: :func:`esolangs.to_json`.
        """
        return esolangs.to_json(
            self.name,
            program,
            settings=self.dialect if settings is None else settings,
            catalog=self.catalog,
        )

    def prepare(
        self,
        program: ProgramSource,
        *,
        settings: DialectSettings | None = None,
        scale: int | None = None,
    ) -> PreparedProgram:
        """Load reusable source; each run or VM owns fresh IO, state and randomness.

        Arguments and errors: :func:`esolangs.prepare`.
        """
        return esolangs.prepare(
            self.name,
            program,
            settings=self.dialect if settings is None else settings,
            scale=scale,
            catalog=self.catalog,
        )

    def plan_generation(
        self,
        truth_table: str,
        *,
        width: int | None = None,
        balance: bool = False,
        scale: int | None = None,
        settings: DialectSettings | None = None,
    ) -> Ready | Unsupported:
        """Return a ready construction or its table-specific limit.

        Planning performs generation once, including layout and compression.
        Invalid requests still raise their usual errors.
        """
        return esolangs.plan_generation(
            self.name,
            truth_table,
            width=width,
            balance=balance,
            scale=scale,
            settings=self.dialect if settings is None else settings,
            catalog=self.catalog,
        )

    def generate(
        self,
        truth_table: str,
        *,
        width: int | None = None,
        balance: bool = False,
        scale: int | None = None,
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
            settings=self.dialect if settings is None else settings,
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

        Arguments and errors: :func:`esolangs.evaluate`.
        """
        return esolangs.evaluate(
            self.name, artifact, bits, limits=limits, catalog=self.catalog
        )

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
            settings=self.dialect if settings is None else settings,
            catalog=self.catalog,
        )

    def run(
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

        Arguments and errors: :func:`esolangs.run`.
        """
        return esolangs.run(
            self.name,
            program,
            stdin=stdin,
            limits=limits,
            seed=seed,
            isolated=isolated,
            settings=self.dialect if settings is None else settings,
            scale=scale,
            catalog=self.catalog,
        )

    def make_vm(
        self,
        program: ProgramSource,
        *,
        stdin: InputSource = "",
        seed: int | None = None,
        settings: DialectSettings | None = None,
        scale: int | None = None,
    ) -> VM:
        """Return a step-and-inspect machine over ``program``.

        Arguments and errors: :func:`esolangs.debugger.make_vm`.
        """
        return make_vm(
            self.name,
            program,
            stdin=stdin,
            seed=seed,
            settings=self.dialect if settings is None else settings,
            scale=scale,
            catalog=self.catalog,
        )

    def make_debugger(
        self,
        program: ProgramSource,
        *,
        stdin: InputSource = "",
        seed: int | None = None,
        settings: DialectSettings | None = None,
        scale: int | None = None,
    ) -> Debugger:
        """Return a debugger over a fresh machine for ``program``.

        Arguments and errors: :func:`esolangs.debugger.make_debugger`.
        """
        return make_debugger(
            self.name,
            program,
            stdin=stdin,
            seed=seed,
            settings=self.dialect if settings is None else settings,
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
