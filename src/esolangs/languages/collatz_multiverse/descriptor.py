"""Runtime and compiler capabilities for Collatz Multiverse."""

from esolangs.languages.collatz_multiverse.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

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
        entrypoint=FunctionRef(
            "esolangs.languages.collatz_multiverse.generator",
            "collatz_multiverse",
            ("truth_table", "width"),
        ),
        balance=FunctionRef(
            "esolangs.languages.collatz_multiverse.generator",
            "balance_collatz_multiverse",
            ("truth_table", "default"),
        ),
        no_wrap="each line is one complete register assignment",
    ),
)
