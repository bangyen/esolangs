"""Runtime and compiler capabilities for Befunge."""

from esolangs.languages.befunge.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

MAX_INPUTS = 13


LANGUAGE = Language(
    "Befunge",
    RuntimeSpec(
        "befunge",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        split=True,
        empty_program="Befunge program cannot be empty",
    ),
    backend=BooleanBackend(
        max_inputs=MAX_INPUTS,
        entrypoint=FunctionRef(
            "esolangs.languages.befunge.generator", "befunge", ("truth_table", "width")
        ),
        # Not a tree: reads a packed grid cell with ``g``.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.befunge.generator",
            "balance_befunge",
            ("truth_table", "default"),
        ),
        no_wrap="a row is a grid row and the lookup table is indexed by column",
        grid=True,
    ),
    # ``.`` writes the digit and a trailing space, so the committed
    # answer carries it and the sweep strips it.
    example=Example(expected="0 "),
)
