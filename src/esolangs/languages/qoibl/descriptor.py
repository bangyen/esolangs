"""Runtime and compiler capabilities for Qoibl."""

from esolangs.languages.qoibl.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Qoibl",
    RuntimeSpec(
        "qoibl",
        category="register_based",
        split=True,
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.qoibl.generator", "qoibl", ("truth_table", "width")
        ),
        # Not a tree: the table is one binary literal the reads divide down.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.qoibl.generator", "balance_qoibl", ("table", "default")
        ),
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
