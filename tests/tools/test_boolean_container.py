"""Container's tree route (``n <= 6``) and its wide threshold route."""

import itertools

import pytest

from esolangs import tools as boolean
from esolangs.interpreters.other.container import _Machine
from tests.interpreters.container_observer import check
from tests.interpreters.container_reference import Reference
from tests.tools.boolean_runners import five_input_sample


class TestContainer:
    @pytest.mark.medium
    def test_narrow_threshold_layout_executes_wide_table(self) -> None:
        n = 7
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        program = boolean.container(table, 1)
        assert max(map(len, program.splitlines())) < max(
            map(len, boolean.container(table).splitlines())
        )
        for row in (0, 1, 63, 64, 127):
            assert (
                check(program.splitlines(), f"{row:07b}", _Machine, table[row])[
                    "generations"
                ]
                <= 2 * n + 2
            )

    @pytest.mark.parametrize(
        "original", ["A:\n+9 A<=18\nEXIT:", "A=27:\n-9 A>=9\nEXIT:"]
    )
    def test_exact_delta_chunks_preserve_each_tick(self, original: str) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.container import _Machine
        from esolangs.tools.container import _narrow_rules

        before = Reference(original.splitlines())
        after = _Machine(_narrow_rules(original, 1).splitlines(), ScriptedIO(""))
        for _ in range(4):
            before.step()
            after.step()
            assert before.values == {key: after.var[key] for key in before.values}
            assert before.halted == after.halted

    @pytest.mark.parametrize("width", [1, 7, 8, 13])
    def test_narrow_rules_respect_every_three_input_width(self, width: int) -> None:
        for value in range(256):
            table = f"{value:08b}"
            program = boolean.container(table, width)
            assert max(map(len, program.splitlines())) <= max(7, width)

    @pytest.mark.medium
    def test_factored_rules_preserve_synchronous_state(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.container import _Machine
        from esolangs.tools.container import _container_threshold, _narrow_rules

        original = _container_threshold("01101001")
        narrow = _narrow_rules(original, 7)
        assert max(map(len, narrow.splitlines())) == 7
        assert max(map(len, original.splitlines())) > 7
        for row in range(8):
            inputs = f"{row:03b}"
            before = Reference(original.splitlines(), inputs)
            after = _Machine(narrow.splitlines(), ScriptedIO(inputs))
            keys = before.values.keys()
            for _ in range(8):
                before.step()
                after.step()
                assert before.values == {key: after.var[key] for key in keys}
                assert before.halted == after.halted
                assert before.output == after.io.getvalue()

    def test_name_allocation_steps_over_container_s_own_names(self) -> None:
        """``_forbin_name`` reaches ``T`` at 45 and ``IN`` at 754, so it collides.

        Both routes draw from one namespace, and the skip is live rather than
        defensive: a generated container called ``T`` would be the tick
        counter and a generated ``IN`` would be overwritten by every read.
        """
        from esolangs.tools.container import _RESERVED, _allocate_names

        uses = {("node", 0, index): 1000 - index for index in range(800)}
        names = _allocate_names(uses)
        assert not _RESERVED & set(names.values())
        assert len(set(names.values())) == len(uses)
        # Descending use counts, so the allocation order is the key order.
        assert [names[key] for key in list(uses)[:3]] == ["a", "b", "c"]

    def test_small_tree_uses_one_character_generated_names(self) -> None:
        """Gates and survivors share one compact identifier namespace."""
        declarations = [
            line[:-1].split("=", 1)[0]
            for line in boolean.container("01101001").splitlines()
            if line.endswith(":")
        ]
        special = {"", "T", "IN", "OUT", "PRINT", "EXIT"}
        assert all(len(name) == 1 for name in declarations if name not in special)

    @pytest.mark.slow
    def test_tree_removes_the_minterm_factor(self) -> None:
        """Each additional row adds bounded tree work, not n tests."""
        sizes = [len(boolean.container("01" * (2 ** (n - 1)))) for n in range(7, 11)]
        assert all(b <= 2 * a + 4000 for a, b in itertools.pairwise(sizes))

    def test_dense_tables_evaluate_the_complement(self) -> None:
        """A dense table is summed from its zero leaves and inverted.

        ``OUT`` costs one ``1 S{row}>=Gout`` line per leaf the table sends
        to 1, so before this the length rose with the ones-count all the way
        to the all-ones table.  A table and its complement share one tree,
        so taking whichever leaf set is smaller makes them the same length
        but for the sign: an inverted line spells ``-1`` where a plain one
        spells ``1``.
        """
        from esolangs.tools.container import _container_tree

        full = [
            len(_container_tree("1" * k + "0" * (8 - k), prune=False)) for k in range(9)
        ]
        assert full[4] == max(full)  # four ones is the worst case
        # k ones against k zeros: the same k answer lines, each one signed,
        # but for one ``-`` fewer at k = 1, whose lone answering leaf is a
        # high child and so declares only the high gate (``1 T>=``).
        assert [full[8 - k] - full[k] for k in range(4)] == [0, 0, 2, 3]
        flip = str.maketrans("01", "10")
        for i in range(256):
            table = format(i, "08b")
            complement = table.translate(flip)
            difference = len(_container_tree(table)) - len(_container_tree(complement))
            assert abs(difference) <= 3  # leaf signs differ, not their count

    def test_constants_test_nothing(self) -> None:
        """The positive control: a constant reads its inputs and prints.

        Its root is its only leaf, so it has no gate and no test at all, and
        what is left is the reader, the leaf and the output block.
        """
        for table in ("0" * 8, "1" * 8, "0" * 16):
            program = boolean.container(table)
            assert "IN>=" not in program
            assert "IN<=" not in program
            len(table).bit_length() - 1
        assert len(boolean.container("0" * 8)) == 123  # 856 unpruned

    def test_only_dependent_levels_are_tested(self) -> None:
        """A level whose halves agree is read but never tested.

        Each test is one ``IN>=``/``IN<=`` mismatch line on an emitted
        child, and a leaf that does not answer is not emitted; parity's
        eight leaves are four answers, shared into two, beside four nodes.
        """

        def tests(table: str) -> int:
            program = boolean.container(table)
            return program.count("IN>=") + program.count("IN<=")

        assert tests("00001111") == 1  # the first input alone
        assert tests("01010101") == 1  # the last input alone
        assert tests("00010011") == 5  # four nodes test, not seven
        assert tests("01101001") == 8

    def test_pruning_never_grows_a_table(self) -> None:
        """No table up to three inputs comes out longer than its full tree.

        Summed over all 256 three-input tables the shipped build is 110,437
        characters against 154,833 unpruned.
        """
        from esolangs.tools.container import _container_tree

        for n in (1, 2, 3):
            for i in range(1 << (1 << n)):
                table = format(i, f"0{1 << n}b")
                assert len(boolean.container(table)) <= len(
                    _container_tree(table, prune=False)
                )
        tables = [format(i, "08b") for i in range(256)]
        assert sum(len(boolean.container(t)) for t in tables) == 110_437
        assert sum(len(_container_tree(t, prune=False)) for t in tables) == 154_833

    def test_no_line_restores_what_nothing_reads(self) -> None:
        """Unsigned deltas, no leaf decay, no output restore, a static ``OUT``.

        A leaf is read once, by the output gate, so it keeps its birth value;
        the gate and ``OUT`` never need to come back, since ``EXIT`` halts the
        tick after ``PRINT``.  The 256 three-input tables went from 166,768
        characters to 141,366.
        """
        program = boolean.container("01101001")
        assert "+" not in program
        assert "OUT=48:" in program
        # Parity's tree: only the root and the nodes above the leaves decay,
        # two a level, since the level above the leaves is two distinct.
        decays = [line for line in program.split("\n") if line.endswith(">=1")]
        assert sum(line.startswith("-1 ") for line in decays) == 1 + 2 + 2


class TestContainerSharing:
    """A subtree already born at its depth is fed by every parent, not repeated.

    Retiring unshared candidates adds 0.302% to the three-input total
    and nothing to the seeded five-input total. Before this the totals were
    141,366
    and 345,287: the leaves that do not answer, never read, are not emitted
    in either build.
    """

    @staticmethod
    def _totals(tables: list[str]) -> tuple[int, int]:
        """Return unshared and shipped character totals."""
        from esolangs.tools.container import _container_tree

        before = after = 0
        for table in tables:
            plain = len(_container_tree(table))
            shipped = len(boolean.container(table))
            before, after = before + plain, after + shipped
        return before, after

    def test_three_input_total(self) -> None:
        """All 256 three-input tables: 112,857 to 110,437 characters, 2.4%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._totals(tables) == (112_857, 110_437)
        assert 110_437 * 100 < 110_105 * 105

    def test_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 284,564 to 237,480 characters, 16.5%."""
        assert self._totals(five_input_sample()) == (284_564, 237_480)

    def test_a_relay_feeds_the_other_side_s_copy(self) -> None:
        """Four-input parity relays its repeated nodes and runs every row.

        A node's mismatch rule names its side's gate, so a repeat on the other
        side is a relay: it kills itself a tick after birth (``-2 X>=1``) and
        feeds the copy one less (``1 X>=1``).
        """
        table = "0110100110010110"
        program = boolean.container(table)
        assert len(program) == 820  # 1,136 unshared
        kills = [line for line in program.splitlines() if line.endswith(">=1")]
        assert sum(line.startswith("-2 ") and "T" not in line for line in kills) == 4
