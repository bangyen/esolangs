"""Declared fish completion and debugger attributes."""

from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._lifecycle import Completion

CAPABILITIES = MachineCapabilities(
    completion=Completion.HALTED,
    eof_is_a_value=True,
    debug=DebugSpec(
        ip="ip",
        stack="stack",
        views=(
            "cells",
            "dx",
            "dy",
            "height",
            "quote",
            "registers",
            "stacks",
            "width",
            "x",
            "y",
        ),
        ip_shape="grid",
    ),
)
