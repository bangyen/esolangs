"""Reusable source preparation, independent of invocation state and Boolean I/O."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from types import FunctionType, ModuleType
from typing import TYPE_CHECKING, Any, Self, cast

from esolangs._dialect import Scalar
from esolangs.artifacts import ProgramArtifact
from esolangs.compressed import CompressedText
from esolangs.exceptions import InterpreterLimitError
from esolangs.outcomes import ExecutionOutcome
from esolangs.registry._catalog import Catalog, get_catalog
from esolangs.runtime._acquire import PendingInput
from esolangs.runtime._artifact_source import check_program
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._execution import (
    execute_prepared,
    execution_options,
    interpreter_module,
    prepare_call,
    runtime_hook,
)
from esolangs.runtime._input import CheckedInput, InputSource, RecordFrame
from esolangs.runtime._interpreter_errors import interpreter_errors
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import (
    MachineFactory,
    MachinePreparation,
    RandomRuntimePlan,
    RuntimePlan,
)
from esolangs.runtime._program import Program, RunnerProgram
from esolangs.runtime._source import (
    ProgramSource,
    anchor_program_source,
    check_scale_for,
    effective_scale,
    source_for,
)
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime.io import ScriptedIO, _scripted_io
from esolangs.settings import DialectSettings, effective_settings

if TYPE_CHECKING:
    from esolangs.runtime._definition import RuntimeSpec


def _runtime_reads_stdin(runtime: RuntimeSpec) -> bool:
    """Keep stdin available to custom hooks that may change input behavior."""
    if runtime.completion_entrypoint is None:
        return runtime.reads_stdin
    return runtime.reads_stdin or not runtime.uses_native_plan


def _scoped_dialect_defaults(
    runtime: RuntimeSpec, module: ModuleType
) -> dict[str, Scalar]:
    schema = runtime.dialect_schema
    if schema is None:
        return {}
    if runtime.completion_entrypoint is None:
        return schema.defaults
    plan = runtime.native_plan
    if plan is None or not runtime.uses_native_plan:
        runner = vars(module).get(str.__str__(runtime.completion_entrypoint))
        if type(runner) is not FunctionType:
            return {}
        code = runner.__code__
        end = code.co_argcount
        start = max(min(2, end), code.co_posonlyargcount)
        # A native runner receives source and IO positionally.
        names = code.co_varnames[start : end + code.co_kwonlyargcount]
        return {key: value for key, value in schema.defaults.items() if key in names}
    original = plan.schema
    if original is None or original is schema:
        return {}
    # Only keys already consumed by this interpreter belong in its options.
    built_in = original.defaults
    return {
        key: value
        for key, value in schema.defaults.items()
        if key in built_in and value != built_in[key]
    }


def _artifact_input_frame(
    artifact: ProgramArtifact[Program], catalog: Catalog
) -> RecordFrame | None:
    """Only explicitly framed languages bind input using their artifact arity."""
    contract = catalog.languages[artifact.language].contract
    return contract.input_frame(artifact.input_arity)


@dataclass(frozen=True, slots=True)
class _PreparedRuntime:
    """Bind checked source to its native runner and step machine."""

    artifact: ProgramArtifact[Program]
    catalog: Catalog = field(repr=False)
    _module: ModuleType = field(init=False, repr=False, compare=False)
    _runnable_artifact: ProgramArtifact[Program] = field(
        init=False, repr=False, compare=False
    )
    _code: Program | tuple[str, ...] = field(init=False, repr=False, compare=False)
    _dialect_defaults: tuple[tuple[str, Scalar], ...] = field(
        init=False, repr=False, compare=False
    )
    _source_options: tuple[tuple[str, Any], ...] = field(
        init=False, repr=False, compare=False
    )
    _plan: RuntimePlan | RandomRuntimePlan | None = field(
        default=None, init=False, repr=False, compare=False
    )

    @classmethod
    def _from_checked(
        cls, artifact: ProgramArtifact[Program], catalog: Catalog
    ) -> Self:
        """Bind a source whose runtime options were checked before acquisition."""
        prepared = object.__new__(cls)
        object.__setattr__(prepared, "_plan", None)
        prepared._bind_artifact(artifact, catalog)
        return prepared

    def _bind_artifact(
        self, artifact: ProgramArtifact[Program], catalog: Catalog
    ) -> None:
        """Shape validated source and bind its runtime."""
        source = artifact.source
        if _has_backing_type(source, CompressedText):
            source = source_for(artifact.language, source, catalog=catalog)
        runnable = artifact
        if source is not artifact.source:
            runnable = ProgramArtifact(
                source,
                artifact.language,
                settings=artifact.settings,
                scale=artifact.scale,
                input_arity=artifact.input_arity,
            )
        object.__setattr__(self, "artifact", artifact)
        object.__setattr__(self, "catalog", catalog)
        object.__setattr__(self, "_runnable_artifact", runnable)
        with interpreter_errors(
            f"the {self.language} interpreter recursed deeper than CPython's "
            "stack limit allows while loading this program",
            language=self.language,
        ):
            module = interpreter_module(self.language, catalog=self.catalog)
        self._bind_module(module)
        code, options = prepare_call(
            self.language,
            runnable.source,
            ExecutionContext(scale=self.artifact.scale),
            catalog=self.catalog,
        )
        if artifact.settings is not None:
            options.update(DialectSettings.options(artifact.settings))
        object.__setattr__(
            self, "_code", tuple(code) if isinstance(code, list) else code
        )
        object.__setattr__(self, "_source_options", tuple(options.items()))

    def _bind_module(self, module: ModuleType) -> None:
        runtime = self.catalog.languages[self.language].runtime
        defaults = _scoped_dialect_defaults(runtime, module)
        object.__setattr__(self, "_module", module)
        object.__setattr__(self, "_dialect_defaults", tuple(defaults.items()))

    @property
    def language(self) -> str:
        """The canonical language owning this program."""
        return self.artifact.language

    @property
    def _input_frame(self) -> RecordFrame | None:
        return _artifact_input_frame(self.artifact, self.catalog)

    def _options(
        self, *, seed: int | None = None, reproducible: bool = False
    ) -> dict[str, Any]:
        return dict(self._dialect_defaults + self._source_options) | execution_options(
            self.language,
            ExecutionContext(seed=seed, reproducible=reproducible),
            catalog=self.catalog,
        )

    def _call(
        self, *, seed: int | None = None, reproducible: bool = False
    ) -> tuple[RunnerProgram, dict[str, Any]]:
        code = list(self._code) if isinstance(self._code, tuple) else self._code
        return code, self._options(seed=seed, reproducible=reproducible)

    def _bind_machine(self) -> None:
        """Prepare the machine before returning a reusable program."""
        with interpreter_errors(
            f"the {self.language} interpreter recursed deeper than CPython's stack "
            "limit allows while preparing this program",
            language=self.language,
        ):
            self._factory()

    def _factory(
        self, *, seed: int | None = None, reproducible: bool = True
    ) -> MachineFactory:
        runtime = self.catalog.languages[self.language].runtime
        if isinstance(self._plan, RuntimePlan):
            return self._plan
        if isinstance(self._plan, RandomRuntimePlan):
            options = self._options(seed=seed, reproducible=reproducible)
            return self._plan.bind(options.get("rng"))
        code, options = self._call(seed=seed, reproducible=reproducible)
        prepare = cast(
            MachinePreparation,
            runtime_hook(self._module, self.language, runtime.machine_preparation),
        )
        plan = prepare(code, options)
        if not callable(plan):
            raise InterpreterLimitError(
                f"{self.language}'s preparation hook returned no machine factory"
            )
        # Keep only the read-only origin of an RNG-bound invocation plan.
        if isinstance(plan, RuntimePlan):
            if runtime.random and plan.random_source is not None:
                object.__setattr__(self, "_plan", plan.random_source)
            elif not runtime.random and plan.random_source is None:
                object.__setattr__(self, "_plan", plan)
        return plan

    def _execute_native(
        self,
        stdin: CheckedInput | PendingInput,
        *,
        seed: int | None,
        io_factory: Callable[[InputSource], ScriptedIO] = ScriptedIO,
    ) -> ExecutionOutcome:
        runtime = self.catalog.languages[self.language].runtime
        plan = self._plan
        if runtime.completion_entrypoint is None:
            factory = self._factory(seed=seed, reproducible=False)
            if not isinstance(factory, RuntimePlan):
                raise InterpreterLimitError(
                    f"{self.language}'s preparation hook must return a RuntimePlan"
                )
            plan = factory
        elif not runtime.uses_native_plan:
            # A legacy catalog may override just the standalone runner.
            plan = None
        if plan is None:
            assert runtime.completion_entrypoint is not None
            runner = runtime_hook(
                self._module, self.language, runtime.completion_entrypoint
            )
            code, options = self._call(seed=seed)
            if options:
                runner = partial(runner, **options)
        else:
            code = self._runnable_artifact.source
            if isinstance(plan, RandomRuntimePlan):
                plan = plan.bind(self._options(seed=seed).get("rng"))
            runner = partial(_run_plan, plan)
        frame = self._input_frame
        if isinstance(stdin, PendingInput):
            stdin = stdin.snapshot(frame=frame)
        return execute_prepared(
            self.language,
            runner,
            code,
            _scripted_io(stdin, io_factory, frame=frame),
            catalog=self.catalog,
        )


def _check_source_options(
    name: str,
    program: ProgramSource,
    settings: DialectSettings | None,
    scale: int | None,
    *,
    catalog: Catalog,
    _loaded: ProgramArtifact[Program] | None = None,
) -> tuple[DialectSettings | None, int | None]:
    """Resolve explicit and retained choices before acquiring any streams."""
    settings = (
        effective_settings(name, program, settings, catalog=catalog)
        if _loaded is None
        else _loaded.settings
    )
    scale = effective_scale(name, program, scale, catalog=catalog)
    check_scale_for(name, scale, catalog=catalog)
    return settings, scale


def prepare_program[T: _PreparedRuntime](
    prepared_type: type[T],
    language: str,
    program: ProgramSource,
    *,
    settings: DialectSettings | None = None,
    scale: int | None = None,
    catalog: Catalog | None = None,
    module_loader: Callable[..., ModuleType] = interpreter_module,
    bind_machine: bool = False,
) -> T:
    """Load source once, resolving provenance and explicit execution choices."""
    program = anchor_program_source(program)
    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    settings, scale = _check_source_options(
        name, program, settings, scale, catalog=catalog
    )
    return _prepare_checked_program(
        prepared_type,
        name,
        program,
        settings=settings,
        scale=scale,
        catalog=catalog,
        module_loader=module_loader,
        bind_machine=bind_machine,
    )


def _prepare_checked_program[T: _PreparedRuntime](
    prepared_type: type[T],
    name: str,
    program: ProgramSource,
    *,
    settings: DialectSettings | None,
    scale: int | None,
    catalog: Catalog,
    module_loader: Callable[..., ModuleType] = interpreter_module,
    bind_machine: bool = False,
    _loaded: ProgramArtifact[Program] | None = None,
) -> T:
    """Load source after preflight, applying any further file metadata."""
    artifact = _loaded
    if artifact is None:
        artifact = check_program(
            name,
            program,
            settings=settings,
            catalog=catalog,
            preserve_compression=True,
            _settings_validated=True,
        )
    settings = artifact.settings
    scale = effective_scale(name, artifact, scale, catalog=catalog)
    check_scale_for(name, scale, catalog=catalog)
    prepared = prepared_type._from_checked(  # noqa: SLF001
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
        prepared._bind_module(module)  # noqa: SLF001 - preparation owns module binding
    if bind_machine:
        prepared._bind_machine()  # noqa: SLF001 - preparation owns the plan
    return prepared


def _run_plan(
    plan: RuntimePlan, _source: RunnerProgram, io: ScriptedIO
) -> CompletionReport:
    """Adapt a language-owned plan to the shared completion/error guard."""
    return plan.run(io)
