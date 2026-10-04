"""Independent Clockwise transitions, encoding, and generated programs."""

import itertools
from collections import deque

import pytest

from esolangs.interpreters.grid_based.clockwise import _Machine
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.clockwise import clockwise
from tests.interpreters.clockwise_observer import Factory, compare
from tests.interpreters.clockwise_reference import Reference


@pytest.mark.parametrize("char", list("R?!+-.;S #λ"))
def test_complete_local_transitions(char):
    prefixes = sorted(
        {
            tuple(int(pattern[i % len(pattern)]) for i in range(length))
            for length in range(7)
            for pattern in ("0", "1", "01")
        }
    )
    counts = (-(10**100), -4, -3, -2, -1, 0, 1, 2, 3, 4, 10**100)
    queues = ((), (0,), (1,), (0, 1), (1, 0))
    for heading, accumulator, prefix, queue in itertools.product(
        range(4), counts, prefixes, queues
    ):
        code = ["   ", " " + char + " ", "   "]
        ref = Reference(code)
        ref.position = 1 + 1j
        ref.direction = (1, 1j, -1, -1j)[heading]
        ref.accumulator = accumulator
        ref.pending = list(prefix)
        ref.queue = deque(queue)
        io = ScriptedIO()
        native = _Machine(code, io)
        native.state = ref.state()
        before = compare(ref, native, io, native.code)
        try:
            ref.step()
        except EOFError:
            try:
                native.step()
            except EOFError:
                pass
            else:
                raise AssertionError("empty queue accepted")
            assert compare(ref, native, io, native.code) == before
        else:
            native.step()
            compare(ref, native, io, native.code)
        assert before == (
            *(
                (
                    1,
                    1,
                    heading,
                    accumulator,
                    tuple(map(str, prefix)),
                    tuple(map(str, queue)),
                )
            ),
            ref.offset,
        )


def test_ascii_and_complete_character_stream():
    top = ".;" * 7 + "R"
    factory = Factory([top, "R" + " " * (len(top) - 2) + "R"])
    for value in range(128):
        assert factory.check(chr(value), chr(value))["halted"]
    for text in ("AB", "A\nB", "A\r\nB", "\x00\x7f", "λ", "😀", "\ud800"):
        value = ord(text[0])
        expected = chr(value // 2 ** (max(7, value.bit_length()) - 7))
        assert factory.check(text, expected)["halted"]
    assert factory.check("")["error"] == "EOFError"


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "shard"), [(1, 0), (2, 0), *((3, shard) for shard in range(16))]
)
@pytest.mark.parametrize("width", [None, 1, 13, 100])
def test_generated_small_tables(n, shard, width):
    stride = 16 if n == 3 else 1
    for value in range(shard, 1 << (1 << n), stride):
        table = format(value, f"0{1 << n}b")
        factory = Factory(clockwise(table, width).splitlines())
        for values in itertools.product("01", repeat=n):
            bits = "".join(values)
            assert factory.check(bits, table[int(bits, 2)])["halted"]


def test_published_programs_and_exact_cycle():
    truth = Factory(
        ["+-?.;.;.;.;.;.;.;?R", "  R              R", "R                 R"]
    )
    for text, expected in (("0", "0"), ("AB", "AB"), ("A\nB", "A\n")):
        assert truth.check(text, expected)["halted"]
    for lines, text, expected in (
        (["+;S;S;S;S;S;+;R", "R             R"], "", "A"),
        (["  !", "! !"], "", ""),
    ):
        assert Factory(lines).check(text, expected)["halted"]
    result = Factory(["SS?R ", "+?+S-", "R!!RS"]).check("")
    assert result["cycle_start"] == 5
    assert result["period"] == 6
    assert not result["halted"]


def test_four_input_zero_minterm():
    table = "1" + "0" * 15
    factory = Factory(clockwise(table).splitlines())
    for value, expected in enumerate(table):
        assert factory.check(format(value, "04b"), expected)["halted"]
