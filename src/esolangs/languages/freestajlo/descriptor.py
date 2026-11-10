"""Runtime and compiler capabilities for Freestajlo."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.freestajlo.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

_UNIT = r'"[^"]*"|\'[\s\S]|\d+|[\s\S]'


LANGUAGE = Language(
    "Freestajlo",
    RuntimeSpec(
        "freestajlo",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        eof="an exhausted ',' is the spec's -1, an exhausted ';' its 0",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.freestajlo.generator", "freestajlo_request"
        ),
        layout_width=False,
        shape=Shape.LOOKUP,
        wrap=TokenWrapper(_UNIT),
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.freestajlo.generator", "freestajlo_balance_request"
        ),
    ),
)
