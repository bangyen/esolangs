"""Evaluate a single row through a generated program's Boolean contract."""

from __future__ import annotations

from esolangs.artifacts import Artifact, BooleanEvaluation, TemplateArtifact
from esolangs.exceptions import ArgumentError
from esolangs.limits import ExecutionLimits
from esolangs.operations.boolean_io import encode_inputs, read_answer
from esolangs.operations.execution import _execute_outcome
from esolangs.registry._catalog import Catalog
from esolangs.runtime._prepared import PreparedProgram
from esolangs.runtime._validate import check_bit_count, check_bits


def evaluate(
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
    contract = catalog.languages[name].contract
    row = check_bits(bits, "bits")
    program = artifact.fill(row) if isinstance(artifact, TemplateArtifact) else artifact
    if isinstance(artifact, TemplateArtifact):
        stdin = ""
    else:
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
        return BooleanEvaluation(
            read_answer(name, result.output, catalog=catalog), result
        )

    selected = ExecutionLimits() if limits is None else limits
    bounded_locally = selected.max_steps is not None and all(
        limit is None
        for limit in (
            selected.preparation_timeout,
            selected.execution_timeout,
            selected.total_timeout,
            selected.max_memory,
            selected.max_output,
        )
    )
    if bounded_locally:
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
            preparation_timeout=selected.preparation_timeout,
            catalog=catalog,
        )
    answer = "halts" if proof.decision.halts else "diverges"
    return BooleanEvaluation(
        str(contract.answer_values.index(answer)), proof.observation, proof.decision
    )
