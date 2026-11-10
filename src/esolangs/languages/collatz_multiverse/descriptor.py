"""Runtime and compiler capabilities for Collatz Multiverse."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.collatz_multiverse.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Collatz Multiverse",
    RuntimeSpec(
        "collatz_multiverse",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.collatz_multiverse.generator",
            "collatz_multiverse_request",
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.collatz_multiverse.generator",
            "collatz_multiverse_balance_request",
        ),
        no_wrap="each line is one complete register assignment",
    ),
)
