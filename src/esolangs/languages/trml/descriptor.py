"""Runtime and compiler capabilities for Trml."""

from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("0", "1")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.trml.generator", "trml_request"
        ),
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR, char="@"),
    )


LANGUAGE = LanguageDeclaration(
    "Trml",
    RuntimeSpec(
        "trml",
        category="program_based",
        reads_stdin=False,
        empty_program="Trml needs semicolon-terminated statements followed by '$'",
        machine_preparation="prepare_machine",
        completion_entrypoint="complete",
        capabilities=MachineCapabilities(debug=DebugSpec(views=("text",))),
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    example=Example(),
)
