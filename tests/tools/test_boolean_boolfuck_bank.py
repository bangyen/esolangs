"""Execute same-level residual banks under byte, bit, and final-flag rules."""

import random

import pytest


def _bank_tables():
    rng = random.Random(99107)
    a, b = "00010111", "01101001"
    tables = [a + b + b + a + a + b + a + b]
    four = (
        "0001011101101001",
        "0110100100010111",
        "1010110010001101",
        "1101001010010010",
    )
    tables.append("".join(four[(row // 4 + row % 4) % 4] for row in range(16)))
    tables += ["".join(str(rng.randrange(2)) for _ in range(128)) for _ in range(6)]
    return tables


@pytest.mark.medium
@pytest.mark.parametrize("kind", ["byte", "bit", "binary"])
@pytest.mark.parametrize(
    ("case", "table"),
    list(enumerate(_bank_tables())),
    ids=["two", "four", *map(str, range(6))],
)
def test_banked_residuals_execute_and_match_command_price(kind, case, table):
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.tools.boolfuck import _boolfuck_tree
    from esolangs.tools.helpers import permute_truth_table
    from esolangs.tools.shared_block import repeated_bank
    from esolangs.tools.shared_flag import flag_tree_body
    from scripts.benchmark import WrittenState

    served = 0
    n = len(table).bit_length() - 1
    for perm in (tuple(range(n)), tuple(reversed(range(n)))):
        if kind == "bit" and perm != tuple(range(n)):
            continue
        ordered = permute_truth_table(table, perm)
        blocks, levels = repeated_bank(ordered, reserve_last=kind == "binary")
        if not blocks:
            continue
        served += 1
        if kind == "bit":
            language = "Boolfuck"
            program, limit = _boolfuck_tree(
                table, shared_blocks=blocks, flag_levels=levels
            )
        else:
            language = "brainfuck"
            header = ">>".join("," + "-" * 48 for _ in range(n))
            result = 2 * perm[-1] + 1 if kind == "binary" else 2 * n
            body, cost = flag_tree_body(
                ordered,
                perm,
                2 * (n - 1),
                result,
                shared_blocks=blocks,
                flag_levels=levels,
                binary_leaves=kind == "binary",
            )
            program = header + body + "+" * 48 + "."
            limit = len(header) + cost + 49
        for row, expected in enumerate(table):
            machine = make_vm(language, program, stdin=f"{row:0{n}b}")
            written = WrittenState(machine.snapshot())
            commands = 0
            while not machine.halted and commands <= limit:
                machine.step()
                written.sample(machine.snapshot())
                commands += 1
            assert machine.halted
            assert esolangs.read_answer(language, machine.output) == expected
            assert commands <= limit
            if kind != "bit":
                assert (
                    written.bits
                    <= 2 * n
                    + 6
                    + (2 * n).bit_length()
                    + n.bit_length()
                    + len(program).bit_length()
                )
    if case < 2:
        assert served > 0
    elif not served:
        pytest.skip("no eligible residual bank")


@pytest.mark.parametrize(
    ("blocks", "levels", "result"),
    [
        (((1, 0), (1, 4)), (1,), 6),
        (((1, 0), (1, 4)), (1, 1), 6),
        (((1, 0), (1, 4)), (0, 2), 6),
        (((1, 0), (1, 4)), (1, 3), 6),
        (((1, 0), (1, 4)), (1, 2), 5),
        (((1, 0), (2, 0)), (1, 2), 6),
    ],
)
def test_bank_requires_distinct_unused_flags_at_one_level(blocks, levels, result):
    from esolangs.tools.shared_flag import flag_tree_body

    with pytest.raises(ValueError, match="bank needs distinct unused flags"):
        flag_tree_body(
            "00010110", (0, 1, 2), 4, result, shared_blocks=blocks, flag_levels=levels
        )


def test_duplicate_residual_definitions_abort():
    from esolangs.tools.shared_flag import flag_tree_body

    with pytest.raises(ValueError, match="distinct residuals"):
        flag_tree_body(
            "01100110",
            (0, 1, 2),
            4,
            6,
            shared_blocks=((1, 0), (1, 4)),
            flag_levels=(1, 2),
        )


@pytest.mark.medium
@pytest.mark.parametrize("language", ["brainfuck", "Boolfuck"])
def test_public_bank_reduces_cap_dense_table_within_ledger(language):
    from esolangs.tools.boolfuck import _boolfuck_tree
    from esolangs.tools.brainfuck import _bf_ordered
    from esolangs.tools.helpers import in_input_order
    from esolangs.tools.shared_block import repeated_block, repeated_blocks
    from tests.generator_support import assert_shared_program

    n = 16
    rng = random.Random(99123)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    if language == "brainfuck":
        previous = in_input_order(table, lambda t, p: _bf_ordered(t, p, bank=False))
        bound = 69 * n + 44

        def space(p):
            return (
                2 * n + 6 + (2 * n).bit_length() + n.bit_length() + len(p).bit_length()
            )
    else:
        bound = 2 * n * n + 27 * n + 8
        forms = [
            _boolfuck_tree(table),
            _boolfuck_tree(table, repeated_block(table)),
            _boolfuck_tree(table, shared_blocks=repeated_blocks(table)),
        ]
        previous = min((p for p, c in forms if c <= bound), key=len)

        def space(p):
            return (
                (len(p) - 1).bit_length()
                + max(12, (2 * n - 2).bit_length() + 10)
                + n
                + sum(i.bit_length() for i in range(n))
                + (2 * n).bit_length()
                + n.bit_length()
            )

    assert_shared_program(
        language, table, previous, bound, space, rows=[0, 1, 32768, 65534, 65535]
    )
