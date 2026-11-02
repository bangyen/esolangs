"""Raw-command semantics independent of both production execution paths."""

import itertools
import random

import pytest

from esolangs.languages.brainfuck.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.semantic_oracles import STDINS, agrees, brainfuck


def _corpus():
    for n in range(4):
        yield from map("".join, itertools.product("+-<>.,", repeat=n))
    yield from [
        "[",
        "]",
        "[[]",
        "+[]",
        "+[+]",
        "[-].",
        "-[+].",
        ",.[-]",
        "++[>+++<-]>.",
        "++[>--<-]>.",
        "<+<++>>.<.<.",
    ]
    rng = random.Random(20261102)
    for _ in range(64):
        yield "".join(rng.choices(["+", "-", "<", ">", ".", ",", "[-]", "[>+<-]"], k=8))


def test_raw_programs_match_independent_oracle():
    for stdin in [*STDINS, "Ā", "ā"]:
        for code in _corpus():
            expected = agrees(_Machine, brainfuck, code, stdin)
            if isinstance(expected, Exception):
                with pytest.raises(type(expected)):
                    run(code, ScriptedIO(stdin))
            elif expected.halted:
                io = ScriptedIO(stdin)
                run(code, io)
                assert (io.getvalue(), io.position()) == (
                    expected.output,
                    expected.consumed,
                )
    io = ScriptedIO()
    run("+" * 256 + ".", io)
    assert io.getvalue() == "\x00"
    assert brainfuck("-.", "", 200).output == "\xff"
    assert brainfuck(",.", "λ", 200).output == chr(ord("λ") % 256)
    assert not brainfuck("+[]", "", 200).halted
    with pytest.raises(EOFError):
        brainfuck(",", "", 200)
    with pytest.raises(ValueError, match="unmatched close"):
        brainfuck("][", "", 200)
