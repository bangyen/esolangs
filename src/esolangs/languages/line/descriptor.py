"""Runtime and compiler capabilities for Line."""

from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.languages.line.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import (
    RasterSourcePolicy,
    RuntimeSpec,
)
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Line",
    RuntimeSpec(
        "line",
        source_policy=RasterSourcePolicy(),
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        empty_program="image contains no ink",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.line.generator", "line_request"
        ),
        layout_width=False,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.line.generator", "line_balance_request"
        ),
        no_wrap="tree geometry fixes the width; balance chooses orientation",
    ),
)
