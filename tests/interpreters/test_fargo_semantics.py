"""Independent Fargo expression and generated-program execution checks."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fargo import _Machine, run
from esolangs.tools.fargo import fargo
from tests.interpreters.fargo_reference import Reference


def check(code, stdin="0"):
    reference = Reference(code, stdin)
    reference.execute()
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(10000):
        if machine.halted:
            break
        machine.step()
    else:
        pytest.fail("Fargo execution exceeded the bounded control")
    assert (io.getvalue(), io.position(), machine.output) == (
        reference.text,
        reference.offset,
        reference.output,
    )
    return reference.text


@pytest.mark.medium
def test_binary_expressions_and_input_framing():
    atoms = [
        "0",
        "1",
        "10",
        "101",
        "@ 0",
        "@ 1",
        "< 101",
        "> 11",
        "[?] +[] [] 1 [] 0 0",
        "[?] +[] [] 0 [] 1 1",
    ]
    expressions = atoms + [
        f"{op} {left} {right}"
        for op in ("&", "|", "^")
        for left, right in itertools.product(atoms, repeat=2)
    ]
    for expression, stdin in itertools.product(
        expressions, ("", "0", "-7", "10", "bad", "٣", "+257 next")
    ):
        check(f"% 0 {expression}\n$", stdin)


@pytest.mark.parametrize(
    ("body", "argument", "expected"),
    [
        ("f", "emit", "1"),
        (": 1 f", "emit", "1"),
        (": 0 f", "emit", "0"),
        (": 1 f", ":emit", "1"),
    ],
)
def test_marked_parameter_passes_a_function_without_running_it(
    body, argument, expected
):
    code = f"emit % 0 1\napply :f {body}\napply {argument}\n$"
    assert check(code) == expected
    io = ScriptedIO("0")
    run(code, io)
    assert io.getvalue() == expected


@pytest.mark.slow
def test_all_small_generated_tables_at_width_boundaries():
    for n in (1, 2, 3):
        for values in itertools.product("01", repeat=1 << n):
            table = "".join(values)
            for width in (None, 1, 4, 20):
                code = fargo(table, width=width)
                for row, expected in enumerate(table):
                    assert check(code, str(row)) == expected


@pytest.mark.parametrize(
    ("definition", "target", "arguments", "expected"),
    [
        ("identity x | x 0", "identity", "1", "1"),
        ("identity x | x 0", "identity", "0", "0"),
        ("", "<", "10", "1"),
        ("", ">", "1", "0"),
        ("", "&", "1 0", "0"),
        ("", "|", "0 1", "1"),
        ("", "^", "1 1", "0"),
    ],
)
def test_bound_function_calls_consume_their_arguments(
    definition, target, arguments, expected
):
    names = " ".join(("x", "y")[: len(arguments.split())])
    for mark in ("", ":"):
        code = (
            f"{definition}\napply :f {names} f {names}\n"
            f"% 0 apply {mark}{target} {arguments}\n$"
        )
        assert check(code) == expected
        io = ScriptedIO("0")
        run(code, io)
        assert io.getvalue() == expected


def test_bound_arity_rejects_extra_calls_before_side_effects():
    code = "emit % 0 1\napply :f f $\napply emit"
    io = ScriptedIO("0")
    machine = _Machine(code, io)

    def advance():
        for _ in range(100):
            machine.step()

    with pytest.raises(ValueError, match="more than one outer call"):
        advance()
    assert (machine.output, io.getvalue()) == (0, "")


@pytest.mark.parametrize(
    "code",
    [
        "% 0 nope 1",
        "% 0",
        "% 0 [?] [] 1 1",
        "% 0 [?] 1 0",
        "% 0 < [] 1",
        "% 0 : 1 <",
        "apply f : 1 f\napply 1",
        "f & 1\n$",
        "empty",
        "f & 1 nope\nf",
        "f $ $\n$",
        "emit % 0 1\napply :f f $\napply emit",
        "emit % 0 1\napply :f & f\napply emit",
    ],
)
def test_independent_error_controls(code):
    from esolangs.exceptions import HaltError

    reference = None
    io = ScriptedIO("0")
    machine = None
    expected_error = actual_error = None
    try:
        reference = Reference(code, "0")
        reference.execute()
    except (ValueError, HaltError) as error:
        expected_error = type(error)
    try:
        machine = _Machine(code, io)
        for _ in range(500):
            if machine.halted:
                break
            machine.step()
        else:
            pytest.fail("error control exceeded its step bound")
    except (ValueError, HaltError) as error:
        actual_error = type(error)
    assert expected_error is not None
    assert actual_error is expected_error
    assert io.getvalue() == ("" if reference is None else reference.text)
    assert io.position() == (0 if reference is None else reference.offset)


@pytest.mark.parametrize("stdin", ["0", "1"])
def test_truth_machine_has_an_independent_recursive_call_certificate(stdin):
    from esolangs.vm import run_until_halt_or_ancestor
    from tests.interpreters.fargo_reference import CycleError

    code = "one ^ $ one\n% 0 @ 0\n: @ 0 one\n$"
    reference = Reference(code, stdin)
    if stdin == "1":
        with pytest.raises(CycleError):
            reference.execute()
    else:
        reference.execute()
        assert reference.text == "0"
    machine = _Machine(code, ScriptedIO(stdin))
    assert run_until_halt_or_ancestor(machine) is (stdin == "0")


@pytest.mark.medium
def test_generated_program_positive_controls():
    for table in ("0000", "1111", "0110", "1000", "0011", "0101"):
        for width in (None, 1):
            code = fargo(table, width=width)
            for row, expected in enumerate(table):
                assert check(code, str(row)) == expected


@pytest.mark.parametrize(
    "code",
    [
        "% 0 1\n% 1 1\n% 100 1\n$\n% 1 0\n$",
        "% 0 | 0 $\n$",
        "% 0 | 0 % 11 1\n$",
        "% 0 [?] +[] +[] +[] +[] [] 0 [] 0 [] 1 [] 0 [] 0 > 1\n$",
        "% 0 [?] +[] +[] +[] +[] [] 0 [] 0 [] 1 [] 0 [] 0 < 100\n$",
    ],
)
def test_sequential_writes_and_full_shift_values(code):
    check(code)


@pytest.mark.parametrize(
    ("body", "call"),
    [("loop :f loop emit", "loop emit"), ("loop x loop [] :emit", "loop [] :emit")],
)
def test_repeated_function_resolution_has_a_recursive_call_certificate(body, call):
    from esolangs.vm import run_until_halt_or_ancestor
    from tests.interpreters.fargo_reference import CycleError

    code = f"emit % 0 1\n{body}\n{call}"
    reference = Reference(code, "0")
    with pytest.raises(CycleError):
        reference.execute()
    machine = _Machine(code, ScriptedIO("0"))
    assert run_until_halt_or_ancestor(machine, limit=100) is False


def test_names_comments_and_unused_definitions():
    code = (
        "# ignored # comment\n\n"
        "f: x | x 0\n2 x > x\nunused x & x nope\n"
        "​% 0 f: [?] +[] [] 0 [] 1 1 # ignored\n$ $"
    )
    assert check(code, "  +3 next") == "11"


@pytest.mark.slow
def test_wide_generated_programs_and_input_index_boundaries():
    rng = random.Random(83121)
    for n, count in ((4, 40), (5, 20), (6, 4)):
        size = 1 << n
        tables = [
            "0" * size,
            "1" * size,
            "".join(str(row.bit_count() & 1) for row in range(size)),
        ]
        tables += ["".join(rng.choice("01") for _ in range(size)) for _ in range(count)]
        tables += [
            "".join(str(int(row == point)) for row in range(size))
            for point in (0, size // 2, size - 1)
        ]
        for table in tables:
            for width in (None, 1):
                code = fargo(table, width=width)
                for row, expected in enumerate(table):
                    assert check(code, str(row)) == expected
    for n in (8, 10, 12, 17):
        size = 1 << n
        indices = sorted(
            {
                0,
                size - 1,
                size // 2 - 1,
                size // 2,
                *[1 << bit for bit in range(n)],
                *[size - 1 - (1 << bit) for bit in range(n)],
            }
        )
        tables = (
            "0" * size,
            "1" * size,
            "".join(str((row >> (n - 1)) ^ (row & 1)) for row in range(size)),
        )
        for table in tables:
            for width in (None, 1):
                code = fargo(table, width=width)
                for row in indices:
                    assert check(code, str(row)) == table[row]


@pytest.mark.parametrize(
    "code",
    ["", "f | 1 0\nf | 0 0\n% 0 f\n$", "% 0 : 1 1\n$", "% 0 1\n: 1 $", "% 0 1\n: 0 $"],
)
def test_empty_program_and_conditional_values(code):
    check(code)
