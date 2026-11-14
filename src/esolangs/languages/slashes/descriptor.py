"""Runtime and compiler capabilities for ///."""

from esolangs.languages.slashes.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec, TextSourcePolicy


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.slashes.generator", "slashes_request"
        ),
        layout_width=False,
        # Not a tree: an indexed table rewrite.
        shape=Shape.LOOKUP,
        no_wrap="newlines are literal output and substitution data",
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.slashes.generator", "slashes_balance_request"
        ),
        template=TemplateSpec(pair=("a", "b")),
    )


LANGUAGE = LanguageDeclaration(
    "///",
    RuntimeSpec(
        "slashes",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
        source_policy=TextSourcePolicy(),
    ),
    id="slashes",
    aliases=("Slashalash",),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="Inputs fill the binary row index before unary selection; "
        "constant tables parse the input letters as a nonmatching rule pattern.",
    ),
)
