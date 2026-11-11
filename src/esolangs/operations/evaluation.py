"""Evaluate a single row through a generated program's Boolean contract."""

from __future__ import annotations

from esolangs.artifacts import Artifact, BooleanEvaluation, TemplateArtifact
from esolangs.exceptions import ArgumentError, ExecutionTimeoutError
from esolangs.limits import ExecutionLimits
from esolangs.operations.boolean_io import encode_inputs, read_answer
from esolangs.operations.execution import _execute_outcome
from esolangs.registry._catalog import Catalog
from esolangs.runtime._validate import check_bits


def evaluate(
    artifact: Artifact,
    bits: list[int] | tuple[int, ...],
    *,
    limits: ExecutionLimits | None = None,
    catalog: Catalog | None = None,
) -> BooleanEvaluation:
    """Bind or encode one row, then decode the answer using its contract."""
    from esolangs.registry._catalog import get_catalog

    if limits is not None and not isinstance(limits, ExecutionLimits):
        raise ArgumentError("limits must be ExecutionLimits or None")
    catalog = get_catalog(catalog)
    name = catalog.resolve(artifact.language)
    contract = catalog.languages[name].contract
    row = check_bits(bits, "bits")
    program = artifact.fill(row) if isinstance(artifact, TemplateArtifact) else artifact
    if isinstance(artifact, TemplateArtifact):
        stdin = ""
    else:
        if program.input_arity is not None and len(row) != program.input_arity:
            raise ArgumentError(
                f"{name} program expects {program.input_arity} bits, got {len(row)}"
            )
        stdin = encode_inputs(name, row, catalog=catalog)

    if contract.answer_mode != "termination":
        result = _execute_outcome(
            name,
            program,
            stdin=stdin,
            limits=limits,
            isolated=limits is not None and limits.execution_timeout is not None,
            catalog=catalog,
        ).unwrap()
        return BooleanEvaluation(
            read_answer(name, result.output, catalog=catalog), result
        )

    from esolangs.runtime._isolated import termination_result_isolated

    selected = ExecutionLimits() if limits is None else limits
    try:
        proof = termination_result_isolated(
            name,
            program,
            stdin,
            30.0 if selected.total_timeout is None else selected.total_timeout,
            max_steps=selected.max_steps,
            max_output=selected.max_output,
            max_memory=selected.max_memory,
            execution_timeout=selected.execution_timeout,
            preparation_timeout=selected.preparation_timeout,
            catalog=catalog,
        )
    except ExecutionTimeoutError as error:
        if error.bound == "timeout":
            error.bound = "total_timeout"
        raise
    answer = "halts" if proof.decision.halts else "diverges"
    return BooleanEvaluation(
        str(contract.answer_values.index(answer)), proof.observation, proof.decision
    )
