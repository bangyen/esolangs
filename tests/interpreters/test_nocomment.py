"""Unit tests for the NoComment interpreter.

NoComment is a full wiki language: 10 commands (``i d c l r n f s b o``)
over a byte tape and a byte stack.  Non-command characters are errors (the
wiki allows no comments), as are stack underflow and jumps out of code
space.  These tests pin the plain semantics.
"""

import importlib
import io
from contextlib import redirect_stdout

import pytest

import esolangs
from esolangs.interpreters.io import IO
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    SnapshotContract,
)

nocomment = importlib.import_module("esolangs.interpreters.tape_based.nocomment")


def run_and_capture(code: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        nocomment.run(code, IO())
    return buffer.getvalue()


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 2, 3, 7, 13, 80])
def test_generated_nocomment_templates_run_at_arbitrary_breaks(width: int) -> None:
    from esolangs.tools.nocomment import nocomment as generate
    from esolangs.tools.wrap import wrap_chars
    from tests.tools.test_boolean_nocomment import TestParameterizedNoComment

    tables = [f"{value:04b}" for value in range(16)]
    tables += ["00000000", "11111111", "01101001", "01010011", "01101001" * 2]
    oracle = TestParameterizedNoComment()
    for table in tables:
        n = len(table).bit_length() - 1
        template = wrap_chars(generate(table), width)
        assert max(map(len, template.splitlines())) <= width
        for row, expected in enumerate(table):
            bits = [int(bit) for bit in f"{row:0{n}b}"]
            source = oracle.instantiate(template, bits)
            assert oracle.run_nocomment(source) == expected


class TestNoComment:
    def test_a_long_increment_run_prints_hello_world(self) -> None:
        """Thirteen characters walked out on one cell with ``i``/``d``."""
        program = (
            "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii"
            "iiiioiiiiiiiiiiiiiiiiiiiiiiiiiiiiioiiiiiiiooiiiodddddddddddddddddddd"
            "dddddddddddddddddddddddddddddddddddddddddddddddoddddddddddddoiiiiiii"
            "iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiioiiiiiiiiiiiiiiiiiii"
            "iiiiioiiioddddddoddddddddodddddddddddddddddddddddddddddddddddddddddd"
            "dddddddddddddddddddddddddo"
        )
        assert esolangs.run("NoComment", program) == "Hello, World!"


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.nocomment import _Machine

    return _Machine(code, ScriptedIO())


class TestContract(EmptyProgramContract, SnapshotContract, CycleContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_and_capture)
    machine = staticmethod(_machine)
    stepping_program = "co"
    halting_program = "ciio"
    looping_program = "inbb"
