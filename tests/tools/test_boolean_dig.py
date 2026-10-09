"""dig generator tests."""

import importlib

import pytest

import esolangs
from esolangs import tools as boolean
from esolangs._evaluate import _evaluate
from esolangs.tools.dig import _DIG_BRANCH, _DIG_STRIDE
from tests.tools.boolean_runners import (
    run_dig,
)


class TestDig:
    def test_four_input_parity_keeps_the_compact_layout(self) -> None:
        """Dropping the banded candidate grew this program from 436 to 706."""
        table = "0110100110010110"
        program = boolean.dig(table)
        assert len(program) <= 436
        for row, expected in enumerate(table):
            assert run_dig(program, list(format(row, "04b"))) == expected

    @pytest.mark.medium
    def test_alternating_layout_executes_every_row(self) -> None:
        """The alternating-axis tree computes two dense wide tables."""
        for n in (5, 6):
            size = 1 << n
            tables = (
                ("01101001" * size)[:size],
                "".join(str((row * 73 + row // 3) & 1) for row in range(size)),
            )
            for table in tables:
                program = boolean.dig(table)
                for combo in range(size):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    assert run_dig(program, [str(bit) for bit in bits]) == table[combo]

    def test_alternating_layout_has_linear_area(self) -> None:
        """Text per entry stays under a constant as the arity grows."""
        sizes = [len(boolean.dig("01" * (2 ** (n - 1)))) / 2**n for n in (7, 9, 11)]
        assert max(sizes) < 9

    def test_xor_layout(self) -> None:
        """The XOR gate produces the standard two-level decision tree."""
        expected = (
            "'         >$30:@\n"
            "     >$3~;#\n"
            "          >$31:@\n"
            ">$3~;#\n"
            "          >$31:@\n"
            "     >$3~;#\n"
            "          >$30:@"
        )
        assert boolean.dig("0110", width=80) == expected

    def test_banded_layout_remains_available_for_width_requests(self) -> None:
        """A banded tree fits when the flat tree exceeds the requested width."""
        from esolangs.tools.dig import _dig_grid

        table = "0110100110010110"
        n = 4
        flat = _dig_grid(table, n, None)
        banded = _dig_grid(table, n, -(-(n + 2) // 2))
        assert len(banded) < len(flat)
        assert boolean.dig(table, width=18) == banded

    def test_a_constant_table_is_one_line(self) -> None:
        """Nothing to branch on, so the whole grid is a single leaf."""
        program = boolean.dig("1111")
        assert program.split("\n") == ["'", ">$5~~1:@"]

    def test_a_constant_leaf_is_a_row_of_reads(self) -> None:
        """A constant half sizes its own box, so the grid shrinks."""
        import random

        rng = random.Random(3)
        half = "".join(rng.choice("01") for _ in range(64))
        mixed = boolean.dig(half + "0" * 64).split("\n")
        full = boolean.dig(half + half[::-1]).split("\n")
        assert len(mixed) * max(map(len, mixed)) < len(full) * max(map(len, full))

    def test_constant_subtrees_prune_their_rows(self) -> None:
        """A folded node's descendants are never written."""
        folded = boolean.dig("11110000")
        full = boolean.dig("10010110")
        assert len(folded) < len(full)
        assert sum(1 for r in folded.split("\n") if r.strip()) < sum(
            1 for r in full.split("\n") if r.strip()
        )
        assert all(row.strip() for row in folded.splitlines())

    def test_a_repeated_flat_leaf_is_shared_and_still_computes(self) -> None:
        """Quarters A B B A hold two leaves' worth of text, not four."""
        import random

        rng = random.Random(5)
        a, b, c, d = ("".join(rng.choice("01") for _ in range(64)) for _ in range(4))
        table = a + b + b + a
        program = boolean.dig(table)
        assert len(program) < 0.7 * len(boolean.dig(a + b + c + d))
        for row in range(0, 256, 17):
            assert run_dig(program, list(format(row, "08b"))) == table[row]

    def test_unmatched_leaf_groups_still_answer(self) -> None:
        """Three-leaf nine-input groups keep the unshared layout."""
        import random

        rng = random.Random(262)
        blocks = ["".join(rng.choice("01") for _ in range(64)) for _ in range(3)]
        table = "".join(blocks[i] for i in (1, 1, 1, 0, 0, 2, 0, 2))
        program = boolean.dig(table)
        assert program == boolean.dig(table, share=False)
        for row in range(0, 512, 37):
            assert run_dig(program, list(format(row, "09b"))) == table[row]

    def test_unaligned_leaf_chains_seven_input_reads(self) -> None:
        """A folded flat leaf needs two windows beyond its six-read tail."""
        from esolangs.interpreters.grid_based.dig import run
        from esolangs.interpreters.io import ScriptedIO

        for expected in "01":
            program = boolean.dig(expected * 128, 1000)
            for row in range(128):
                io = ScriptedIO("\n".join(format(row, "07b")) + "\n")
                run(program.splitlines(), io)
                assert io.getvalue() == expected
                assert io.reads == 7

    def test_a_long_read_run_chains_its_windows(self) -> None:
        """Past nine cells the ``$`` runs chain rather than growing a digit."""
        table = "1" * 128  # n == 7, constant
        program = boolean.dig(table)
        assert program.count("$") > 1  # more than one window
        assert esolangs.run("Dig", program, stdin="\n".join(["1"] * 7)).strip() == "1"

    def test_a_width_turns_the_tree_round_and_it_still_computes(self) -> None:
        """A narrower grid is the same walk, folded back over its own columns."""
        for table in ("0110", "10010110", "0110100110010110", "00010111"):
            n = len(table).bit_length() - 1
            flat = boolean.dig(table, 10_000)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.dig(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 12, 18, 24, wide):
                narrow = boolean.dig(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = run_dig(narrow, [str(b) for b in bits])
                    assert got == str(int(table[combo])), (table, width, bits)

    def test_rotated_small_dig_trees_keep_all_operand_reads(self) -> None:
        """Quarter-turning changes neighbor priority, so execute every path."""
        assert max(map(len, boolean.dig("0110", 1).splitlines())) == 4
        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                program = boolean.dig(table, 1)
                for row, expected in enumerate(table):
                    bits = list(format(row, f"0{n}b"))
                    assert run_dig(program, bits) == expected

    def test_xor_polynomial_uses_four_operand_columns(self) -> None:
        from esolangs.interpreters.grid_based.dig import run
        from esolangs.interpreters.io import ScriptedIO

        # Every width up to 7 builds this same program.
        program = esolangs.generate("Dig", "0110", width=1)
        assert max(map(len, program.splitlines())) == 4
        for row, expected in enumerate("0110"):
            io = ScriptedIO("\n".join(f"{row:02b}") + "\n")
            run(program.splitlines(), io)
            assert (io.getvalue(), io.reads) == (expected, 2)

    def test_a_folded_table_keeps_the_flat_layout(self) -> None:
        """Turning round is not always narrower, so the narrower one wins."""
        for table in ("1" * 64, "1" * 32 + "0" * 32):
            n = len(table).bit_length() - 1
            flat = boolean.dig(table, 10_000)
            assert boolean.dig(table, 1) == flat, table
            for combo in (0, 2 ** (n - 1), 2**n - 1):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = run_dig(flat, [str(b) for b in bits])
                assert got == str(int(table[combo])), (table, bits)

    def test_the_turn_mirrors_the_blocks_it_writes(self) -> None:
        """Past the turn a block is written backwards, so its ``$`` comes first."""
        narrow = boolean.dig("0110100110010110", 1)
        assert _DIG_BRANCH[::-1] in narrow, "no mirrored block: the tree never turned"
        assert "<" in narrow, "nothing points the mole west"
        flat = boolean.dig("0110100110010110", 10_000)
        assert _DIG_BRANCH[::-1] not in flat
        assert "<" not in flat

    def test_the_layout_check_refuses_a_stride_that_collides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The clearance check is what licenses the two bands sharing columns."""
        dig_module = importlib.import_module("esolangs.tools.dig")

        monkeypatch.setattr(dig_module, "_DIG_BAND", _DIG_STRIDE)
        for table in ("0110", "10010110", "0110100110010110"):
            with pytest.raises(AssertionError):
                boolean.dig(table, 8)
        monkeypatch.undo()
        # and the stride the rule names still builds
        assert boolean.dig("0110100110010110", 1)

    def test_ignored_leading_inputs_are_read_down_one_column(self) -> None:
        """Leading ignored inputs and constants cost a column, not a wider tree."""
        inner = "0110"
        for count in (1, 7, 8, 9):
            table = inner * (1 << count)
            n = count + 2
            program = boolean.dig(table)
            assert program.endswith("\n" + boolean.dig(inner))
            for row in (0, 1, 2, 3, (1 << n) - 1, (1 << n) - 2):
                bits = [str(row >> (n - 1 - i) & 1) for i in range(n)]
                assert run_dig(program, bits) == table[row], (count, row)
        for n in (6, 7, 8):
            for value in "01":
                program = boolean.dig(value * (1 << n))
                assert len(program) < 4 * n + 8
                assert run_dig(program, ["1"] * n) == value

    @pytest.mark.medium
    def test_an_ignored_middle_input_costs_no_level(self) -> None:
        """A bare ``~`` in an adder or the next block, not a level: 802 -> 355."""

        def ignore(table: str, at: int) -> str:
            low = len(table).bit_length() - 1 - at
            return "".join(
                table[row >> (low + 1) << low | row & ((1 << low) - 1)]
                for row in range(2 * len(table))
            )

        six, seven, eight = (
            "".join(str((row * 73 + row // 3) & 1) for row in range(size))
            for size in (64, 128, 256)
        )
        # Seven essential inputs put the ignored one just above the leaf's
        # six; eight put it between two tree levels, in the second's block.
        cases = [(six, at) for at in (1, 3, 5)] + [(seven, 1), (eight, 1)]
        for inner, at in cases:
            table = ignore(inner, at)
            n = len(table).bit_length() - 1
            program = boolean.dig(table)
            assert len(program) < 1.03 * len(boolean.dig(inner))
            for row in range(0, 1 << n, 1 if n == 7 else 11):
                bits = [str(row >> (n - 1 - i) & 1) for i in range(n)]
                assert run_dig(program, bits) == table[row], (at, row)


@pytest.mark.parametrize("width", [40, 10_000])
def test_a_width_tree_reads_an_ignored_input_in_the_next_block(width: int) -> None:
    """f(a, c, d) with b ignored: one ``$4~~;#`` skip, not a fourth level."""
    inner = "01101001"
    table = "".join(inner[(i >> 3) << 2 | i & 3] for i in range(16))  # b ignored
    program = boolean.dig(table, width)
    assert "$4~~;#" in program
    assert len(program) < len(boolean.dig("0110100110010110", width))
    for row in range(16):
        assert run_dig(program, list(format(row, "04b"))) == table[row], row


@pytest.mark.parametrize("table", ["00", "0000"])
def test_narrow_balance_regime_edge_executes(table):
    """The smallest tables reaching an otherwise-untaken balance arm."""
    balanced = esolangs.generate("Dig", table, balance=True)
    assert _evaluate("Dig", balanced, inputs=len(table).bit_length() - 1) == table


@pytest.mark.medium
@pytest.mark.parametrize("width", [35, 40, 10_000])
def test_wide_requests_admit_the_unshared_alternating_grid(width: int) -> None:
    """The repeated-leaf case fits 35 columns and keeps the 220-step bound."""
    import random

    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.tools.dig import _dig_grid

    rng = random.Random(2026)
    a, b = ("".join(rng.choice("01") for _ in range(64)) for _ in range(2))
    table = a + b + b + a
    program = boolean.dig(table, width, share=False)
    rows = program.splitlines()
    assert max(map(len, rows)) <= width
    assert len(rows) * max(map(len, rows)) == 1925
    banded = _dig_grid(table, 8, 5).splitlines()
    assert len(banded) * max(map(len, banded)) == 11250
    worst = 0
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, "08b")) + "\n")
        machine = _Machine(rows, io)
        steps = 0
        while not machine.halted and steps <= 220:
            machine.step()
            steps += 1
        assert machine.halted
        assert (io.getvalue(), io.reads) == (expected, 8)
        worst = max(worst, steps)
    assert worst == 220


@pytest.mark.medium
@pytest.mark.parametrize("width", [None, 1, 8, 26, 40])
def test_shared_routes_keep_the_execution_bound(
    width: int | None,
) -> None:
    import random

    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import ScriptedIO

    rng = random.Random(2026)
    a, b = ("".join(rng.choice("01") for _ in range(64)) for _ in range(2))
    table = a + b + b + a
    program = boolean.dig(table, width)
    rows = program.splitlines()
    wide = width is None or width >= 35
    assert (len(rows), max(map(len, rows)), len(program)) == (
        (33, 35, 912) if wide else (47, 26, 1091)
    )
    worst = 0
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, "08b")) + "\n")
        machine = _Machine(rows, io)
        steps = 0
        while not machine.halted and steps <= 220:
            machine.step()
            steps += 1
        assert machine.halted
        assert (io.getvalue(), io.reads) == (expected, 8)
        worst = max(worst, steps)
    assert worst == (208 if wide else 218)


@pytest.mark.medium
@pytest.mark.parametrize(("a", "b"), [("01" * 32, "10" * 32), ("0" * 64, "1" * 64)])
def test_fixed_pair_reads_ignored_and_constant_leaf_inputs(a: str, b: str) -> None:
    from esolangs.interpreters.grid_based.dig import run
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.tools.dig import _dig_shared_pair

    table = a + b + b + a
    program = _dig_shared_pair(table, 8)
    assert program is not None
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, "08b")) + "\n")
        run(program.splitlines(), io)
        assert (io.getvalue(), io.reads) == (expected, 8)


@pytest.mark.medium
@pytest.mark.parametrize("pattern", [format(mask, "04b") for mask in range(16)])
def test_two_leaf_prefixes_keep_the_execution_ledger(pattern: str) -> None:
    import random

    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import ScriptedIO

    rng = random.Random(2026)
    blocks = ["".join(rng.choice("01") for _ in range(64)) for _ in range(2)]
    table = "".join(blocks[int(bit)] for bit in pattern)
    rows = boolean.dig(table).splitlines()
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, "08b")) + "\n")
        machine = _Machine(rows, io)
        steps = 0
        while not machine.halted and steps <= 220:
            machine.step()
            steps += 1
        assert machine.halted, (pattern, row, steps)
        assert (io.getvalue(), io.reads) == (expected, 8)


@pytest.mark.medium
@pytest.mark.parametrize("ignored", [0, 1, 2])
def test_column_routes_consume_ignored_prefix_inputs(ignored: int) -> None:
    import random

    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.tools.dig import _dig_lane_shared

    rng = random.Random(2026)
    a, b = ("".join(rng.choice("01") for _ in range(64)) for _ in range(2))
    table = (a + b + b + a) * (1 << ignored)
    n = 8 + ignored
    program = _dig_lane_shared(table, n)
    assert program is not None
    rows = program.splitlines()
    assert len(rows) * max(map(len, rows)) == 1155
    worst = 0
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, f"0{n}b")) + "\n")
        machine = _Machine(rows, io)
        steps = 0
        while not machine.halted and steps <= 208:
            machine.step()
            steps += 1
        assert machine.halted
        assert (io.getvalue(), io.reads) == (expected, n)
        worst = max(worst, steps)
    assert worst == 208


@pytest.mark.medium
@pytest.mark.parametrize(
    ("pattern", "expected_steps"),
    [("0000000000000001", 297), ("0110100110010110", 279)],
)
def test_multiple_copies_merge_along_one_column(
    pattern: str, expected_steps: int
) -> None:
    import random

    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.tools.dig import _dig_lane_shared

    rng = random.Random(2026)
    blocks = ["".join(rng.choice("01") for _ in range(64)) for _ in range(2)]
    table = "".join(blocks[int(bit)] for bit in pattern)
    program = _dig_lane_shared(table, 10)
    assert program is not None
    rows = program.splitlines()
    unshared = boolean.dig(table, share=False).splitlines()
    assert len(rows) * max(map(len, rows)) < 0.7 * len(unshared) * max(
        map(len, unshared)
    )
    worst = 0
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, "010b")) + "\n")
        machine = _Machine(rows, io)
        steps = 0
        while not machine.halted and steps <= 312:
            machine.step()
            steps += 1
        assert machine.halted
        assert (io.getvalue(), io.reads) == (expected, 10)
        worst = max(worst, steps)
    assert worst == expected_steps


@pytest.mark.medium
@pytest.mark.parametrize("ignored", [0, 1, 2])
def test_vertical_leaves_share_a_spare_row(ignored: int) -> None:
    import random

    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.tools.dig import _dig_lane_shared

    rng = random.Random(2026)
    blocks = ["".join(rng.choice("01") for _ in range(64)) for _ in range(2)]
    table = "".join(blocks[int(bit)] for bit in "01101001") * (1 << ignored)
    n = 9 + ignored
    program = _dig_lane_shared(table, n)
    assert program is not None
    rows = program.splitlines()
    assert (len(rows), max(map(len, rows)), len(program)) == (
        71,
        36 + ignored,
        2252 + 67 * ignored,
    )
    worst = 0
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, f"0{n}b")) + "\n")
        machine = _Machine(rows, io)
        steps = 0
        while not machine.halted and steps <= 251 + 3 * ignored:
            machine.step()
            steps += 1
        assert machine.halted
        assert (io.getvalue(), io.reads) == (expected, n)
        worst = max(worst, steps)
    assert worst == 251 + 3 * ignored


@pytest.mark.medium
@pytest.mark.parametrize("width", [None, 1, 8, 40])
def test_spare_row_routes_reach_every_width_path(width: int | None) -> None:
    import random

    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import ScriptedIO

    rng = random.Random(2026)
    blocks = ["".join(rng.choice("01") for _ in range(64)) for _ in range(2)]
    table = "".join(blocks[int(bit)] for bit in "01101001")
    program = boolean.dig(table, width)
    rows = program.splitlines()
    assert (len(rows), max(map(len, rows)), len(program)) == (71, 36, 2252)
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, "09b")) + "\n")
        machine = _Machine(rows, io)
        steps = 0
        while not machine.halted and steps <= 251:
            machine.step()
            steps += 1
        assert machine.halted
        assert (io.getvalue(), io.reads) == (expected, 9)


@pytest.mark.medium
@pytest.mark.parametrize(
    ("pattern", "shared", "expected_steps", "expected_area"),
    [("0220200231131331", True, 301, 4899), ("1230301230121230", False, 312, 7881)],
)
def test_disjoint_lane_groups_share_and_over_budget_groups_fall_back(
    pattern: str, *, shared: bool, expected_steps: int, expected_area: int
) -> None:
    import random

    from esolangs.interpreters.grid_based.dig import _Machine
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.tools.dig import _dig_lane_shared

    rng = random.Random(2026)
    blocks = ["".join(rng.choice("01") for _ in range(64)) for _ in range(4)]
    table = "".join(blocks[int(bit)] for bit in pattern)
    candidate = _dig_lane_shared(table, 10)
    assert (candidate is not None) == shared
    program = boolean.dig(table)
    rows = program.splitlines()
    assert len(rows) * max(map(len, rows)) == expected_area
    worst = 0
    for row, expected in enumerate(table):
        io = ScriptedIO("\n".join(format(row, "010b")) + "\n")
        machine = _Machine(rows, io)
        steps = 0
        while not machine.halted and steps <= 312:
            machine.step()
            steps += 1
        assert machine.halted
        assert (io.getvalue(), io.reads) == (expected, 10)
        worst = max(worst, steps)
    assert worst == expected_steps
