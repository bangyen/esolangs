"""Execute conflicting specification readings and their generated programs."""

import pytest

from esolangs.interpreters.grid_based import alight
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other import packlang
from esolangs.tools.alight import alight as build_alight
from esolangs.tools.packlang import packlang as build_packlang
from tests.interpreters.test_packlang import DEPENDENCY

_TABLES = [
    *(format(value, "04b") for value in range(16)),
    "01",
    "10",
    "01101001",
    "00110110011010100101110010100110",
]


@pytest.mark.medium
@pytest.mark.parametrize("table", _TABLES)
@pytest.mark.parametrize("syntax", ["infix", "postfix"])
@pytest.mark.parametrize("width", [None, 100])
def test_alight_generated(table, syntax, width):
    source = build_alight(table, width, expression_syntax=syntax)
    if width is not None:
        assert max(map(len, source.splitlines())) <= width
    n = (len(table) - 1).bit_length()
    for row in range(len(table)):
        io = ScriptedIO(format(row, f"0{n}b"))
        alight.run(source, io, expression_syntax=syntax)
        assert io.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("table", _TABLES)
@pytest.mark.parametrize("policy", ["decimal", "binary_digits"])
def test_packlang_generated(table, policy):
    source = build_packlang(table, 32, literal_policy=policy)
    n = (len(table) - 1).bit_length()
    for row in range(len(table)):
        io = ScriptedIO(format(row, f"0{n}b"))
        packlang.run(source, io, literal_policy=policy)
        assert io.getvalue() == table[row]


@pytest.mark.medium
def test_packlang_dependency_readings():
    for policy, expected in (("decimal", "°±±°"), ("binary_digits", "0110")):
        io = ScriptedIO("")
        packlang.run(DEPENDENCY, io, literal_policy=policy)
        assert io.getvalue() == expected


@pytest.mark.medium
@pytest.mark.parametrize(
    ("source", "syntax"),
    [("65 1 +", "postfix"), ("65+1", "infix"), ("[65, 66] 0.5", "bad")],
)
def test_alight_notation(source, syntax):
    io = ScriptedIO("")
    if syntax == "bad":
        with pytest.raises(ValueError, match="one value"):
            alight.run(
                f"begin;var a;set a {source};end;", io, expression_syntax="postfix"
            )
    else:
        alight.run(
            f"begin;var a;set a {source};out a;end;", io, expression_syntax=syntax
        )
        assert io.getvalue() == "B"


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 20, 40])
def test_alight_postfix_narrow_layout(width):
    table = "01101001"
    source = build_alight(table, width, expression_syntax="postfix")
    assert max(map(len, source.splitlines())) <= width
    for row in range(8):
        io = ScriptedIO(format(row, "03b"))
        alight.run(source, io, expression_syntax="postfix")
        assert io.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 11])
def test_packlang_hybrid_multiple_blocks(n):
    table = "00110110" * (2**n // 8)
    source = build_packlang(table, literal_policy="binary_digits")
    for row in (0, 127, 128, 2**n - 1):
        io = ScriptedIO(format(row, f"0{n}b"))
        packlang.run(source, io, literal_policy="binary_digits")
        assert io.getvalue() == table[row]


@pytest.mark.parametrize(
    ("build", "table", "options", "message"),
    [
        (build_alight, "01", {"expression_syntax": "mixed"}, "expression_syntax"),
        (build_packlang, "01", {"literal_policy": "binary"}, "literal_policy"),
    ],
)
def test_invalid_dialects_are_rejected(build, table, options, message):
    with pytest.raises(ValueError, match=message):
        build(table, **options)


@pytest.mark.medium
def test_settings_do_not_leak_between_runs():
    for build, options in (
        (build_alight, {"expression_syntax": "postfix"}),
        (build_packlang, {"literal_policy": "binary_digits"}),
    ):
        before = build("0110")
        build("0110", **options)
        assert build("0110") == before


@pytest.mark.medium
@pytest.mark.parametrize(
    ("expr", "expected"),
    [("right !", "A"), ("left !", "B"), ("at{[65, 66], 1.5}", "B")],
)
def test_postfix_unary_and_nested_lists(expr, expected):
    io = ScriptedIO("")
    command = (
        f"set a {expr}" if expr.startswith("at") else f"set a 65;skip {expr};set a 66"
    )
    alight.run(f"begin;var a;{command};out a;end;", io, expression_syntax="postfix")
    assert io.getvalue() == expected


@pytest.mark.medium
@pytest.mark.parametrize("expr", ["+", "65 +", "!"])
def test_postfix_operator_requires_operands(expr):
    with pytest.raises(ValueError, match="lacks operands"):
        alight.run(
            f"begin;var a;set a {expr};end;",
            ScriptedIO(""),
            expression_syntax="postfix",
        )


def test_postfix_width_must_be_positive():
    with pytest.raises(ValueError, match="width"):
        build_alight("01", 0, expression_syntax="postfix")


@pytest.mark.parametrize("policy", ["decimal", "binary_digits"])
def test_packlang_literal_roundtrip(policy):
    from esolangs._dialects import PacklangLiterals

    literals = PacklangLiterals(policy)
    for value in (0, 1, 2, 10, 48, 128, 255):
        assert literals.parse(literals.emit(value)) == value
    assert literals.parse("255") == 255


@pytest.mark.medium
def test_alight_postfix_chunked_lookup():
    table = "01101001" * 8
    source = build_alight(table, 80, expression_syntax="postfix")
    assert max(map(len, source.splitlines())) <= 80
    for row in range(64):
        io = ScriptedIO(format(row, "06b"))
        alight.run(source, io, expression_syntax="postfix")
        assert io.getvalue() == table[row]
