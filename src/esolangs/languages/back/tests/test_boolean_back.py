"""Covers :mod:`esolangs.languages.back.generator`."""

import random
from itertools import pairwise, permutations

import pytest

import esolangs
from esolangs import run as execute
from esolangs.debugger import make_vm
from esolangs.generation.helpers import TEMPLATE_CHAR, permute_truth_table, runs
from esolangs.generation.wrap import balance_score
from esolangs.languages.back.generator import _back_ordered
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace
from scripts.benchmark import WrittenState
from tests.proofs.deep.execution import run_to_answer
from tests.support.evaluation import _evaluate
from tests.support.event_io import count_steps
from tests.support.generator_support import constant_artifacts, three_input_corpus_size
from tests.support.witness_tables import _drawing, row_bits, witnesses


class TestParameterizedBack:
    """Input-by-substitution generators for the no-input language Back."""

    def run_back(self, prog: str, n: int) -> str:
        # Back has no output instruction: it dumps the whole tape at halt.
        # The generator puts the answer in cell n, so the dump's (n+1)th
        # field is the result -- no need to track the head, which the dump
        # does not report.
        from esolangs.languages.back.interpreter import run

        io = ScriptedIO()
        run(prog.splitlines(), io)
        return io.getvalue().split()[n]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Bind native source with explicitly declared setters."""
        from esolangs.languages.back.descriptor import PAIR

        bindings = esolangs.TemplateBindings(setters=(PAIR,) * len(bits))
        template = esolangs.TemplateArtifact(tpl, "Back", bindings)
        return esolangs.instantiate("Back", template, bits).source

    @pytest.mark.medium
    def test_constant_embedding_keeps_its_resource_bounds(self) -> None:
        from esolangs import generate, instantiate, read_answer
        from scripts.docs.resource_evidence import resource_bounds

        bounds = resource_bounds("Back")
        execution = bounds["execution"].formula
        workspace = bounds["workspace"].formula

        for n in (1, 2, 3, 6, 9, 12):
            for bit in "01":
                for width in (None, 1):
                    template = generate("Back", bit * (1 << n), width=width)
                    sizes = set()
                    for row in range(1 << n) if n <= 3 else (0, (1 << n) - 1):
                        source = instantiate("Back", template, row_bits(row, n))
                        sizes.add(len(source.source))
                        machine = make_vm("Back", source)
                        written = WrittenState(_capture_workspace(machine))
                        steps = run_to_answer(
                            machine,
                            cap=execution(n, template.source),
                            sample=written.sample,
                        )
                        assert steps is not None
                        machine.step()  # Back dumps on the post-halt step.
                        written.sample(_capture_workspace(machine))
                        assert read_answer("Back", machine.output) == bit
                        assert written.bits <= workspace(n, template.source)
                        if width is None:
                            if row == 0:
                                assert steps + 1 == execution(n, template.source)
                            assert written.bits == workspace(n, template.source)
                    assert len(sizes) == 1

        table = "0" * 63 + "1"
        template = generate("Back", table)
        assert "\\" in template.source  # a nonconstant beam layout, not a flat constant
        commands = bits = 0
        for row, expected in enumerate(table):
            source = instantiate("Back", template, row_bits(row, 6))
            machine = make_vm("Back", source)
            written = WrittenState(_capture_workspace(machine))
            steps = run_to_answer(
                machine, cap=execution(6, template.source), sample=written.sample
            )
            assert steps is not None
            machine.step()
            written.sample(_capture_workspace(machine))
            assert read_answer("Back", machine.output) == expected
            commands = max(commands, steps)
            bits = max(bits, written.bits)
        assert (commands, bits) == (52, 26)
        assert commands <= execution(6, template.source)
        assert bits <= workspace(6, template.source)
        _check_exact_preload_bounds()

    def test_a_falling_beam_reuses_the_next_zero_subtree(self) -> None:
        """A one-edge onto an equal zero side draws no rows, and still answers."""
        from esolangs.languages.back import generator as generators

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

        analyze = generator.subtree_ids
        monkeypatch.setattr(
            generator,
            "subtree_ids",
            lambda table: [[0] * len(layer) for layer in analyze(table)],
        )
        for program in (
            _back_ordered("0001", (0, 1)),
            _back_htree("0001", [1, 1]),
        ):
            assert (
                "".join(
                    self.run_back(self.instantiate(program, [row >> 1, row & 1]), 2)
                    for row in range(4)
                )
                == "0000"
            )

    def test_area_is_linear_where_the_comb_is_not(self) -> None:
        """Rudin-Shapiro shares nothing: the comb is 3n + 5 wide, the fold is not."""
        from esolangs.generation.helpers import grid_area
        from esolangs.languages.back import generator as generators

        n = 12
        table = "".join(
            str((i & i >> 1).bit_count() % 2 ^ n % 2 ^ (i == 1)) for i in range(1 << n)
        )
        assert grid_area(generators.back(table)) < 0.75 * (3 * n + 5) * (
            3 * (1 << n) // 4 + 1
        )
        assert grid_area(generators.back(table)) <= 27.5 * (1 << n)

    def test_template_is_input_independent(self) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.languages.back import generator as generators
        from esolangs.languages.back.descriptor import PAIR

        template = generators.back("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, (PAIR,) * 2)) == 2

    def test_each_input_is_stored_once(self) -> None:
        """Constant runs clear one scratch cell before the fixed answer cell."""
        from esolangs.languages.back.interpreter import _Machine

        _check_held_input_and_dump()
        for n, bit, options, template in constant_artifacts("Back", range(1, 13)):
            assert template.source.count(TEMPLATE_CHAR) == n
            if not options:
                assert len(template.source) == 3 * n + 1 + int(bit)
            rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
            for row in rows:
                bits = list(map(int, format(row, f"0{n}b")))
                program = esolangs.instantiate("Back", template, bits)
                assert len(program.source) == len(template.source)
                io = ScriptedIO()
                machine = _Machine(program.source.splitlines(), io)
                written = WrittenState(machine.workspace_snapshot())
                steps = 0
                while not machine.halted and steps < 3 * n + 4:
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                    steps += 1
                assert machine.halted
                assert machine.tape == (0,) * n + (int(bit),)
                assert not io.getvalue()
                machine.step()
                written.sample(machine.workspace_snapshot())
                assert io.getvalue().split()[n] == bit
                if not options:
                    assert steps + 1 == 3 * n + 2 + int(bit) - row.bit_count()
                    assert (
                        written.bits
                        == n + 3 + (3 * n + int(bit)).bit_length() + n.bit_length()
                    )
        assert three_input_corpus_size("Back") == 61542

    def test_tree_uses_tape_decision_nodes(self) -> None:
        """The reflected decision tree retains its skip and both mirrors."""
        from esolangs.languages.back import generator as generators

        template = generators.back("0110")
        assert "+" in template
        assert "/" in template
        assert "\\" in template
        assert "*" in template  # leaves halt

    def test_the_natural_order_folds_its_aligned_dependency(self) -> None:
        """A one-input dependency folds wherever the input sits."""
        from esolangs.languages.back import generator as generators

        scattered = len(generators.back("10101010"))
        aligned = len(generators.back("11110000"))
        parity = len(generators.back("01101001"))
        assert scattered < parity
        assert aligned < parity

    def test_symmetric_tables_reverse_the_loader(self) -> None:
        """Symmetric tables keep their tree and shorten the loader walk."""
        from esolangs.languages.back import generator as generators

        # Every input matters in each; an ignored one is indexed past.
        for table in ("01101001", "00010111", "01111110", "00011110", "10010110"):
            n = (len(table) - 1).bit_length()
            order = tuple(range(n))
            if table in ("01101001", "00010111", "01111110", "10010110"):
                order = tuple(reversed(order))
            assert generators.back(table) == _back_ordered(table, order), table

    def test_reordering_pays_a_walk_and_keeps_name_order(self) -> None:
        """A permuted load spends rows on the walk, and keeps its runs in name order."""
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

        from esolangs.languages.back import generator as generators

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
        from esolangs.languages.back import generator as generators

        for table in ("10101010", "11001100", "01101001"):
            template = generators.back(table)
            sizes = {
                len(self.instantiate(template, [(c >> (2 - i)) & 1 for i in range(3)]))
                for c in range(8)
            }
            assert len(sizes) == 1, f"{table} sizes {sorted(sizes)}"


@pytest.mark.parametrize("width", [1, 10, 20, 80])
def test_descending_loader_preserves_inputs_and_answers(width: int) -> None:
    """The narrower entry reads page-order runs into matching tape cells."""

    runner = TestParameterizedBack()
    for n in range(1, 7):
        table = "".join(str((row * 73 + row // 3) & 1) for row in range(1 << n))
        plain = esolangs.generate("Back", table)
        template = esolangs.generate("Back", table, width=width)
        floor = max(map(len, plain.source.splitlines())) - 2
        assert max(map(len, template.source.splitlines())) <= max(width, floor)
        sizes = set()
        for row, expected in enumerate(table):
            bits = list(map(int, f"{row:0{n}b}"))
            program = esolangs.instantiate("Back", template, bits, truth_table=table)
            sizes.add(len(program.source))
            assert runner.run_back(program.source, n) == expected
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

    table = "00010011"
    order = (2, 0, 1)
    template = _back_ordered(permute_truth_table(table, order), order, 1)
    runner = TestParameterizedBack()
    for row, expected in enumerate(table):
        bits = list(map(int, f"{row:03b}"))
        assert runner.run_back(runner.instantiate(template, bits), 3) == expected


@pytest.mark.medium
def test_vertical_leaf_finish_preserves_every_small_table() -> None:

    runner = TestParameterizedBack()
    for n in range(1, 4):
        for table in witnesses(n):
            template = esolangs.generate("back", table, width=1)
            for row, expected in enumerate(table):
                bits = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
                code = esolangs.instantiate("back", template, bits, truth_table=table)
                assert runner.run_back(code.source, n) == expected
    assert (
        max(map(len, esolangs.generate("back", "0110", width=1).source.splitlines()))
        == 1
    )
    assert (
        max(map(len, esolangs.generate("back", "0110", width=8).source.splitlines()))
        == 5
    )


@pytest.mark.parametrize("width", [1, 4, 7, 10, 80])
@pytest.mark.parametrize("n", [1, 2, 3, 5])
@pytest.mark.parametrize("bias", [0, 1])
def test_parity_accumulator_keeps_public_slots_and_provenance(
    n: int, bias: int, width: int
) -> None:

    table = "".join(str((row.bit_count() & 1) ^ bias) for row in range(1 << n))
    runner = TestParameterizedBack()
    generated = esolangs.generate("Back", table, width=width)
    assert generated.bindings.setters == (("-", "+"),) * n
    for template in (
        generated,
        esolangs.load_program("Back", esolangs.dump_program("Back", generated)),
    ):
        for row, expected in enumerate(table):
            bits = list(map(int, f"{row:0{n}b}"))
            program = esolangs.instantiate("Back", template, bits, truth_table=table)
            assert runner.run_back(program.source, n) == expected
            assert len(program.source) == len(generated.source)
            if width == 1:
                assert max(map(len, program.source.splitlines())) == 1
        with pytest.raises(esolangs.TemplateError):
            esolangs.instantiate(
                "Back", template, [0] * n, truth_table="0" * len(table)
            )
    assert (
        max(map(len, esolangs.generate("Back", table, width=1).source.splitlines()))
        == 1
    )


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """Borrowed loads preserve all three physical positions around the held bit."""
    from esolangs.languages.back.descriptor import PAIR
    from esolangs.languages.back.generator import back

    n = 6
    bindings = esolangs.TemplateBindings(setters=(PAIR,) * (n + 1))
    inner = "".join(str(int(row.bit_count() == 1)) for row in range(1 << n))
    for at, cost in ((0, 209), (3, 117), (6, 117)):
        low = n - at
        table = "".join(
            inner[row >> (low + 1) << low | row & ((1 << low) - 1)]
            for row in range(2 * len(inner))
        )
        program = back(table)
        assert len(program) - len(back(inner)) == cost
        template = esolangs.TemplateArtifact(program, "Back", bindings)
        assert _evaluate("Back", template, inputs=n + 1) == table


@pytest.mark.slow  # builds every permuting generator over several tables
def test_a_permuting_generator_changes_its_drawing() -> None:
    """A generator that permutes its slots must emit a different *drawing*."""
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
        if level == levels - 1 or constant(block * size, (block + 1) * size):
            return
        if ids[level + 1][2 * block] == ids[level + 1][2 * block + 1]:
            walk(order, level + 1, 2 * block, k, shared)
            return
        if level == k:
            order.append(block)
        walk(order, level + 1, 2 * block, k, shared)
        if (level, block) not in shared:
            walk(order, level + 1, 2 * block + 1, k, shared)

    shared = set()
    for k in range(levels - 1):
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
            levels=levels - 1,
            n=n,
            vertical=vertical,
            shared=shared | tried,
            ids=ids,
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
    from esolangs.generation.helpers import subtree_ids
    from esolangs.languages.back.generator import _BackContext

    rng = random.Random(7)
    tables = ["0" * 64, "01" * 32, "0" * 32 + "1" * 32]
    for n in (5, 6, 7, 8):
        for block in (2, 4, 8, 16):
            pool = ["".join(rng.choice("01") for _ in range(block)) for _ in range(2)]
            tables.extend(
                "".join(rng.choice(pool) for _ in range(2**n // block))
                for _ in range(2)
            )
        tables.append("".join("1" if rng.random() < 0.06 else "0" for _ in range(2**n)))
        tables.append("0" * 2 ** (n - 1) + "".join(rng.choices("01", k=2 ** (n - 1))))
    kept = 0
    for table in tables:
        levels = len(table).bit_length() - 1
        for vertical in (False, True):
            rule = _BackContext(
                truth_table=table,
                levels=levels - 1,
                n=levels,
                vertical=vertical,
                ids=subtree_ids(table),
            ).plan()
            assert rule == _drawn_plan(table, levels, levels, vertical)
            kept += len(rule)
    assert kept == 369  # fewer tests/pair leaves; the full old corpus still fires


@pytest.mark.parametrize(("n", "side"), [(7, 66), (8, 82)])
def test_balance_races_the_folded_tree(n: int, side: int) -> None:
    """The comb wins area but the fold, at its best comb base, is the smaller square."""
    table = format(random.Random(131 * 0 + n).getrandbits(1 << n), f"0{1 << n}b")
    comb = esolangs.generate("Back", table)
    balanced = esolangs.generate("Back", table, balance=True)
    assert balance_score(balanced.source)[0] == side < balance_score(comb.source)[0]
    assert _evaluate("Back", balanced, inputs=n) == table


def _check_held_input_and_dump() -> None:
    from esolangs.languages.back.interpreter import _Machine

    for n, used in ((1, (0,)), (3, (0, 2)), (8, (0, 2, 6)), (8, (1, 3, 7))):
        table = "".join(
            str(
                ((row >> (n - 1 - used[0])) & (row >> (n - 1 - used[-1])) & 1)
                ^ sum((row >> (n - 1 - bit)) & 1 for bit in used[1:-1]) % 2
            )
            for row in range(1 << n)
        )
        for options in ({}, {"width": 1}, {"balance": True}):
            template = esolangs.generate("Back", table, **options)
            for row in (0, (1 << n) // 3, (1 << n) - 1):
                source = esolangs.instantiate("Back", template, row_bits(row, n))
                io = ScriptedIO("Q")
                machine = _Machine(source.source.splitlines(), io)
                count_steps(machine, 4999)
                machine.step()
                assert len(machine.tape) == n + 1
                assert io.getvalue().split()[n] == table[row]
                assert io.position() == 0
                assert io.input_char() == ord("Q")
    # Non-answer cells are storage/scratch; only cell n is the answer contract.
    template = esolangs.generate("Back", "0001")
    source = esolangs.instantiate("Back", template, [1, 0])
    assert execute("Back", source).output == "0 0 0"


def _check_exact_preload_bounds() -> None:
    from esolangs.generation.helpers import grid_area
    from esolangs.languages.back.tests.formulas import (
        execution_witness,
        witness,
    )
    from scripts.docs.resource_evidence import resource_bounds

    bounds = resource_bounds("Back")
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula
    scaling = bounds["scaling"].formula
    for n in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        area_table = witness(n)
        template = esolangs.generate("Back", area_table)
        assert grid_area(template.source) == scaling(n, template.source)
        table = execution_witness(n)
        template = esolangs.generate("Back", table)
        source = esolangs.instantiate("Back", template, [1] * n)
        machine = make_vm("Back", source)
        assert run_to_answer(machine) == execution(n, template.source)
        machine.step()
        assert esolangs.read_answer("Back", machine.output) == table[-1]
        if n in (3, 6):
            machine = make_vm("Back", source)
            state = WrittenState(_capture_workspace(machine))
            run_to_answer(machine, sample=state.sample)
            machine.step()
            state.sample(_capture_workspace(machine))
            assert state.bits == workspace(n, template.source)
