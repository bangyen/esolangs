"""Boolfuck with a two-sided bit tape and little-endian byte I/O.

Commands act on the bit under the pointer: ``+`` flips it, ``,`` reads a bit
into it, ``;`` writes it, ``<`` and ``>`` move the pointer, and ``[ ]`` loop
while it is 1.  Noncommands are ignored.

Input/output:
    Bits move least-significant first, eight to a byte.  Unicode input is
    reduced modulo 256, matching the package's byte interfaces.  EOF supplies
    zero bits, so a read never raises.  A partial output byte is padded with
    zero bits at halt.

Errors:
    ProgramError: unmatched brackets.
"""

from collections.abc import Mapping
from functools import partial
from typing import Any

from esolangs.languages.boolfuck.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import MachineFactory
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel
from esolangs.runtime.bit_tape import _BitTapeMachine
from esolangs.runtime.io import IO


class _Machine(_BitTapeMachine):
    """Language-owned bit-tape machine."""

    _workspace_model = WorkspaceModel(
        "boolfuck-v1", ("control", "ones", "input_cursor")
    )


def prepare_machine(
    source: RunnerProgram, options: Mapping[str, Any]
) -> MachineFactory:
    """Bind fresh language-owned bit-tape machines."""
    if not isinstance(source, str):
        raise TypeError("boolfuck machines require text source")
    if options:
        raise TypeError("boolfuck machines accept no runtime options")
    return partial(_Machine, source)


def _execute(code: str, io: IO) -> CompletionReport:
    """Execute Boolfuck and flush its final partial byte."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Execute Boolfuck and flush its final partial byte."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
