import random

import pytest

from esolangs._drive import drive
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.stack_based.grapheme import _Machine
from esolangs.tools.grapheme import _grapheme_literal, grapheme
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.grapheme_cases import finite_cases
from tests.interpreters.grapheme_observer import check


@pytest.mark.parametrize("shard", range(8))
def test_finite_state(shard):
    for source, text in finite_cases()[shard::8]:
        check(source, text)


@pytest.mark.parametrize(("n", "shard"), [(1, 0), (2, 0)] + [(3, s) for s in range(16)])
def test_small_generated_state(n, shard):
    for value in range(shard, 2 ** (2**n), 16 if n == 3 else 1):
        table = format(value, f"0{2**n}b")
        source = grapheme(table)
        for row, answer in enumerate(table):
            text = (
                "\n".join("%" if bit == "0" else "A" for bit in format(row, f"0{n}b"))
                + "\n"
            )
            result = check(source, text)
            assert result["output"] == answer
            assert result["reads"] == n
            assert result["halted"]


@pytest.mark.parametrize(
    ("source", "expected"), [("FAFHHZ", False), ("HHZ", True), ("FAFHMHZ", True)]
)
def test_empty_function_repeat(source, expected):
    assert (
        run_until_halt_or_cycle(_Machine(source, ScriptedIO()), limit=100) == expected
    )


@pytest.mark.medium
@pytest.mark.parametrize("n", range(4, 11))
@pytest.mark.parametrize(
    "family", ["zero", "one", "parity", "sparse", "dense", "random", "minterm"]
)
@pytest.mark.parametrize("shard", range(16))
def test_wide_generated_state(n, family, shard):
    rng = random.Random(1000 + n)
    tables = {
        "zero": "0" * (2**n),
        "one": "1" * (2**n),
        "parity": "".join(str(i.bit_count() % 2) for i in range(2**n)),
        "sparse": "".join(
            "1" if i in (0, 2**n - 1, 2 ** (n - 1)) else "0" for i in range(2**n)
        ),
        "dense": "".join(
            "0" if i in (0, 2**n - 1, 2 ** (n - 1)) else "1" for i in range(2**n)
        ),
        "random": "".join(rng.choice("01") for _ in range(2**n)),
        "minterm": "1" + "0" * (2**n - 1),
    }
    table = tables[family]
    source = grapheme(table)
    for row in range(shard, 2**n, 16):
        text = (
            "\n".join("%" if bit == "0" else "A" for bit in format(row, f"0{n}b"))
            + "\n"
        )
        result = check(source, text)
        assert result["output"] == table[row]
        assert result["reads"] == n
        assert result["halted"]


@pytest.mark.parametrize("value", [0, 1, 16, 106, 1006, 1263460, 9999996, 5666666])
def test_borrowed_digit_literal(value):
    result = check(_grapheme_literal(value) + "Y", "")
    assert result["output"] == str(10 * value)


class Cursorless(IO):
    def __init__(self):
        super().__init__()
        self.lines = iter([""] * 8)
        self.successful = 0

    def _read(self, _prompt):
        try:
            value = next(self.lines)
        except StopIteration:
            raise EOFError from None
        self.successful += 1
        return value

    def _write(self, value):
        pass


def test_cursorless_reads_reach_eof():
    io = Cursorless()
    vm = _Machine("EAEHWMHZ", io)
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(vm, limit=100)
    assert io.successful == 8


@pytest.mark.parametrize("source", ["FAFFZFBN", "FBFFZFBN"])
def test_negative_integer_string_aborts(source):
    vm = _Machine(source, ScriptedIO())
    with pytest.raises(HaltError, match="negative"):
        drive(vm)
