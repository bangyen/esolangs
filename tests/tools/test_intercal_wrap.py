"""INTERCAL lays logical statements across valid token boundaries."""

import random

import pytest

import esolangs
from esolangs.tools.intercal import intercal


@pytest.mark.parametrize("inputs", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("width", [1, 20, 31, 40, 80, None])
def test_intercal_narrow_expressions_compute_every_row(
    inputs: int, width: int | None
) -> None:
    table = format(random.Random(inputs).getrandbits(1 << inputs), f"0{1 << inputs}b")
    template = esolangs.generate("INTERCAL", table, width)
    natural = intercal(table)
    floor = max(map(len, intercal(table, 1).splitlines()))
    assert template.count("@") == 2 * inputs
    if width is None:
        assert template == natural
    else:
        assert max(map(len, template.splitlines())) <= max(width, floor)
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.intercal import _Machine

    lines = _Machine(
        esolangs.instantiate("INTERCAL", template, [0] * inputs), ScriptedIO("")
    ).lines
    polite = sum(line.startswith("PLEASE ") for line in lines)
    assert len(lines) <= 5 * polite
    assert len(lines) >= 3 * polite
    assert esolangs.evaluate("INTERCAL", table, width=width) == table


@pytest.mark.parametrize(
    "table", ["00", "11", "01", "10", "0000", "1111", "0110", "0001"]
)
def test_intercal_narrow_constant_and_shared_paths(table: str) -> None:
    assert esolangs.evaluate("INTERCAL", table, width=1) == table


def test_intercal_width_splits_an_overwide_expression() -> None:
    table = "01101001"
    assert max(map(len, intercal(table, 1).splitlines())) < max(
        map(len, intercal(table).splitlines())
    )
    assert intercal(table, 1000) == intercal(table)


@pytest.mark.parametrize("width", [1, 6, 9, 13, 17, 19, 22, 26, 40, 80])
def test_intercal_narrow_identities_execute_every_small_table(width: int) -> None:
    for n in range(1, 4):
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            assert esolangs.evaluate("INTERCAL", table, width=width) == table


def test_intercal_xor_floor_and_narrow_corpus_size() -> None:
    assert max(map(len, intercal("0110", 1).splitlines())) == 6
    assert sum(len(intercal(format(value, "08b"), 1)) for value in range(256)) == 92560


@pytest.mark.medium
@pytest.mark.parametrize("n", [7, 9])
def test_intercal_narrow_larger_complementary_branches(n: int) -> None:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.intercal import run
    from esolangs.tools.helpers import fill_runs
    from esolangs.tools.intercal import PAIR, TEMPLATE_CHAR

    rng = random.Random(20260930 + n)
    half = format(rng.getrandbits(2 ** (n - 1)), f"0{2 ** (n - 1)}b")
    for table in (
        "".join(str(row.bit_count() & 1) for row in range(2**n)),
        half + half.translate(str.maketrans("01", "10")),
        format(rng.getrandbits(2**n), f"0{2**n}b"),
    ):
        for width in (1, 22, 40, 80):
            template = intercal(table, width)
            shapes = set()
            for row in rng.sample(range(2**n), 12):
                bits = [int(bit) for bit in format(row, f"0{n}b")]
                program = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
                shapes.add(tuple(map(len, program.splitlines())))
                io = ScriptedIO("")
                run(program, io)
                assert io.getvalue() == ("I\n" if table[row] == "1" else "\n")
            assert len(shapes) == 1


def test_intercal_fitting_primitive_layout_keeps_its_source() -> None:
    from esolangs.tools.intercal import _intercal_narrow

    table = "01101001"
    previous = _intercal_narrow(table, simplify=False)
    width = max(map(len, previous.splitlines()))
    assert intercal(table, width) == previous
    assert esolangs.evaluate("INTERCAL", table, width=width) == table


@pytest.mark.parametrize("width", [1, 6, 9, 17, 19, 20, 22, 40, 80])
@pytest.mark.parametrize("as_string", [False, True])
def test_intercal_split_operations_keep_public_provenance(
    width: int, *, as_string: bool
) -> None:
    table = "0110"
    template = esolangs.generate("INTERCAL", table, width)
    if as_string:
        template = str(template)
    shapes = set()
    for row, expected in enumerate(table):
        bits = list(map(int, format(row, "02b")))
        program = esolangs.instantiate("INTERCAL", template, bits, truth_table=table)
        shapes.add(tuple(map(len, program.splitlines())))
        assert (
            esolangs.read_answer("INTERCAL", esolangs.run("INTERCAL", program))
            == expected
        )
    assert len(shapes) == 1
    with pytest.raises(esolangs.TemplateError, match="is not the template"):
        esolangs.instantiate("INTERCAL", template, [0, 1], truth_table="1001")


@pytest.mark.parametrize("operator", ["&", "V", "?"])
def test_intercal_split_intermediates_fit_onespots(operator: str) -> None:
    from esolangs.interpreters.other.intercal import _expression

    for left in (0, 1):
        for right in (0, 1):
            value, end = _expression(f"'{operator}.1$.2'", {1: left, 2: right})
            intermediate, _bits = value
            assert end == 8
            assert 0 <= intermediate <= 7
            answer, _end = _expression("'.3~#2'", {3: intermediate})
            expected = (
                left & right
                if operator == "&"
                else left | right
                if operator == "V"
                else left ^ right
            )
            assert answer[0] == expected
