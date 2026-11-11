"""Runtime and compiler capabilities for Bitdeque."""

from esolangs.languages.bitdeque.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import BackendDefinition, DeferredBackend, Language
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.bitdeque.generator", "bitdeque_request"
        ),
        layout_width=True,
        same_layout=FunctionRef(
            "esolangs.languages.bitdeque.generator",
            "_same_layout",
            ("template", "plain", "layout"),
        ),
        # Space-delimited, but ``GOTO`` and its target must stay on one line.
        wrap=FunctionRef(
            "esolangs.languages.bitdeque.generator", "_bitdeque", ("program", "width")
        ),
        balance=OperationRef[BalanceRequest, TemplateLayout](
            "esolangs.languages.bitdeque.generator", "bitdeque_balance_request"
        ),
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.bitdeque.generator",
                "bitdeque_setters",
                ("template", "n"),
            )
        ),
    )


LANGUAGE = Language(
    "Bitdeque",
    RuntimeSpec(
        "bitdeque",
        category="queue_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        note="Bitdeque has no output instruction and dumps its deque at "
        "halt; the generator leaves exactly one bit on it, so the "
        "whole dump is the answer and there is no position to name",
    ),
)
