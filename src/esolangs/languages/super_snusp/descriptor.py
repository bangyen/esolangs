"""Runtime and compiler capabilities for Super SNUSP."""

from esolangs.languages.super_snusp.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Super SNUSP",
    RuntimeSpec(
        "super_snusp",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        split=True,
        empty_program="Super SNUSP program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.super_snusp.generator",
            "super_snusp",
            ("truth_table", "width"),
        ),
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        balance=FunctionRef(
            "esolangs.languages.super_snusp.generator", "_balance", ("table", "default")
        ),
        no_wrap="a row is a grid row; a break moves code, it does not reflow",
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
