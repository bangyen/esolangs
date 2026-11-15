"""Runtime and generation capabilities for NB."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.wrap import wrap_space_delimited
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.nb.generator", "nb_request"
        ),
        wrap=wrap_space_delimited,
        wrap_multiline=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.nb.generator", "nb_balance_request"
        ),
    )


LANGUAGE = LanguageDeclaration(
    "NB",
    RuntimeSpec(
        "nb",
        category="variable_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=MachineCapabilities(
            debug=DebugSpec(ip="ip", ip_shape="opaque", memory="memory")
        ),
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="line_per_bit"),
)
