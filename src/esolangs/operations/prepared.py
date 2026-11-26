"""Public operations on reusable interpreter preparation."""

from __future__ import annotations

from dataclasses import dataclass

from esolangs.artifacts import BooleanEvaluation, ProgramArtifact
from esolangs.debugger import Debugger
from esolangs.exceptions import ProgramError
from esolangs.limits import ExecutionLimits
from esolangs.outcomes import ExecutionOutcome

# The generated initializer resolves the base dataclass's annotations here.
from esolangs.registry._catalog import Catalog as Catalog
from esolangs.registry._catalog import get_catalog, resolve_origin
from esolangs.results import ExecutionResult
from esolangs.runtime._artifact_source import check_program
from esolangs.runtime._input import InputSource
from esolangs.runtime._prepared import _PreparedRuntime
from esolangs.runtime._program import Program as Program
from esolangs.runtime._source import check_scale_for
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime._vm_protocol import VM


@dataclass(frozen=True, slots=True)
class PreparedProgram(_PreparedRuntime):
    """Loaded source and bound runtime; every invocation owns its IO and RNG.

    Source decoding and language resolution happen once. Runtime plans retain
    language-owned parsed data and bind fresh randomness for each invocation;
    other hooks may defer parsing.
    Native runners retain their own compiled representations and caches.
    The public artifact retains compressed source and its export limits.
    """

    def __post_init__(self) -> None:
        """Validate source and retain its machine preparation."""
        if not _has_backing_type(self.artifact, ProgramArtifact):
            raise ProgramError("a prepared program requires a program artifact")
        catalog = get_catalog(self.catalog)
        origin = self.artifact.language
        name = resolve_origin(origin, catalog=catalog)
        artifact = check_program(
            name or origin,
            self.artifact,
            catalog=catalog,
            preserve_compression=True,
        )
        check_scale_for(artifact.language, artifact.scale, catalog=catalog)
        self._bind_artifact(artifact, catalog)
        self._bind_machine()

    def execute(
        self,
        *,
        stdin: InputSource = "",
        limits: ExecutionLimits | None = None,
        seed: int | None = None,
        isolated: bool = False,
    ) -> ExecutionOutcome:
        """Return a fresh invocation's outcome; preparation already happened."""
        from esolangs.operations.execution import _execute_outcome

        return _execute_outcome(
            self.language,
            self._runnable_artifact,
            stdin=stdin,
            limits=limits,
            seed=seed,
            isolated=isolated,
            catalog=self.catalog,
            prepared=self,
        )

    def evaluate(
        self,
        bits: list[int] | tuple[int, ...],
        *,
        limits: ExecutionLimits | None = None,
    ) -> BooleanEvaluation:
        """Evaluate a generated stdin row against the retained preparation."""
        from esolangs.operations.evaluation import evaluate_artifact

        return evaluate_artifact(
            self._runnable_artifact,
            bits,
            limits=limits,
            catalog=self.catalog,
            prepared=self,
        )

    def run(
        self,
        *,
        stdin: InputSource = "",
        limits: ExecutionLimits | None = None,
        seed: int | None = None,
        isolated: bool = False,
    ) -> ExecutionResult:
        """Run fresh state; arguments and errors follow :func:`esolangs.run`."""
        return self.execute(
            stdin=stdin, limits=limits, seed=seed, isolated=isolated
        ).unwrap()

    def make_debugger(
        self, *, stdin: InputSource = "", seed: int | None = None
    ) -> Debugger:
        """Wrap a fresh step machine in a debugger; errors follow make_vm."""
        return Debugger(self.make_vm(stdin=stdin, seed=seed))

    def make_vm(self, *, stdin: InputSource = "", seed: int | None = None) -> VM:
        """Create an independent step machine; errors follow debugger.make_vm."""
        from esolangs.vm import _make_vm

        return _make_vm(
            self.language,
            self._runnable_artifact,
            stdin=stdin,
            seed=seed,
            catalog=self.catalog,
            prepared=self,
        )
