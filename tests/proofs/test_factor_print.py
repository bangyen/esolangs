"""Execute both fixed Factor witnesses and check their averaged size law."""

import itertools
import random
import sys

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.factor import run
from esolangs.tools.factor import _encode
from tests.proofs._factor_print import printed_program
from tests.witness_tables import witnesses


def _render(code: str) -> str:
    number = _encode(code)
    limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(0)
    try:
        return str(number)
    finally:
        sys.set_int_max_str_digits(limit)


@pytest.mark.parametrize("n", [1, 3])
@pytest.mark.parametrize("reverse", [False, True])
def test_printed_witness_executes(n: int, *, reverse: bool) -> None:
    for table in witnesses(n):
        program = _render(printed_program(table, reverse_last=reverse))
        for bits in itertools.product("01", repeat=n):
            io = ScriptedIO("".join(bits))
            run(program, io)
            assert io.getvalue() == table[int("".join(bits), 2)]


def test_averaged_character_bound() -> None:
    rng = random.Random(921)
    for n in range(2, 13):
        length = 2**n
        sum_bound = 20 * length + 12 * n**2 + 96 * n + 117
        ones = "1" * length
        assert (
            len(printed_program(ones)) + len(printed_program(ones, reverse_last=True))
            == sum_bound
        )
        tables = (
            [format(i, f"0{length}b") for i in range(2**length)]
            if n <= 3
            else ["".join(rng.choice("01") for _ in range(length)) for _ in range(8)]
        )
        for table in tables:
            a = len(printed_program(table))
            b = len(printed_program(table, reverse_last=True))
            assert a + b <= sum_bound
            assert min(a, b) <= 10 * length + 6 * n**2 + 48 * n + 59
