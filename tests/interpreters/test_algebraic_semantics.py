"""Independent expressions, line state, function calls and generated tables."""

import itertools
import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.algebraic_programming_language import (
    _Definition,
    _Machine,
    run,
)
from esolangs.tools.algebraic_programming_language import algebraic_programming_language
from tests.interpreters.algebraic_reference import (
    Function,
    Reference,
    RuntimeFaultError,
    contains_return,
)


def tree(node):
    tag = node[0]
    if tag in ("lit", "var", "ref"):
        return ({"lit": "constant", "var": "variable", "ref": "function"}[tag], node[1])
    if tag in ("neg", "ret"):
        return ({"neg": "minus", "ret": "return"}[tag], tree(node[1]))
    if tag == "bin":
        return ("binary", node[1], tree(node[2]), tree(node[3]))
    return ("invoke", node[1], tuple(tree(arg) for arg in node[2]))


def check(code, stdin="", expected=None, *, snapshots=False):
    reference = Reference(code, stdin)
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    native_cache = {}
    reference_cache = {}
    structures = {}
    control_cache = {}

    def value_key(value):
        if isinstance(value, _Definition):
            key = (value, id(value.body))
            if key not in native_cache:
                shape = (
                    "function",
                    value.name,
                    tuple(value.params),
                    tuple(map(tree, value.body)),
                )
                native_cache[key] = structures.setdefault(shape, shape)
            return native_cache[key]
        if isinstance(value, Function):
            key = (value, id(value.statements))
            if key not in reference_cache:
                shape = (
                    "function",
                    value.name,
                    value.arguments,
                    tuple(value.statements),
                )
                reference_cache[key] = structures.setdefault(shape, shape)
            return reference_cache[key]
        return (type(value).__name__, value)

    steps = 0
    seen_snapshots = set()
    call_keys = {}

    def roots(value, definitions, bindings):
        return tuple(
            (scope, name)
            for scope, mapping in (("definition", definitions), ("global", bindings))
            for name, item in sorted(mapping.items())
            if item is value
        )

    def function_aliases(definitions, bindings, kind):
        groups = {}
        for scope, mapping in (("definition", definitions), ("global", bindings)):
            for name, item in mapping.items():
                if isinstance(item, kind):
                    groups.setdefault(item, []).append((scope, name))
        return sorted(tuple(sorted(labels)) for labels in groups.values())

    while reference.line < len(reference.lines):
        first_call = len(reference.calls)
        reference.step_line()
        calls = []
        while machine.line < reference.line or machine.frames:
            depth = len(machine.frames)
            if snapshots:
                snapshot = machine.snapshot()
                assert snapshot not in seen_snapshots, (
                    "finite evaluation repeats an incomplete snapshot"
                )
                seen_snapshots.add(snapshot)
            machine.step()
            if len(machine.frames) > depth and machine.frames[-1].fn.name:
                frame = machine.frames[-1]
                calls.append(
                    (
                        value_key(frame.fn),
                        roots(frame.fn, machine.defs, machine.globals),
                        tuple(
                            (
                                name,
                                value_key(value),
                                roots(value, machine.defs, machine.globals)
                                if isinstance(value, _Definition)
                                else None,
                            )
                            for name, value in frame.locals.items()
                        ),
                        io.position(),
                    )
                )
                key = machine.frame_entry_key(frame)
                entry = (
                    calls[-1][0],
                    tuple((name, value) for name, value, _ in calls[-1][2]),
                    calls[-1][3],
                )
                assert call_keys.setdefault(key, entry) == entry, (
                    "distinct bodies, arguments or cursors share an ancestor key"
                )
            steps += 1
            assert steps < 100000, "execution bound reached; termination unverified"
        expected_calls = []
        for fn, arguments, offset, aliases, argument_aliases in reference.calls[
            first_call:
        ]:
            expected_calls.append(
                (
                    value_key(fn),
                    aliases,
                    tuple(
                        (name, value_key(value), labels)
                        for name, value, labels in zip(
                            fn.arguments, arguments, argument_aliases, strict=True
                        )
                    ),
                    offset,
                )
            )
        assert calls == expected_calls
        assert machine.line == reference.line
        assert (io.getvalue(), io.position(), io.past_end) == (
            reference.stdout,
            reference.offset,
            reference.past_end,
        )
        assert {name: value_key(value) for name, value in machine.globals.items()} == {
            name: value_key(value) for name, value in reference.globals.items()
        }
        assert {name: value_key(value) for name, value in machine.defs.items()} == {
            name: value_key(value) for name, value in reference.functions.items()
        }
        for name, definition in machine.defs.items():
            fn = reference.functions[name]
            key = (fn, id(fn.statements))
            if key not in control_cache:
                control_cache[key] = [contains_return(node) for node in fn.statements]
            assert definition.control == control_cache[key]
        assert function_aliases(
            machine.defs, machine.globals, _Definition
        ) == function_aliases(reference.functions, reference.globals, Function)
        assert machine.stack == []
        assert machine.ip == (reference.line,)
        assert machine.memory == [
            int(value) if isinstance(value, int | float) else 0
            for _, value in sorted(machine.globals.items())
        ]
    assert machine.halted
    if expected is not None:
        assert reference.stdout == expected
    return machine, io.getvalue()


@pytest.mark.parametrize("operator", ["+", "-", "*", "/", "%", "**", "&", "|"])
def test_arithmetic_and_short_circuit(operator):
    for left, right in itertools.product(
        (-3, -2, -1, 0, 1, 2, 3, 0.1, 0.5, 1.5, 2.0, 3.0), repeat=2
    ):
        code = f"({left}){operator}({right})"
        reference = Reference(code)
        try:
            expected = reference.run()
        except RuntimeFaultError:
            with pytest.raises(HaltError):
                run(code, ScriptedIO())
        else:
            check(code, expected=expected)


@pytest.mark.parametrize(
    "expression", ["-2**2", "-2**-2", "2**3**2", "(-2)**2", "2**-2", "-(2**2)"]
)
def test_power_and_negation(expression):
    check(expression)


@pytest.mark.parametrize(
    "expression",
    ["ab**2", "a**bc", "ab+c", "a+bc", "ab/c", "a/bc", "abc", "-ab**2", "a**-bc"],
)
def test_shorthand_has_multiplication_precedence(expression):
    for a, b, c in itertools.product((1, 2, 3), repeat=3):
        check(f"a={a}\nb={b}\nc={c}\n{expression}")


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        ("72\n101\n108\n108\n111", "", "72\n101\n108\n108\n111\n"),
        ("n", "-2.5\n", "-2.5\n"),
        ("x?=x&x?\nn?", "0", "0\n"),
        ("FLOOR(n)=n-n%1\nFLOOR(x)", "3.25", "3\n"),
        ("CEIL(n)={\nn%1&$(n-n%1+1)\nn\n}\nCEIL(x)", "3.25", "4\n"),
        ("!x={\nx&$0\n$1\n}\n!n", "0", "1\n"),
        ("!x={\nx&$0\n$1\n}\n!n", "2", "0\n"),
        ("IF(x,c)=x&c()\nF()=7\nIF(1,F)", "", "7\n"),
        ("WHILE(x,c)=x()&((c()|1)&WHILE(x,c))\nF()=0\nG()=3\nWHILE(F,G)", "", "0\n"),
        ("a~b=(a+b)/2\n6~8", "", "7\n"),
        ("a@=a*2\n3@@", "", "12\n"),
        ("^a^b^c^=a+b+c\n^1^2^3^", "", "6\n"),
        ("~a`b``c~=(a/b)%c\n~9`3``2~", "", "1\n"),
        ("F()={\n2\n3\n4\n5\n}\nF()", "", "2\n3\n4\n5\n"),
        ("F()={\n0&$1\n7\n}\nF()", "", "7\n"),
        ("F()={\n$4\n5\n}\nF()", "", "4\n"),
        ("F()=7\nf=F\nG(c)=c()\nF()=G(f)\nF()", "", "7\n"),
        ("F()=7\nG(c)=c&3\nG(F)", "", "3\n"),
        (" \nF()={\n\n0&$1\n\n7\n}\n\nF()\n", "", "7\n"),
        ("a+b+d\nc+e+b", "1 2 3 4 5", "6\n11\n"),
        ("0&x\ny+x", "6 7", "0\n13\n"),
    ],
)
def test_function_and_input_profiles(code, stdin, expected):
    check(code, stdin, expected)


@pytest.mark.parametrize(
    "header", ["F(x,x)", "F(xy)", "F(,x)", "F(x,)", "F(x,,y)", "F(", "F(x,"]
)
def test_function_headers_reject_ambiguous_binding(header):
    with pytest.raises(ValueError, match=r".+"):
        run(header + "=x", ScriptedIO())
    with pytest.raises(ValueError, match=r".+"):
        Reference(header + "=x").run()


@pytest.mark.parametrize("code", ["F()={}\nF()", "1a", "(a)b", "1(2)"])
def test_empty_bodies_and_invalid_multiplication(code):
    with pytest.raises(ValueError, match=r".+"):
        run(code, ScriptedIO("2 3"))
    with pytest.raises(ValueError, match=r".+"):
        Reference(code, "2 3").run()


@pytest.mark.parametrize("digits", [400, 4500, 5000])
def test_exact_integer_division_and_output_are_unbounded(digits):
    literal = "1" + "0" * digits
    for code in (literal, literal + "/1", "(" + literal + "+1)/1"):
        expected = (
            literal + "\n" if "+1" not in code else "1" + "0" * (digits - 1) + "1\n"
        )
        check(code, expected=expected)


def test_exact_division_does_not_round_large_integer():
    check("9007199254740993/1", expected="9007199254740993\n")


def test_retained_definition_does_not_alias_redefined_ancestor():
    from esolangs.vm import run_until_halt_or_ancestor

    code = "F()=7\nf=F\nG(c)=c()\nF()=G(f)\nF()"
    io = ScriptedIO()
    machine = _Machine(code, io)
    assert run_until_halt_or_ancestor(machine, limit=1000)
    assert io.getvalue() == "7\n"


@pytest.mark.parametrize("width", [None, 1, 13, 100])
@pytest.mark.parametrize(
    ("n", "start"),
    [(n, start) for n in (1, 2, 3) for start in range(0, 1 << (1 << n), 16)],
)
def test_generated_small_tables(n, start, width):
    for value in range(start, min(start + 16, 1 << (1 << n))):
        table = format(value, f"0{1 << n}b")
        code = algebraic_programming_language(table, width)
        for row in range(1 << n):
            stdin = " ".join(str(row >> (n - 1 - i) & 1) for i in range(n)) + "\n"
            check(code, stdin, table[row] + "\n", snapshots=True)


def wide_table(n, kind):
    length = 1 << n
    if kind == "zero":
        return "0" * length
    if kind == "one":
        return "1" * length
    if kind == "first":
        return "1" + "0" * (length - 1)
    if kind == "last":
        return "0" * (length - 1) + "1"
    if kind == "parity":
        return "".join(str(row.bit_count() % 2) for row in range(length))
    rng = random.Random(731 + n)
    return "".join(str(rng.randrange(2)) for _ in range(length))


@pytest.mark.medium
@pytest.mark.parametrize("width", [None, 1, 13, 100])
@pytest.mark.parametrize("kind", ["zero", "one", "first", "last", "parity", "random"])
@pytest.mark.parametrize(
    ("n", "start", "span"),
    [
        (n, start, 8 if n >= 9 else 16)
        for n in range(4, 11)
        for start in range(0, 1 << n, 8 if n >= 9 else 16)
    ],
)
def test_generated_wide_tables(n, start, span, kind, width):
    table = wide_table(n, kind)
    code = algebraic_programming_language(table, width)
    for row in range(start, min(start + span, 1 << n)):
        stdin = " ".join(str(row >> (n - 1 - i) & 1) for i in range(n)) + "\n"
        check(code, stdin, table[row] + "\n")


@pytest.mark.parametrize("operator", ["+", "-", "*", "/", "%", "&", "|"])
def test_chained_expressions(operator):
    for a, b, c in itertools.product((-1, 0, 1, 2), repeat=3):
        code = f"({a}){operator}({b})+({c})*2"
        try:
            expected = Reference(code).run()
        except RuntimeFaultError:
            with pytest.raises(HaltError):
                run(code, ScriptedIO())
        else:
            check(code, expected=expected)


@pytest.mark.medium  # 4.20s including coverage for 524,289 valid lines.
def test_valid_lines_do_not_exhaust_an_unrelated_cumulative_work_limit():
    source = "0\n" * 524289
    io = ScriptedIO()
    run(source, io)
    assert io.getvalue() == source


@pytest.mark.parametrize(
    "definition",
    ["a~b=a*10+b", "a@=a*2", "!a=a+1", "^a^b^c^=a*100+b*10+c", "~a`b``c~=(a/b)%c"],
)
def test_custom_operator_composition(definition):
    invocation = {
        "a~b": "2~3",
        "a@": "2@",
        "!a": "!2",
        "^a^b^c^": "^2^3^4^",
        "~a`b``c~": "~8`2``3~",
    }[definition.split("=")[0]]
    for expression in (
        invocation,
        "1+" + invocation,
        invocation + "+1",
        "2*" + invocation,
        invocation + "*2",
        invocation + "**2",
        "-(" + invocation + ")",
        "F(" + invocation + ")",
    ):
        check(definition + "\nF(x)=x+5\n" + expression)


def test_longest_operator_match_can_backtrack_without_consuming_input():
    for expression in ("^2", "^2^3", "^2+3", "1+^2^3", "^2^3+4"):
        check("^a=a+1\n^a^b=a*10+b\n" + expression)


@pytest.mark.parametrize(
    ("code", "stdin", "category"),
    [
        ("a=b", "", ValueError),
        ("F()", "", ValueError),
        ("F(x)=x\nF()", "", ValueError),
        ("F()=1\nF", "", HaltError),
        ("F()=1\nF+2", "", HaltError),
        ("(-1)**0.5", "", HaltError),
        ("1" + "0" * 400 + ".0", "", HaltError),
        ("10.0**400", "", HaltError),
        ("a+b", "7", EOFError),
        ("a+b", "7 nope", HaltError),
        ("a", "1" + "0" * 400 + ".0", HaltError),
    ],
)
def test_failure_categories_and_partial_input_state(code, stdin, category):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)

    def execute_invalid():
        for _ in range(1000):
            if machine.halted:
                pytest.fail("invalid program halted without an error")
            machine.step()
        pytest.fail("execution bound reached; error unverified")

    with pytest.raises(category):
        execute_invalid()
    reference = Reference(code, stdin)
    expected_category = RuntimeFaultError if category is HaltError else category
    with pytest.raises(expected_category):
        reference.run()
    assert (io.getvalue(), io.position(), io.past_end) == (
        reference.stdout,
        reference.offset,
        reference.past_end,
    )
    assert machine.globals == reference.globals


def test_function_assignment_records_call_aliases_before_result_binding():
    check("G()=G\nf=G()\nF(c)=c()\ng=F(G)\n1", expected="1\n")


def test_recursive_calls_use_no_host_call_stack():
    check("F(x)={\nx&$F(x-1)\n7\n}\nF(3000)", expected="7\n")


@pytest.mark.parametrize("width", [7, 9, 10, 17, 40, 80])
@pytest.mark.parametrize(
    ("n", "start"),
    [(n, start) for n in (1, 2, 3) for start in range(0, 1 << (1 << n), 16)],
)
def test_old_elementary_width_cases_have_independent_state_checks(n, start, width):
    for value in range(start, min(start + 16, 1 << (1 << n))):
        table = format(value, f"0{1 << n}b")
        code = algebraic_programming_language(table, width)
        for row in range(1 << n):
            stdin = " ".join(str(row >> (n - 1 - i) & 1) for i in range(n)) + "\n"
            check(code, stdin, table[row] + "\n")


@pytest.mark.parametrize("width", [None, 1, 13, 100])
@pytest.mark.parametrize("n", [1, 2, 3])
def test_generated_finite_state_driver(n, width):
    from esolangs.vm import run_until_halt_or_cycle

    tables = sorted(
        {
            wide_table(n, kind)
            for kind in ("zero", "one", "first", "last", "parity", "random")
        }
    )
    for table in tables:
        code = algebraic_programming_language(table, width)
        for row in range(1 << n):
            stdin = " ".join(str(row >> (n - 1 - i) & 1) for i in range(n)) + "\n"
            expected = Reference(code, stdin).run()
            io = ScriptedIO(stdin)
            machine = _Machine(code, io)
            assert run_until_halt_or_cycle(machine, limit=100000)
            assert (expected, io.getvalue()) == (table[row] + "\n",) * 2
            assert io.reads == n


@pytest.mark.parametrize(
    "code",
    [
        "1+1",
        "1" + "0" * 5000,
        "F()=7\nf=F\nF()=8\nG(c)=c()\nG(f)",
        "F(x)=x+x\nF(1)+F(1.0)",
    ],
)
def test_snapshot_driver_preserves_numbers_work_and_retained_functions(code):
    from esolangs.vm import run_until_halt_or_cycle

    expected = Reference(code).run()
    io = ScriptedIO()
    machine = _Machine(code, io)
    assert run_until_halt_or_cycle(machine, limit=100000)
    assert io.getvalue() == expected


@pytest.mark.parametrize("value", [1, -1, 2, 0.5])
def test_same_entry_recursive_call_has_an_independent_repeat_certificate(value):
    from esolangs.vm import run_until_halt_or_ancestor

    class ObservationCompleteError(Exception):
        pass

    class Calls(list):
        def append(self, value):
            if len(self) == 8:
                raise ObservationCompleteError()
            super().append(value)

    code = "x?=x&x?\nn?"
    control = Reference(code, "0")
    control.calls = Calls()
    assert control.run() == "0\n"
    assert len(control.calls) == 1
    reference = Reference(code, str(value))
    reference.calls = Calls()
    with pytest.raises(ObservationCompleteError):
        reference.run()
    assert len(reference.calls) == 8
    assert all(entry == reference.calls[0] for entry in reference.calls)
    assert reference.stdout == ""
    machine = _Machine(code, ScriptedIO(str(value)))
    assert run_until_halt_or_ancestor(machine, limit=16) is False


def test_changing_recursive_bindings_remains_inconclusive():
    from esolangs.vm import run_until_halt_or_ancestor

    with pytest.raises(TimeoutError, match="undecided after 64 pushed frames"):
        run_until_halt_or_ancestor(
            _Machine("F(x)=F(x+1)\nF(0)", ScriptedIO()), limit=64
        )


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        ("F(x)=x\nF(1)\nn\nF(1)", "5", "1\n5\n1\n"),
        ("F(x)=x\nF(1)+F(2)", "", "3\n"),
        ("1+1", "", "2\n"),
        ("1" + "0" * 5000, "", "1" + "0" * 5000 + "\n"),
    ],
)
def test_snapshot_and_entry_keys_distinguish_known_counterexamples(
    code, stdin, expected
):
    check(code, stdin, expected, snapshots=True)


@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("width", [1, 18, 25, 30, 60])
def test_legacy_asymmetric_width_regressions(n, width):
    rng = random.Random(42)
    tables = {}
    for size in range(4, 7):
        tables[size] = "".join(rng.choice("01") for _ in range(1 << size))
    table = tables[n]
    code = algebraic_programming_language(table, width)
    for row in range(1 << n):
        stdin = " ".join(format(row, f"0{n}b")) + "\n"
        check(code, stdin, table[row] + "\n")


@pytest.mark.parametrize(
    ("n", "start", "builder"),
    [
        (n, start, builder)
        for n, count in ((3, 256), (5, 200))
        for start in range(0, count, 8)
        for builder in ("inline", "reduced")
    ],
)
def test_measured_source_corpora_are_executable(n, start, builder):
    from esolangs.tools.algebraic_programming_language import _apl_tree_ordered
    from esolangs.tools.helpers import best_input_order
    from tests.tools.boolean_runners import five_input_sample

    tables = (
        [format(value, "08b") for value in range(256)]
        if n == 3
        else five_input_sample()
    )
    for table in tables[start : start + 8]:
        code = (
            best_input_order(table, _apl_tree_ordered)
            if builder == "inline"
            else algebraic_programming_language(table)
        )
        for row in range(1 << n):
            stdin = " ".join(format(row, f"0{n}b")) + "\n"
            check(code, stdin, table[row] + "\n")
