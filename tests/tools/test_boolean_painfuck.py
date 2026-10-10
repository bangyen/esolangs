"""painfuck generator tests."""

import random

import pytest

from esolangs import tools as boolean


class TestPainfuck:
    def test_commands_are_preshifted_for_the_trans_table(self) -> None:
        """The interpreter shifts commands through its cycles, so the source
        must be the inverse shift; the translated commands are the BF moves."""
        from esolangs.interpreters.tape_based.painfuck import _translate

        program = boolean.painfuck("0110")
        translated = _translate(program)
        assert "a" in translated  # [ loops
        assert "b" in translated  # ] loops
        assert translated.count("a") == translated.count("b")
        assert "rl" in translated or "l" in translated  # pointer moves


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.tools.painfuck import _painfuck_tree
    from scripts.screens.canonical import corpus
    from tests.generator_support import assert_shared_program

    table = corpus(8)["tiled"]
    plain, _ = _painfuck_tree(table, tuple(range(8)))
    assert_shared_program(
        "Painfuck",
        table,
        plain,
        212,
        lambda p: 2 * 8 + 5 + 3 * (8).bit_length() + 9 * len(p).bit_length(),
    )


def _multiple_tables():
    rng = random.Random(88417)
    a, b = "00010111", "01101001"
    four = (
        "0001011101101001",
        "0110100100010111",
        "1010110010001101",
        "1101001010010010",
    )
    return [
        a + b + b + a + a + b + a + b,
        "".join(four[(row // 4 + row % 4) % 4] for row in range(16)),
        *("".join(str(rng.randrange(2)) for _ in range(128)) for _ in range(6)),
    ]


@pytest.mark.medium
@pytest.mark.parametrize("table", _multiple_tables())
def test_multiple_flags_execute_with_their_native_command_price(table):
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.tools.helpers import permute_truth_table
    from esolangs.tools.painfuck import _painfuck_shared
    from esolangs.tools.shared_block import repeated_bank, repeated_blocks
    from scripts.benchmark import WrittenState

    n = len(table).bit_length() - 1
    served = 0
    for perm in (tuple(range(n)), tuple(reversed(range(n)))):
        ordered = permute_truth_table(table, perm)
        plans = [(repeated_blocks(ordered), ())]
        plans.extend(repeated_bank(ordered, ranked=ranked) for ranked in (False, True))
        for blocks, flags in dict.fromkeys(plans):
            if len(blocks) < 2:
                continue
            served += 1
            program, limit = _painfuck_shared(ordered, perm, blocks, flags)
            bound = 2 * n + 5 + 3 * n.bit_length() + (n + 1) * len(program).bit_length()
            for row, expected in enumerate(table):
                stdin = esolangs.encode_inputs(
                    "Painfuck", [int(bit) for bit in f"{row:0{n}b}"]
                )
                machine = make_vm("Painfuck", program, stdin=stdin)
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
    assert served > 0


# 4.9s on 3.12 alone (n=16), at the 5s medium ceiling; the loaded CI faster
# shard pushed it past the 15s scaled limit.
@pytest.mark.slow
def test_multiple_flags_reduce_dense_cap_program_within_ledger():
    from esolangs.tools.painfuck import _painfuck_tree
    from esolangs.tools.shared_block import repeated_block
    from tests.generator_support import assert_shared_program

    n = 16
    rng = random.Random(99123)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    perm = tuple(range(n))
    bound = (3 * n * n + 3) // 4 + 20 * n + 4
    forms = [
        _painfuck_tree(table, perm),
        _painfuck_tree(table, perm, repeated_block(table)),
    ]
    previous = min((p for p, c in forms if c <= bound), key=len)
    assert_shared_program(
        "Painfuck",
        table,
        previous,
        bound,
        lambda p: 2 * n + 5 + 3 * n.bit_length() + (n + 1) * len(p).bit_length(),
        rows=[0, 1, 1 << (n - 1), (1 << n) - 2, (1 << n) - 1],
    )
