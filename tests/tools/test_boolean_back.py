"""Covers :mod:`esolangs.tools.back`."""

from itertools import pairwise

import pytest

from esolangs.tools.back import _back_ordered
from esolangs.tools.helpers import TEMPLATE_CHAR, permute_truth_table, runs
from tests.generator_support import assert_an_ignored_input_costs
from tests.tools.test_boolean_parameterized_contract import _drawing
from tests.witness_tables import row_bits, witnesses


class TestParameterizedBack:
    """Input-by-substitution generators for the no-input language Back."""

    def run_back(self, prog: str, n: int) -> str:
        # Back has no output instruction: it dumps the whole tape at halt.
        # The generator puts the answer in cell n, so the dump's (n+1)th
        # field is the result -- no need to track the head, which the dump
        # does not report.
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import run

        io = ScriptedIO()
        run(prog.splitlines(), io)
        return io.getvalue().split()[n]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from tests.tools.fills import fill

        _fill_back = fill("Back")

        return _fill_back(tpl, bits)

    def test_program_length_is_the_same_for_every_input(self) -> None:
        """Both bits cost one command, so the size reveals nothing."""
        from esolangs import tools as generators
        from tests.tools.fills import fill

        _fill_back = fill("Back")

        for n in (1, 2, 3):
            template = generators.back(format(0, f"0{2**n}b"))
            sizes = {len(_fill_back(template, row_bits(c, n))) for c in range(2**n)}
            assert len(sizes) == 1, f"n={n} sizes {sorted(sizes)}"

    def test_a_falling_beam_reuses_the_next_zero_subtree(self) -> None:
        """A one-edge onto an equal zero side draws no rows, and still answers."""
        import random

        from esolangs import tools as generators

        rng = random.Random(5)
        table = "".join(rng.choice("01") for _ in range(128))
        program = generators.back(table)
        assert len(program.splitlines()) < 80  # 84 when every one-edge is drawn
        for row in range(128):
            bits = [(row >> (6 - i)) & 1 for i in range(7)]
            assert self.run_back(self.instantiate(program, bits), 7) == table[row]

    def test_a_fall_off_the_bottom_wraps_onto_the_first_mirror(self) -> None:
        """A last node equal to the first is drawn once, and still answers."""
        import random

        from esolangs import tools as generators

        rng = random.Random(1)
        blocks = ["".join(rng.choice("01") for _ in range(8)) for _ in range(3)]
        pattern = [2, 1, 2, 2, 0, 1, 1, 2, 1, 2, 1, 2, 0, 1, 0, 2]
        table = "0" * 128 + "".join(blocks[i] for i in pattern)
        program = generators.back(table)
        assert len(program) < 0.98 * len(generators.back(table, wrap=False))
        for row in range(0, 256, 3):
            bits = [(row >> (7 - i)) & 1 for i in range(8)]
            assert self.run_back(self.instantiate(program, bits), 8) == table[row]

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs import tools as generators
        from esolangs.tools.back import PAIR

        template = generators.back("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, (PAIR,) * 2)) == 2

    def test_each_input_is_stored_once(self) -> None:
        """Each input is embedded once in the tape load, not re-embedded."""

        from esolangs import tools as generators

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = generators.back(table)
            assert template.count(TEMPLATE_CHAR) == n

    def test_tree_uses_tape_decision_nodes(self) -> None:
        """The reflected decision tree retains its skip and both mirrors."""
        from esolangs import tools as generators

        template = generators.back("0110")
        assert "+" in template
        assert "/" in template
        assert "\\" in template
        assert "*" in template  # leaves halt

    def test_the_natural_order_folds_its_aligned_dependency(self) -> None:
        """A one-input dependency folds wherever the input sits."""
        from esolangs import tools as generators

        scattered = len(generators.back("10101010"))
        aligned = len(generators.back("11110000"))
        parity = len(generators.back("01101001"))
        assert scattered < parity
        assert aligned < parity

    def test_the_identity_template_is_emitted(self) -> None:
        """Back no longer contests input orders."""
        from esolangs import tools as generators

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

        from esolangs import tools as generators

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
        from esolangs import tools as generators
        from tests.tools.fills import fill

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
    from esolangs.tools.back import back

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
    from esolangs.tools.back import _back_ordered
    from esolangs.tools.helpers import permute_truth_table

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

    from esolangs.tools.helpers import permute_truth_table

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


@pytest.mark.parametrize(
    ("n", "seed"),
    [
        (6, 2031),
        (7, 2033),
        (8, 2034),
        (9, 2035),
        (10, 2036),
        pytest.param(11, 2037, marks=pytest.mark.medium),
        # 5.24s alone with coverage exceeds the five-second medium band.
        pytest.param(12, 2038, marks=pytest.mark.slow),
    ],
)
def test_selective_bend_preserves_the_command_bound(n: int, seed: int) -> None:
    """Every input executes; admission compares with both original layouts."""
    import random

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.back import _Machine
    from esolangs.tools.back import back
    from tests.tools.fills import _fill_back

    rng = random.Random(seed)
    blocks = ["".join(rng.choice("01") for _ in range(2 ** (n - 3))) for _ in range(3)]
    table = "".join(blocks[int(c)] for c in "01201201")
    baseline = min(
        (_back_ordered(table, tuple(range(n)), wrap=w) for w in (False, True)), key=len
    )
    program = back(table)

    def area(code: str) -> int:
        return len(code.splitlines()) * max(map(len, code.splitlines()))

    assert len(program) <= len(baseline)
    assert area(program) <= area(baseline)
    rows = 3 * 2**n // 4 + 1
    bound = max(rows, 6 * n - 1) + rows + 3 * n + 6
    worst = 0
    for row, answer in enumerate(table):
        bits = [row >> (n - 1 - i) & 1 for i in range(n)]
        machine = _Machine(_fill_back(program, bits).splitlines(), ScriptedIO())
        steps = 0
        while not machine.halted and steps < bound:
            machine.step()
            steps += 1
        assert machine.halted
        assert machine.tape[n] == int(answer)
        worst = max(worst, steps)
    if n == 7:
        assert (len(baseline), len(program), area(baseline), area(program), worst) == (
            1267,
            1156,
            1560,
            1274,
            179,
        )


def test_bend_walk_rejects_cycles_and_counts_both_skip_outcomes() -> None:
    from esolangs.tools.back_routes import _back_walk

    assert _back_walk({(0, 1): "*"}, 1, 3) == 1
    assert _back_walk({(0, 1): "+", (0, 3): "*"}, 1, 4) == 3
    assert _back_walk({(0, 1): " "}, 1, 3) is None


@pytest.mark.parametrize("obstruction", ["owner", "distance", "occupied"])
def test_bend_refuses_a_missing_owner_or_blocked_corridor(obstruction: str) -> None:
    from esolangs.tools.back_routes import _back_bend

    positions = {(1, 0): (1, 5), (1, 1): (4, 5), (1, 2): (10, 5)}
    grid = dict.fromkeys(positions.values(), "\\")
    ids = [[0], [0, 0], [0, 7, 1, 8, 7, 9]]

    def draw(_shared: set[tuple[int, int]]):
        cells = dict(grid)
        nodes = dict(positions)
        if obstruction == "owner":
            del nodes[1, 2]
        elif obstruction == "distance":
            nodes[1, 2] = (2, 5)
        else:
            cells[2, 3] = ">"
        return cells, nodes

    assert _back_bend(grid, positions, set(), ids, draw) is None
