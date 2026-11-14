"""Runtime and compiler capabilities for Stisp."""

from esolangs.languages.stisp.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec

_TOKEN = r"->|[A-Za-z0-9_]+|[\s\S]"


PAIR = ("0", "1")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import TokenWrapper
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.stisp.generator", "stisp_request"
        ),
        layout_width=False,
        wrap=TokenWrapper(_TOKEN),
        template=TemplateSpec(pair=PAIR),
    )


LANGUAGE = LanguageDeclaration(
    "Stisp",
    RuntimeSpec(
        "stisp",
        category="other",
        empty_program="a Stisp program needs a stack expression",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        note="Stisp has no input or output: each input is the atom 0 or 1 "
        "in the template, and the result printed at halt is the answer atom",
    ),
)
