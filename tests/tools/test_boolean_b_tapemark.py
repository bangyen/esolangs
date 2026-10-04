"""B-tapemark emitted sizes and layout budgets."""

from itertools import product

from esolangs import tools


def test_measured_sizes() -> None:
    assert [len(tools.b_tapemark("0" * 2**n)) for n in range(1, 5)] == [
        106,
        221,
        364,
        545,
    ]


def test_dense_scaling_is_linear() -> None:
    """The copy is one line and the walk's runs sum to the table."""
    sizes = [len(tools.b_tapemark("01101001" * 2 ** (n - 3))) for n in (7, 8)]
    assert sizes[1] < 2.1 * sizes[0]


def test_size_does_not_depend_on_the_table() -> None:
    """Every entry costs the same three cells, whichever digit it holds."""
    sizes = {len(tools.b_tapemark("".join(t))) for t in product("01", repeat=8)}
    assert len(sizes) == 1


def test_weighted_layout_width_budgets() -> None:
    for n in range(4, 7):
        table = "".join(
            str((row * 17 + row // 3).bit_count() % 2) for row in range(1 << n)
        )
        for width in (1, 9, 19, 80):
            program = tools.b_tapemark(table, width)
            assert max(map(len, program.splitlines())) <= max(
                width, len(table) // 2 + 7
            )


def test_narrow_source_growth_is_linear() -> None:
    from esolangs.tools.b_tapemark import _b_tapemark_narrow

    sizes = [len(_b_tapemark_narrow("01" * (1 << (n - 1)), n)) for n in (7, 8, 9)]
    assert sizes[2] < 2.1 * sizes[1] < 4.41 * sizes[0]
