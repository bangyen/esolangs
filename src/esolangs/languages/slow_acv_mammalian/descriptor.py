"""Runtime and compiler capabilities for SLOW ACV MAMMALIAN."""

from esolangs.languages.slow_acv_mammalian.interpreter import LEAPFROG_RESUMES, MODULI
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "SLOW ACV MAMMALIAN",
    RuntimeSpec(
        "slow_acv_mammalian",
        category="tape_based",
        dialect=FunctionRef(
            "esolangs.languages.slow_acv_mammalian.interpreter",
            "MammalianModuli",
            ("cell_modulus", "io_modulus", "leapfrog_resume"),
        ),
        dialect_values={
            "cell_modulus": MODULI,
            "io_modulus": MODULI,
            "leapfrog_resume": LEAPFROG_RESUMES,
        },
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.slow_acv_mammalian.generator",
            "slow_acv_mammalian",
            ("truth_table", "cell_modulus", "io_modulus", "leapfrog_resume"),
        ),
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
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    certification=CertificationSpec(
        slow_width_sweep=True,
    ),
)
