"""Reusable source preparation, independent of invocation state and Boolean I/O."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache, partial
from types import FunctionType, ModuleType
from typing import TYPE_CHECKING, Any, cast

from esolangs._dialect import Scalar
from esolangs.artifacts import BooleanEvaluation, ProgramArtifact
from esolangs.compressed import CompressedText
from esolangs.debugger import Debugger
from esolangs.exceptions import InterpreterLimitError, ProgramError
from esolangs.limits import ExecutionLimits
from esolangs.outcomes import ExecutionOutcome
from esolangs.registry._catalog import Catalog, get_catalog, resolve_origin
from esolangs.results import ExecutionResult
from esolangs.runtime._acquire import PendingInput
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._execution import (
    execute_prepared,
    execution_options,
    interpreter_errors,
    interpreter_module,
    prepare_call,
    runtime_hook,
)
from esolangs.runtime._input import CheckedInput, InputSource
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
from esolangs.runtime._vm_protocol import VM
from esolangs.runtime.io import ScriptedIO, _scripted_io
from esolangs.settings import DialectSettings, effective_settings

if TYPE_CHECKING:
    from esolangs.runtime._definition import RuntimeSpec


type _RuntimeHooks = tuple[str | None, str, str]


def _plan_hooks(runtime: RuntimeSpec) -> _RuntimeHooks:
    return (
        runtime.interpreter,
        runtime.machine_preparation,
        runtime.completion_entrypoint,
    )


@cache
def _installed_plan_hooks() -> dict[_RuntimeHooks, RuntimeSpec]:
    """Recognize the installed hook pairs whose native paths share a plan."""
    from esolangs.registry._table import LANGUAGES

    return {
        _plan_hooks(runtime): runtime
        for declaration in LANGUAGES.values()
        if (runtime := declaration.runtime).interpreter is not None
    }


def _scoped_dialect_defaults(
    runtime: RuntimeSpec, module: ModuleType
) -> dict[str, Scalar]:
    schema = runtime.dialect_schema
    if schema is None:
        return {}
    installed = _installed_plan_hooks().get(_plan_hooks(runtime))
    if installed is None:
        runner = vars(module).get(str.__str__(runtime.completion_entrypoint))
        if type(runner) is not FunctionType:
            return {}
        code = runner.__code__
        end = code.co_argcount
        start = max(min(2, end), code.co_posonlyargcount)
        # A native runner receives source and IO positionally.
        names = code.co_varnames[start : end + code.co_kwonlyargcount]
        return {key: value for key, value in schema.defaults.items() if key in names}
    original = installed.dialect_schema
    if original is None or original is schema:
        return {}
    # Only keys already consumed by this interpreter belong in its options.
    built_in = original.defaults
    return {
        key: value
        for key, value in schema.defaults.items()
        if key in built_in and value != built_in[key]
    }


@dataclass(frozen=True, slots=True)
class PreparedProgram:
    """Loaded source and bound runtime; every invocation owns its IO and RNG.

    Source decoding and language resolution happen once. Runtime plans retain
    language-owned parsed data and bind fresh randomness for each invocation;
    other hooks may defer parsing.
    Native runners retain their own compiled representations and caches.
    The public artifact retains compressed source and its export limits.
    """

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

    def __post_init__(self) -> None:
        """Retain validated dialect options and immutable shaped source."""
        from esolangs.operations.source import _check_program

        if not _has_backing_type(self.artifact, ProgramArtifact):
            raise ProgramError("a prepared program requires a program artifact")
        catalog = get_catalog(self.catalog)
        origin = self.artifact.language
        name = resolve_origin(origin, catalog=catalog)
        artifact = _check_program(
            name or origin,
            self.artifact,
            catalog=catalog,
            preserve_compression=True,
        )
        check_scale_for(artifact.language, artifact.scale, catalog=catalog)
        self._bind_artifact(artifact, catalog)

    @classmethod
    def _from_checked(
        cls, artifact: ProgramArtifact[Program], catalog: Catalog
    ) -> PreparedProgram:
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
        runner = runtime_hook(
            self._module, self.language, runtime.completion_entrypoint
        )
        plan = self._plan
        # A scoped hook can override either half of the installed runtime.
        # The machine's parse plan must not replace that declared native runner.
        if plan is not None and _plan_hooks(runtime) not in _installed_plan_hooks():
            plan = None
        if plan is None:
            code, options = self._call(seed=seed)
            if options:
                runner = partial(runner, **options)
        else:
            code = self._runnable_artifact.source
            if isinstance(plan, RandomRuntimePlan):
                plan = plan.bind(self._options(seed=seed).get("rng"))
            runner = partial(_run_plan, plan)
        if isinstance(stdin, PendingInput):
            stdin = stdin.snapshot()
        return execute_prepared(
            self.language,
            runner,
            code,
            _scripted_io(stdin, io_factory),
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


def _check_source_options(
    name: str,
    program: ProgramSource,
    settings: DialectSettings | None,
    scale: int | None,
    *,
    catalog: Catalog,
) -> tuple[DialectSettings | None, int | None]:
    """Resolve explicit and retained choices before acquiring any streams."""
    settings = effective_settings(name, program, settings, catalog=catalog)
    scale = effective_scale(name, program, scale, catalog=catalog)
    check_scale_for(name, scale, catalog=catalog)
    return settings, scale


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
    program = anchor_program_source(program)
    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    settings, scale = _check_source_options(
        name, program, settings, scale, catalog=catalog
    )
    return _prepare_checked_program(
        name,
        program,
        settings=settings,
        scale=scale,
        catalog=catalog,
        module_loader=module_loader,
        bind_machine=bind_machine,
    )


def _prepare_checked_program(
    name: str,
    program: ProgramSource,
    *,
    settings: DialectSettings | None,
    scale: int | None,
    catalog: Catalog,
    module_loader: Callable[..., ModuleType] = interpreter_module,
    bind_machine: bool = False,
) -> PreparedProgram:
    """Load source after preflight, applying any further file metadata."""
    from esolangs.operations.source import _check_program

    artifact = _check_program(
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
    prepared = PreparedProgram._from_checked(  # noqa: SLF001
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
