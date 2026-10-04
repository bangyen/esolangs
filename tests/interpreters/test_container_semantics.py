"""Independent synchronous rules, ports and generated Container programs."""

# ruff: noqa: SLF001 -- Inspect complete native state.

import itertools

import pytest

from esolangs.interpreters.io import IO, ScriptedIO
from esolangs.interpreters.other import container as native
from esolangs.tools.container import container
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.container_observer import check
from tests.interpreters.test_container import HELLO_WORLD


@pytest.mark.parametrize("operation", ["<=", ">="])
def test_signed_rule_sums_clamp_once(operation):
    for initial, first, second, threshold in itertools.product(
        range(4), range(-3, 4), range(-3, 4), range(4)
    ):
        check(
            [
                f"A={initial}:",
                f"{first} A{operation}{threshold}",
                f"{second} A{operation}{threshold}",
                "EXIT:",
                "1 EXIT>=0",
            ],
            "",
            native._Machine,
        )


def test_every_container_reads_the_old_generation():
    for a, b, delta in itertools.product(range(4), range(4), range(-3, 4)):
        code = [
            f"A={a}:",
            f"{delta} B>=2",
            f"B={b}:",
            f"{-delta} A<=1",
            "EXIT:",
            "1 EXIT>=0",
        ]
        check(code, "", native._Machine)
        check(code[2:4] + code[:2] + code[4:], "", native._Machine)


@pytest.mark.parametrize("port", ["PRINT", ""])
def test_ports_fire_only_on_zero_to_nonzero(port):
    for old, delta, out in itertools.product(
        range(3), range(-2, 3), (0, 65, 127, 128, 200, 511)
    ):
        code = [
            f"{port}={old}:",
            f"{delta} {port}>=0",
            f"OUT={out}:",
            "3 OUT>=0",
            "IN:",
            "EXIT:",
            "1 EXIT>=0",
        ]
        check(code, "λ", native._Machine)


@pytest.mark.parametrize("stdin", ["", "A", "AAB", "\0", "\n", "λ", "😀"])
def test_input_pulses_and_eof_are_complete_states(stdin):
    check(
        [":", "1 <=0", "-1 >=1", "IN:", "EXIT:", "1 IN>=66"],
        stdin,
        native._Machine,
        limit=12,
    )


def test_simultaneous_print_read_and_exit():
    code = [
        ":",
        "1 <=0",
        "PRINT:",
        "1 PRINT<=0",
        "OUT=65:",
        "1 OUT>=0",
        "IN:",
        "EXIT:",
        "1 EXIT>=0",
    ]
    result = check(code, "Z", native._Machine, "B")
    assert result["generations"] == 1
    assert result["reads"] == 1


def test_repeated_input_prevents_a_false_cycle():
    code = [":", "1 <=0", "-1 >=1", "IN:", "EXIT:", "1 IN>=66"]

    class Cursorless(IO):
        def __init__(self):
            super().__init__()
            self.characters = iter("AAB")

        def _read_char(self, _prompt):
            try:
                return next(self.characters)
            except StopIteration:
                raise EOFError from None

    for io in (ScriptedIO("AAB"), Cursorless()):
        machine = native._Machine(code, io)
        assert run_until_halt_or_cycle(machine)
        assert machine.tick == 6
        assert machine.exit_code == 1


def test_genuine_cycles_and_halt_noop():
    result = check(["A:", "1 A<=0", "-1 A>=1"], "", native._Machine)
    assert result["cycle_start"] == 0
    assert result["generations"] == 2
    io = ScriptedIO()
    machine = native._Machine([], io)
    state = machine.snapshot()
    machine.step()
    assert machine.snapshot() == state
    assert machine.tick == 0
    assert io.getvalue() == ""


def test_published_hello_world():
    result = check(HELLO_WORLD, "", native._Machine, "Hello, world!")
    assert result["generations"] == 25
    assert result["reads"] == 0


@pytest.mark.parametrize("position", ["initial", "delta", "operand"])
def test_long_decimal_literals(position):
    literal = "0" * 5000 + "1"
    code = {
        "initial": ["A=" + literal + ":"],
        "delta": ["A:", literal + " A>=0"],
        "operand": ["A=1:", "1 A>=" + literal],
    }[position]
    check([*code, "EXIT:", "1 EXIT>=0"], "", native._Machine)


def test_initial_values_are_nonnegative():
    with pytest.raises(ValueError, match="nonnegative"):
        native._Machine(["A=-1:"], ScriptedIO())
    check(["A=-0:", "EXIT:", "1 EXIT>=0"], "", native._Machine)


@pytest.mark.parametrize(
    ("n", "shard"), [(1, 0), (2, 0), *((3, shard) for shard in range(8))]
)
@pytest.mark.parametrize("width", [None, 1, 7, 8, 13, 100])
@pytest.mark.medium
def test_all_small_generated_tables(n, shard, width):
    stride = 8 if n == 3 else 1
    for value in range(shard, 1 << (1 << n), stride):
        table = format(value, f"0{1 << n}b")
        code = container(table, width).splitlines()
        for row in range(1 << n):
            result = check(code, format(row, f"0{n}b"), native._Machine, table[row])
            assert result["generations"] <= 2 * n + 2
            assert result["reads"] == n


@pytest.mark.parametrize("variant", ["unpruned", "shared", "threshold", "narrow"])
@pytest.mark.medium
@pytest.mark.parametrize("shard", range(8))
def test_direct_generator_paths(variant, shard):
    from esolangs.tools.container import (
        _container_threshold,
        _container_tree,
        _narrow_rules,
    )

    for n in (1, 2, 3):
        if n < 3 and shard:
            continue
        stride = 8 if n == 3 else 1
        for value in range(shard, 1 << (1 << n), stride):
            table = format(value, f"0{1 << n}b")
            if variant == "threshold":
                program = _container_threshold(table)
            elif variant == "narrow":
                program = _narrow_rules(_container_threshold(table), 7)
            else:
                program = _container_tree(
                    table, prune=variant != "unpruned", share=variant == "shared"
                )
            for row in range(1 << n):
                result = check(
                    program.splitlines(),
                    format(row, f"0{n}b"),
                    native._Machine,
                    table[row],
                )
                assert result["generations"] <= 2 * n + 2
                assert result["reads"] == n


@pytest.mark.parametrize("n", [7, 8])
@pytest.mark.parametrize("width", [None, 1, 13, 100])
@pytest.mark.medium
def test_wide_tables_have_linear_tick_bound(n, width):
    import random

    rng = random.Random(20260922 + n)
    table = "".join(rng.choice("01") for _ in range(1 << n))
    code = container(table, width).splitlines()
    for row in range(1 << n):
        result = check(code, format(row, f"0{n}b"), native._Machine, table[row])
        assert result["generations"] <= 2 * n + 2
        assert result["reads"] == n
