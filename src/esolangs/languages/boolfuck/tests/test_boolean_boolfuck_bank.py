"""Execute same-level residual banks under byte and final-flag rules."""

import random

import pytest

from tests.support.reference import REFERENCE


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
@pytest.mark.parametrize("kind", ["byte", "binary"])
# The two structured tables cover every arc the six seeded random ones did.
@pytest.mark.parametrize("table", _bank_tables()[:2], ids=["two", "four"])
def test_banked_residuals_execute_and_match_command_price(kind, table) -> None:
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.generation.helpers import permute_truth_table
    from esolangs.generation.shared_block import repeated_bank
    from esolangs.generation.shared_flag import flag_tree_body
    from scripts.benchmark import WrittenState

    served = 0
    n = len(table).bit_length() - 1
    for perm in (tuple(range(n)), tuple(reversed(range(n)))):
        ordered = permute_truth_table(table, perm)
        blocks, levels = repeated_bank(ordered, reserve_last=kind == "binary")
        if not blocks:
            continue
        served += 1
        language = REFERENCE
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
            assert (
                written.bits
                <= 2 * n
                + 6
                + (2 * n).bit_length()
                + n.bit_length()
                + len(program).bit_length()
            )
    assert served > 0


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
def test_bank_requires_distinct_unused_descendant_flags(blocks, levels, result) -> None:
    from esolangs.generation.shared_flag import flag_tree_body

    # A block at depth d may use any distinct unused flag at level >= d.  A
    # shallower flag would be rewritten by the ancestor that owns it before
    # the deferred dispatch runs, so that stays rejected; mixed depths do not.
    with pytest.raises(ValueError, match="bank needs distinct unused descendant flags"):
        flag_tree_body(
            "00010110", (0, 1, 2), 4, result, shared_blocks=blocks, flag_levels=levels
        )


def test_duplicate_residual_definitions_abort() -> None:
    from esolangs.generation.shared_flag import flag_tree_body

    with pytest.raises(ValueError, match="distinct residuals"):
        flag_tree_body(
            "01100110",
            (0, 1, 2),
            4,
            6,
            shared_blocks=((1, 0), (1, 4)),
            flag_levels=(1, 2),
        )
