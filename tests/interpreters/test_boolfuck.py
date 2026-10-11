"""Boolfuck byte conventions and generated execution."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.boolfuck import _Machine, run
from esolangs.tools.boolfuck import boolfuck
from tests.interpreters.semantic_oracles import STDINS, agrees
from tests.interpreters.semantic_oracles import boolfuck as oracle
from tests.support.raises import assert_rejected_with_hint
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        ("+;", "", "\x01"),
        ("<+;>;<;", "", "\x05"),
        (",;" * 8, "A", "A"),
        (",;" * 8, "", "\x00"),
        ("+[,];", "", "\x00"),
        ("ignored text", "", ""),
    ],
)
def test_byte_conventions(code: str, stdin: str, expected: str) -> None:
    io = ScriptedIO(stdin)
    run(code, io)
    assert io.getvalue() == expected


@pytest.mark.parametrize("n", [1, 2, 3])
def test_all_three_input_tables(n: int) -> None:
    for table in witnesses(n):
        code = boolfuck(table)
        for row in range(1 << n):
            io = ScriptedIO(f"{row:0{n}b}")
            run(code, io)
            assert io.getvalue() == table[row]


@pytest.mark.medium
def test_hints_for_bad_programs_and_input():
    assert_rejected_with_hint("Boolfuck", "[", "close this '[' with ']'")


def _corpus():
    for n in range(4):
        yield from ("".join(c) for c in itertools.product("+<>;,", repeat=n))
    yield from ["+[+]", "+[]", "[+;]", "+[>+<+]", "+[>+[+] <+]", ",;" * 17]
    yield from ["+" + ";" * 9, "ignored +;", "<+>+<;>;"]
    rng = random.Random(1701)
    pieces = ["+", "<", ">", ",", ";", "[+]", "[>+<+]", "[]"]
    for _ in range(64):
        yield "".join(rng.choices(pieces, k=8))


@pytest.mark.parametrize("stdin", STDINS)
def test_bounded_programs_match_the_oracle(stdin):
    for code in _corpus():
        agrees(_Machine, oracle, code, stdin)


@pytest.mark.parametrize(
    ("code", "output"), [("[", None), ("]", None), (",;" * 8, "\x81"), ("+;", "\x01")]
)
def test_oracle_controls(code, output):
    result = agrees(_Machine, oracle, code, "\x81")
    assert result.output == output if output else isinstance(result, ValueError)
    assert not agrees(_Machine, oracle, "+[]", "").halted  # a cap is not a halt
