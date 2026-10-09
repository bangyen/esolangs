"""Container's tree route (``n <= 6``) and its wide threshold route."""

import itertools
import random

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs._evaluate import _evaluate
from tests.generator_support import assert_an_ignored_input_costs
from tests.tools.boolean_runners import run_container
from tests.tools.sample_tables import five_input_sample
from tests.witness_tables import row_bits, witnesses


def _run_container_capped(program: str, inputs: list[str], *, budget: int) -> str:
    """Run a Container program under a hard tick budget and return its output."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.container import _Machine

    stream = ScriptedIO("".join(f"{line}" for line in inputs))
    machine = _Machine(program.splitlines(), stream)
    for _ in range(budget):
        if machine.halted:
            return stream.getvalue()
        machine.step()
    if not machine.halted:
        raise AssertionError(f"still running after {budget} ticks")
    return stream.getvalue()


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
                _run_container_capped(program, list(f"{row:07b}"), budget=2 * n + 2)
                == table[row]
            )

    @pytest.mark.parametrize(
        "original", ["A:\n+9 A<=18\nEXIT:", "A=27:\n-9 A>=9\nEXIT:"]
    )
    def test_exact_delta_chunks_preserve_each_tick(self, original: str) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.container import _Machine
        from esolangs.tools.container import _narrow_rules

        before = _Machine(original.splitlines(), ScriptedIO(""))
        after = _Machine(_narrow_rules(original, 1).splitlines(), ScriptedIO(""))
        for _ in range(4):
            before.step()
            after.step()
            assert before.var == {key: after.var[key] for key in before.var}
            assert before.halted == after.halted

    @pytest.mark.parametrize("width", [1, 7, 8])
    def test_narrow_rules_execute_the_three_input_witnesses(self, width: int) -> None:
        for table in witnesses(3):
            program = boolean.container(table, width)
            assert max(map(len, program.splitlines())) <= max(7, width)
            for row in range(8):
                assert (
                    _run_container_capped(program, list(f"{row:03b}"), budget=8)
                    == (table[row])
                )

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
            before = _Machine(original.splitlines(), ScriptedIO(inputs))
            after = _Machine(narrow.splitlines(), ScriptedIO(inputs))
            keys = before.var.keys()
            for _ in range(8):
                before.step()
                after.step()
                assert before.var == {key: after.var[key] for key in keys}
                assert before.halted == after.halted
                assert before.io.getvalue() == after.io.getvalue()

    @pytest.mark.medium
    def test_wide_tables_decode_every_row_inside_a_tick_budget(self) -> None:
        """A *random dense* wide table answers every row in ``2n + 2`` ticks."""
        rng = random.Random(20260922)
        for n in (7, 8):
            table = "".join(rng.choice("01") for _ in range(1 << n))
            assert table.count("1") > (1 << n) // 4, "not a dense table"
            program = boolean.container(table)
            for combo in range(1 << n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                got = _run_container_capped(program, bits, budget=2 * n + 2)
                assert got == table[combo], f"n={n} row {combo}"

    def test_name_allocation_steps_over_container_s_own_names(self) -> None:
        """Letter names reach ``T`` at 45 and ``IN`` at 754, so they collide."""
        from esolangs.tools.container import _RESERVED, _allocate_names

        uses = {("node", 0, index): 1000 - index for index in range(800)}
        names = _allocate_names(uses)
        assert not _RESERVED & set(names.values())
        assert len(set(names.values())) == len(uses)
        # Descending use counts, so the allocation order is the key order.
        assert [names[key] for key in list(uses)[:3]] == ["a", "b", "c"]

    def test_wide_tables_read_exactly_n_inputs(self) -> None:
        """The latch-and-gate route still reads one line per input."""
        program = boolean.container("0110100110010110" * 8)
        assert program.count("IN>=") == 7  # one latch per input, no rescan
        assert program.count("PRINT:") == 1

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
        """A dense table is summed from its zero leaves and inverted."""
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
        """The positive control: a constant reads its inputs and prints."""
        for table in ("0" * 8, "1" * 8, "0" * 16):
            program = boolean.container(table)
            assert "IN>=" not in program
            assert ">=IN" not in program
            n = len(table).bit_length() - 1
            for combo in range(2**n):
                bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                assert run_container(program, bits) == table[0]
        assert len(boolean.container("0" * 8)) == 123  # 856 unpruned

    def test_only_dependent_levels_are_tested(self) -> None:
        """A level whose halves agree is read but never tested."""

        def tests(table: str) -> int:
            program = boolean.container(table)
            return program.count("IN>=") + program.count(">=IN")

        assert tests("00001111") == 1  # the first input alone
        assert tests("01010101") == 1  # the last input alone
        assert tests("00010011") == 5  # four nodes test, not seven
        assert tests("01101001") == 8
        for table in ("00001111", "01010101", "00010011", "00110000"):
            for combo in range(8):
                bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
                assert run_container(boolean.container(table), bits) == table[combo]

    def test_pruning_never_grows_a_table(self) -> None:
        """No table up to three inputs comes out longer than its full tree."""
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
        """Unsigned deltas, no leaf decay, no output restore, a static ``OUT``."""
        program = boolean.container("01101001")
        assert "+" not in program
        assert "OUT=48:" in program
        # Parity's tree: only the root and the nodes above the leaves decay,
        # two a level, since the level above the leaves is two distinct.
        decays = [line for line in program.split("\n") if line.endswith(">=1")]
        assert sum(line.startswith("-1 ") for line in decays) == 1 + 2 + 2
        for combo in range(8):
            bits = [str((combo >> (2 - i)) & 1) for i in range(3)]
            assert run_container(program, bits) == "01101001"[combo]

    @pytest.mark.parametrize("table", ["11111110", "11111111", "1110", "0111"])
    def test_complemented_tables_still_compute(self, table: str) -> None:
        """The inverted form answers the original table."""
        n = (len(table) - 1).bit_length()
        program = boolean.container(table)
        for combo in range(2**n):
            bits = row_bits(combo, n)
            got = run_container(program, [str(b) for b in bits])
            assert got == str(int(table[combo])), f"inputs {bits}"


class TestContainerSharing:
    """A subtree already born at its depth is fed by every parent, not repeated."""

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
        """Four-input parity relays its repeated nodes and runs every row."""
        table = "0110100110010110"
        program = boolean.container(table)
        assert len(program) == 820  # 1,136 unshared
        kills = [line for line in program.splitlines() if line.endswith(">=1")]
        assert sum(line.startswith("-2 ") and "T" not in line for line in kills) == 4
        for combo in range(16):
            bits = [str((combo >> (3 - i)) & 1) for i in range(4)]
            assert run_container(program, bits) == table[combo]


@pytest.mark.medium
def test_an_ignored_input_is_read_and_dropped() -> None:
    """Its latch and window, no weight (the threshold route starts at seven)."""
    assert_an_ignored_input_costs("Container", 7, 66)


@pytest.mark.parametrize("table", ["01" * 64])
def test_narrow_balance_regime_edge_executes(table):
    """The smallest tables reaching an otherwise-untaken balance arm."""
    balanced = esolangs.generate("Container", table, balance=True)
    assert _evaluate("Container", balanced, inputs=len(table).bit_length() - 1) == table
