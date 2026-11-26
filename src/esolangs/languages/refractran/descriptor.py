"""Runtime and compiler capabilities for REFRACTRAN."""

from esolangs.languages.refractran.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("0", "1")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import wrap_space_delimited
    from esolangs.registry._backend import (
        BooleanBackend,
        ConstructedLayout,
        TemplateSpec,
    )
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.refractran.generator", "refractran_request"
        ),
        layout=ConstructedLayout(
            layout_balance=True,
            wrap=wrap_space_delimited,
            same_layout=FunctionRef(
                "esolangs.generation.helpers",
                "same_token_layout",
                ("template", "plain", "_layout"),
            ),
        ),
        template=TemplateSpec(pair=PAIR),
    )


LANGUAGE = LanguageDeclaration(
    "REFRACTRAN",
    RuntimeSpec(
        "refractran",
        reads_stdin=False,
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
        empty_program="REFRACTRAN needs an initial integer",
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"([01])$",
        note="Inputs are ordered prime exponents in the initial integer; "
        "the final binary state ends in the answer bit.",
    ),
    example=Example(expected_compared=False),
)
