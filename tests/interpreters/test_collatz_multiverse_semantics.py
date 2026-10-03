"""Independent Collatz Multiverse state, input-order and program execution."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.collatz_multiverse import _Machine, run
from esolangs.tools.collatz_multiverse import collatz_multiverse
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.collatz_reference import Reference


def check(code, stdin="", limit=100):
    ref = Reference(code, stdin)
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for i in range(limit):
        expected_error = actual_error = None
        try:
            ref.step()
        except (ValueError, EOFError) as exc:
            expected_error = type(exc)
        try:
            machine.step()
        except (ValueError, EOFError) as exc:
            actual_error = type(exc)
        assert (
            actual_error is None
            if expected_error is None
            else actual_error is not None and issubclass(actual_error, expected_error)
        ), (code, stdin, i, expected_error, actual_error)
        assert (ref.pc, ref.offset, ref.output, ref.halted) == (
            machine.ip,
            io.position(),
            io.getvalue(),
            machine.halted,
        ), (
            code,
            stdin,
            i,
            ref.cells,
            machine.registers,
            machine.arrays,
            ref.output,
            io.getvalue(),
        )
        actual = {(name, 0): value for name, value in machine.registers.items()}
        actual.update(
            {
                (name, index): value
                for name, cells in machine.arrays.items()
                for index, value in cells.items()
            }
        )
        assert ref.cells == actual, (code, stdin, i, ref.cells, actual)
        if ref.halted:
            before = (
                machine.ip,
                machine.registers,
                machine.arrays,
                io.position(),
                io.getvalue(),
            )
            machine.step()
            assert before == (
                machine.ip,
                machine.registers,
                machine.arrays,
                io.position(),
                io.getvalue(),
            )
            return ref
        if expected_error:
            return ref
    return ref


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("arr", "arr[zero]", "\xff\x01"),
        ("arr[zero]", "arr", "\xff\x01"),
        ("arr[negativeOne]", "arr", "\xff\x00"),
        ("arr", "arr[negativeOne]", "\xff\x00"),
    ],
)
def test_bare_names_and_cell_zero_share_storage(first, second, expected):
    code = (
        f"{first}=negativeOne x+negativeOne,DO PRINT.\n"
        f"{second}=negativeOne x+zero,DO PRINT."
    )
    assert check(code).output == expected
    io = ScriptedIO("")
    run(code, io)
    assert io.getvalue() == expected


@pytest.mark.medium
def test_signed_arithmetic_inputs_and_nonzero_array_cells():
    operands = (
        "zero",
        "negativeOne",
        "v",
        "v[negativeOne]",
        "input",
        "lineNumber",
        "missing[input]",
        "v[input]",
        "input[input]",
    )
    values = (-1000, -257, -4, -3, -2, -1, 0, 1, 2, 3, 6, 255, 256, 257, 1001)
    for target, value, left, right, flag in itertools.product(
        ("v", "v[negativeOne]"), values, operands, operands, ("DO", "NOT")
    ):
        code = (
            f"{target}=zero x+input,NOT PRINT.\n{target}={left} x+{right},{flag} PRINT."
        )
        assert check(code, f"{value} 3 -7 9 -11", limit=5).halted


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        ("lineNumber=zero x+lineNumber,DO PRINT.", "", False),
        ("a=zero x+negativeOne,DO PRINT.\nlineNumber=zero x+zero,DO PRINT.", "", False),
        ("lineNumber=zero x+zero,DO PRINT.", "", True),
        ("lineNumber=negativeOne x+negativeOne,DO PRINT.", "", True),
        ("lineNumber=zero x+input,DO PRINT.", "1 0", True),
        (
            "v=zero x+input,NOT PRINT.\n"
            "v=negativeOne x+negativeOne,NOT PRINT.\n"
            "lineNumber=zero x+v,NOT PRINT.",
            "4 0",
            True,
        ),
        (
            "v[negativeOne]=zero x+input,NOT PRINT.\n"
            "v[negativeOne]=negativeOne x+negativeOne,NOT PRINT.\n"
            "lineNumber=zero x+v[negativeOne],NOT PRINT.",
            "4 0",
            True,
        ),
    ],
)
def test_complete_state_repetition_certifies_halt_or_cycle(code, stdin, expected):
    reference = Reference(code, stdin)
    seen = set()
    for _ in range(100):
        if reference.halted:
            outcome = True
            break
        key = (reference.pc, tuple(sorted(reference.cells.items())), reference.offset)
        if key in seen:
            outcome = False
            break
        seen.add(key)
        reference.step()
    else:
        pytest.fail("no complete-state certificate within the bounded control")
    assert outcome is expected
    assert (
        run_until_halt_or_cycle(_Machine(code, ScriptedIO(stdin)), limit=100)
        is expected
    )
    check(code, stdin, limit=25)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "a=negativeOne x+zero,DO PRINT",
        "a=negativeOne x+zero,YES PRINT.",
        "a=3x+zero,DO PRINT.",
        "a=negativeOne x+1,DO PRINT.",
        "a[1]=negativeOne x+zero,DO PRINT.",
        "input=negativeOne x+zero,DO PRINT.",
        "input[zero]=negativeOne x+zero,DO PRINT.",
        "a=negativeOne+zero,DO PRINT.",
        "a=negativeOne y+zero,DO PRINT.",
        "a=negativeOne x+zero,DOprint.",
        "a=negativeOne x+zero,DO PRINT..",
        "a=negativeOne x+zero,DO PRINT.#comment",
        "a=negativeOne x+zero,DO PRINT. extra",
        "a[b[c]]=zero x+zero,DO PRINT.",
        "a=negativeOne x+zero,do PRINT.",
    ],
)
def test_whole_program_syntax_before_input(bad):
    for prefix in (
        "",
        "a=negativeOne x+zero,DO PRINT.\n",
        "lineNumber=zero x+zero,NOT PRINT.\n",
    ):
        code = prefix + bad
        expected_error = None
        try:
            Reference(code, "")
        except ValueError:
            expected_error = ValueError
        io = ScriptedIO("9")
        if expected_error:
            with pytest.raises(expected_error):
                _Machine(code, io)
        else:
            _Machine(code, io)
        assert io.position() == 0


@pytest.mark.medium
def test_generator_positive_controls():
    for table in ("00", "01", "10", "11", "0110", "0011", "0101", "10000000"):
        n = (len(table) - 1).bit_length()
        for width in (None, 1):
            code = collatz_multiverse(table, width=width)
            for row, expected in enumerate(table):
                reference = check(code, " ".join(format(row, f"0{n}b")), limit=10000)
                assert reference.halted
                assert reference.output == expected
                assert reference.offset == 2 * n - 1


@pytest.mark.slow
def test_all_small_generated_tables():
    for n in (1, 2, 3):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            for width in (None, 1):
                code = collatz_multiverse(table, width=width)
                for row, expected in enumerate(table):
                    reference = check(
                        code, " ".join(format(row, f"0{n}b")), limit=10000
                    )
                    assert reference.halted
                    assert reference.output == expected
                    assert reference.offset == 2 * n - 1


@pytest.mark.slow
def test_wide_generated_tables_and_high_input_indices():
    rng = random.Random(189082)
    for n, count in ((4, 12), (5, 4), (6, 2)):
        size = 1 << n
        tables = [
            "0" * size,
            "1" * size,
            "".join(str(row.bit_count() % 2) for row in range(size)),
        ]
        tables += ["".join(rng.choice("01") for _ in range(size)) for _ in range(count)]
        tables += [
            "".join(str(int(row == point)) for row in range(size))
            for point in (0, size // 2, size - 1)
        ]
        for table in tables:
            for width in (None, 1):
                code = collatz_multiverse(table, width=width)
                for row, expected in enumerate(table):
                    reference = check(
                        code, " ".join(format(row, f"0{n}b")), limit=10000
                    )
                    assert reference.halted
                    assert reference.output == expected
                    assert reference.offset == 2 * n - 1
    for n in (8, 10, 12):
        size = 1 << n
        table = "".join(rng.choice("01") for _ in range(size))
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
        for width in (None, 1, 29, 40, 80):
            code = collatz_multiverse(table, width=width)
            for row in indices:
                reference = check(code, " ".join(format(row, f"0{n}b")), limit=10000)
                assert reference.halted
                assert reference.output == table[row]
                assert reference.offset == 2 * n - 1
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
                code = collatz_multiverse(table, width=width)
                for row in indices:
                    reference = check(
                        code, " ".join(format(row, f"0{n}b")), limit=10000
                    )
                    assert reference.halted
                    assert reference.output == table[row]
                    assert reference.offset == 2 * n - 1


@pytest.mark.medium
def test_public_generator_width_transitions():
    from esolangs import generate

    for table in ("00", "11", "0110", "0001", "10010110"):
        n = (len(table) - 1).bit_length()
        for width in (1, 25, 26, 27, 28, 29, 40):
            code = generate("collatz-multiverse", table, width)
            for row, expected in enumerate(table):
                reference = check(code, " ".join(format(row, f"0{n}b")), limit=10000)
                assert reference.halted
                assert reference.output == expected
                assert reference.offset == 2 * n - 1


@pytest.mark.parametrize(
    "stdin", ["", " ", "\n\t", "bad", "3 bad", "³", "٣ 0", "-7 257"]
)
def test_empty_program_and_numeric_input_errors(stdin):
    assert check("", stdin).halted
    check("x=zero x+input,DO PRINT.\nx=input x+input,DO PRINT.", stdin)
