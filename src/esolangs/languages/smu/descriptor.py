"""Runtime and compiler capabilities for Smu."""

from esolangs.languages.smu.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.smu.generator", "smu_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "Smu",
    RuntimeSpec(
        "smu",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        # Every run pushes its input bit, and the spec's EOF bit is ``=``.
        eof="an exhausted read pushes the spec's '=' bit",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
        note="Smu reads one bit a run, low bit of each byte first, and "
        "packs its output bits into bytes the same way",
    ),
)
