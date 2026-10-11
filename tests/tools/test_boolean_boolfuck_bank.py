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


@pytest.mark.medium
@pytest.mark.parametrize("case", range(len(_bank_tables())))
def test_mixed_depth_bank_executes_and_matches_command_price(case):
    """A bank whose blocks sit at several depths shares all of them and computes."""
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.tools.boolfuck import _boolfuck_tree
    from esolangs.tools.shared_block import repeated_bank, repeated_mixed_bank

    table = _bank_tables()[case]
    n = len(table).bit_length() - 1
    mixed, levels = repeated_mixed_bank(table)
    bank, _ = repeated_bank(table)
    if len({depth for depth, _ in mixed}) <= len({depth for depth, _ in bank}):
        pytest.skip("no mixed-depth bank for this table")
    program, limit = _boolfuck_tree(table, shared_blocks=mixed, flag_levels=levels)
    for row, expected in enumerate(table):
        machine = make_vm("Boolfuck", program, stdin=f"{row:0{n}b}")
        commands = 0
        while not machine.halted and commands <= limit:
            machine.step()
            commands += 1
        assert machine.halted
        assert esolangs.read_answer("Boolfuck", machine.output) == expected
        assert commands <= limit


@pytest.mark.parametrize(
    ("blocks", "levels", "result"),
    [
        (((1, 0), (1, 4)), (1,), 6),
        (((1, 0), (1, 4)), (1, 1), 6),
        (((1, 0), (1, 4)), (0, 2), 6),
        (((1, 0), (1, 4)), (1, 3), 6),
        (((1, 0), (1, 4)), (1, 2), 5),
    ],
)
def test_bank_requires_distinct_unused_descendant_flags(blocks, levels, result):
    from esolangs.tools.shared_flag import flag_tree_body

    # A block at depth d may use any distinct unused flag at level >= d.  A
    # shallower flag would be rewritten by the ancestor that owns it before
    # the deferred dispatch runs, so that stays rejected; mixed depths do not.
    with pytest.raises(ValueError, match="bank needs distinct unused descendant flags"):
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
