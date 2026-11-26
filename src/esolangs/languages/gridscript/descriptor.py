"""Runtime and compiler capabilities for GridScript."""

from esolangs.languages.gridscript.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape, SourceLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.gridscript.generator", "gridscript_request"
        ),
        layout=SourceLayout(
            no_wrap="each node definition is one line and a break splits it",
        ),
        # One straight pass: the table is packed chunks indexed by arithmetic.
        shape=Shape.LOOKUP,
    )


LANGUAGE = LanguageDeclaration(
    "GridScript",
    RuntimeSpec(
        "gridscript",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        empty_program="cannot parse ''",
        eof="INPUT stores NULL, as the specification says it should",
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
)
