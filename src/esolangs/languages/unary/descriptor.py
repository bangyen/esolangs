"""Runtime and compiler capabilities for Unary."""

from esolangs.languages.unary.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import (
    CompressedSourcePolicy,
    RuntimeSpec,
)


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.unary.generator", "unary_request"
        ),
        layout_width=False,
        max_inputs=9,
        restrictions=(
            "raw export 32 Mi characters; generation 256 Mi characters; "
            "gzip 256 KiB; table-dependent caps"
        ),
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
    "Unary",
    RuntimeSpec(
        "unary",
        source_policy=CompressedSourcePolicy(),
        category="tape_based",
        eof="stores zero",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        alphabet=("\x00", "\xff"),
        input_shape="char_stream",
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Bytes 0/255 encode inputs; halt means 0, a fixed cycle means 1.",
    ),
    example=Example(expected="", expected_compared=False, slow_build=True),
)
