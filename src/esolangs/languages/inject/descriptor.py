"""Runtime and compiler capabilities for Inject."""

from esolangs.languages.inject.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Inject",
    RuntimeSpec(
        "inject",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
        # The wiki cat's only clean exit is a ``readto`` that gets no line.
        eof="an exhausted readto empties the block",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.inject.generator", "inject", ("truth_table", "width")
        ),
        balance=FunctionRef(
            "esolangs.languages.inject.generator", "_balance", ("table", "default")
        ),
        no_wrap="blocks and executable commands are delimited by source lines",
    ),
    contract=BooleanContract(
        note="send terminates each line, so the answer ends in a newline",
    ),
    # ``send`` terminates every line it writes, so the answer arrives
    # with a newline after it -- there is no other output command.
    example=Example(expected="0\n"),
)
