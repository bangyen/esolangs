"""Runtime and compiler capabilities for Fish."""

from esolangs.languages.fish.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Fish",
    RuntimeSpec(
        "fish",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        split=True,
        eof="an exhausted 'i' is the spec's -1",
        empty_program="Fish program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.fish.generator", "fish", ("truth_table", "width")
        ),
        # Not a tree: an indexed table read.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.fish.generator",
            "balance_fish",
            ("truth_table", "default"),
        ),
        no_wrap="a row is a codebox row and the lookup table is indexed by column",
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
