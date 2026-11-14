"""Runtime and compiler capabilities for SLOW ACV MAMMALIAN."""

from esolangs._dialect import DialectSchema
from esolangs.languages.slow_acv_mammalian.dialect import LEAPFROG_RESUMES, MODULI
from esolangs.languages.slow_acv_mammalian.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.slow_acv_mammalian.generator",
            "slow_acv_mammalian_request",
        ),
        layout_width=False,
        # Not a tree: a branch-free chain into a flat leaf table.
        shape=Shape.LOOKUP,
        # Four-character cells align the ``SEED`` runs; longer words span cells.
        wrap=FunctionRef(
            "esolangs.languages.slow_acv_mammalian.wrapping",
            "_mammalian",
            ("program", "width"),
        ),
        wrap_balance=FunctionRef(
            "esolangs.languages.slow_acv_mammalian.wrapping",
            "_balance_mammalian",
            ("program",),
        ),
        same_layout=FunctionRef(
            "esolangs.generation.helpers",
            "same_token_layout",
            ("template", "plain", "_layout"),
        ),
    )


LANGUAGE = LanguageDeclaration(
    "SLOW ACV MAMMALIAN",
    RuntimeSpec(
        "slow_acv_mammalian",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
        dialect=FunctionRef(
            "esolangs.languages.slow_acv_mammalian.dialect",
            "MammalianModuli",
            ("cell_modulus", "io_modulus", "leapfrog_resume"),
        ),
        dialect_schema=DialectSchema(
            "SLOW ACV MAMMALIAN",
            {
                "cell_modulus": MODULI,
                "io_modulus": MODULI,
                "leapfrog_resume": LEAPFROG_RESUMES,
            },
            {
                "cell_modulus": 256,
                "io_modulus": 255,
                "leapfrog_resume": "after",
            },
        ),
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
