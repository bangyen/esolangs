"""Execute the generated DAG and check its reversible swap invariant."""

from fractions import Fraction
from itertools import product
from math import gcd
from random import Random
from unittest.mock import patch

import esolangs
from esolangs import run
from esolangs.generation.decision import reduced_diagram
from esolangs.languages.refractran import generator
from esolangs.languages.refractran.generator import _swap
from esolangs.languages.refractran.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO
from tests.support.generator_support import evaluate_generated, measure_run


def _rational_run(value: int, program: list[str]) -> int:
    """A spec-derived Fraction model, independent of the integer transition."""
    index, direction = 0, 1
    fractions = list(map(Fraction, program))
    for _ in range(10_000):
        if not 0 <= index < len(fractions):
            return value
        result = Fraction(value) * fractions[index] ** direction
        if result.denominator == 1:
            value = result.numerator
            direction = -direction
        index += direction
    raise AssertionError("reference step cap")


def _check_controlled_swap() -> None:
    """Every target/control assignment, with an omitted-reflection control."""
    for target, c0, c1 in product((0, 1), repeat=3):
        before = (3 if target else 2) * 19**c0 * 23**c1
        program = _swap(2, 3, (19, 23))
        expected = (3 if target ^ (c0 & c1) else 2) * 19**c0 * 23**c1
        machine = _Machine(f"{before} " + " ".join(program), ScriptedIO())
        for _ in range(16):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert machine.state.value == _rational_run(before, program) == expected

    assert _rational_run(2 * 19 * 23, _swap(2, 3, (19, 23))[:-1]) != 3 * 19 * 23


def test_tables_and_reference() -> None:
    """Swap invariants, all small tables and seeded larger tables, every row."""
    _check_constants()
    _check_controlled_swap()
    _check_marked_paths()
    _check_pruned_children_and_polarity()
    with patch.object(
        generator,
        "reduced_diagram",
        side_effect=lambda table, n: reduced_diagram(
            table.translate(str.maketrans("01", "10")), n
        ),
    ) as corrupted:
        assert evaluate_generated("REFRACTRAN", "0001") == "1110"
        assert corrupted.called
    parity = "01101001"
    compact = esolangs.generate("REFRACTRAN", parity).source
    with patch.object(generator, "parity_bias", return_value=None) as disabled:
        expanded = esolangs.generate("REFRACTRAN", parity).source
        assert len(expanded) > len(compact)
        assert evaluate_generated("REFRACTRAN", parity) == parity
        assert disabled.called
    assert not hasattr(generator, "_is_parity")
    for n in (1, 2, 3):
        for value in range(2**2**n):
            table = format(value, f"0{2**n}b")
            assert evaluate_generated("REFRACTRAN", table) == table
    for n in (4, 5, 6):
        rng = Random(1847 + n)
        table = "".join(rng.choice("01") for _ in range(2**n))
        template = esolangs.generate("REFRACTRAN", table)
        for row, bits in enumerate(product((0, 1), repeat=n)):
            program = esolangs.instantiate("REFRACTRAN", template, bits)
            initial, *fractions = program.source.split()
            value = 1
            for term in initial.split("*"):
                base, _, exponent = term.partition("^")
                value *= int(base) ** int(exponent or "1")
            answer = _rational_run(value, fractions)
            output = run("REFRACTRAN", program).output
            assert int(output, 2) == answer
            assert esolangs.read_answer("REFRACTRAN", output) == table[row]


def _check_constants() -> None:
    for bit in "01":
        assert generator._diagram(bit, 0) == ([], int(bit))
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("REFRACTRAN", bit * (1 << n), **options)
                assert template.source.count("$") == n
                for bits in ([0] * n, [1] * n):
                    source = esolangs.instantiate("REFRACTRAN", template, bits)
                    io = ScriptedIO("7")
                    machine = _Machine(source.source, io)
                    assert machine.state.value == (1 if bit == "1" else 2) * 3 ** sum(
                        bits
                    )
                    assert machine.state.value.bit_length() <= 2 * n + 1
                    assert not machine.fractions
                    assert not io.getvalue()
                    machine.step()
                    assert machine.halted
                    assert esolangs.read_answer("REFRACTRAN", io.getvalue()) == bit
                    assert io.reads == 0
                    assert io.input_char() == ord("7")


def _check_pruned_children_and_polarity() -> None:

    for table in ("10", "1101", "0110"):
        n = len(table).bit_length() - 1
        for options in ({}, {"width": 1}, {"balance": True}):
            template = esolangs.generate("REFRACTRAN", table, **options)
            assert template.source.count("$") == n
            for row, bits in enumerate(product((0, 1), repeat=n)):
                source = esolangs.instantiate("REFRACTRAN", template, bits)
                io = ScriptedIO("Q")
                machine = _Machine(source.source, io)
                initial = machine.state.value
                if options.get("balance") and not template.source.startswith("2*"):
                    assert initial % 2 == 1
                else:
                    assert initial % 2 == 0
                assert initial % 3 != 0
                assert all(initial % scratch for scratch in (11, 13, 17))
                steps, measured = measure_run(machine)
                assert io.getvalue()[-1] == table[row]
                assert io.reads == 0
                assert io.input_char() == ord("Q")
                assert steps <= 2 * len(source.source) + 1
                assert (
                    measured.bits
                    <= 8 * len(source.source) + len(source.source).bit_length() + 16
                )
    # A complemented root still needs the output rail: odd 1 is not true rail 3.
    source = esolangs.instantiate(
        "REFRACTRAN", esolangs.generate("REFRACTRAN", "10"), [1]
    )
    invalid = source.source.replace("2*", "1*", 1)
    io = ScriptedIO()
    machine = _Machine(invalid, io)
    while not machine.halted:
        machine.step()
    assert io.getvalue()[-1] != "10"[1]


def _check_marked_paths() -> None:
    for table in ("10", "1101", "0110", "00110110", "00010111"):
        n = len(table).bit_length() - 1
        layout = generator._path_program(table)
        assert layout is not None
        text = layout.source
        template = esolangs.TemplateArtifact(
            text, "REFRACTRAN", esolangs.TemplateBindings(setters=(("0", "1"),) * n)
        )
        for row, bits in enumerate(product((0, 1), repeat=n)):
            program = template.fill(bits)
            io = ScriptedIO("Q")
            machine = _Machine(program.source, io)
            initial = machine.state.value
            steps, measured = measure_run(machine, limit=2 * len(text) + 1)
            assert machine.halted
            assert machine.state.value == _rational_run(
                initial, program.source.split()[1:]
            )
            assert io.getvalue()[-1] == table[row]
            assert io.reads == 0
            assert io.input_char() == ord("Q")
            assert steps <= 2 * len(text) + 1
            assert measured.bits <= 8 * len(text) + len(text).bit_length() + 16

    table = "00110110"
    with patch.object(generator, "_swap", wraps=_swap) as swaps:
        generator._path_program(table)
    markers = {
        first.args[0]: gcd(first.args[1], second.args[1])
        for first, second in zip(
            swaps.call_args_list[::2], swaps.call_args_list[1::2], strict=True
        )
    }
    with patch.object(
        generator,
        "_swap",
        side_effect=lambda a, b, controls: _swap(a, b // markers[a], controls),
    ):
        layout = generator._path_program(table)
    assert layout is not None
    broken = layout.source
    template = esolangs.TemplateArtifact(
        broken, "REFRACTRAN", esolangs.TemplateBindings(setters=(("0", "1"),) * 3)
    )
    caught = False
    for row, bits in enumerate(product((0, 1), repeat=3)):
        try:
            result = run(
                "REFRACTRAN",
                template.fill(bits),
                limits=esolangs.ExecutionLimits(max_steps=2 * len(broken) + 1),
            )
        except esolangs.ExecutionCapError:
            caught = True
        else:
            caught |= esolangs.read_answer("REFRACTRAN", result.output) != table[row]
    assert caught
