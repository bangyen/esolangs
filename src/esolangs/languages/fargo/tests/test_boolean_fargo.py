"""fargo generator tests."""

import itertools
import random

import pytest

from esolangs.languages import generators as boolean
from tests.interpreters.runner import run_program


def run_fargo(program: str, inputs: list[str]) -> str:
    """Run a Fargo program, packing ``inputs`` into its one input number."""
    from esolangs.languages.fargo.interpreter import run

    number = int("".join(inputs), 2) if inputs else 0
    return run_program(run, program, f"{number}\n")


class TestFargo:
    """The Fargo boolean generator: a recursively factored ANF, arms chosen."""

    @pytest.mark.parametrize("n", [4, 5, 8])
    def test_higher_arity_tables(self, n: int) -> None:
        """The construction is uncapped: no arity limit, no search."""
        rng = random.Random(20260830 + n)
        for _ in range(4):
            table = "".join(rng.choice("01") for _ in range(2**n))
            program = boolean.fargo(table)
            for _ in range(10):
                combo = rng.randrange(2**n)
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_fargo(program, bits) == table[combo]

    def test_constant_tables_need_no_reads(self) -> None:
        """A constant table is its degree-zero coefficient alone."""
        assert boolean.fargo("00000000") == "% 0 0\n$\n"
        assert boolean.fargo("11111111") == "% 0 1\n$\n"

    def test_an_all_zero_table_wraps_to_a_constant(self) -> None:
        """No terms to combine: the factored path indexed an empty list."""
        for width in (1, 2, 3, 4):
            assert boolean.fargo("0000", width=width) == "% 0 0\n$\n"
            assert boolean.fargo("00000000", width=width) == "% 0 0\n$\n"

    def test_narrow_dense_anf_keeps_constant_and_long_names(self) -> None:
        """Wrapping NOR keeps the constant term; wrapped, it shrinks vs the ANF form."""
        table = "1" + "0" * 31
        program = boolean.fargo(table, width=1)
        for row in range(32):
            assert run_fargo(program, list(format(row, "05b"))) == table[row]

    def test_narrow_one_input_keeps_literal_one(self) -> None:
        """Literal 1 is not input 1 when only input 0 exists."""
        for table in ("01", "10"):
            program = boolean.fargo(table, width=1)
            assert [run_fargo(program, [b]) for b in "01"] == list(table)

    def test_parity_is_one_term_per_input(self) -> None:
        """Parity's ANF is the sum of the single-variable terms."""
        assert boolean.fargo("01101001") == "% 0 ^ ^ @ 0 @ 1 @ 10\n$\n"

    def test_parity_grows_linearly_not_exponentially(self) -> None:
        """The size tracks algebraic complexity, so parity is O(n log n)."""
        sizes = [
            len(boolean.fargo("".join(str(bin(r).count("1") % 2) for r in range(2**n))))
            for n in (2, 4, 6, 8)
        ]
        gaps = [b - a for a, b in itertools.pairwise(sizes)]
        # Each step of two inputs costs a bounded amount, nowhere near the
        # doubling per input a decision tree would pay.
        assert all(12 <= gap <= 20 for gap in gaps), f"not linear: {sizes}"
        # A decision tree over n == 8 would be thousands of characters.
        assert sizes[-1] < 100, f"growing too fast: {sizes}"

    def test_a_one_dependency_table_folds(self) -> None:
        """One term whatever the arity, which is what the catalogue checks."""
        assert boolean.fargo("11110000") == "% 0 ^ 1 @ 10\n$\n"
        assert len(boolean.fargo("11110000")) < len(boolean.fargo("01101001"))

    def test_dense_anf_growth_is_linear(self) -> None:
        """NOR has every ANF coefficient set, but its source only doubles."""
        sizes = [len(boolean.fargo("1" + "0" * ((1 << n) - 1))) for n in (7, 8)]
        assert sizes[1] < 2 * sizes[0] + 16

    def test_choosing_arms_shrinks_the_corpus(self) -> None:
        """Tables to two inputs never grow; the three-input corpus shrinks 10.2%."""
        from esolangs.languages.fargo.generator import anf_coefficients
        from esolangs.languages.fargo.tests.fargo_oracle import _anf_expression

        before = after = 0
        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                at = tuple(range(n))
                positive = _anf_expression(anf_coefficients(table), n, at)
                old = len(f"% 0 {positive}\n$\n")
                built = len(boolean.fargo(table))
                if n < 3:
                    assert built <= old, table
                else:
                    before += old
                    after += built
        assert (before, after) == (9556, 8580)

    @pytest.mark.parametrize(
        ("table", "program"),
        [
            # NOR3: no 1-arm vanishes, so Davio0 keeps the 0-arm and names the
            # repeated ``1 ^ x0`` node.
            ("10000000", "a ^ 1 @ 0\nb ^ a & @ 1 a\n% 0 ^ b & @ 10 b\n$\n"),
            # OR3: each 1-arm is constant one, so each node is ``f0 | x``.
            ("01111111", "% 0 | | @ 0 @ 1 @ 10\n$\n"),
        ],
    )
    def test_a_node_keeps_its_cheap_arm(self, table: str, program: str) -> None:
        """The monotone OR is chosen per node by the construction, not the fill."""
        assert boolean.fargo(table) == program
        for combo in range(8):
            bits = list(format(combo, "03b"))
            assert run_fargo(program, bits) == table[combo]


@pytest.mark.medium
def test_default_names_only_the_nodes_sharing_shortens() -> None:
    from tests.support.screen_support import corpus

    table = corpus(8)["tiled"]
    program = boolean.fargo(table)
    # 441 when every node was named; now only the ones sharing shortens.
    assert len(program) == 242
    # Width 1 fits nothing, so it falls back to naming every node.
    assert len(program) < len(boolean.fargo(table, width=1))
    for row, answer in enumerate(table):
        assert run_fargo(program, list(format(row, "08b"))) == answer


@pytest.mark.parametrize("width", [1, 12, 40, 10**6])
def test_packed_lines_name_shared_or_overlong_nodes(width: int) -> None:
    from esolangs.languages.fargo.generator import _expression, _packed_program
    from esolangs.runtime._evaluate import _evaluate

    table = format(random.Random(1847).getrandbits(64), "064b")
    program = _packed_program(_expression(table, 6), 6, width)
    assert _evaluate("Fargo", program, inputs=6) == table
    if width >= 12:
        # Up to a name's length past the width, from lettering in line order.
        assert max(map(len, program.splitlines())) <= width + 2
    # A positive control: flipping the first input read flips some answer.
    mutant = program.replace("@ 0", "@ 1", 1)
    assert _evaluate("Fargo", mutant, inputs=6) != table


@pytest.mark.parametrize(
    ("table", "width", "size"),
    [("10", 9, 18), ("01", 7, 10)],
)
def test_a_width_request_keeps_the_exact_fit_and_counts_every_use(
    table: str, width: int, size: int
) -> None:
    """Both programs fit their width exactly or inline shared uses; sizes are exact."""
    import esolangs
    from esolangs.runtime._evaluate import _evaluate

    program = esolangs.generate("fargo", table, width=width)
    assert len(str(program)) == size
    assert _evaluate("Fargo", program, inputs=1 if len(table) == 2 else 2) == table


@pytest.mark.parametrize(
    ("table", "score"),
    [("1101", (10, 32, 9)), ("11000010", (14, 53, 11))],
)
def test_balanced_layout_scores_are_exact(
    table: str, score: tuple[int, int, int]
) -> None:
    """The squarest packing the width walk finds, as side, length and width."""
    import esolangs
    from esolangs.generation.wrap import balance_score
    from esolangs.runtime._evaluate import _evaluate

    program = esolangs.generate("fargo", table, balance=True)
    assert balance_score(str(program)) == score
    assert _evaluate("Fargo", program, inputs=len(table).bit_length() - 1) == table


def test_width_ten_keeps_the_exact_fit_definition() -> None:
    """The naming budget's exact-fit edge, pinned as exact text.

    At width 10 the definition's children sum exactly to the budget, so
    the naming loop stops where it is; one name more (or a longer
    lookahead) rewrites the whole assignment.
    """
    program = boolean.fargo("10", width=10)
    assert program == "a @ 0\nb ^ 1 a\n% 0 b\n$\n"
    assert [run_fargo(program, [bit]) for bit in "01"] == ["1", "0"]


def test_a_wide_definition_keeps_its_pinned_silhouette() -> None:
    """A width-40 definition whose naming the budget lookahead fixes.

    The lookahead reserves the next name's length against the width;
    reserving one character more, or naming past the exact fit, moves
    this table's program to 684 chars in a ragged block.
    """
    table = (
        "0110111010001010100110010101001111011011001100100000111110110110"
        "0101001111010111101101000100110000100011000011001010101011101100"
        "0000110110001110110011001001100011110011100001010110000000001001"
        "1001011000100100001100010100001000110010111010011011000100110011"
    )
    program = boolean.fargo(table, width=40)
    rows = program.splitlines()
    assert len(program) == 680
    assert len(rows) * max(map(len, rows)) == 1406
