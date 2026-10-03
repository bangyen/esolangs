"""Independent scanner and rational arithmetic; esolangs.org/wiki/FRACTRAN."""

# ruff: noqa: SLF001

import itertools
import random
from fractions import Fraction

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import _Machine, run
from tests.raises import raises_message

PRIMEGAME = (
    "17/91 78/85 19/51 23/38 29/33 77/29 95/23 77/19 1/17 11/13 13/11 15/14 15/2 55/1"
)


def product(text):
    result = 1
    for term in text.split("*"):
        parts = term.split("^")
        if len(parts) not in (1, 2) or any(
            not part or not all(char.isdecimal() for char in part) for part in parts
        ):
            raise ValueError(f"{term!r} is not a FRACTRAN number or power")
        base = int(parts[0])
        exponent = int(parts[1]) if len(parts) == 2 else 1
        result *= pow(base, exponent)
    return result


def parse(code):
    tokens = []
    at = 0
    while at < len(code):
        if code[at].isspace() or code[at] == ",":
            at += 1
            continue
        start = at
        while at < len(code) and not code[at].isspace() and code[at] != ",":
            at += 1
        tokens.append((start, code[start:at]))
    if not tokens:
        raise ValueError("a FRACTRAN program needs a starting value")
    value = product(tokens[0][1])
    if value <= 0:
        raise ValueError("a FRACTRAN starting value must be positive")
    raw = []
    for _, token in tokens[1:]:
        parts = token.split("/", 1)
        numerator = product(parts[0])
        denominator = product(parts[1]) if len(parts) == 2 else 1
        if denominator == 0:
            raise ValueError(f"FRACTRAN fraction {token!r} divides by zero")
        if numerator <= 0:
            raise ValueError(f"FRACTRAN fraction {token!r} is not positive")
        raw.append((numerator, denominator))
    return value, tuple(raw), tuple(start for start, _ in tokens)


def selection(value, fractions):
    for index, fraction in enumerate(fractions):
        result = value * fraction
        if result.denominator == 1:
            return index, result.numerator
    return None, value


def reference(code, cap):
    value, raw, offsets = parse(code)
    fractions = [Fraction(a, b) for a, b in raw]
    printed = False
    output = ""
    for _ in range(cap):
        if printed:
            break
        chosen, following = selection(value, fractions)
        if chosen is None:
            output = str(value)
            printed = True
        else:
            value = following
    chosen, _ = selection(value, fractions)
    ip = None if chosen is None else offsets[chosen + 1]
    return output, value, ip, printed, printed


def observe(code, cap, threshold_n=None, max_steps=None):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    _, fractions, offsets = parse(code)
    assert machine.fractions == fractions
    assert machine.offsets == offsets
    if threshold_n is not None:
        assert machine._index is not None
        assert all(keys is not None for keys in machine._index.keys.values())
    steps = 0
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
        steps += 1
    if max_steps is not None:
        assert steps <= max_steps
    if threshold_n is not None:
        assert steps <= 4 * threshold_n + 4
        assert machine.inspections <= 16 * (threshold_n + 1) ** 2
    assert io.position() == 0
    assert machine.memory == machine.stack == []
    if machine.halted:
        before = machine.snapshot(), io.getvalue()
        machine.step()
        machine.step()
        assert (machine.snapshot(), io.getvalue()) == before
    return io.getvalue(), machine.value, machine.ip, machine.printed, machine.halted


def corpus():
    pool = [
        "1/2",
        "3/2",
        "2/3",
        "5/2",
        "7/3",
        "6/4",
        "4/6",
        "1/1",
        "1/6",
        "2",
        "1/4",
        "3/4",
    ]
    for count in range(3):
        for rules in itertools.product(pool, repeat=count):
            for start in range(1, 13):
                yield " ".join([str(start), *rules])
                yield " ".join([f"257*{start}", *rules])
    yield from [
        "2^3*3^4 3/2",
        "257*2^3*3^4 3/2",
        "4^3 3/2",
        "2^3*3^4,3/2",
        "6 5/2 7/3",
        "6 7/3 5/2",
        "  6,\t5/2,\n7/3 ",
        "0^0 1/2",
        "257 1/257",
        "258 6/4",
        "257 6/4 1/257",
        "65537 1/65537",
        "2^200 3/2",
        "2^100*3^100 1/2*3",
        "4 3/2^2 1/3",
        "\u0662^\u0663*\u0665 \u0667/\u0662",
        "1 4/6 6/4",
        "2 3/2 2/3",
        "",
        " , \n\t",
        "0 3/2",
        "2 3/0",
        "5 0/3",
        "2 3/x",
        "2 3/2/1",
        "-2",
        "1 -3/2",
        "1 2^-1",
        "1 2^",
        "1 ^2",
        "1 1**2",
        "1 1/",
        "1 /2",
        "1 ²/2",
        "1 1^2^3",
        "1 0/0",
    ]
    rng = random.Random(1716)
    for _ in range(100):
        pairs = [(rng.randrange(1, 25), rng.randrange(1, 25)) for _ in range(6)]
        yield " ".join([str(rng.randrange(1, 50)), *(f"{a}/{b}" for a, b in pairs)])


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 32])
def test_bounded_states_and_parse_errors_match_independent_rationals(cap):
    for code in corpus():
        try:
            expected = reference(code, cap)
        except ValueError as exc:
            with raises_message(ValueError, str(exc)):
                _Machine(code, ScriptedIO())
        else:
            assert observe(code, cap) == expected, (code, cap)


def test_run_matches_proven_halting_reference():
    for code in corpus():
        try:
            result = reference(code, 32)
        except ValueError:
            continue
        if result[-1]:
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == result[0], code
            assert io.position() == 0


@pytest.mark.parametrize(
    ("code", "value", "cap"),
    [
        ("2^3*3^4 3/2", 3**7, 4),
        ("7", 7, 1),
        ("6 5/2 7/3", 15, 1),
        ("6 7/3 5/2", 14, 1),
        ("2 6/4", 3, 1),
        ("2 2/2", 2, 9),
        ("2^3*5 7/2", 1715, 3),
        ("4 3/2^2 1/3", 1, 3),
        ("257 1/257", 1, 2),
        ("0^0 1/2", 1, 1),
    ],
)
def test_reference_positive_controls(code, value, cap):
    result = reference(code, cap)
    assert result[1] == value
    assert observe(code, cap) == result


def test_public_run_uses_supplied_io():
    io = ScriptedIO("unused")
    run("7", io)
    assert io.getvalue() == "7"
    assert io.position() == 0


@pytest.mark.medium
def test_primegame_matches_independent_rational_stream():
    code = "2 " + PRIMEGAME
    value, raw, offsets = parse(code)
    fractions = [Fraction(a, b) for a, b in raw]
    machine = _Machine(code, ScriptedIO())
    seen = []
    for _ in range(60_000):
        assert machine.value == value
        chosen, following = selection(value, fractions)
        assert chosen is not None
        assert machine.ip == offsets[chosen + 1]
        if value & (value - 1) == 0 and value.bit_length() > 2:
            seen.append(value.bit_length() - 1)
        value = following
        machine.step()
    assert seen[:8] == [2, 3, 5, 7, 11, 13, 17, 19]


def test_snapshot_distinguishes_value_and_final_output_step():
    machine = _Machine("2 3/2", ScriptedIO())
    before = machine.snapshot()
    machine.step()
    assert machine.value == 3
    assert machine.snapshot() != before
    before = machine.snapshot()
    assert machine.ip is None
    assert not machine.halted
    machine.step()
    assert machine.snapshot() != before
    assert machine.halted
    assert machine.io.getvalue() == "3"
    literal = _Machine("257 1/257", ScriptedIO())
    assert literal._index is None
    before = literal.snapshot()
    literal.step()
    assert literal.value == 1
    assert literal.snapshot() != before


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("layout", [None, 1, 4, 9, 40, 80, "threshold", "packed"])
def test_every_small_generated_table_in_independent_engine(n, layout):
    from esolangs.tools.fractran import _packed, _threshold

    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        if layout == "threshold":
            template = _threshold(table, n)
        elif layout == "packed":
            template = _packed(table, n)
        else:
            template = esolangs.generate("FRACTRAN", table, width=layout)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("FRACTRAN", template, bits)
            result = reference(code, 10_000)
            assert result[-1], (table, row, layout)
            assert result[1] == (2 if answer == "1" else 1), (table, row, layout)
            assert (
                observe(
                    code,
                    10_000,
                    n if layout == "threshold" else None,
                    4 * n + 4 if layout == 1 else None,
                )
                == result
            ), (table, row, layout)
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == result[0]
            assert io.position() == 0


def test_cancelled_factors_have_canonical_equal_snapshots():
    one = _Machine("2 1/2", ScriptedIO())
    other = _Machine("1 1/2", ScriptedIO())
    one.step()
    assert one.value == other.value == 1
    assert one.ip is other.ip is None
    assert one.snapshot() == other.snapshot()
