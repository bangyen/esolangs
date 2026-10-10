"""bfpda generator tests."""

import random

import pytest

from tests.tools.fills import _run_form


class TestParameterizedBfpda:
    """Input-by-substitution boolean generator for the no-input language BF-PDA."""

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is four characters whichever bit it carries."""
        from esolangs.tools.bfpda import BFPDA_PAIR
        from tests.tools.fills import fill

        _fill_bfpda = fill("BF-PDA")

        for n in (1, 2, 3):
            template = _run_form(BFPDA_PAIR, n)
            for i in range(n):
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bfpda(template, zeros)) == len(
                    _fill_bfpda(template, ones)
                ), f"n={n} input {i}"

    def test_leaf_leaves_the_stack_empty(self) -> None:
        """A zero drains and prints the empty stack; a one prints the bottom marker."""
        from esolangs import tools as generators

        assert generators.bfpda("10") == "@<$[>>.]>[>@.>]"  # NOT
        assert generators.bfpda("0110") == (
            "@<$<@<$[>>[>>.]>[>@.>]]>[>[>>@.>]>[>.]]"  # XOR
        )

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        """Total emitted bytes over every three-input table."""
        from esolangs import tools as generators

        total = sum(len(generators.bfpda(format(v, "08b"))) for v in range(256))
        assert total == 14502


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.tools.bfpda import _bfpda_tree, _reflected
    from tests.generator_support import assert_shared_program

    a, b = "0001" * 16, "0110" * 16
    table = _reflected(a + b + b + a, 8)
    plain, _ = _bfpda_tree(table)
    assert_shared_program("BF-PDA", table, plain, 82, lambda _: 3 * 8 + 4)


def _execute_bank(table, template, rows):
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.bf_pda import _Machine
    from scripts.benchmark import WrittenState
    from tests.tools.fills import _fill_bfpda

    n = len(table).bit_length() - 1
    header, tail = template[: 4 * n - 1], template[4 * n - 1 :]
    vm = _Machine(_fill_bfpda(template, [0] * n), ScriptedIO(""))
    maximum = 0
    for row in rows:
        vm.code = _fill_bfpda(header, [int(bit) for bit in f"{row:0{n}b}"]) + tail
        vm.io, vm.state = ScriptedIO(""), (0, ())
        written = WrittenState(vm.snapshot())
        commands = 0
        while not vm.halted and commands <= 10 * n + 2:
            vm.step()
            written.sample(vm.snapshot())
            commands += 1
        assert vm.halted
        assert vm.io.getvalue() == table[row]
        assert commands <= 10 * n + 2
        assert written.bits <= 3 * n + 4
        maximum = max(maximum, commands)
    return maximum


@pytest.mark.medium
def test_deeper_classifier_is_selected_only_within_command_bound():
    from esolangs.tools.bfpda import _bfpda_tree, _reflected, bfpda

    for n, admitted in ((8, False), (10, True)):
        blocks = ("0001" * (1 << (n - 5)), "0110" * (1 << (n - 5)))
        table = _reflected("".join(blocks[int(bit)] for bit in "00101110"), n)
        candidate, commands = _bfpda_tree(table, classes=blocks, class_depth=3)
        program = bfpda(table)
        assert (program == candidate) == admitted
        assert (commands <= 10 * n + 2) == admitted
        _execute_bank(table, program, range(1 << n))


def test_classifier_cannot_exceed_retired_stack_space():
    from esolangs.tools.bfpda import _bfpda_tree

    with pytest.raises(ValueError, match="two consumed inputs"):
        _bfpda_tree("00010110", classes=("0001", "0110"), class_depth=1)


@pytest.mark.medium
def test_deeper_classifier_preserves_a_constant_class():
    from esolangs.tools.bfpda import _bfpda_tree, _reflected, bfpda

    blocks = ("0" * 128, "0110" * 32)
    table = _reflected("".join(blocks[int(bit)] for bit in "00101110"), 10)
    candidate, price = _bfpda_tree(table, classes=blocks, class_depth=3)
    assert price <= 102
    assert _execute_bank(table, candidate, range(1024)) <= price
    _execute_bank(table, bfpda(table), range(1024))


@pytest.mark.medium
@pytest.mark.parametrize("seed", [73027, 73028, 73029])
@pytest.mark.parametrize("start", range(0, 2048, 128))
def test_cap_classifier_covers_every_essential_row(seed, start):
    from esolangs.tools.bfpda import _bfpda_tree, _reflected, bfpda

    rng = random.Random(seed)
    blocks = tuple(
        "".join(str(rng.randrange(2)) for _ in range(256)) * 32 for _ in range(2)
    )
    table = _reflected("".join(blocks[int(bit)] for bit in "00101110"), 16)
    candidate, price = _bfpda_tree(table, classes=blocks, class_depth=3)
    assert bfpda(table) == candidate
    plain, _ = _bfpda_tree(table)
    assert len(candidate) < len(plain)
    maximum = _execute_bank(
        table,
        candidate,
        [
            int(f"{((row >> 8) << 13) | (padding << 8) | (row & 255):016b}"[::-1], 2)
            for row in range(start, start + 128)
            for padding in (0, 31)
        ],
    )
    assert maximum <= price <= 162
