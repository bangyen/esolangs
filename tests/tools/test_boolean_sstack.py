"""SStack generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from tests.tools.boolean_runners import run_sstack


def test_screen_sharing_potential_is_mostly_below_the_label_reach() -> None:
    """The screen's n=5 sharing potential is 82% size-2 repeats.

    A deferral needs two unread inputs, so subtables of size 2 (the deepest
    level) cannot be labeled; the screen counts them anyway. The constructs
    reach the size >= 4 repeats and save 4.8% of the plain tree.
    """
    from esolangs.tools.sstack import _sstack_tree, sstack
    from tests.tools.sample_tables import five_input_sample

    def by_size(table: str) -> dict[int, int]:
        out: dict[int, int] = {}
        width = len(table)
        while width > 1:
            level = [table[i : i + width] for i in range(0, len(table), width)]
            live = [sub for sub in level if len(set(sub)) > 1]
            out[width] = out.get(width, 0) + len(live) - len(set(live))
            width //= 2
        return out

    sample = five_input_sample()
    totals: dict[int, int] = {}
    for table in sample:
        for size, count in by_size(table).items():
            totals[size] = totals.get(size, 0) + count
    assert (totals[2], totals[4], totals[8]) == (1229, 262, 3)
    assert totals[2] > 4 * (sum(totals.values()) - totals[2])  # over 80%
    plain = sum(len(_sstack_tree(table)[0]) for table in sample)
    shipped = sum(len(sstack(table)) for table in sample)
    assert (plain, shipped) == (102_108, 97_194)
    assert round(100 * (plain - shipped) / plain, 2) == 4.81


@pytest.mark.parametrize(
    ("table", "shared"), [("01101001", (0, 0)), ("00000000", (1, 0))]
)
def test_dispatch_prices_single_reachable_path_classes(table, shared):
    from esolangs.debugger import make_vm
    from esolangs.tools.sstack import _sstack_tree

    program, bound = _sstack_tree(table, shared)
    for row, expected in enumerate(table):
        machine = make_vm("SStack", program, stdin=f"{row:03b}")
        commands = 0
        while not machine.halted and commands <= bound:
            machine.step()
            commands += 1
        assert machine.halted
        assert machine.output == expected
        assert commands <= bound


def test_every_two_input_table_on_every_row() -> None:
    for code in range(16):
        table = f"{code:04b}"
        program = boolean.sstack(table)
        for row in range(4):
            assert run_sstack(program, list(f"{row:02b}")) == table[row], table


def test_a_full_tree_is_21_characters_a_node_and_3_a_leaf() -> None:
    """O(T): 21(T - 1) + 3T + 12 for the prologue, parity folds nothing."""
    from esolangs.tools.sstack import _sstack_tree

    for n in (1, 4, 6):
        parity = "".join(str(r.bit_count() % 2) for r in range(1 << n))
        plain, _ = _sstack_tree(parity)
        assert len(plain) == 24 * (1 << n) - 9
        assert len(boolean.sstack(parity)) <= len(plain)


def test_a_constant_subtree_still_reads_its_inputs() -> None:
    """The fold drops branches, never reads: a trailing read sees the next byte."""
    program = boolean.sstack("0" * 8 + "01" * 4)
    assert program.count(";d;") == 5  # 3 folded, 2 at nodes whose halves agree
    stdin = esolangs.encode_inputs("SStack", [0, 1, 1, 0]) + "B"
    assert esolangs.run("SStack", program + ";e;:e:", stdin=stdin) == "0B"


def test_popping_before_descent_admits_shared_parity_without_nested_test_bytes():
    from esolangs.debugger import make_vm
    from esolangs.tools.sstack import _sstack_tree

    n = 6
    table = "".join(str(row.bit_count() % 2) for row in range(1 << n))
    program = boolean.sstack(table)
    assert len(program) < len(_sstack_tree(table)[0])
    for row, expected in enumerate(table):
        machine = make_vm("SStack", program, stdin=f"{row:06b}" + "B")
        commands = 0
        while not machine.halted and commands <= 7 * n + 3:
            machine.step()
            commands += 1
            test_stack = machine.snapshot()[1][0]
            assert test_stack is None or test_stack[1] is None
        assert machine.halted
        assert machine.output == expected
        assert commands <= 7 * n + 3
        assert machine.snapshot()[1][0] is None
        assert (
            esolangs.run("SStack", program + ";e;:e:", stdin=f"{row:06b}" + "B")
            == expected + "B"
        )


def test_the_program_is_only_sstack_glyphs() -> None:
    for table in ("10", "0110", "0001", "1" * 8):
        assert set(boolean.sstack(table)) <= set('"0123456789/;[]\\+~:abcd'), table


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.interpreters.stack_based.sstack import _parse
    from esolangs.tools.sstack import _sstack_tree
    from tests.support.generator_support import assert_shared_program

    a, b = "0001" * 16, "0110" * 16
    table = a + b + b + a
    plain, _ = _sstack_tree(table)
    assert_shared_program(
        "SStack",
        table,
        plain,
        59,
        lambda p: 6 * 8 + 12 + len(_parse(p)).bit_length() + (8).bit_length(),
    )


@pytest.mark.medium
@pytest.mark.parametrize("branching", [False, True])
def test_multiple_definitions_preserve_inputs_commands_and_workspace(branching):
    from esolangs.debugger import make_vm
    from esolangs.interpreters.stack_based.sstack import _parse
    from esolangs.tools.shared_block import repeated_definitions
    from esolangs.tools.sstack import _sstack_shared
    from scripts.benchmark import WrittenState

    n = 8
    a, b = "0001" * 16, "0110" * 16
    table = a + b + b + a
    blocks = repeated_definitions(table, branching_only=branching)
    assert len(blocks) > 1
    program, limit = _sstack_shared(table, blocks)
    bound = 6 * n + 12 + len(_parse(program)).bit_length() + n.bit_length()
    for row, expected in enumerate(table):
        machine = make_vm("SStack", program, stdin=f"{row:08b}" + "B")
        written = WrittenState(machine.snapshot())
        commands = 0
        while not machine.halted and commands <= limit:
            machine.step()
            written.sample(machine.snapshot())
            commands += 1
        assert machine.halted
        assert machine.output == expected
        assert commands <= limit
        assert written.bits <= bound
        assert (
            esolangs.run("SStack", program + ";e;:e:", stdin=f"{row:08b}" + "B")
            == expected + "B"
        )


@pytest.mark.medium
def test_six_bit_labels_include_the_ascii_constants_and_last_label():
    from esolangs.debugger import make_vm
    from esolangs.interpreters.stack_based.sstack import _parse
    from esolangs.tools.shared_block import repeated_definitions
    from esolangs.tools.sstack import _sstack_shared
    from scripts.benchmark import WrittenState

    n = 11
    rng = random.Random(77319)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    blocks = repeated_definitions(table)[:63]
    assert len(blocks) == 63
    program, limit = _sstack_shared(table, blocks)
    bound = 6 * n + 12 + len(_parse(program)).bit_length() + n.bit_length()
    seen = set()
    for row in [0, len(table) - 1, *[blocks[i][1] for i in (47, 48, 62)]]:
        machine = make_vm("SStack", program, stdin=f"{row:011b}")
        written = WrittenState(machine.snapshot())
        commands = 0
        while not machine.halted and commands <= limit:
            machine.step()
            state = machine.snapshot()
            written.sample(state)
            commands += 1
            pending = state[1][4]
            if pending is not None:
                seen.add(pending[0])
        assert machine.halted
        assert machine.output == table[row]
        assert commands <= limit
        assert written.bits <= bound
    assert {48, 49, 63} <= seen
    assert _sstack_shared(table, (*blocks, repeated_definitions(table)[63])) is None
    assert _sstack_shared(table, ()) is None


@pytest.mark.parametrize(
    ("table", "blocks", "message"),
    [
        ("01101001", ((-1, 0),), "increasing depths"),
        ("01101001", ((2, 0),), "increasing depths"),
        ("0110100110010110", ((2, 0), (1, 0)), "increasing depths"),
        ("01101001", ((1, -1),), "aligned table spans"),
        ("01101001", ((1, 1),), "aligned table spans"),
        ("01101001", ((1, 8),), "aligned table spans"),
        ("01100110", ((1, 0), (1, 4)), "distinct nonconstant"),
        ("00000000", ((1, 0),), "distinct nonconstant"),
    ],
)
def test_invalid_shared_definitions_abort(table, blocks, message):
    from esolangs.tools.sstack import _sstack_shared

    with pytest.raises(ValueError, match=message):
        _sstack_shared(table, blocks)


@pytest.mark.medium
def test_multiple_definitions_reduce_cap_program_within_ledger():
    from esolangs.interpreters.stack_based.sstack import _parse
    from esolangs.tools.shared_block import repeated_block
    from esolangs.tools.sstack import _sstack_tree
    from tests.support.generator_support import assert_shared_program

    n = 16
    a, b = "0001" * (1 << (n - 4)), "0110" * (1 << (n - 4))
    table = a + b + b + a
    forms = [_sstack_tree(table), _sstack_tree(table, repeated_block(table))]
    previous = min((p for p, c in forms if c <= 7 * n + 3), key=len)
    ignored = ((1 << (n - 4)) - 1) << 2
    rows = [
        (prefix << (n - 2)) | suffix | padding
        for prefix in range(4)
        for suffix in range(4)
        for padding in (0, ignored)
    ]
    assert_shared_program(
        "SStack",
        table,
        previous,
        7 * n + 3,
        lambda p: 6 * n + 12 + len(_parse(p)).bit_length() + n.bit_length(),
        rows=rows,
    )


def _binary_bank_table() -> str:
    sequence = [*range(1, 66), *range(65, 0, -1), *range(1, 64), *range(63, 0, -1)]
    return "".join(f"{code:08b}" for code in sequence) * 32


@pytest.mark.medium
def test_binary_bank_shares_more_than_sixty_three_residuals_within_ledger():
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.sstack import _Machine, _parse
    from esolangs.tools.shared_block import _repeated_blocks
    from esolangs.tools.sstack import _sstack_tree
    from esolangs.tools.sstack._binary import binary_bank
    from scripts.benchmark import WrittenState

    table = _binary_bank_table()
    blocks = tuple(
        (depth, row) for depth, row, _ in _repeated_blocks(table) if depth == 13
    )
    assert len(blocks) == 64
    program, limit = binary_bank(table, blocks, _sstack_tree)
    assert limit <= 115
    assert len(boolean.sstack(table)) <= len(program)
    ops = _parse(program)
    workspace = 108 + len(ops).bit_length() + (16).bit_length()
    # Parsing is immutable; every row starts with fresh native state and I/O.
    for _, first in blocks:
        for suffix in range(8):
            for padding in (0, 31 << 11):
                row = (first + suffix) | padding
                machine = object.__new__(_Machine)
                machine.ops = ops
                machine.io = ScriptedIO(f"{row:016b}" + "B")
                machine.state = (0, (None,) * 7)
                written = WrittenState(machine.snapshot())
                commands = 0
                while not machine.halted and commands <= limit:
                    machine.step()
                    written.sample(machine.snapshot())
                    commands += 1
                assert machine.halted
                assert machine.io.getvalue() == table[row]
                assert commands <= limit
                assert written.bits <= workspace
                assert machine.state[1][0] is None
                assert machine.state[1][4] is None
    assert (
        esolangs.run("SStack", program + ";e;:e:", stdin="1" * 16 + "B")
        == table[-1] + "B"
    )


@pytest.mark.parametrize(
    "words",
    [
        ("0001", "0110", "0000", "1111"),
        ("0001", "0010", "0110", "0000"),
        ("0001", "0110", "0000", "0000", "1111", "1111", "0001", "0110"),
    ],
)
def test_binary_codes_preserve_completed_outputs_and_fixed_digits(words):
    from esolangs.debugger import make_vm
    from esolangs.tools.sstack import _sstack_tree
    from esolangs.tools.sstack._binary import binary_bank

    table = "".join(words)
    n = len(table).bit_length() - 1
    first = {word: i for i, word in enumerate(words) if word not in ("0000", "1111")}
    blocks = tuple((n - 2, 4 * i) for i in first.values())
    program, limit = binary_bank(table, blocks, _sstack_tree)
    for row, expected in enumerate(table):
        machine = make_vm("SStack", program, stdin=f"{row:0{n}b}" + "B")
        commands = 0
        while not machine.halted and commands <= limit:
            machine.step()
            commands += 1
        assert machine.halted
        assert machine.output == expected
        assert commands <= limit
        assert machine.snapshot()[1][4] is None
        assert (
            esolangs.run("SStack", program + ";e;:e:", stdin=f"{row:0{n}b}" + "B")
            == expected + "B"
        )


@pytest.mark.parametrize(
    ("table", "blocks", "message"),
    [
        ("01101001", (), "multiple definitions"),
        ("01101001", ((1, 0),), "multiple definitions"),
        ("01101001", ((0, 0), (1, 0)), "one level"),
        ("01101001", ((-1, 0), (-1, 4)), "bit budget"),
        ("01101001", ((2, 0), (2, 4)), "bit budget"),
        ("01101001", ((1, -1), (1, 4)), "aligned"),
        ("01101001", ((1, 1), (1, 4)), "aligned"),
        ("01101001", ((1, 0), (1, 8)), "aligned"),
        ("01100110", ((1, 0), (1, 4)), "distinct nonconstant"),
        ("00000110", ((1, 0), (1, 4)), "distinct nonconstant"),
        ("0001" * 32, tuple((5, 4 * i) for i in range(17)), "bit budget"),
    ],
)
def test_invalid_binary_banks_abort(table, blocks, message):
    from esolangs.tools.sstack import _sstack_tree
    from esolangs.tools.sstack._binary import binary_bank

    with pytest.raises(ValueError, match=message):
        binary_bank(table, blocks, _sstack_tree)


def test_binary_selector_rejects_inadmissible_or_unprofitable_banks():
    from esolangs.tools.sstack import _sstack_tree
    from esolangs.tools.sstack._binary import best_binary_bank

    assert best_binary_bank("0" * 16, _sstack_tree, 100, 1000) is None
    table = _binary_bank_table()
    assert best_binary_bank(table, _sstack_tree, 0, 10**9) is None
    assert best_binary_bank(table, _sstack_tree, 115, 1) is None
    assert best_binary_bank(table, _sstack_tree, 115, 10**9) is not None


def test_binary_selector_skips_a_bank_whose_word_exceeds_the_workspace_budget():
    from esolangs.tools.shared_block import _repeated_blocks
    from esolangs.tools.sstack import _sstack_tree
    from esolangs.tools.sstack._binary import best_binary_bank

    sequence = [*range(256), *range(255, -1, -1)]
    table = "".join(f"{code:08b}" for code in sequence)
    assert sum(depth == 9 for depth, _, _ in _repeated_blocks(table)) == 254
    assert best_binary_bank(table, _sstack_tree, 0, 10**9) is None


def test_binary_bank_refuses_a_drifted_inline_builder():
    from esolangs.tools.sstack import _sstack_tree
    from esolangs.tools.sstack._binary import binary_bank

    def drifted(table):
        program, commands = _sstack_tree(table)
        return program, commands + 1

    with pytest.raises(ValueError, match="builder disagrees"):
        binary_bank("00010110", ((1, 0), (1, 4)), drifted)
