"""SStack generator tests."""

import random

import pytest

import esolangs
from esolangs import tools as boolean
from tests.tools.boolean_runners import run_sstack


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


def test_a_full_tree_is_28_characters_a_node_and_3_a_leaf() -> None:
    """O(T): 28(T - 1) + 3T + 12 for the prologue, parity folds nothing."""
    for n in (1, 4, 6):
        parity = "".join(str(r.bit_count() % 2) for r in range(1 << n))
        assert len(boolean.sstack(parity)) == 31 * (1 << n) - 16


def test_a_constant_subtree_still_reads_its_inputs() -> None:
    """The fold drops branches, never reads: a trailing read sees the next byte."""
    program = boolean.sstack("0" * 8 + "01" * 4)
    assert program.count(";d;") == 5  # 3 folded, 2 at nodes whose halves agree
    stdin = esolangs.encode_inputs("SStack", [0, 1, 1, 0]) + "B"
    assert esolangs.run("SStack", program + ";e;:e:", stdin=stdin) == "0B"


def test_the_program_is_only_sstack_glyphs() -> None:
    for table in ("10", "0110", "0001", "1" * 8):
        assert set(boolean.sstack(table)) <= set('"0123456789/;[]\\+~:abcd'), table


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.interpreters.stack_based.sstack import _parse
    from esolangs.tools.sstack import _sstack_tree
    from tests.generator_support import assert_shared_program

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
    from tests.generator_support import assert_shared_program

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
