"""painfuck generator tests."""

import random

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.generation.helpers import permute_truth_table
from esolangs.generation.shared_block import repeated_bank
from esolangs.languages.painfuck import generator as boolean
from esolangs.languages.painfuck.generator import _constant, _painfuck_shared, painfuck
from esolangs.runtime.io import ScriptedIO
from tests.support.evaluation import _evaluate
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import (
    assert_constant_output,
    assert_shared_program,
    constant_programs,
    measure_run,
    multiple_tables,
)
from tests.support.screen_support import corpus


class TestPainfuck:
    def test_commands_are_preshifted_for_the_trans_table(self, monkeypatch) -> None:
        """The interpreter shifts commands through its cycles, so the source
        must be the inverse shift; the translated commands are the BF moves."""
        from esolangs.languages.painfuck.interpreter import _translate

        _check_constants()
        _check_zero_fold_and_chain()
        program = boolean.painfuck("0110")
        translated = _translate(program)
        assert "a" in translated  # [ loops
        assert "b" in translated  # ] loops
        assert translated.count("a") == translated.count("b")
        assert "rl" in translated or "l" in translated  # pointer moves

        from esolangs.generation import shared_block
        from esolangs.generation.algebraic import affine_form
        from esolangs.generation.shared_flag import flag_tree_body

        assert boolean.affine_form is affine_form
        assert boolean.flag_tree_body is flag_tree_body
        assert boolean.repeated_block is shared_block.repeated_block
        assert boolean.repeated_bank is shared_block.repeated_bank
        assert boolean.repeated_mixed_bank is shared_block.repeated_mixed_bank

        def flipped_bias(table: str, n: int):
            form = affine_form(table, n)
            return None if form is None else form._replace(bias=1 - form.bias)

        table = "".join(str(row.bit_count() & 1) for row in range(64))
        with monkeypatch.context() as patch:
            patch.setattr(boolean, "affine_form", flipped_bias)
            damaged = boolean.painfuck(table)
        assert _evaluate("Painfuck", damaged, inputs=6) == table.translate(
            str.maketrans("01", "10")
        )
        monkeypatch.setattr(
            boolean,
            "flag_tree_body",
            lambda table, *args, **kwargs: flag_tree_body(
                table.translate(str.maketrans("01", "10")), *args, **kwargs
            ),
        )
        damaged, _ = boolean._painfuck_shared("0001", (0, 1), ())
        assert _evaluate("Painfuck", damaged, inputs=2) == "1110"


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    table = corpus(8)["tiled"]
    plain, _ = _painfuck_shared(table, tuple(range(8)), ())
    assert_shared_program(
        "Painfuck",
        table,
        plain,
        212,
        lambda p: 2 * 8 + 5 + 3 * (8).bit_length() + 9 * len(p).bit_length(),
    )


@pytest.mark.medium
@pytest.mark.parametrize("table", multiple_tables())
def test_multiple_flags_execute_with_their_native_command_price(table) -> None:
    n = len(table).bit_length() - 1
    served = 0
    for perm in (tuple(range(n)), tuple(reversed(range(n)))):
        ordered = permute_truth_table(table, perm)
        plans = [repeated_bank(ordered, ranked=ranked) for ranked in (False, True)]
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
                commands, written = measure_run(machine, limit=limit)
                assert machine.halted
                assert machine.output == expected
                assert commands <= limit
                assert written.bits <= bound
    assert served > 0


# 4.9s on 3.12 alone (n=16), at the 5s medium ceiling; the loaded CI faster
# shard pushed it past the 15s scaled limit.
@pytest.mark.slow
def test_multiple_flags_reduce_dense_cap_program_within_ledger() -> None:
    n = 16
    rng = random.Random(99123)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    perm = tuple(range(n))
    bound = (3 * n * n + 3) // 4 + 20 * n + 4
    previous, _ = _painfuck_shared(table, perm, ())
    assert_shared_program(
        "Painfuck",
        table,
        previous,
        bound,
        lambda p: 2 * n + 5 + 3 * n.bit_length() + (n + 1) * len(p).bit_length(),
        rows=[0, 1, 1 << (n - 1), (1 << n) - 2, (1 << n) - 1],
    )


def test_admission_bound_keeps_the_winning_shared_form() -> None:
    """The admission bound keeps the shared form it was priced on.

    Both tables are won by a shared form whose command count sits
    under ``(3 * n * n + 3) // 4 + 20 * n + 4`` but over the bound
    with either product of the quadratic term replaced by a sum;
    a bound computed that way excludes the winner and falls back
    to a longer form (368 and 675 characters respectively).
    """
    assert len(painfuck("10000001000101100001011001101000")) == 297
    assert (
        len(
            painfuck("1000010101001101010111100001001111011110000000010101111010000110")
        )
        == 620
    )


def _check_constants() -> None:
    from esolangs.languages.painfuck.interpreter import run

    for n, bit, _options, program in constant_programs("Painfuck", range(1, 13)):
        for row in ("0" * n, "1" * n):
            io = ReadFirstIO(
                esolangs.encode_inputs("Painfuck", [int(b) for b in row]) + "7\n",
                expected=n,
            )
            assert_constant_output(run, program, io, bit, n)
            assert io.input_num() == 7

    for n in (6, 7, 8, 13, 14, 48, 49, 50, 342, 343, 344, 511, 512):
        for bit in (0, 1):
            io = ScriptedIO("1\n" * n + "7\n")
            run(_constant(n, bit), io)
            assert io.getvalue() == str(bit)
            assert io.reads == n
            assert io.input_num() == 7


def _check_zero_fold_and_chain() -> None:
    from esolangs.languages.painfuck.interpreter import _Machine, _translate
    from esolangs.languages.painfuck.tests.formulas import _execution

    program, _ = _painfuck_shared("00000001", (0, 1, 2), ())
    # The empty zero child has no flag protocol; only the result adds one.
    assert _translate(program).count("a") == 3
    assert _translate(program).count("ps") == 1
    for n in range(1, 9):
        for table in ("0" + "1" * ((1 << n) - 1), "1" + "0" * ((1 << n) - 1)):
            program = painfuck(table)
            for row in (0, 1, (1 << n) - 1):
                io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\n7\n")
                machine = _Machine(program, io)
                steps = 0
                while not machine.halted:
                    machine.step()
                    steps += 1
                assert io.getvalue() == table[row]
                assert steps <= _execution(n, program)
                assert io.reads == n
                assert io.input_num() == 7
    table = "11101001"  # The 62-step maximum remains after canonical pruning.
    program = painfuck(table)
    machine = _Machine(program, ScriptedIO("1\n1\n1\n"))
    steps = 0
    while not machine.halted:
        machine.step()
        steps += 1
    assert machine.io.getvalue() == "1"
    assert steps == _execution(3, program) == 62
