"""Runtime and compiler capabilities for 6-5."""

from esolangs.generation.wrap import _six_five
from esolangs.languages.six_five.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "6-5",
    RuntimeSpec(
        "six_five",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.six_five.generator", "six_five", ("truth_table",)
        ),
        # 7n/8n are two-character tokens; see ``_SIX_FIVE_COMMAND``.
        wrap=_six_five,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
