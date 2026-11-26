"""Evaluate a single row through a generated program's Boolean contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from esolangs.artifacts import (
    Artifact,
    BooleanEvaluation,
    BoundRow,
    ProgramArtifact,
    TemplateArtifact,
)
from esolangs.exceptions import ArgumentError, ProgramError, TemplateError
from esolangs.limits import ExecutionLimits
from esolangs.operations.boolean_io import (
    _answer_codec,
    _read_output_answer,
)
from esolangs.operations.execution import _execute_outcome, _execution_route
from esolangs.registry._catalog import Catalog
from esolangs.registry._contracts import BooleanContract
from esolangs.runtime._prepared import _PreparedRuntime
from esolangs.runtime._program import Program
from esolangs.runtime._validate import _has_backing_type, check_bit_count, check_bits


def evaluate_artifact(
    artifact: Artifact,
    bits: list[int] | tuple[int, ...],
    *,
    limits: ExecutionLimits | None = None,
    catalog: Catalog | None = None,
    prepared: _PreparedRuntime | None = None,
) -> BooleanEvaluation:
    """Bind or encode one row, then decode the answer using its contract."""
    if limits is not None and not _has_backing_type(limits, ExecutionLimits):
        raise ArgumentError("limits must be ExecutionLimits or None")
    return _prepare_evaluator(artifact, catalog=catalog)(bits, limits, prepared)


def _row_binder(
    artifact: Artifact, *, catalog: Catalog | None
) -> tuple[str, BooleanContract, Callable[[list[int] | tuple[int, ...]], BoundRow]]:
    from esolangs.registry._catalog import get_catalog, resolve_origin

    catalog = get_catalog(catalog)
    origin = artifact.language
    name = resolve_origin(origin, catalog=catalog)
    if name is None:
        from esolangs.runtime._artifact_source import check_origin

        name = catalog.resolve(origin)
        check_origin(name, origin, catalog=catalog)
    declaration = catalog.languages[name]
    contract = declaration.contract
    encode = (
        contract.row_encoder(name)
        if declaration.runtime.reads_stdin and not declaration.parameterized
        else None
    )

    def bind(bits: list[int] | tuple[int, ...]) -> BoundRow:
        row = check_bits(
            bits,
            "bits",
            allow_empty=_has_backing_type(artifact, TemplateArtifact)
            and not artifact.bindings.setters,
        )
        program: ProgramArtifact[Program]
        if _has_backing_type(artifact, TemplateArtifact):
            if not declaration.parameterized:
                raise TemplateError(f"{name} has no template generator")
            program = TemplateArtifact.fill(artifact, row)
            stdin = ""
        else:
            if declaration.parameterized:
                raise ArgumentError(
                    f"{name} embeds its inputs in the program; pass the unfilled "
                    "template to evaluate or run the filled program"
                )
            program = cast("ProgramArtifact[Program]", artifact)
            if program.input_arity is not None:
                check_bit_count(row, program.input_arity, f"{name} program")
            if encode is None:
                raise ArgumentError(
                    f"{name} reads no stdin, so there is nothing to encode"
                )
            stdin = encode(row)

        return BoundRow(program, stdin)

    return name, contract, bind


def _prepare_evaluator(
    artifact: Artifact, *, catalog: Catalog | None
) -> Callable[
    [list[int] | tuple[int, ...], ExecutionLimits | None, _PreparedRuntime | None],
    BooleanEvaluation,
]:
    """Bind one artifact's codecs and answer mode while leaving IO per invocation."""
    name, contract, bind = _row_binder(artifact, catalog=catalog)
    values, pattern = _answer_codec(name, contract)

    def evaluate_row(
        bits: list[int] | tuple[int, ...],
        limits: ExecutionLimits | None,
        prepared: _PreparedRuntime | None,
    ) -> BooleanEvaluation:
        row = bind(bits)
        return answer_row(row.program, row.stdin, limits, prepared)

    def output_answer(
        program: ProgramArtifact[Program],
        stdin: str,
        limits: ExecutionLimits | None,
        prepared: _PreparedRuntime | None,
    ) -> BooleanEvaluation:
        result = _execute_outcome(
            name,
            program,
            stdin=stdin,
            limits=limits,
            catalog=catalog,
            prepared=prepared,
        ).unwrap()
        try:
            answer = _read_output_answer(
                name, result.output, values, pattern, contract.note
            )
        except ProgramError as error:
            error.observation = result
            error.partial_output = result.output
            raise
        return BooleanEvaluation(answer, result)

    def termination_answer(
        program: ProgramArtifact[Program],
        stdin: str,
        limits: ExecutionLimits | None,
        prepared: _PreparedRuntime | None,
    ) -> BooleanEvaluation:
        selected = ExecutionLimits() if limits is None else limits
        use_worker, preparation_timeout = _execution_route(
            selected, isolated=selected.max_steps is None, prepared=prepared is not None
        )
        if not use_worker:
            from esolangs.runtime._termination import _termination_result

            proof = _termination_result(
                name,
                program,
                stdin,
                max_steps=selected.max_steps,
                catalog=catalog,
                prepared=prepared,
            )
        else:
            from esolangs.operations.execution import default_total
            from esolangs.runtime._isolated import termination_result_isolated

            proof = termination_result_isolated(
                name,
                program,
                stdin,
                default_total(selected.total_timeout, selected.execution_timeout),
                max_steps=selected.max_steps,
                max_output=selected.max_output,
                max_memory=selected.max_memory,
                execution_timeout=selected.execution_timeout,
                preparation_timeout=preparation_timeout,
                catalog=catalog,
            )
        answer = "halts" if proof.decision.halts else "diverges"
        return BooleanEvaluation(
            str(values.index(answer)),
            proof.observation,
            termination=proof.decision,
        )

    answer_row = (
        termination_answer if contract.answer_mode == "termination" else output_answer
    )
    return evaluate_row


def evaluate(
    language: str,
    artifact: Artifact,
    bits: list[int] | tuple[int, ...],
    *,
    limits: ExecutionLimits | None = None,
    catalog: Catalog | None = None,
) -> BooleanEvaluation:
    """Run one Boolean row and return its answer and execution evidence.

    Raises:
        UnknownLanguageError: ``language`` is not registered.
        ProgramError: ``artifact`` is not an artifact, belongs to another
            language, or that language's Boolean contract is invalid.
        ArgumentError: ``bits`` is not one 0 or 1 per input, or an embedded
            input requires the unfilled template.
        TemplateError: ``artifact`` is a template for a stdin language.
        EsolangError: Any error :func:`esolangs.run` raises for the row.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.resolve(language)
    if not (
        _has_backing_type(artifact, ProgramArtifact)
        or _has_backing_type(artifact, TemplateArtifact)
    ):
        raise ProgramError("evaluation requires a program or template artifact")
    from esolangs.runtime._artifact_source import check_origin

    check_origin(name, artifact.language, catalog=catalog)
    return evaluate_artifact(artifact, bits, limits=limits, catalog=catalog)
