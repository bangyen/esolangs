"""Executed tests for the Underload promise-tree generator."""

from dataclasses import replace

import pytest

import esolangs
from esolangs import run as execute
from esolangs._bindings import TEMPLATE_CHAR
from esolangs.generation.helpers import _validate_truth_table, constant_span_test
from esolangs.languages.underload.generator import PAIR, underload, underload_setters
from esolangs.languages.underload.interpreter import run
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import make_vm
from tests.generators.sample_tables import five_input_sample
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import measure_run, run_filled, verify_generated
from tests.support.witness_tables import witnesses


def _run(table: str, row: int, width: int | None = None) -> str:
    n = len(table).bit_length() - 1
    template = underload(table, width)
    return run_filled(run, template, underload_setters(template, n), row, n)


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 3, 7, 8, 13, 40, 80])
def test_wrapped_templates_execute_every_three_input_table(width: int) -> None:
    for table in witnesses(3):
        template = underload(table, width)
        assert max(map(len, template.split("\n"))) <= max(7, width)
        if width >= 5:
            assert template.replace("\n", "") == underload(table)
        assert "".join(_run(table, row, width) for row in range(8)) == table


@pytest.mark.medium
def test_wrapped_public_templates_preserve_input_slots() -> None:
    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("Underload", bit * (1 << n), **options)
                assert len(template.source.replace("\n", "")) == 4 * n + 4
                assert underload_setters(template.source, n) == (("(0)", "(1)"),) * n
                for row in (0, 1, (1 << n) - 1):
                    bits = list(map(int, f"{row:0{n}b}"))
                    vm = make_vm("Underload", template.fill(bits))
                    steps, state = measure_run(vm)
                    assert vm.output == bit
                    if not options:
                        assert steps == 2 * n + 2
                        assert state.bits == 8 * (n + 1) + (4 * n + 4).bit_length()
    table = "0110100110010110"
    for width in (1, 7, 13, 40):
        template = esolangs.generate("Underload", table, width=width)
        for row in range(16):
            bits = [int(bit) for bit in f"{row:04b}"]
            io = ScriptedIO("")
            run(template.fill(bits).source, io)
            assert io.getvalue() == table[row]


@pytest.mark.parametrize("n", range(1, 4))
def test_first_eight_tables_through_three_inputs(n: int) -> None:
    """The remaining 248 tables killed no additional mutant."""
    width = 1 << n
    for value in range(min(8, 1 << width)):
        table = f"{value:0{width}b}"
        assert "".join(_run(table, row) for row in range(width)) == table


def test_setters_are_equal_width_and_embedded_once() -> None:
    assert_analysis_complement("Underload", "SubtreeDiagram")
    assert len(PAIR[0]) == len(PAIR[1]) == 5
    for n in range(1, 8):
        template = underload("01" * (1 << (n - 1)))
        assert template.count(TEMPLATE_CHAR) == 5 * n


@pytest.mark.medium
def test_repeated_subtrees_are_carried_and_no_table_grows() -> None:
    """The reduced, carrying tree cuts both totals and lengthens no table."""
    assert underload("01101001")[15:] == (
        "((((0))~((1))~^)~(~(^)~(!((1))~((0))~^)~^)~(~(!((1))~((0))~^)~(^)~^)~^)^S"
    )
    _check_terminal_drops()
    three = [format(value, "08b") for value in range(256)]
    for tables, before, after in (
        (three, 19496, 16276),
        (five_input_sample(), 56565, 42756),
    ):
        plain = [len(underload_plain(table)) for table in tables]
        shared = [len(underload(table)) for table in tables]
        assert (sum(plain), sum(shared)) == (before, after)
        assert all(s <= p for s, p in zip(shared, plain, strict=True))
    for table in five_input_sample()[::10]:
        assert "".join(_run(table, row) for row in range(32)) == table
    for n in (4, 6):
        for value in (0x6996, 0x1234ABCD5678EF01):
            table = format(value % 2**2**n, f"0{2**n}b")
            assert verify_generated("Underload", table), table


def test_short_selectors_keep_public_provenance_and_uniform_width() -> None:
    for width in (1, 2, 3, 4, 5, 13, 40, 80):
        table = "0110"
        template = esolangs.generate("Underload", table, width=width)
        template = esolangs.load_program(
            "Underload", esolangs.dump_program("Underload", template)
        )
        setters = underload_setters(template.source, 2)
        assert setters == template.bindings.setters
        assert len(set(setters)) == 1
        assert all(
            not char.isspace() for pair in setters for value in pair for char in value
        )
        if width < 5:
            assert setters == (("!", "*"),) * 2
        for row, expected in enumerate(table):
            filled = esolangs.instantiate(
                "Underload", template, [row // 2, row % 2], truth_table=table
            )
            assert execute("Underload", filled).output == expected
            if width < 5:
                assert max(map(len, filled.source.splitlines())) <= max(3, width)
        with pytest.raises(esolangs.TemplateError, match="not the template"):
            esolangs.instantiate("Underload", template, [0, 1], truth_table="0001")

        from esolangs.languages.underload.generator import _same_layout

        plain = underload(table)
        assert _same_layout(
            template.source, plain, lambda width, table=table: underload(table, width)
        )
        assert not _same_layout(
            template.source + "+",
            plain,
            lambda width, table=table: underload(table, width),
        )


def test_short_selector_floor_and_actual_narrow_corpus() -> None:
    template = underload("0110", 1)
    assert max(map(len, template.splitlines())) == 3
    assert len(template) == 115
    assert sum(len(underload(format(value, "08b"), 1)) for value in range(256)) == 40572


def test_layout_provenance_does_not_ignore_output_literal_newlines() -> None:
    template = esolangs.generate("Underload", "0000", width=1)
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate(
            "Underload",
            replace(
                template,
                source=template.source.replace("(0)", "(0\n)"),
                spans=None,
            ),
            [0, 1],
            truth_table="0000",
        )


@pytest.mark.parametrize("n", [4, 5, 6])
def test_short_selectors_execute_larger_carried_trees(n: int) -> None:
    for table in [format(0x6996 % 2 ** (2**n), f"0{2**n}b"), "0110" * 2 ** (n - 2)]:
        for width in [1, 4]:
            for row in [0, 1, 2**n // 3, 2**n - 1]:
                assert _run(table, row, width) == table[row]


def underload_plain(truth_table: str) -> str:
    """Return the unshared promise tree, each leaf printing its own bit."""
    from esolangs._bindings import TEMPLATE_CHAR
    from esolangs.generation.helpers import reflected_table
    from esolangs.languages.underload.generator import PAIR

    n = _validate_truth_table(truth_table)
    reflected = reflected_table(truth_table, n)
    constant = constant_span_test(reflected)

    def tree(level: int, lo: int, hi: int) -> str:
        if constant(lo, hi):
            return "!" * (n - level) + f"({reflected[lo]})S"
        mid = (lo + hi) // 2
        return f"({tree(level + 1, lo, mid)})~({tree(level + 1, mid, hi)})~^"

    slots = TEMPLATE_CHAR * (len(PAIR[0]) * n)
    return slots + f"({tree(0, 0, len(reflected))})^"


def _check_terminal_drops() -> None:
    from esolangs.languages.underload.generator import _terminal_family
    from esolangs.languages.underload.tests.ablations import ablate

    totals = [0, 0]
    for value in range(256):
        table = f"{value:08b}"
        assert ablate(table, "default") == underload(table)
        totals[0] += len(ablate(table, "terminal_drops"))
        totals[1] += len(underload(table))
    assert totals == [16296, 16276]
    for n in (4, 7, 8):
        for threshold in (1, 2, n - 1, n):
            table = "".join(
                str(int(row.bit_count() >= threshold)) for row in range(1 << n)
            )
            for candidate in (table, table.translate(str.maketrans("01", "10"))):
                assert _terminal_family(candidate, n)
                for width in (None, 1, 4, 7):
                    template = underload(candidate, width)
                    pairs = underload_setters(template, n)
                    assert len(set(pairs)) == 1
                    for row in (0, 1, (1 << n) - 1):
                        assert _run(candidate, row, width) == candidate[row]
    table = "0" * 127 + "1"
    mutant = "1" + table[1:]
    assert not _terminal_family(mutant, 7)
