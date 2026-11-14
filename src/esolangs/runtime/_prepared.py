"""Reusable source preparation, independent of invocation state and Boolean I/O."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from types import ModuleType
from typing import Any, cast

from esolangs.artifacts import BooleanEvaluation, ProgramArtifact
from esolangs.debugger import Debugger
from esolangs.limits import ExecutionLimits
from esolangs.outcomes import ExecutionOutcome
from esolangs.registry._catalog import Catalog, get_catalog
from esolangs.results import ExecutionResult
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._execution import (
    execute_prepared,
    execution_options,
    interpreter_errors,
    interpreter_module,
    prepare_call,
)
from esolangs.runtime._input import InputSource
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import (
    MachineFactory,
    MachinePreparation,
    RandomRuntimePlan,
    RuntimePlan,
)
from esolangs.runtime._program import Program, RunnerProgram
from esolangs.runtime._source import ProgramSource, check_scale_for, effective_scale
from esolangs.runtime._vm_protocol import VM
from esolangs.runtime.io import ScriptedIO
from esolangs.settings import DialectSettings, dialect_options, effective_settings


@dataclass(frozen=True, slots=True)
class PreparedProgram:
    """Loaded source and bound runtime; every invocation owns its IO and RNG.

    Source decoding and language resolution happen once. Runtime plans retain
    language-owned parsed data and bind fresh randomness for each invocation;
    other hooks may defer parsing.
    Native runners retain their own compiled representations and caches.
    """

    artifact: ProgramArtifact[Program]
    catalog: Catalog = field(repr=False)
    _module: ModuleType = field(init=False, repr=False, compare=False)
    _code: Program | tuple[str, ...] = field(init=False, repr=False, compare=False)
    _source_options: tuple[tuple[str, Any], ...] = field(
        init=False, repr=False, compare=False
    )
    _plan: RuntimePlan | RandomRuntimePlan | None = field(
        default=None, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        """Retain validated dialect options and immutable shaped source."""
        with interpreter_errors(
            f"the {self.language} interpreter recursed deeper than CPython's "
            "stack limit allows while loading this program",
            language=self.language,
        ):
            module = interpreter_module(self.language, catalog=self.catalog)
        object.__setattr__(self, "_module", module)
        code, options = prepare_call(
            self.language,
            self.artifact.source,
            ExecutionContext(
                scale=self.artifact.scale, settings=self.artifact.settings
            ),
            catalog=self.catalog,
        )
        object.__setattr__(
            self, "_code", tuple(code) if isinstance(code, list) else code
        )
        object.__setattr__(self, "_source_options", tuple(options.items()))

    @property
    def language(self) -> str:
        """The canonical language owning this program."""
        return self.artifact.language

    def _options(
        self, *, seed: int | None = None, reproducible: bool = False
    ) -> dict[str, Any]:
        return dict(self._source_options) | execution_options(
            self.language,
            ExecutionContext(seed=seed, reproducible=reproducible),
            catalog=self.catalog,
        )

    def _call(
        self, *, seed: int | None = None, reproducible: bool = False
    ) -> tuple[RunnerProgram, dict[str, Any]]:
        code = list(self._code) if isinstance(self._code, tuple) else self._code
        return code, self._options(seed=seed, reproducible=reproducible)

    def _factory(self, *, seed: int | None = None) -> MachineFactory:
        runtime = self.catalog.languages[self.language].runtime
        if isinstance(self._plan, RuntimePlan):
            return self._plan
        if isinstance(self._plan, RandomRuntimePlan):
            options = self._options(seed=seed, reproducible=True)
            return self._plan.bind(options.get("rng"))
        code, options = self._call(seed=seed, reproducible=True)
        prepare = cast(
            MachinePreparation, getattr(self._module, runtime.machine_preparation)
        )
        plan = prepare(code, options)
        # Keep only the read-only origin of an RNG-bound invocation plan.
        if isinstance(plan, RuntimePlan):
            if runtime.random and plan.random_source is not None:
                object.__setattr__(self, "_plan", plan.random_source)
            elif not runtime.random and plan.random_source is None:
                object.__setattr__(self, "_plan", plan)
        return plan

    def _execute_native(
        self,
        stdin: InputSource,
        *,
        seed: int | None,
        io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    ) -> ExecutionOutcome:
        runtime = self.catalog.languages[self.language].runtime
        if self._plan is None:
            code, options = self._call(seed=seed)
        else:
            code, options = self.artifact.source, self._options(seed=seed)
        if isinstance(self._plan, RandomRuntimePlan):
            runner = partial(_run_plan, self._plan.bind(options.get("rng")))
        elif isinstance(self._plan, RuntimePlan):
            runner = partial(_run_plan, self._plan)
        else:
            runner = getattr(self._module, runtime.completion_entrypoint)
            if options:
                runner = partial(runner, **options)
        return execute_prepared(
            self.language,
            runner,
            code,
            io_factory(stdin),
            catalog=self.catalog,
        )

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
            self.artifact,
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
            self.artifact, bits, limits=limits, catalog=self.catalog, prepared=self
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
            self.artifact,
            stdin=stdin,
            seed=seed,
            catalog=self.catalog,
            prepared=self,
        )


def prepare_program(
    language: str,
    program: ProgramSource,
    *,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
    module_loader: Callable[..., ModuleType] = interpreter_module,
    bind_machine: bool = False,
) -> PreparedProgram:
    """Load source once, resolving provenance and explicit execution choices."""
    from esolangs.operations.source import _check_program

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    settings = effective_settings(name, program, settings, catalog=catalog)
    dialect_options(name, settings, catalog=catalog)
    scale = effective_scale(name, program, scale, catalog=catalog)
    artifact = _check_program(name, program, catalog=catalog)
    settings = effective_settings(name, artifact, settings, catalog=catalog)
    scale = effective_scale(name, artifact, scale, catalog=catalog)
    check_scale_for(name, scale, catalog=catalog)
    prepared = PreparedProgram(
        ProgramArtifact(
            artifact.source,
            name,
            settings=settings,
            scale=scale,
            input_arity=artifact.input_arity,
        ),
        catalog,
    )
    if module_loader is not interpreter_module:
        # A caller's own loader (tests replace one route's) wins over the
        # default the constructor resolved.
        with interpreter_errors(
            f"the {name} interpreter recursed deeper than CPython's stack "
            "limit allows while loading this program",
            language=name,
        ):
            module = module_loader(name, catalog=catalog)
        object.__setattr__(prepared, "_module", module)
    if bind_machine:
        with interpreter_errors(
            f"the {name} interpreter recursed deeper than CPython's stack "
            "limit allows while preparing this program",
            language=name,
        ):
            prepared._factory()  # noqa: SLF001 - preparation owns the plan
    return prepared


def _run_plan(
    plan: RuntimePlan, _source: RunnerProgram, io: ScriptedIO
) -> CompletionReport:
    """Adapt a language-owned plan to the shared completion/error guard."""
    return plan.run(io)
