"""Runtime and compiler capabilities for Line."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec, SourceKind

LANGUAGE = Language(
    "Line",
    RuntimeSpec(
        "line",
        category="tape_based",
        source_kind=SourceKind.RASTER,
        empty_program="image contains no ink",
    ),
    certification=CertificationSpec(
        # A 2^12-row raster renders in about 24s.
        slow_scaling=True,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.line.generator",
            "line",
            ("truth_table", "scale", "unit"),
        ),
        balance=FunctionRef(
            "esolangs.languages.line.generator",
            "balance",
            ("truth_table", "default", "unit"),
        ),
        no_wrap="tree geometry fixes the width; balance chooses orientation",
    ),
)
