"""Executed tests for the Smallfuck banded-result tree."""

import random
from itertools import pairwise

import pytest

import esolangs
from esolangs.interpreters.tape_based.smallfuck import run
from esolangs.registry import LANGUAGES
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.tools.smallfuck import PAIR, smallfuck
from tests.generator_support import run_filled


def _run(table: str, row: int) -> str:
    n = len(table).bit_length() - 1
    return run_filled(run, smallfuck(table), [PAIR] * n, row, n)


@pytest.mark.parametrize("n", range(1, 4))
def test_first_eight_tables_through_three_inputs(n: int) -> None:
    """The remaining 248 tables killed no additional mutant."""
    width = 1 << n
    for value in range(min(8, 1 << width)):
        table = f"{value:0{width}b}"
        assert "".join(_run(table, row) for row in range(width)) == table


def test_setters_are_equal_width_and_embedded_once() -> None:
    assert len(PAIR[0]) == len(PAIR[1]) == 4
    for n in range(1, 8):
        template = smallfuck("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 4 * n


def test_source_growth_is_linear() -> None:
    # The slack covers a band boundary crossing a level as n grows.
    sizes = [len(smallfuck("0110" * (1 << (n - 2)))) for n in range(2, 13)]
    assert all(right <= 2 * left + 64 for left, right in pairwise(sizes))


def test_constant_arms_and_banded_results_shrink_the_tree() -> None:
    """Pin the three-input total: 57,894 characters before, 20,145 after."""
    assert smallfuck("0001") == TEMPLATE_CHAR * 8 + "<<<<<<[*>>>[*<*>]]"
    assert smallfuck("0110").endswith("<<<]>[*>>[*<*>]]")
    assert sum(len(smallfuck(f"{value:08b}")) for value in range(256)) == 20145


@pytest.mark.medium
def test_fresh_setters_lower_the_public_floor() -> None:
    for inputs in (1, 2, 3):
        for value in range(1 << (1 << inputs)):
            table = format(value, f"0{1 << inputs}b")
            template = esolangs.generate("Smallfuck", table, width=1)
            assert max(map(len, template.splitlines())) == 1
            for row, expected in enumerate(table):
                bits = [int(bit) for bit in format(row, f"0{inputs}b")]
                source = esolangs.instantiate("Smallfuck", template, bits, width=1)
                assert esolangs.run("Smallfuck", source) == expected


@pytest.mark.parametrize("tagged", [False, True])
def test_narrow_smallfuck_saved_provenance(*, tagged: bool) -> None:
    table = "0110"
    template = esolangs.generate("Smallfuck", table, width=1)
    source = template if tagged else str(template)
    for row, expected in enumerate(table):
        program = esolangs.instantiate(
            "Smallfuck", source, [row >> 1, row & 1], width=1, truth_table=table
        )
        assert max(map(len, program.splitlines())) == 1
        assert esolangs.run("Smallfuck", program) == expected
    with pytest.raises(ValueError, match="does not compute that table"):
        esolangs.instantiate("Smallfuck", source, [0, 1], truth_table="1001")


def test_narrow_smallfuck_preserves_fitting_and_large_execution() -> None:
    for n in (4, 5, 6):
        table = "0110" * (2 ** (n - 2))
        natural = smallfuck(table)
        assert smallfuck(table, 0) == natural
        assert smallfuck(table, len(natural)) == natural
        for row in (0, 1, 2, 3, 2**n - 1):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            template = esolangs.generate("Smallfuck", table, width=1)
            assert (
                esolangs.run(
                    "Smallfuck", esolangs.instantiate("Smallfuck", template, bits)
                )
                == table[row]
            )


def test_smallfuck_matches_a_narrow_layout_without_its_newlines() -> None:
    same_layout = LANGUAGES["Smallfuck"].same_layout
    assert same_layout is not None
    narrow = {1: "*\n<", 4: "*>\n*"}
    assert same_layout("*>*", "*>*<", lambda width: narrow[width])
    assert same_layout("*>\n*<", "*>*<", lambda width: narrow[width])


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.tools.smallfuck import _smallfuck_tree
    from tests.generator_support import assert_shared_program
    from tests.screen_support import corpus

    table = corpus(8)["tiled"]
    plain, _ = _smallfuck_tree(table, tuple(range(8)))
    assert_shared_program(
        "Smallfuck",
        table,
        plain,
        1396,
        lambda p: len(p) + len(p).bit_length() + (3 * 8).bit_length(),
    )


def test_complemented_shared_arm_contributes_its_constant_first() -> None:
    from esolangs.tools.smallfuck import _smallfuck_tree
    from tests.generator_support import assert_shared_program

    table = "1111011001101111"
    plain, _ = _smallfuck_tree(table, tuple(range(4)))
    assert_shared_program(
        "Smallfuck",
        table,
        plain,
        564,
        lambda p: len(p) + len(p).bit_length() + (12).bit_length(),
    )


def _multiple_tables():
    rng = random.Random(88417)
    a, b = "00010111", "01101001"
    four = (
        "0001011101101001",
        "0110100100010111",
        "1010110010001101",
        "1101001010010010",
    )
    return [
        a + b + b + a + a + b + a + b,
        "".join(four[(row // 4 + row % 4) % 4] for row in range(16)),
        *("".join(str(rng.randrange(2)) for _ in range(128)) for _ in range(6)),
    ]


@pytest.mark.medium
@pytest.mark.parametrize("table", _multiple_tables())
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("kind", ["levels", "first", "ranked"])
@pytest.mark.parametrize("half", [0, 1])
def test_multiple_residuals_preserve_bands_and_native_bounds(
    table, reverse, kind, half
):
    from esolangs.debugger import make_vm
    from esolangs.tools.helpers import permute_truth_table
    from esolangs.tools.shared_block import repeated_bank, repeated_blocks
    from esolangs.tools.smallfuck import _smallfuck_tree
    from scripts.benchmark import WrittenState

    n = len(table).bit_length() - 1
    perm = tuple(reversed(range(n))) if reverse else tuple(range(n))
    ordered = permute_truth_table(table, perm)
    blocks, flags = (
        (repeated_blocks(ordered), ())
        if kind == "levels"
        else repeated_bank(ordered, ranked=kind == "ranked")
    )
    if len(blocks) < 2:
        assert kind == "levels"
        pytest.skip("only one repeated residual level")
    template, limit = _smallfuck_tree(
        ordered, perm, shared_blocks=blocks, flag_levels=flags
    )
    bound = len(template) + len(template).bit_length() + (3 * n).bit_length()
    width = len(table) // 2
    for row in range(half * width, (half + 1) * width):
        bits = [int(bit) for bit in f"{row:0{n}b}"]
        program = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
        machine = make_vm("Smallfuck", program)
        written = WrittenState(machine.snapshot())
        commands = 0
        while not machine.halted and commands <= limit:
            machine.step()
            written.sample(machine.snapshot())
            commands += 1
        assert machine.halted
        machine.step()
        written.sample(machine.snapshot())
        commands += 1
        assert machine.output == table[row]
        assert commands <= limit
        assert written.bits <= bound


@pytest.mark.parametrize(
    ("blocks", "flags", "message"),
    [
        (((1, 0), (1, 4)), (1,), "distinct unused flags"),
        (((0, 0), (1, 0)), (1, 2), "distinct unused flags"),
        (((1, 0), (1, 4)), (1, 1), "distinct unused flags"),
        (((1, 0), (1, 4)), (0, 2), "distinct unused flags"),
        (((1, 0), (1, 4)), (1, 3), "distinct unused flags"),
        (((1, 0), (1, 4)), (), "distinct and increasing"),
        (((-1, 0),), (), "distinct and increasing"),
        (((3, 0),), (), "distinct and increasing"),
        (((1, 0), (1, 4)), (1, 2), "distinct residuals"),
    ],
)
def test_invalid_multiple_definitions_abort(blocks, flags, message):
    from esolangs.tools.smallfuck import _smallfuck_tree

    with pytest.raises(ValueError, match=message):
        _smallfuck_tree("01100110", (0, 1, 2), shared_blocks=blocks, flag_levels=flags)


@pytest.mark.medium
def test_multiple_residuals_reduce_tiled_cap_program_within_ledger():
    from esolangs.tools.shared_block import repeated_block
    from esolangs.tools.smallfuck import _smallfuck_tree
    from tests.generator_support import assert_shared_program

    n = 16
    a, b = "00010111" * (1 << (n - 6)), "01101001" * (1 << (n - 6))
    table = a + b + b + a + a + b + a + b
    perm = tuple(range(n))
    bound = 9 * n * n + 100 * n + 20
    forms = [
        _smallfuck_tree(table, perm),
        _smallfuck_tree(table, perm, repeated_block(table)),
    ]
    previous = min((p for p, c in forms if c <= bound), key=len)
    ignored = ((1 << (n - 6)) - 1) << 3
    rows = [
        (prefix << (n - 3)) | suffix | padding
        for prefix in range(8)
        for suffix in range(8)
        for padding in (0, ignored)
    ]
    assert_shared_program(
        "Smallfuck",
        table,
        previous,
        bound,
        lambda p: len(p) + len(p).bit_length() + (3 * n).bit_length(),
        rows=rows,
    )


@pytest.mark.medium
@pytest.mark.parametrize("swap_suffix", [False, True])
@pytest.mark.parametrize("half", [0, 1])
def test_all_two_input_complement_pairs_and_ignored_prefixes(swap_suffix, half):
    from esolangs.debugger import make_vm
    from esolangs.tools.helpers import permute_truth_table
    from esolangs.tools.shared_block import repeated_block
    from esolangs.tools.smallfuck import _paired_roots, _smallfuck_tree
    from scripts.benchmark import WrittenState

    table = "".join(f"{code:04b}" for code in range(16)) * 4
    n = 8
    assert repeated_block(table) is None
    perm = (*range(n - 2), n - 1, n - 2) if swap_suffix else tuple(range(n))
    ordered = permute_truth_table(table, perm)
    pairs = _paired_roots(ordered)
    assert {code for code, _ in pairs} == set(range(1, 8))
    template, limit = _smallfuck_tree(ordered, perm, paired_roots=pairs)
    bound = len(template) + len(template).bit_length() + (3 * n).bit_length()
    for row in range(half * 128, (half + 1) * 128):
        program = fill_runs(
            template, TEMPLATE_CHAR, [PAIR] * n, [int(bit) for bit in f"{row:08b}"]
        )
        machine = make_vm("Smallfuck", program)
        written = WrittenState(machine.snapshot())
        commands = 0
        while not machine.halted and commands <= limit:
            machine.step()
            written.sample(machine.snapshot())
            commands += 1
        assert machine.halted
        machine.step()
        written.sample(machine.snapshot())
        commands += 1
        assert machine.output == table[row]
        assert commands <= limit
        assert written.bits <= bound


def test_pair_definitions_require_retired_levels_and_an_exclusive_mode():
    from esolangs.tools.smallfuck import _smallfuck_tree

    with pytest.raises(ValueError, match="two retired levels"):
        _smallfuck_tree("0110", (0, 1), paired_roots=((6, 0),))
    with pytest.raises(ValueError, match="no other definitions"):
        _smallfuck_tree(
            "0110100110010110", (0, 1, 2, 3), (2, 0), paired_roots=((6, 0),)
        )


@pytest.mark.parametrize("word", ["0001", "0100"])
def test_one_pair_keeps_completed_constant_paths_and_fixed_code_bits(word):
    from esolangs.tools.smallfuck import _paired_roots, _smallfuck_tree

    complement = "".join("1" if bit == "0" else "0" for bit in word)
    table = word + complement + "0000" + "1111"
    pairs = _paired_roots(table)
    assert len(pairs) == 1
    template, _ = _smallfuck_tree(table, (0, 1, 2, 3), paired_roots=pairs)
    for row, expected in enumerate(table):
        program = fill_runs(
            template, TEMPLATE_CHAR, [PAIR] * 4, [int(bit) for bit in f"{row:04b}"]
        )
        assert esolangs.run("Smallfuck", program) == expected
