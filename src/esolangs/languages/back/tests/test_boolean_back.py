"""Covers :mod:`esolangs.languages.back.generator`."""

from itertools import pairwise

import pytest

from esolangs.generation.helpers import TEMPLATE_CHAR, permute_truth_table, runs
from esolangs.languages.back.generator import _back_ordered
from tests.generators.test_boolean_parameterized_contract import _drawing
from tests.support.generator_support import assert_an_ignored_input_costs
from tests.support.witness_tables import row_bits, witnesses


class TestParameterizedBack:
    """Input-by-substitution generators for the no-input language Back."""

    def run_back(self, prog: str, n: int) -> str:
        # Back has no output instruction: it dumps the whole tape at halt.
        # The generator puts the answer in cell n, so the dump's (n+1)th
        # field is the result -- no need to track the head, which the dump
        # does not report.
        from esolangs.languages.back.interpreter import run
        from esolangs.runtime.io import ScriptedIO

        io = ScriptedIO()
        run(prog.splitlines(), io)
        return io.getvalue().split()[n]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.generators.fills import fill

        _fill_back = fill("Back")

        return _fill_back(tpl, bits)

    def test_program_length_is_the_same_for_every_input(self) -> None:
        """Both bits cost one command, so the size reveals nothing."""
        from esolangs.languages import generators
        from tests.generators.fills import fill

        _fill_back = fill("Back")

        for n in (1, 2, 3):
            template = generators.back(format(0, f"0{2**n}b"))
            sizes = {len(_fill_back(template, row_bits(c, n))) for c in range(2**n)}
            assert len(sizes) == 1, f"n={n} sizes {sorted(sizes)}"

    def test_a_falling_beam_reuses_the_next_zero_subtree(self) -> None:
        """A one-edge onto an equal zero side draws no rows, and still answers."""
        import random

        from esolangs.languages import generators

        rng = random.Random(5)
        table = "".join(rng.choice("01") for _ in range(128))
        program = generators.back(table)
        assert len(program.splitlines()) < 80  # 84 when every one-edge is drawn
        for row in range(128):
            bits = [(row >> (6 - i)) & 1 for i in range(7)]
            assert self.run_back(self.instantiate(program, bits), 7) == table[row]

    def test_the_fold_answers_every_three_input_table(self, monkeypatch) -> None:
        """Folding from the first level up still computes each table."""
        from esolangs.languages.back import generator
        from esolangs.languages.back.generator import _back_htree

        monkeypatch.setattr(generator, "_FOLD_BASE", 1)
        for value in range(256):
            table = format(value, "08b")
            program = _back_htree(table, [1, 1, 1])
            for row in range(8):
                bits = [(row >> (2 - i)) & 1 for i in range(3)]
                assert self.run_back(self.instantiate(program, bits), 3) == table[row]

    def test_area_is_linear_where_the_comb_is_not(self) -> None:
        """Rudin-Shapiro shares nothing: the comb is 3n + 5 wide, the fold is not."""
        from esolangs.generation.helpers import grid_area
        from esolangs.languages import generators

        n = 12
        table = "".join(
            str(bin(i & i >> 1).count("1") % 2 ^ n % 2 ^ (i == 1))
            for i in range(1 << n)
        )
        assert grid_area(generators.back(table)) < 0.75 * (3 * n + 5) * (
            3 * (1 << n) // 4 + 1
        )
        assert grid_area(generators.back(table)) <= 27.5 * (1 << n)

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.languages import generators
        from esolangs.languages.back.generator import PAIR

        template = generators.back("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, (PAIR,) * 2)) == 2

    def test_each_input_is_stored_once(self) -> None:
        """Each input is embedded once in the tape load, not re-embedded."""

        from esolangs.languages import generators

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = generators.back(table)
            assert template.count(TEMPLATE_CHAR) == n

    def test_tree_uses_tape_decision_nodes(self) -> None:
        """The reflected decision tree retains its skip and both mirrors."""
        from esolangs.languages import generators

        template = generators.back("0110")
        assert "+" in template
        assert "/" in template
        assert "\\" in template
        assert "*" in template  # leaves halt

    def test_the_natural_order_folds_its_aligned_dependency(self) -> None:
        """A one-input dependency folds wherever the input sits."""
        from esolangs.languages import generators

        scattered = len(generators.back("10101010"))
        aligned = len(generators.back("11110000"))
        parity = len(generators.back("01101001"))
        assert scattered < parity
        assert aligned < parity

    def test_the_identity_template_is_emitted(self) -> None:
        """Back no longer contests input orders."""
        from esolangs.languages import generators

        # Every input matters in each; an ignored one is indexed past.
        for table in ("01101001", "00010111", "01111110", "00011110", "10010110"):
            n = (len(table) - 1).bit_length()
            identity = _back_ordered(table, tuple(range(n)))
            assert generators.back(table) == identity, table

    def test_reordering_pays_a_walk_and_keeps_name_order(self) -> None:
        """A permuted load spends rows on the walk, and keeps its runs in name order."""
        from itertools import permutations

        walked = 0
        for table in ("0110", "10101010", "01101001"):
            n = (len(table) - 1).bit_length()
            for perm in permutations(range(n)):
                permuted = permute_truth_table(table, perm)
                built = _back_ordered(permuted, perm)
                assert built.count(TEMPLATE_CHAR) == n, (table, perm)
                walked += built.count("<")
        # A non-identity order has to step the pointer back at some point;
        # a build with no leftward step is not reordering anything.
        assert walked > 0

    def test_placeholders_run_in_name_order_while_still_reordering(self) -> None:
        """Back reorders through the *walk*, not through its input order."""

        from esolangs.languages import generators

        walked = 0
        for table in ("11110000", "10101010", "01101001", "00111100"):
            template = generators.back(table)
            assert template.count(TEMPLATE_CHAR) == 3, f"{table} embeds each once"
            # Reflection moves the load to the last occupied cell of its row.
            column = [
                line.rstrip()[-1] for line in template.split("\n") if line.strip()
            ]
            walked += column.count("<")
        # At least one of these tables reorders, so at least one leftward
        # step is emitted -- a plain ascending load never steps back.
        assert walked > 0

    def test_reordering_keeps_the_equal_width_embedding(self) -> None:
        """Reordered loads still cost the same for either bit."""
        from esolangs.languages import generators
        from tests.generators.fills import fill

        _fill_back = fill("Back")

        for table in ("10101010", "11001100", "01101001"):
            template = generators.back(table)
            sizes = {
                len(_fill_back(template, [(c >> (2 - i)) & 1 for i in range(3)]))
                for c in range(8)
            }
            assert len(sizes) == 1, f"{table} sizes {sorted(sizes)}"


@pytest.mark.parametrize("width", [1, 10, 20, 80])
def test_descending_loader_preserves_inputs_and_answers(width: int) -> None:
    """The narrower entry reads page-order runs into matching tape cells."""
    import esolangs

    runner = TestParameterizedBack()
    for n in range(1, 7):
        table = "".join(str((row * 73 + row // 3) & 1) for row in range(1 << n))
        plain = esolangs.generate("Back", table)
        template = esolangs.generate("Back", table, width=width)
        floor = max(map(len, plain.splitlines())) - 2
        assert max(map(len, template.splitlines())) <= max(width, floor)
        sizes = set()
        for row, expected in enumerate(table):
            bits = list(map(int, f"{row:0{n}b}"))
            program = esolangs.instantiate(
                "Back", str(template), bits, truth_table=table
            )
            sizes.add(len(program))
            assert runner.run_back(program, n) == expected
        assert len(sizes) == 1


def test_descending_loader_rendered_size_stays_linear() -> None:
    from esolangs.languages.back.generator import back

    sizes = []
    for n in range(6, 11):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        template = back(table, 1)
        assert max(map(len, template.splitlines())) < max(
            map(len, back(table).splitlines())
        )
        sizes.append(len(template))
    assert all(later <= 2 * earlier for earlier, later in pairwise(sizes))


def test_descending_loader_walks_permuted_cells_in_name_order() -> None:
    from esolangs.generation.helpers import permute_truth_table
    from esolangs.languages.back.generator import _back_ordered

    table = "00010011"
    order = (2, 0, 1)
    template = _back_ordered(permute_truth_table(table, order), order, 1)
    runner = TestParameterizedBack()
    for row, expected in enumerate(table):
        bits = list(map(int, f"{row:03b}"))
        assert runner.run_back(runner.instantiate(template, bits), 3) == expected


@pytest.mark.medium
def test_vertical_leaf_finish_preserves_every_small_table() -> None:
    import esolangs

    runner = TestParameterizedBack()
    for n in range(1, 4):
        for table in witnesses(n):
            template = esolangs.generate("back", table, width=1)
            for row, expected in enumerate(table):
                bits = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
                code = esolangs.instantiate(
                    "back", str(template), bits, truth_table=table
                )
                assert runner.run_back(code, n) == expected
    assert max(map(len, esolangs.generate("back", "0110", width=1).splitlines())) == 1
    assert max(map(len, esolangs.generate("back", "0110", width=8).splitlines())) == 8


@pytest.mark.parametrize("width", [1, 4, 7, 10, 80])
@pytest.mark.parametrize("n", [1, 2, 3, 5])
@pytest.mark.parametrize("bias", [0, 1])
def test_parity_accumulator_keeps_public_slots_and_provenance(
    n: int, bias: int, width: int
) -> None:
    import esolangs

    table = "".join(str((row.bit_count() & 1) ^ bias) for row in range(1 << n))
    runner = TestParameterizedBack()
    tagged = esolangs.generate("Back", table, width=width)
    assert tagged.setters == (("-", "+"),) * n
    for template in (tagged, str(tagged)):
        for row, expected in enumerate(table):
            bits = list(map(int, f"{row:0{n}b}"))
            program = esolangs.instantiate("Back", template, bits, truth_table=table)
            assert runner.run_back(program, n) == expected
            assert len(program) == len(tagged)
            if width == 1:
                assert max(map(len, program.splitlines())) == 1
        with pytest.raises(esolangs.TemplateError):
            esolangs.instantiate(
                "Back", template, [0] * n, truth_table="0" * len(table)
            )
    assert max(map(len, esolangs.generate("Back", table, width=1).splitlines())) == 1


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """Two load rows on a borrowed cell; each leaf walks one more."""
    assert_an_ignored_input_costs("Back", 6, 131)


@pytest.mark.slow  # builds every permuting generator over several tables
def test_a_permuting_generator_changes_its_drawing() -> None:
    """A generator that permutes its slots must emit a different *drawing*."""
    from itertools import permutations

    from esolangs.generation.helpers import permute_truth_table

    checked = 0
    for name in ("back",):
        build = _back_ordered
        for table in ("10101010", "11001100", "00111100"):
            n = 3
            builds: dict[str, set[int]] = {}
            for perm in permutations(range(n)):
                built = build(permute_truth_table(table, perm), perm)
                builds.setdefault(_drawing(built), set()).add(len(built))
            checked += 1
            # The orders must not all collapse onto one drawing, or the
            # reorder is a relabelling.
            assert len(builds) > 1, (
                name,
                table,
                "every input order draws the same program, so permuting the "
                "slots emits an identical program and books a fake saving",
            )
            # And size must be a function of the drawing, not of the labels:
            # orders sharing a drawing are the same program.
            for drawing, sizes in builds.items():
                assert len(sizes) == 1, (name, table, len(drawing), sorted(sizes))
    assert checked >= 3, checked


def _drawn_plan(table, levels, n, vertical):
    """The replaced search: mark candidates, redraw, keep the ones that land."""
    from esolangs.generation.helpers import constant_span_test, subtree_ids
    from esolangs.languages.back.generator import _BackContext, _extent

    constant, ids = constant_span_test(table), subtree_ids(table)

    def walk(order, level, block, k, shared):
        size = 2 ** (levels - level)
        if level == levels or constant(block * size, (block + 1) * size):
            return
        if level == k:
            order.append(block)
        walk(order, level + 1, 2 * block, k, shared)
        if (level, block) not in shared:
            walk(order, level + 1, 2 * block + 1, k, shared)

    shared = set()
    for k in range(levels):
        order = []
        walk(order, 0, 0, k, shared)
        follower = dict(pairwise(order))
        tried = {
            (k, a)
            for a, b in follower.items()
            if ids[k + 1][2 * a + 1] == ids[k + 1][2 * b]
        }
        if not tried:
            continue
        grid, where = _BackContext(
            truth_table=table,
            levels=levels,
            n=n,
            constant=constant,
            vertical=vertical,
            shared=shared | tried,
        ).draw()
        height, column = _extent(grid)[0], 3 * k + 2
        owner = {cell: node for node, cell in where.items()}
        for _, a in tried:
            row = where[k, a][0] + 1
            while row < height and (row, column) not in grid:
                row += 1
            if owner.get((row, column)) == (k, follower[a]):
                shared.add((k, a))
    return shared


@pytest.mark.medium
def test_the_landing_rule_matches_drawing_the_tree() -> None:
    """The geometric rule picks the sets the draw-and-verify search kept."""
    import random

    from esolangs.generation.helpers import constant_span_test, subtree_ids
    from esolangs.languages.back.generator import _BackContext

    rng = random.Random(7)
    tables = ["0" * 64, "01" * 32, "0" * 32 + "1" * 32]
    for n in (5, 6, 7, 8):
        for block in (2, 4, 8, 16):
            pool = ["".join(rng.choice("01") for _ in range(block)) for _ in range(2)]
            for _ in range(2):
                tables.append("".join(rng.choice(pool) for _ in range(2**n // block)))
        tables.append("".join("1" if rng.random() < 0.06 else "0" for _ in range(2**n)))
        tables.append("0" * 2 ** (n - 1) + "".join(rng.choices("01", k=2 ** (n - 1))))
    kept = 0
    for table in tables:
        levels = len(table).bit_length() - 1
        for vertical in (False, True):
            rule = _BackContext(
                truth_table=table,
                levels=levels,
                n=levels,
                constant=constant_span_test(table),
                vertical=vertical,
                ids=subtree_ids(table),
            ).plan()
            assert rule == _drawn_plan(table, levels, levels, vertical)
            kept += len(rule)
    assert kept > 500  # positive control: the corpus shares nodes
