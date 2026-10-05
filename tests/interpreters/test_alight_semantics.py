"""Independent Alight geometry, postfix tapes, frames and list graphs."""

import itertools

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.alight import _Machine
from esolangs.interpreters.io import ScriptedIO


def execute(program):
    io = ScriptedIO()
    machine = _Machine([program], io)
    for _ in range(10000):
        machine.snapshot()
        if machine.halted:
            return machine, io.getvalue()
        machine.step()
    pytest.fail("execution bound reached; termination unverified")


@pytest.mark.parametrize("space", [" ", "\t", "\v", "\f", "\u2003"])
def test_token_whitespace(space):
    machine, output = execute(
        f"begin;var{space}x;set{space}x{space}65{space}+{space}0;out{space}x;end;"
    )
    assert output == "A"
    assert machine.vars == {"x": 65}


@pytest.mark.parametrize(
    "expr", ["[65,[66]]", "[[65],66]", "[65]+[[66]]", "[[65]]+[66]"]
)
def test_lists_reject_mixed_element_kinds(expr):
    with pytest.raises(HaltError, match="wrong type"):
        execute(f"begin;var x;set x {expr};end;")


@pytest.mark.parametrize("special", ["nil", "eof", "left", "right"])
def test_specials_do_not_determine_list_kind(special):
    _, output = execute(
        f"begin;var x;set x [{special},[65]];set x at{{x,0.5,[66]}};"
        "var c;set c at{at{x,0.5},0.5};out c;end;"
    )
    assert output == "B"
    with pytest.raises(HaltError, match="wrong type"):
        execute(f"begin;var x;set x [{special},[65]];at{{x,0.5,66}};end;")


def partitions(size):
    for values in itertools.product(range(size), repeat=size):
        if values[0] == 0 and all(
            values[i] <= 1 + max(values[:i]) for i in range(1, size)
        ):
            yield values


def test_all_five_variable_alias_partitions_have_distinct_snapshots():
    snapshots = set()
    for groups in partitions(5):
        commands = ["begin"]
        for i, group in enumerate(groups):
            commands.append(f"var v{i}")
            first = groups.index(group)
            commands.append(f'set v{i} "A"' if first == i else f"set v{i} v{first}")
        machine, _ = execute(";".join([*commands, "end", ""]))
        snapshot = machine.snapshot()
        assert hash(snapshot) == hash(machine.snapshot())
        assert snapshot not in snapshots
        snapshots.add(snapshot)
        # Mutation distinguishes each alias class independently of the encoding.
        for changed in range(5):
            original = machine.vars[f"v{changed}"][0]
            machine.vars[f"v{changed}"][0] = 66
            assert [machine.vars[f"v{i}"][0] for i in range(5)] == [
                66 if groups[i] == groups[changed] else 65 for i in range(5)
            ]
            assert machine.snapshot() != snapshot
            machine.vars[f"v{changed}"][0] = original
            assert machine.snapshot() == snapshot
    assert len(snapshots) == 52


@pytest.mark.parametrize("size", [1, 2, 3])
def test_cyclic_list_graphs_snapshot_without_recursion(size):
    snapshots = set()
    for edges in itertools.product(range(size), repeat=size):
        prefix = ["begin"]
        for i in range(size):
            prefix.extend([f"var v{i}", f"set v{i} [[]]"])
        machine, _ = execute(";".join([*prefix, "end", ""]))
        for i, target in enumerate(edges):
            machine.vars[f"v{i}"][0] = machine.vars[f"v{target}"]
        for i, target in enumerate(edges):
            assert machine.vars[f"v{i}"][0] is machine.vars[f"v{target}"]
        snapshot = machine.snapshot()
        assert snapshot not in snapshots
        snapshots.add(snapshot)
        # Reallocation preserves the same graph while removing every host identity.
        rebuilt = [[] for _ in range(size)]
        for i, target in enumerate(edges):
            rebuilt[i].append(rebuilt[target])
        machine.vars.update({f"v{i}": node for i, node in enumerate(rebuilt)})
        assert machine.snapshot() == snapshot
    assert len(snapshots) == size**size


def test_deep_list_graph_snapshot_uses_no_host_call_stack():
    machine, _ = execute("begin;var x;set x [65];end;")
    for _ in range(1500):
        machine.vars["x"] = [machine.vars["x"]]
    snapshot = machine.snapshot()
    assert hash(snapshot) == hash(machine.snapshot())


def test_snapshots_preserve_aliases_across_suspended_function_frames():
    machine = _Machine(
        ['begin;var x;set x "A";var z;set z f{x};end;', "func f{a};end a;"],
        ScriptedIO(),
    )
    for _ in range(10):
        machine.step()
        if len(machine.walkers) == 2:
            break
    assert len(machine.walkers) == 2
    parent, child = machine.walkers
    assert child.vars["a"] is parent.vars["x"]
    shared = machine.snapshot()
    child.vars["a"] = [65]
    assert machine.snapshot() != shared
    child.vars["a"] = parent.vars["x"]
    assert machine.snapshot() == shared
    banked_hash = hash(shared)
    parent.vars["x"][0] = 66
    assert child.vars["a"] == [66]
    assert machine.snapshot() != shared
    assert hash(shared) == banked_hash


def test_decimal_arithmetic_against_integer_cross_products():
    from math import gcd

    operands = [
        (value, places) for value in (0, 1, 2, 3, 7, 19) for places in (0, 1, 2)
    ]
    for (a, sa), (b, sb), op in itertools.product(operands, operands, "+-*/"):
        if op == "/" and b == 0:
            continue
        da, db = 10**sa, 10**sb
        if op == "+":
            numerator, denominator = a * db + b * da, da * db
        elif op == "-":
            numerator, denominator = a * db - b * da, da * db
        elif op == "*":
            numerator, denominator = a * b, da * db
        else:
            numerator, denominator = a * db, da * b
        divisor = gcd(numerator, denominator)
        expected = (numerator // divisor, denominator // divisor)

        def literal(value, places):
            digits = str(value).zfill(places + 1)
            return digits if not places else digits[:-places] + "." + digits[-places:]

        machine, _ = execute(
            f"begin;var x;set x {literal(a, sa)}{op}{literal(b, sb)};end;"
        )
        result = machine.vars["x"]
        assert result.as_integer_ratio() == expected
        assert machine.memory == [int(numerator / denominator)]


def test_decimal_equality_selects_the_mathematical_branch():
    _, output = execute("begin;var x;set x 65;skip 0.1+0.2=0.3;end;out x;end;")
    assert output == "A"


@pytest.mark.parametrize("literal", ["0" * 5000 + "65", "0" * 5000 + "65.000"])
def test_long_decimal_literals_have_no_host_digit_limit(literal):
    _, output = execute(f"begin;var x;set x {literal};out x;end;")
    assert output == "A"


@pytest.mark.parametrize("length", [400, 5000])
def test_large_finite_values_raise_language_output_errors(length):
    with pytest.raises(HaltError, match="not a character code"):
        execute(f"begin;var x;set x {'9' * length};out x;end;")


@pytest.mark.parametrize("text", ["'", "a'", "';", "';'", "''a;'"])
def test_apostrophes_inside_strings_do_not_quote_the_closing_delimiter(text):
    machine, _ = execute(f'begin;var x;set x "{text}";end;')
    assert machine.vars["x"] == list(map(ord, text))


def test_geometric_reader_against_independent_tokenized_paths():
    from esolangs.interpreters.grid_based.alight import _scan
    from tests.interpreters.alight_reference import Grid

    commands = [
        "",
        " ",
        "begin",
        "end",
        "turn left",
        "skip right",
        "var x",
        "set x 65",
        'set x "a;b"',
        'set x "\'"',
        "set x \"a';b'\"",
        "set x ';",
        "set x '\"",
        'set x "unclosed',
        "set x '",
    ]
    cases = 0
    for command, suffix, direction, padding in itertools.product(
        commands, [";end;", ""], [1, 1j, -1, -1j], [0, 2]
    ):
        text = command + suffix
        span = max(1, len(text))
        width = span + 2 * padding if direction.real else 1 + 2 * padding
        height = span + 2 * padding if direction.imag else 1 + 2 * padding
        origin = complex(padding, padding)
        if direction.real < 0:
            origin += span - 1
        if direction.imag < 0:
            origin += (span - 1) * 1j
        cells = [[" " for _ in range(width)] for _ in range(height)]
        for offset, char in enumerate(text):
            point = origin + offset * direction
            cells[int(point.imag)][int(point.real)] = char
        rows = ["".join(row) for row in cells]
        reference = Grid(rows)
        native_args = (
            rows,
            int(origin.imag),
            int(origin.real),
            (int(direction.imag), int(direction.real)),
        )
        try:
            value, pivot = reference.read(origin, direction)
        except ValueError:
            with pytest.raises(ValueError, match="unterminated string literal"):
                _scan(*native_args)
        else:
            assert _scan(*native_args) == (value, int(pivot.imag), int(pivot.real))
        cases += 1
    assert cases == 240


@pytest.mark.parametrize("other", ["left", "right"])
def test_cyclic_list_equality_reaches_a_value_instead_of_recursing(other):
    machine, output = execute(
        "begin;var x;set x [[],left];at{x,0.5,x};"
        f"var y;set y [[],{other}];at{{y,0.5,y}};"
        "var c;set c 65;skip x=y;end;out c;end;"
    )
    assert output == ("A" if other == "left" else "")
    assert machine.halted


def test_structural_equality_is_independent_of_aliases_and_cycle_length():
    _, output = execute(
        "begin;var x;set x [[],left];at{x,0.5,x};"
        "var y;set y [[],left];var z;set z [[],left];"
        "at{y,0.5,z};at{z,0.5,y};"
        "var c;set c 65;skip x=y;end;out c;end;"
    )
    assert output == "A"


@pytest.mark.parametrize("operator", "+-*/=<>&|^")
def test_expressions_against_independent_postfix_compiler(operator):
    from tests.interpreters.alight_reference import (
        AlightFaultError,
        evaluate_expression,
    )

    operands = [
        "0",
        "1",
        ".5",
        "0.1",
        "nil",
        "eof",
        "left",
        "right",
        "[1,nil]",
        "[[2]]",
        '"a;b"',
        "v",
        "at{v,.5}",
        "at{v,.5,66}",
        "len{v}",
        "len{v,2}",
        "trunc{0.5}",
        "sign{0-1}",
        "[]",
    ]
    checked = 0
    for a, b in itertools.product(operands, repeat=2):
        expression = f"{a}{operator}{b}"
        variables = {"v": [65]}
        try:
            expected = evaluate_expression(expression, variables)
        except AlightFaultError:
            with pytest.raises(HaltError):
                execute(f"begin;var v;set v [65];var x;set x {expression};end;")
        else:
            machine, _ = execute(
                f"begin;var v;set v [65];var x;set x {expression};end;"
            )
            assert machine.vars["x"] == expected, expression
            assert machine.vars["v"] == variables["v"], expression
        checked += 1
    assert checked == 361


@pytest.mark.parametrize(
    "expression",
    [
        "1/0+at{v,.5,66}",
        "!nil=at{v,.5,66}",
        "unknown+at{v,.5,66}",
        "len{v}+1+at{v,.5,66}",
        "[nil,[65]]+at{v,.5,66}",
    ],
)
def test_effectful_expression_error_state_matches_postfix_evaluation(expression):
    from tests.interpreters.alight_reference import (
        AlightFaultError,
        evaluate_expression,
    )

    variables = {"v": [65]}
    with pytest.raises(AlightFaultError):
        evaluate_expression(expression, variables)
    machine = _Machine(
        [f"begin;var v;set v [65];var x;set x {expression};end;"], ScriptedIO()
    )

    def finish():
        for _ in range(20):
            machine.step()
            if machine.halted:
                pytest.fail("the reference rejected a program that halted normally")
        pytest.fail("execution bound reached; result unverified")

    with pytest.raises(HaltError):
        finish()
    assert machine.vars["v"] == variables["v"]


@pytest.mark.parametrize("first", "+-*/=<>&|^")
def test_chained_expressions_compare_results_and_error_time_state(first):
    from tests.interpreters.alight_reference import (
        AlightFaultError,
        evaluate_expression,
    )

    operands = ["0", "1", "left", "at{v,.5}", "at{v,.5,66}"]
    checked = 0
    for a, b, c, second in itertools.product(
        operands, operands, operands, "+-*/=<>&|^"
    ):
        expression = f"{a}{first}{b}{second}{c}"
        variables = {"v": [65]}
        rejected = False
        try:
            expected = evaluate_expression(expression, variables)
        except AlightFaultError:
            rejected = True
        machine = _Machine(
            [f"begin;var v;set v [65];var x;set x {expression};end;"], ScriptedIO()
        )
        native_rejected = False
        for _ in range(20):
            try:
                machine.step()
            except HaltError:
                native_rejected = True
                break
            if machine.halted:
                break
        else:
            pytest.fail("execution bound reached; result unverified")
        assert native_rejected == rejected, expression
        assert machine.vars["v"] == variables["v"], expression
        if not rejected:
            assert machine.vars["x"] == expected, expression
        checked += 1
    assert checked == 1250


def check_walker(rows, stdin="", limit=2000):
    from tests.interpreters.alight_reference import (
        AlightFaultError,
        Reference,
        structural_equal,
    )

    io = ScriptedIO(stdin)
    native = _Machine(rows, io)
    reference = Reference(rows, stdin)
    from tests.interpreters.alight_reference import reference_state

    seen = {}
    for step in range(limit):
        state = reference_state(reference)
        assert native_state(native) == state
        if state in seen:
            assert native.snapshot() == seen[state]
            return native, reference, step
        seen[state] = native.snapshot()
        assert native.halted == reference.done
        assert io.getvalue() == reference.output
        assert io.position() == reference.offset
        assert io.past_end == reference.past_end
        assert len(native.walkers) == len(reference.frames)
        active = reference.frames[-1]
        assert native.ip == (
            int(active.position.imag),
            int(active.position.real),
            int(active.direction.imag),
            int(active.direction.real),
        )
        assert native.stack == [
            (int(frame.position.imag), int(frame.position.real))
            for frame in reference.frames[:-1]
        ]
        assert native.memory == [
            int(value)
            for _, value in sorted(active.variables.items())
            if not isinstance(value, str | list)
        ]
        for actual, expected in zip(native.walkers, reference.frames, strict=True):
            assert complex(actual.col, actual.row) == expected.position
            assert complex(actual.heading[1], actual.heading[0]) == expected.direction
            assert actual.vars.keys() == expected.variables.keys()
            assert all(
                structural_equal(actual.vars[name], expected.variables[name])
                for name in actual.vars
            )
        if reference.done:
            return native, reference, step
        try:
            reference.step()
        except AlightFaultError:
            with pytest.raises(HaltError):
                native.step()
            assert io.getvalue() == reference.output
            assert io.position() == reference.offset
            expected_variables = reference.frames[-1].variables
            assert native.vars.keys() == expected_variables.keys()
            assert all(
                structural_equal(native.vars[name], expected_variables[name])
                for name in native.vars
            )
            return native, reference, step + 1
        except ValueError:
            with pytest.raises(ValueError, match=r"."):
                native.step()
            assert io.getvalue() == reference.output
            assert io.position() == reference.offset
            assert len(native.walkers) == len(reference.frames)
            expected_variables = reference.frames[-1].variables
            assert native.vars.keys() == expected_variables.keys()
            assert all(
                structural_equal(native.vars[name], expected_variables[name])
                for name in native.vars
            )
            return native, reference, step + 1
        native.step()
    pytest.fail("execution bound reached; result unverified")


def rotate_source(rows, direction):
    width = max(map(len, rows))
    cells = {}
    for y, row in enumerate(rows):
        for x, char in enumerate(row.ljust(width)):
            cells[direction * complex(x, y)] = char
    low_x = int(min(point.real for point in cells))
    low_y = int(min(point.imag for point in cells))
    high_x = int(max(point.real for point in cells))
    high_y = int(max(point.imag for point in cells))
    return [
        "".join(cells.get(complex(x, y), " ") for x in range(low_x, high_x + 1))
        for y in range(low_y, high_y + 1)
    ]


@pytest.mark.parametrize("direction", [1, 1j, -1, -1j])
def test_reference_walks_straight_commands_in_every_heading(direction):
    programs = [
        "begin;end;",
        "begin;;;end",
        "begin;var x;set x 65;out x;end;",
        "begin;var x;inp x;out x;end;",
        "begin;skip left;undefined;end;",
        "begin;skip right;var x;set x 65;out x;end;",
        "begin;wait 0.5;end;",
        'begin;var x;set x "\';a";end;',
        "begin;var x;set x 1/0;end;",
        "begin;var x;set x [65,[66]];end;",
        "begin;out missing;end;",
    ]
    for source, stdin in itertools.product(programs, ["", "A", "\n", "🙂"]):
        check_walker(rotate_source([source], direction), stdin)


@pytest.mark.parametrize("direction", [1, 1j, -1, -1j])
def test_reference_walks_calls_and_suspended_returns(direction):
    cases = [
        ["begin;var x;set x f{65};out x;end;", "func f{a};end a;"],
        [
            "begin;var x;set x f{64}+1;out x;end;",
            "func f{a};end g{a};",
            "func g{b};end b;",
        ],
        [
            "begin;var x;set x f{1}+f{2};out x;end;",
            "func f{a};var c;set c a+64;out c;end 32;",
        ],
        [
            'begin;var x;set x "A";var c;set c f{x};out c;end;',
            "func f{a};at{a,.5,66};end at{a,.5};",
        ],
        ["begin;var x;set x f{};end;", "func f{};end;"],
    ]
    for rows in cases:
        check_walker(rotate_source(rows, direction))


def test_reference_executes_the_three_published_examples():
    from tests.interpreters.alight_examples import CAT_SKIP, CAT_TURN, REVERSED_CAT

    checked = 0
    for rows, stdin in itertools.product(
        [CAT_SKIP, CAT_TURN, REVERSED_CAT],
        ["", "a", "ab", "\n", "a\nb\n", "\n\n", "'\";", "🙂λ\n"],
    ):
        _, reference, _ = check_walker(rows, stdin)
        if rows == REVERSED_CAT and stdin:
            assert not reference.done
            assert reference.output == ""
        else:
            assert reference.done
            assert reference.output == stdin
        assert reference.offset == len(stdin)
        assert reference.past_end == 1
        checked += 1
    assert checked == 24


@pytest.mark.medium  # 3.68s for all 54,756 graph pairs.
def test_cyclic_equality_against_partition_refinement():
    from esolangs.interpreters.grid_based.alight import _compare
    from tests.interpreters.alight_reference import structural_equal

    roots = []
    for size in (1, 2, 3):
        for edges, labels in itertools.product(
            itertools.product(range(size), repeat=size),
            itertools.product(["left", "right"], repeat=size),
        ):
            nodes = [[] for _ in range(size)]
            for index, target in enumerate(edges):
                nodes[index].extend([nodes[target], labels[index]])
            roots.append(nodes[0])
    assert len(roots) == 234
    for a, b in itertools.product(roots, repeat=2):
        expected = "left" if structural_equal(a, b) else "right"
        assert _compare("=", a, b) == expected


def native_expression(expression, returned=None):
    if expression is None:
        return None
    replaced = False

    def convert(node):
        nonlocal replaced
        kind = node[0]
        if kind in ("num", "val", "special"):
            return "value", node[1]
        if kind == "var":
            return "variable", node[1]
        if kind == "not":
            return "not", convert(node[1])
        if kind == "bin":
            return "binary", node[1], convert(node[2]), convert(node[3])
        if kind == "list":
            return "list", tuple(map(convert, node[1]))
        args = tuple(map(convert, node[2]))
        if returned is not None and not replaced:
            replaced = True
            return "value", returned
        return "call", node[1], args

    return convert(expression)


def native_state(machine):
    from tests.interpreters.alight_reference import graph_key

    frames = tuple(
        (
            complex(frame.col, frame.row),
            complex(frame.heading[1], frame.heading[0]),
            frame.vars,
            native_expression(frame.pending, frame.returned),
        )
        for frame in machine.walkers
    )
    return graph_key(frames), machine.halted, machine.io.position()


@pytest.mark.parametrize("direction", [1, 1j, -1, -1j])
def test_complete_state_cycle_certificates_in_main_and_called_walks(direction):
    from esolangs.vm import run_until_halt_or_cycle
    from tests.interpreters.alight_examples import LOOP

    ring = LOOP
    called = [
        "begin;var v;set v r{};end;",
        "func r{};turn right;",
        *["   " + line for line in ring[1:]],
    ]
    for original in (ring, called):
        rows = rotate_source(original, direction)
        native, reference, steps = check_walker(rows)
        assert not reference.done
        assert not native.halted
        assert steps > 0
        assert run_until_halt_or_cycle(_Machine(rows, ScriptedIO())) is False


def clockwise_ring(prefix, commands):
    top = prefix + commands + "turn right;"
    left = len(prefix) - 1
    right = len(top) - 1
    cells = {(x, 0): char for x, char in enumerate(top)}
    for y, char in enumerate("turn right;", start=1):
        cells[right, y] = char
    west = ";" * (right - left - 11) + "turn right;"
    for offset, char in enumerate(west, start=1):
        cells[right - offset, 11] = char
    for offset, char in enumerate("turn right;", start=1):
        cells[left, 11 - offset] = char
    return [
        "".join(cells.get((x, y), " ") for x in range(right + 1)) for y in range(12)
    ]


def test_complete_state_cycle_waits_until_input_and_eof_values_repeat():
    rows = clockwise_ring("begin;var x;", "inp x;")
    native, reference, _ = check_walker(rows, "ab\n")
    assert not native.halted
    assert not reference.done
    assert reference.offset == 3
    assert reference.frames[-1].variables == {"x": "eof"}
    assert reference.past_end >= 2


@pytest.mark.parametrize("width", [None, 1, 13, 100])
@pytest.mark.parametrize(
    ("n", "start"), [(1, 0), (2, 0), *[(3, start) for start in range(0, 256, 32)]]
)
@pytest.mark.medium
def test_generated_small_tables_against_complete_reference(n, start, width):
    from esolangs.tools.alight import alight

    for value in range(start, min(start + 32, 1 << (1 << n))):
        table = format(value, f"0{1 << n}b")
        source = alight(table, width=width)
        for row, answer in enumerate(table):
            _, reference, _ = check_walker(source.splitlines(), format(row, f"0{n}b"))
            assert reference.done
            assert reference.output == answer
            assert reference.offset == n
            assert reference.past_end == 0


@pytest.mark.parametrize("width", [None, 1, 13, 100])
@pytest.mark.parametrize("kind", ["zero", "one", "parity", "first", "last", "random"])
@pytest.mark.parametrize(
    ("n", "start"), [(n, start) for n in range(4, 11) for start in range(0, 1 << n, 64)]
)
@pytest.mark.medium
def test_generated_wider_tables_against_complete_reference(n, start, kind, width):
    import random

    from esolangs.tools.alight import alight

    size = 1 << n
    if kind == "zero":
        table = "0" * size
    elif kind == "one":
        table = "1" * size
    elif kind == "first":
        table = "1" + "0" * (size - 1)
    elif kind == "last":
        table = "0" * (size - 1) + "1"
    elif kind == "parity":
        table = "".join(str(row.bit_count() % 2) for row in range(size))
    else:
        rng = random.Random(197 * n)
        table = "".join(str(rng.randrange(2)) for _ in range(size))
    source = alight(table, width=width)
    for row in range(start, min(start + 64, size)):
        _, reference, _ = check_walker(source.splitlines(), format(row, f"0{n}b"))
        assert reference.done
        assert reference.output == table[row]
        assert reference.offset == n
        assert reference.past_end == 0


@pytest.mark.parametrize("name", ["²", "³", "λ", "x7", "\uff11\uff12x"])
def test_alphanumeric_variables_are_not_superscript_decimal_literals(name):
    _, reference, _ = check_walker(
        [f"begin;var {name};set {name} 65;var x;set x {name};out x;end;"]
    )
    assert reference.done
    assert reference.output == "A"


@pytest.mark.parametrize("name", ["²", "1", "1f", "\uff11\uff12x", "λ"])
def test_call_braces_disambiguate_alphanumeric_function_names(name):
    _, reference, _ = check_walker(
        [f"begin;var x;set x {name}{{65}};out x;end;", f"func {name}{{a}};end a;"]
    )
    assert reference.done
    assert reference.output == "A"


@pytest.mark.parametrize(
    "rows",
    [
        ["begin;var f;set f 65;var x;set x f{f};out x;end;", "func f{a};end a;"],
        ["begin;var a;set a 66;var x;set x f{65};out x;out a;end;", "func f{a};end a;"],
        ["begin;var a;set a 65;var x;set x f{};end;", "func f{};end a;"],
        ["begin;var x;set x f{65};end;", "func f{a,b};end a;"],
        ["begin;var x;set x f{65};end;", "func f{a-b};end a;"],
        ["begin;var x;set x f{65};end;", "func f{end};end 65;"],
        ["begin;var x;set x f{65};end;", "func f{a}trailing;end a;"],
        ["begin;var x;set x f{65};end;", "func f{a};var a;end a;"],
        ["begin;var x;set x f{65};end;", "func f{a};set a 66;end a;"],
    ],
)
def test_reference_checks_namespaces_headers_and_argument_binding(rows):
    check_walker(rows)


@pytest.mark.parametrize(
    "command",
    [
        "f{} trailing",
        "set x f{} trailing",
        "set x at{v,.5,66} trailing",
        "wait at{v,.5,66} trailing",
        "end f{} trailing",
    ],
)
def test_malformed_expression_is_rejected_before_call_effects(command):
    check_walker(
        [
            f"begin;var v;set v [65];var x;{command};end;",
            "func f{};var c;set c 65;out c;end 65;",
        ]
    )


@pytest.mark.parametrize("target", ["end", "missing", "123"])
def test_assignment_target_is_validated_before_rhs_call(target):
    check_walker(
        [
            f"begin;var v;set v [65];set {target} f{{}};end;",
            "func f{};var c;set c 65;out c;end 65;",
        ]
    )


@pytest.mark.parametrize(
    "template",
    [
        "{number}+eof",
        'at{{"A",{number}.5,65}}',
        '"A"*trunc{{0-{number}}}',
        'len{{"A",0-{number}}}',
        "!{number}",
    ],
)
def test_runtime_error_messages_do_not_format_unbounded_numbers(template):
    expression = template.format(number="9" * 5000)
    native, reference, _ = check_walker([f"begin;var x;set x {expression};end;"])
    assert not native.halted
    assert not reference.done


@pytest.mark.parametrize("command", ["out x", "turn x"])
def test_runtime_errors_accept_deep_values_without_repr_recursion(command):
    from tests.interpreters.alight_reference import AlightFaultError, Reference

    rows = [f"begin;var x;{command};end;"]
    native = _Machine(rows, ScriptedIO())
    reference = Reference(rows)
    for _ in range(2):
        native.step()
        reference.step()
    value = [65]
    for _ in range(1500):
        value = [value]
    native.vars["x"] = value
    reference.frames[-1].variables["x"] = value
    with pytest.raises(AlightFaultError):
        reference.step()
    with pytest.raises(HaltError):
        native.step()


@pytest.mark.parametrize("direction", [1, 1j, -1, -1j])
def test_multi_argument_returns_and_sibling_effects_are_executed_once(direction):
    cases = [
        ["begin;var x;set x add{60,5};out x;end;", "func add{a,b};end a+b;"],
        [
            "begin;var l;set l [65];var x;"
            "set x len{at{l,.5,at{l,.5}+1}}+f{}+g{};"
            "var c;set c at{l,.5};out c;end;",
            "func f{};end 0;",
            "func g{};end 0;",
        ],
        [
            "begin;var x;set x f{65};out x;end;",
            "func f{a};var b;" + "set b a;" * 40 + "end b;",
        ],
    ]
    for rows, answer in zip(cases, ("A", "A", "A"), strict=True):
        _, reference, _ = check_walker(rotate_source(rows, direction))
        assert reference.done
        assert reference.output == answer


@pytest.mark.parametrize("direction", [1, 1j, -1, -1j])
def test_bare_builtin_resolves_user_calls_inside_its_arguments(direction):
    rows = [
        "begin;var v;set v [65];at{v,.5,f{66}};var c;set c at{v,.5};out c;end;",
        "func f{a};end a;",
    ]
    _, reference, _ = check_walker(rotate_source(rows, direction))
    assert reference.done
    assert reference.output == "A"


@pytest.mark.parametrize("name", ["nil", "eof", "left", "right"])
def test_function_namespace_can_use_special_names_in_bare_calls(name):
    _, reference, _ = check_walker(
        [
            f"begin;{name}{{65}};end;",
            f"func {name}{{a}};out a;end;",
        ]
    )
    assert reference.done
    assert reference.output == "A"


@pytest.mark.parametrize("command", ["var{65}", "inp{65}", "out{65}"])
def test_command_keywords_take_precedence_over_bare_function_spelling(command):
    check_walker([f"begin;{command};end;"])


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ('"AB"', [65, 66]),
        ("'A", 65),
        ("';", 59),
        ("'\"", 34),
        ("'λ", 955),
        ("65=65", "left"),
        ("65<66", "left"),
        ("66>65", "left"),
        ("left&right", "right"),
        ("left|right", "left"),
        ("left^left", "right"),
    ],
)
def test_literal_and_predicate_results(expression, expected):
    machine, output = execute(f"begin;var x;set x {expression};end;")
    assert machine.vars["x"] == expected
    assert output == ""


@pytest.mark.parametrize("expression", ["", "65+"])
def test_missing_operand_is_rejected(expression):
    with pytest.raises(ValueError, match="expression ends early"):
        execute(f"begin;var x;set x {expression};end;")


@pytest.mark.parametrize("index", ["0", "1", "0.25"])
def test_list_index_must_be_a_nonnegative_half_integer(index):
    with pytest.raises(HaltError, match=r"list index is not 0\.5"):
        execute(f"begin;var x;set x at{{[65],{index}}};end;")
