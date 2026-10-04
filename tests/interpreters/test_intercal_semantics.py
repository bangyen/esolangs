import random

import pytest

from esolangs.interpreters.other.intercal import _expression, _roman
from esolangs.tools.helpers import fill_runs
from esolangs.tools.intercal import PAIR, TEMPLATE_CHAR, intercal
from tests.interpreters.intercal_cases import finite_cases
from tests.interpreters.intercal_expression import expression
from tests.interpreters.intercal_observer import check
from tests.interpreters.intercal_reference import roman


@pytest.mark.parametrize("shard", range(8))
def test_finite_state(shard):
    for source, text in finite_cases()[shard::8]:
        check(source, text)


@pytest.mark.parametrize("operator", "&V?")
@pytest.mark.parametrize("value", [0, 1, 3, 77, 255, 32768, 65535])
def test_unary_reference(operator, value):
    for source in (f"'{operator}#{value}'", f"#{operator}{value}"):
        actual, end = _expression(source, {})
        assert end == len(source)
        assert actual == expression(source)


@pytest.mark.parametrize("shard", range(16))
def test_roman_reference(shard):
    for value in range(shard, 65536, 16):
        assert _roman(value) == roman(value)


@pytest.mark.parametrize(
    "value", [999999, 1000000, 1000001, 4000000, 2**31 - 1, 2**31, 2**32 - 1]
)
def test_extended_roman_reference(value):
    assert _roman(value) == roman(value)


def generated(source, n, row, answer):
    program = fill_runs(
        source, TEMPLATE_CHAR, [PAIR] * n, [int(bit) for bit in format(row, f"0{n}b")]
    )
    result = check(program, limit=10000)
    assert result["halted"]
    assert result["error"] is None
    assert result["output"] == ("I\n" if answer == "1" else "\n")
    assert result["reads"] == 0


@pytest.mark.parametrize(("n", "shard"), [(1, 0), (2, 0)] + [(3, s) for s in range(16)])
def test_small_generated_state(n, shard):
    for value in range(shard, 2 ** (2**n), 16 if n == 3 else 1):
        table = format(value, f"0{2**n}b")
        for source in dict.fromkeys(intercal(table, w) for w in (None, 1, 13, 100)):
            for row, answer in enumerate(table):
                generated(source, n, row, answer)


def wide_shards(n, family):
    # Eight random n10 rows took 5.7-15.6s; four fit the medium band.
    return 1 << (n - 3 + (n == 10)) if family == "random" and n >= 8 else 16


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "family", "shard", "shards"),
    [
        (n, f, s, wide_shards(n, f))
        for n in range(4, 11)
        for f in ("zero", "one", "parity", "sparse", "dense", "random")
        for s in range(wide_shards(n, f))
    ],
)
def test_wide_generated_state(n, family, shard, shards):
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
    }
    table = tables[family]
    for source in dict.fromkeys(intercal(table, w) for w in (None, 1, 13, 100)):
        for row in range(shard, 2**n, shards):
            generated(source, n, row, table[row])


@pytest.mark.medium
@pytest.mark.parametrize("n", [7, 9])
@pytest.mark.parametrize("shard", range(12))
def test_complementary_generated_state(n, shard):
    rng = random.Random(20260930 + n)
    half = format(rng.getrandbits(2 ** (n - 1)), f"0{2 ** (n - 1)}b")
    table = half + half.translate(str.maketrans("01", "10"))
    rows = random.Random(20260930 + n).sample(range(2**n), 12)
    for source in dict.fromkeys(intercal(table, w) for w in (1, 22, 40, 80)):
        for row in rows[shard::12]:
            generated(source, n, row, table[row])


@pytest.mark.parametrize("source", [".0", "'\"#65535$#65535\"$#1'"])
def test_expression_range_boundaries(source):
    from esolangs.exceptions import HaltError
    from tests.interpreters.intercal_expression import InvalidError

    with pytest.raises(InvalidError):
        expression(source)
    with pytest.raises(HaltError):
        _expression(source, {})


@pytest.mark.parametrize("value", [-1, 2**32])
def test_output_range_boundaries(value):
    from esolangs.exceptions import HaltError
    from tests.interpreters.intercal_reference import InvalidError

    with pytest.raises(InvalidError):
        roman(value)
    with pytest.raises(HaltError):
        _roman(value)


@pytest.mark.parametrize("label", ["0", "65536", "999999", "duplicate"])
def test_constructor_label_boundaries(label):
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.intercal import _Machine
    from tests.interpreters.intercal_reference import InvalidError, Reference

    if label == "duplicate":
        source = "(1) PLEASE GIVE UP\n(1) DO GIVE UP\nDO GIVE UP"
    else:
        source = f"({label}) PLEASE GIVE UP\nDO GIVE UP\nDO GIVE UP"
    with pytest.raises(InvalidError):
        Reference(source)
    with pytest.raises(HaltError):
        _Machine(source, ScriptedIO(""))


def test_bare_statements_and_blank_lines():
    result = check("PLEASE .1 <- #1\n\nREAD OUT .1\nGIVE UP")
    assert result["output"] == "I\n"
    assert result["halted"]


def test_invalid_input_target():
    for target in ("#1", ".X"):
        result = check(f"PLEASE WRITE IN {target}\nDO GIVE UP\nDO GIVE UP", "ONE\n")
        assert result["error"] == "invalid"
        assert result["reads"] == 0
