"""Evaluate a single row through a generated program's Boolean contract."""

from __future__ import annotations

from esolangs.artifacts import (
    Artifact,
    BooleanEvaluation,
    ProgramArtifact,
    TemplateArtifact,
)
from esolangs.exceptions import ArgumentError, ProgramError, TemplateError
from esolangs.limits import ExecutionLimits
from esolangs.operations.boolean_io import (
    _answer_codec,
    _read_output_answer,
    encode_inputs,
)
from esolangs.operations.execution import _execute_outcome, _execution_route
from esolangs.registry._catalog import Catalog
from esolangs.runtime._prepared import PreparedProgram
from esolangs.runtime._program import Program
from esolangs.runtime._validate import check_bit_count, check_bits


def evaluate_artifact(
    artifact: Artifact,
    bits: list[int] | tuple[int, ...],
    *,
    limits: ExecutionLimits | None = None,
    catalog: Catalog | None = None,
    prepared: PreparedProgram | None = None,
) -> BooleanEvaluation:
    """Bind or encode one row, then decode the answer using its contract."""
    from esolangs.registry._catalog import get_catalog

    if limits is not None and not isinstance(limits, ExecutionLimits):
        raise ArgumentError("limits must be ExecutionLimits or None")
    catalog = get_catalog(catalog)
    name = catalog.resolve(artifact.language)
    declaration = catalog.languages[name]
    contract = declaration.contract
    values, pattern = _answer_codec(name, contract)
    row = check_bits(
        bits,
        "bits",
        allow_empty=isinstance(artifact, TemplateArtifact)
        and artifact.bindings.inputs == 0,
    )
    program: ProgramArtifact[Program]
    if isinstance(artifact, TemplateArtifact):
        if not declaration.parameterized:
            raise TemplateError(f"{name} has no template generator")
        program = artifact.fill(row)
        stdin = ""
    else:
        if declaration.parameterized:
            raise ArgumentError(
                f"{name} embeds its inputs in the program; pass the unfilled "
                "template to evaluate or run the filled program"
            )
        program = artifact
        if program.input_arity is not None:
            check_bit_count(row, program.input_arity, f"{name} program")
        stdin = encode_inputs(name, row, catalog=catalog)

    if contract.answer_mode != "termination":
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
    if not isinstance(artifact, (ProgramArtifact, TemplateArtifact)):
        raise ProgramError("evaluation requires a program or template artifact")
    from esolangs.operations.source import check_origin

    check_origin(name, artifact.language, catalog=catalog)
    return evaluate_artifact(artifact, bits, limits=limits, catalog=catalog)
