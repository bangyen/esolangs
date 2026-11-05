"""Runtime and compiler capabilities for Piet."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec, SourceKind

LANGUAGE = Language(
    "Piet",
    RuntimeSpec(
        "piet",
        category="stack_based",
        source_kind=SourceKind.RASTER,
        eof="an exhausted input command is ignored, as the spec requires",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.piet.generator",
            "piet",
            ("truth_table", "width", "scale"),
        ),
        balance=FunctionRef(
            "esolangs.languages.piet.generator", "_balance", ("truth_table", "default")
        ),
    ),
    contract=BooleanContract(
        note="the committed example is drawn at 80 pixels per codel; "
        "generate draws 1 unless --scale says otherwise"
    ),
    example=Example(scale=80),
)
