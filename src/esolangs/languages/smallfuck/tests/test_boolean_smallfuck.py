"""Executed tests for the Smallfuck banded-result tree."""

import random
from itertools import pairwise
from unittest.mock import patch

import pytest

import esolangs
from esolangs import run as execute
from esolangs._bindings import TEMPLATE_CHAR, fill_runs
from esolangs.debugger import make_vm
from esolangs.generation.anf import anf_coefficients
from esolangs.generation.helpers import in_input_order
from esolangs.generation.lookup import constant_output
from esolangs.languages.smallfuck import generator as boolean
from esolangs.languages.smallfuck.generator import (
    BAND,
    PAIR,
    _paired_roots,
    _smallfuck_ordered,
    _smallfuck_tree,
    smallfuck,
)
from esolangs.languages.smallfuck.interpreter import run
from esolangs.registry import LANGUAGES
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace
from scripts.docs.evidence import construction_boundaries
from tests.support.generator_support import (
    assert_saved_rows,
    assert_shared_program,
    measure_run,
    multiple_tables,
    run_filled,
)
from tests.support.screen_support import corpus
from tests.support.witness_tables import dense, witnesses


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
    language = esolangs.Language("Smallfuck")
    for witness in construction_boundaries(language.name)[
        "embedded_setter_width_floor"
    ]:
        table = witness.table()
        floor = len(PAIR[0])
        for width in (floor - 1, floor):
            with patch.object(boolean, "_narrow", wraps=boolean._narrow) as narrow:
                artifact = language.generate(table, width=width)
            assert narrow.call_count == int(width < floor)
            assert_saved_rows(language, artifact, table, range(len(table)))

    _check_constants()
    assert len(PAIR[0]) == len(PAIR[1]) == 4
    for n in range(1, 8):
        template = smallfuck("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 4 * n


def test_source_growth_is_linear() -> None:
    # The slack covers a band boundary crossing a level as n grows.
    sizes = [len(smallfuck("0110" * (1 << (n - 2)))) for n in range(2, 13)]
    assert all(right <= 2 * left + 64 for left, right in pairwise(sizes))


def test_constant_arms_and_banded_results_shrink_the_tree() -> None:
    """Pin the Davio source premium at small arities and execute its mixed term."""
    language = esolangs.Language("Smallfuck")
    for witness in construction_boundaries(language.name)[
        "constant_one_off_walk_cell_cutoff"
    ]:
        table = witness.table()
        artifact = language.generate(table)
        assert artifact.source.startswith(">>*<<") == (witness.arity == 3)
        assert_saved_rows(language, artifact, table, range(len(table)))

    assert len(smallfuck("0001")) == 79
    assert sum(len(smallfuck(f"{value:08b}")) for value in range(256)) == 30627
    for code in range(256):
        table = f"{code:08b}"
        for row, expected in enumerate(table):
            assert _run(table, row) == expected

    table = multiple_tables()[0]
    template = esolangs.generate("Smallfuck", table)
    assert len(template.source) <= 641
    for row, expected in enumerate(table):
        bits = [int(bit) for bit in format(row, "06b")]
        program = esolangs.instantiate("Smallfuck", template, bits)
        assert execute("Smallfuck", program, max_steps=10_000).output == expected


@pytest.mark.medium
def test_fresh_setters_lower_the_public_floor() -> None:
    for inputs in (1, 2, 3):
        for value in range(1 << (1 << inputs)):
            table = format(value, f"0{1 << inputs}b")
            template = esolangs.generate("Smallfuck", table, width=1)
            assert max(map(len, template.source.splitlines())) == 1
            for row, expected in enumerate(table):
                bits = [int(bit) for bit in format(row, f"0{inputs}b")]
                source = esolangs.instantiate("Smallfuck", template, bits, width=1)
                assert execute("Smallfuck", source).output == expected


@pytest.mark.parametrize("restored", [False, True])
def test_narrow_smallfuck_saved_provenance(*, restored: bool) -> None:
    table = "0110"
    template = esolangs.generate("Smallfuck", table, width=1)
    source = (
        esolangs.load_program("Smallfuck", esolangs.dump_program("Smallfuck", template))
        if restored
        else template
    )
    for row, expected in enumerate(table):
        program = esolangs.instantiate(
            "Smallfuck", source, [row >> 1, row & 1], width=1, truth_table=table
        )
        assert max(map(len, program.source.splitlines())) == 1
        assert execute("Smallfuck", program).output == expected
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
                execute(
                    "Smallfuck",
                    esolangs.instantiate("Smallfuck", template, bits),
                ).output
                == table[row]
            )


def test_smallfuck_matches_a_narrow_layout_without_its_newlines() -> None:
    same_layout = LANGUAGES["Smallfuck"].backend.same_layout
    assert same_layout is not None
    narrow = {1: "*\n<", 4: "*>\n*"}
    assert same_layout("*>*", "*>*<", lambda width: narrow[width])
    assert same_layout("*>\n*<", "*>*<", lambda width: narrow[width])


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    table = corpus(8)["tiled"]
    plain, _ = _smallfuck_tree(table, tuple(range(8)))
    assert_shared_program(
        "Smallfuck",
        table,
        plain.source,
        1396,
        lambda p: len(p) + len(p).bit_length() + (3 * 8).bit_length() + 1,
    )


def test_complemented_shared_arm_contributes_its_constant_first() -> None:
    from esolangs.generation.shared_block import repeated_blocks

    table = "1111011001101111"
    forced, _ = _smallfuck_tree(
        table, tuple(range(4)), shared_blocks=repeated_blocks(table)
    )
    for row, expected in enumerate(table):
        assert run_filled(run, forced.source, [PAIR] * 4, row, 4) == expected
    assert_shared_program(
        "Smallfuck",
        table,
        None,
        564,
        lambda p: len(p) + len(p).bit_length() + (12).bit_length() + 1,
    )


@pytest.mark.medium
# Table 0 (structured) and 3 (seeded random): the pair reaches every arc of the
# eight-table sweep; table 3 alone reaches the complemented-arm flip.
@pytest.mark.parametrize("table", [multiple_tables()[i] for i in (0, 3)])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("kind", ["levels", "first", "ranked"])
@pytest.mark.parametrize("half", [0, 1])
def test_multiple_residuals_preserve_bands_and_native_bounds(
    table, reverse, kind, half
) -> None:
    from esolangs.generation.helpers import permute_truth_table
    from esolangs.generation.shared_block import repeated_bank, repeated_blocks

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
    width = len(table) // 2
    _check_completed_rows(
        template.source, limit, n, table, range(half * width, (half + 1) * width)
    )


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
def test_invalid_multiple_definitions_abort(blocks, flags, message) -> None:
    with pytest.raises(ValueError, match=message):
        _smallfuck_tree("01100110", (0, 1, 2), shared_blocks=blocks, flag_levels=flags)


@pytest.mark.medium
def test_multiple_residuals_reduce_tiled_cap_program_within_ledger() -> None:
    from esolangs.generation.shared_block import repeated_blocks

    n = 16
    a, b = "00010111" * (1 << (n - 6)), "01101001" * (1 << (n - 6))
    table = a + b + b + a + a + b + a + b
    perm = tuple(range(n))
    bound = 9 * n * n + 100 * n + 20
    forms = [
        _smallfuck_tree(table, perm),
        _smallfuck_tree(table, perm, shared_blocks=repeated_blocks(table)),
    ]
    previous = min((p.source for p, c in forms if c <= bound), key=len)
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
        lambda p: len(p) + len(p).bit_length() + (3 * n).bit_length() + 1,
        rows=rows,
    )


@pytest.mark.medium
@pytest.mark.parametrize("swap_suffix", [False, True])
@pytest.mark.parametrize("half", [0, 1])
def test_all_two_input_complement_pairs_and_ignored_prefixes(swap_suffix, half) -> None:
    from esolangs.generation.helpers import permute_truth_table
    from esolangs.generation.shared_block import repeated_block

    table = "".join(f"{code:04b}" for code in range(16)) * 4
    n = 8
    assert repeated_block(table) is None
    perm = (*range(n - 2), n - 1, n - 2) if swap_suffix else tuple(range(n))
    ordered = permute_truth_table(table, perm)
    pairs = _paired_roots(ordered)
    assert {code for code, _ in pairs} == set(range(1, 8))
    template, limit = _smallfuck_tree(ordered, perm, paired_roots=pairs)
    _check_completed_rows(
        template.source, limit, n, table, range(half * 128, (half + 1) * 128)
    )


def _check_completed_rows(template, limit, n, table, rows):
    bound = len(template) + len(template).bit_length() + (3 * n).bit_length() + 1
    for row in rows:
        bits = [int(bit) for bit in f"{row:0{n}b}"]
        program = fill_runs(template, TEMPLATE_CHAR, [PAIR] * n, bits)
        machine = make_vm("Smallfuck", program)
        commands, written = measure_run(machine, limit=limit)
        assert machine.halted
        machine.step()
        written.sample(_capture_workspace(machine))
        commands += 1
        assert machine.output == table[row]
        assert commands <= limit
        assert written.bits <= bound


def test_pair_definitions_require_retired_levels_and_an_exclusive_mode() -> None:
    with pytest.raises(ValueError, match="two retired levels"):
        _smallfuck_tree("0110", (0, 1), paired_roots=((6, 0),))
    with pytest.raises(ValueError, match="no other definitions"):
        _smallfuck_tree(
            "0110100110010110",
            (0, 1, 2, 3),
            shared_blocks=((2, 0),),
            paired_roots=((6, 0),),
        )


@pytest.mark.parametrize("word", ["0001", "0100"])
def test_one_pair_keeps_completed_constant_paths_and_fixed_code_bits(word) -> None:
    complement = "".join("1" if bit == "0" else "0" for bit in word)
    table = word + complement + "0000" + "1111"
    pairs = _paired_roots(table)
    assert len(pairs) == 1
    template, _ = _smallfuck_tree(table, (0, 1, 2, 3), paired_roots=pairs)
    for row, expected in enumerate(table):
        program = fill_runs(
            template.source,
            TEMPLATE_CHAR,
            [PAIR] * 4,
            [int(bit) for bit in f"{row:04b}"],
        )
        assert execute("Smallfuck", program).output == expected


@pytest.mark.parametrize("n", [4, 9])
def test_davio_weights_use_spare_band_cells(
    n: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The three Davio weights require the spare cells of a five-level band."""
    assert BAND == 5
    if n == 4:
        with pytest.raises(ValueError, match="five-level bands"):
            _smallfuck_tree("0110", (0, 1), band=4)
    rng = random.Random(8)
    table = "".join(rng.choice("01") for _ in range(1 << n))
    template = in_input_order(table, _smallfuck_ordered).source
    for row in range(0, 1 << n, max(1, (1 << n) // 16)):
        assert run_filled(run, template, [PAIR] * n, row, n) == table[row]

    assert boolean.anf_coefficients is anf_coefficients
    assert boolean.constant_output is constant_output
    for name, broken, table, row, expected in (
        ("anf_coefficients", lambda _: (0,) * 4, "0001", 3, "1"),
        ("constant_output", lambda _: "1", "00000010", 0, "0"),
    ):
        with monkeypatch.context() as fault:
            fault.setattr(boolean, name, broken)
            assert _run(table, row) != expected


@pytest.mark.parametrize(
    ("table", "size"),
    [
        (witnesses(4)[5], 200),
        ("00011011010010111011100101000100", 361),
        (witnesses(8)[2], 291),
        (dense(8), 2394),
    ],
    ids=["n4-banded", "n5-paired", "n8-and", "n8-dense"],
)
def test_pinned_template_sizes(table: str, size: int) -> None:
    """Pin band ownership, the paired decoder and coefficient weights."""
    n = len(table).bit_length() - 1
    template = smallfuck(table)
    assert len(template) == size
    for row in range(0, len(table), max(1, len(table) // 16)):
        assert run_filled(run, template, [PAIR] * n, row, n) == table[row]


def _check_constants() -> None:
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("Smallfuck", bit * (1 << n), **options)
                for bits in ([0] * n, [1] * n):
                    program = esolangs.instantiate("Smallfuck", template, bits)
                    assert "[" not in program.source
                    assert "]" not in program.source
                    io = ScriptedIO("7")
                    run(program.source, io)
                    assert io.getvalue() == bit
                    assert io.reads == 0
                    assert io.input_char() == ord("7")
