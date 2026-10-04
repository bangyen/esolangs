"""Execute both readings of specification gaps and their generated programs."""

from itertools import product

import pytest

from esolangs._dialects import LineDialect
from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based import alight, flowchart
from esolangs.interpreters.grid_based.flowchart import _Machine as FlowchartMachine
from esolangs.interpreters.grid_based.flowchart import _Pointer
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other import packlang
from esolangs.interpreters.queue_based import bitdeque
from esolangs.interpreters.queue_based.bitdeque import _Machine as BitdequeMachine
from esolangs.interpreters.stack_based import false
from esolangs.interpreters.tape_based import line
from esolangs.interpreters.tape_based.line import _Machine as LineMachine
from esolangs.interpreters.tape_based.line import simulate
from esolangs.raster import Raster
from esolangs.tools.alight import alight as build_alight
from esolangs.tools.bitdeque import bitdeque as build_bitdeque
from esolangs.tools.bitdeque import bitdeque_setters
from esolangs.tools.false import false as build_false
from esolangs.tools.flowchart import flowchart as build_flowchart
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.tools.line import line as build_line
from esolangs.tools.line.render import chain
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
@pytest.mark.parametrize("base", [0, 1])
@pytest.mark.parametrize("width", [None, 1])
def test_bitdeque_generated(table, base, width):
    source = build_bitdeque(table, width, index_base=base)
    n = (len(table) - 1).bit_length()
    setters = bitdeque_setters(source, n, index_base=base)
    for row, bits in enumerate(product((0, 1), repeat=n)):
        filled = fill_runs(source, TEMPLATE_CHAR, setters, bits)
        io = ScriptedIO("")
        bitdeque.run(filled, io, index_base=base)
        assert io.getvalue() == table[row]


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
@pytest.mark.parametrize("table", _TABLES)
@pytest.mark.parametrize(
    ("base", "unset", "unknown"),
    product((0, 1), ("error", "zero"), ("ignore", "error")),
)
def test_false_generated(table, base, unset, unknown):
    options = {"pick_base": base, "unset_variables": unset, "unknown_commands": unknown}
    source = build_false(table, **options)
    n = (len(table) - 1).bit_length()
    for row in range(len(table)):
        io = ScriptedIO(format(row, f"0{n}b"))
        false.run(source, io, **options)
        assert io.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("table", _TABLES)
@pytest.mark.parametrize(
    ("schedule", "cursor"), product(("creation", "reverse"), ("pointer", "shared"))
)
@pytest.mark.parametrize("width", [None, 20])
def test_flowchart_generated(table, schedule, cursor, width):
    options = {"scheduling": schedule, "deque_cursor": cursor}
    source = build_flowchart(table, width, **options)
    n = (len(table) - 1).bit_length()
    for row in range(len(table)):
        io = ScriptedIO(format(row, f"0{n}b"))
        flowchart.run(source.splitlines(), io, **options)
        assert io.getvalue() == table[row]


@pytest.mark.medium
@pytest.mark.parametrize("table", _TABLES)
@pytest.mark.parametrize("modulus", [None, 2, 255, 256])
@pytest.mark.parametrize("boundary", ["error", "wrap", "clamp"])
def test_line_generated(table, modulus, boundary):
    n = (len(table) - 1).bit_length()
    options = {"cell_modulus": modulus, "tape_size": n + 1, "boundary": boundary}
    source = build_line(table, **options)
    for row in range(len(table)):
        io = ScriptedIO(" ".join(format(row, f"0{n}b")))
        line.run(source, io, **options)
        assert io.getvalue() == table[row]


@pytest.mark.medium
def test_bitdeque_target_readings():
    for base, expected in ((0, ""), (1, "1")):
        io = ScriptedIO("")
        bitdeque.run("INVERT GOTO 3 PUSH", io, index_base=base)
        assert io.getvalue() == expected
    with pytest.raises(ValueError, match="below index_base"):
        BitdequeMachine("GOTO 0", ScriptedIO(""), index_base=1)


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
def test_false_policy_controls():
    for base, expected in ((0, "7"), (1, "8")):
        io = ScriptedIO("")
        false.run("7 8 1ø.", io, pick_base=base)
        assert io.getvalue() == expected
    io = ScriptedIO("")
    false.run("a;.", io, unset_variables="zero")
    assert io.getvalue() == "0"
    with pytest.raises(HaltError, match="before it was stored"):
        false.run("a;", ScriptedIO(""))
    with pytest.raises(ValueError, match="unknown FALSE command"):
        false.run("`", ScriptedIO(""), unknown_commands="error")
    false.run('"`"{`}', ScriptedIO(""), unknown_commands="error")


@pytest.mark.medium
@pytest.mark.parametrize(("boundary", "expected"), [("wrap", "1"), ("clamp", "0")])
def test_line_boundary_controls(boundary, expected):
    io = ScriptedIO("")
    simulate.run_node(
        chain("+", "<", "+", ">", "o"),
        simulate.IO(write=io.print_num),
        dialect=LineDialect(2, 2, boundary),
    )
    assert io.getvalue() == expected
    with pytest.raises(HaltError, match="finite tape"):
        simulate.run_node(chain("<"), simulate.IO(), dialect=LineDialect(tape_size=2))


@pytest.mark.medium
def test_line_cells_and_pixels():
    output = []
    simulate.run_node(
        chain("-", "o"), simulate.IO(write=output.append), dialect=LineDialect(255)
    )
    assert output == [254]
    source = build_line("0110", cell_modulus=2, tape_size=3)
    pixels = Raster(source.rows)
    for row in range(4):
        io = ScriptedIO(" ".join(format(row, "02b")))
        machine = LineMachine(pixels, io, cell_modulus=2, tape_size=3)
        for _ in range(100):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert io.getvalue() == "0110"[row]
    with pytest.raises(ValueError, match="at least 3"):
        build_line("0110", tape_size=2)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("scheduling", "expected"), [("creation", "01"), ("reverse", "10")]
)
def test_flowchart_scheduling_is_observable(scheduling, expected):
    io = ScriptedIO("")
    machine = FlowchartMachine(["( )─\\ \\─(( ))"], io, scheduling=scheduling)
    machine.pointers = [_Pointer(0, 4, (0, 1), reg=bit, prev=(0, 3)) for bit in (0, 1)]
    machine.step()
    assert io.getvalue() == expected


@pytest.mark.medium
@pytest.mark.parametrize(("cursor", "slot"), [("pointer", 0), ("shared", 1)])
def test_flowchart_cursor_is_observable(cursor, slot):
    machine = FlowchartMachine(
        ["( )─[ >─\\[ ]/─(( ))"], ScriptedIO(""), deque_cursor=cursor
    )
    machine.pointers = [
        _Pointer(0, 4, (0, 1), prev=(0, 3)),
        _Pointer(0, 8, (0, 1), reg=1, prev=(0, 7)),
    ]
    before = machine.snapshot()
    machine.step()
    assert machine.deques == {slot: [1]}
    assert machine.snapshot() != before
    if cursor == "shared":
        assert machine.snapshot()[-1] == 1


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
        (build_bitdeque, "01", {"index_base": 2}, "index_base"),
        (build_alight, "01", {"expression_syntax": "mixed"}, "expression_syntax"),
        (build_packlang, "01", {"literal_policy": "binary"}, "literal_policy"),
        (build_false, "01", {"pick_base": 2}, "index_base"),
        (build_false, "01", {"unset_variables": "random"}, "unset_variables"),
        (build_false, "01", {"unknown_commands": "execute"}, "unknown_commands"),
        (build_flowchart, "01", {"scheduling": "random"}, "scheduling"),
        (build_flowchart, "01", {"deque_cursor": "random"}, "deque_cursor"),
        (build_line, "01", {"cell_modulus": 1}, "cell_modulus"),
        (build_line, "01", {"tape_size": 0}, "tape_size"),
        (build_line, "01", {"boundary": "ignore"}, "boundary"),
        (build_line, "01", {"boundary": "wrap"}, "tape_size"),
    ],
)
def test_invalid_dialects_are_rejected(build, table, options, message):
    with pytest.raises(ValueError, match=message):
        build(table, **options)


@pytest.mark.medium
def test_settings_do_not_leak_between_runs():
    for build, options in (
        (build_bitdeque, {"index_base": 1}),
        (build_alight, {"expression_syntax": "postfix"}),
        (build_packlang, {"literal_policy": "binary_digits"}),
        (build_false, {"unset_variables": "zero"}),
        (build_flowchart, {"deque_cursor": "shared"}),
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


@pytest.mark.medium
def test_strict_false_accepts_flush_and_whitespace():
    false.run("B ß\n", ScriptedIO(""), unknown_commands="error")


@pytest.mark.parametrize("policy", ["decimal", "binary_digits"])
def test_packlang_literal_roundtrip(policy):
    from esolangs._dialects import PacklangLiterals

    literals = PacklangLiterals(policy)
    for value in (0, 1, 2, 10, 48, 128, 255):
        assert literals.parse(literals.emit(value)) == value
    assert literals.parse("255") == 255


@pytest.mark.parametrize("value", [True, 1.5])
def test_noninteger_sizes_and_bases_are_rejected(value):
    with pytest.raises(ValueError, match="index_base"):
        build_bitdeque("01", index_base=value)
    with pytest.raises(ValueError, match="cell_modulus"):
        build_line("01", cell_modulus=value)
    with pytest.raises(ValueError, match="tape_size"):
        build_line("01", tape_size=value)


@pytest.mark.medium
def test_alight_postfix_chunked_lookup():
    table = "01101001" * 8
    source = build_alight(table, 80, expression_syntax="postfix")
    assert max(map(len, source.splitlines())) <= 80
    for row in range(64):
        io = ScriptedIO(format(row, "06b"))
        alight.run(source, io, expression_syntax="postfix")
        assert io.getvalue() == table[row]
